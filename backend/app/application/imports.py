"""Import confirmation coordinates public domain commands in one transaction."""

import hashlib
import json
from datetime import timedelta
from decimal import Decimal
from difflib import SequenceMatcher
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.application.transfer_allocation import transfer_and_allocate
from app.modules.funds.contracts import TransferAllocationCreateRequest
from app.modules.imports.contracts import (
    CommitRequest,
    ImportDecisionError,
    ImportGroupingError,
    PreviewRequest,
    decision_groups,
    find_receipt,
    normalize,
    read_file,
    receipt_ids,
    record_receipt,
)
from app.modules.operations.contracts import (
    import_candidates,
    import_existing,
    operation_history_references,
    post_import_operation,
    validate_import_date,
)
from app.modules.scheduling.contracts import confirm_imported_occurrence, import_plan_candidates
from app.modules.settings.contracts import get_application_settings


def source_key(digest: str, sheet: str, row: int) -> str:
    return hashlib.sha256(f"{digest}:{sheet}:{row}".encode()).hexdigest()


def preview(session: Session, request: PreviewRequest) -> dict[str, Any]:
    digest, sheets, rows = read_file(request)
    sheet = request.mapping.sheet or sheets[0]
    from_on = request.occurred_on - timedelta(days=request.window_days)
    through_on = request.occurred_on + timedelta(days=request.window_days)
    facts = import_candidates(session, request.account_id, from_on, through_on)
    plans = import_plan_candidates(session, request.account_id, from_on, through_on)
    receipts = receipt_ids(
        session,
        [
            source_key(digest, sheet, n)
            for n in range(request.mapping.header_row + 1, len(rows) + 1)
        ],
    )
    existing_receipts = operation_history_references(session, set(receipts.values()))
    output = []
    for number, raw in enumerate(rows, 1):
        if number <= request.mapping.header_row:
            continue
        item: dict[str, Any] = dict(row=number, raw=raw, error=None, facts=[], plans=[])
        receipt_id = receipts.get(source_key(digest, sheet, number))
        item["imported_id"] = str(receipt_id) if receipt_id else None
        item["imported_deleted"] = receipt_id is not None and receipt_id not in existing_receipts
        try:
            kind, amount, description, currency = normalize(raw, request.mapping)
            item.update(type=kind, amount=amount, description=description, currency=currency)
            for label, candidates in (("facts", facts), ("plans", plans)):
                matches = []
                for candidate in candidates:
                    if candidate["direction"] != kind:
                        continue
                    reasons = []
                    if Decimal(str(candidate["amount"])) == Decimal(amount):
                        reasons.append("amount")
                    if (
                        description
                        and SequenceMatcher(
                            None, description.casefold(), str(candidate["description"]).casefold()
                        ).ratio()
                        >= 0.45
                    ):
                        reasons.append("description")
                    if reasons:
                        if candidate["date"] == request.occurred_on.isoformat():
                            reasons.append("date")
                        matches.append(dict(candidate, reasons=reasons))
                item[label] = sorted(matches, key=lambda x: (-len(x["reasons"]), str(x["id"])))
        except ValueError as error:
            item["error"] = str(error)
        output.append(item)
    return dict(
        sheets=sheets,
        headers=rows[request.mapping.header_row - 1]
        if len(rows) >= request.mapping.header_row
        else [],
        rows=output,
        facts=facts,
        plans=plans,
    )


def commit(session: Session, request: CommitRequest) -> dict[str, Any]:
    digest, sheets, rows = read_file(request)
    sheet = request.mapping.sheet or sheets[0]
    # One owner, bounded rare batch: serialize imports and establish schedule-before-ledger order.
    session.execute(text("SELECT pg_advisory_xact_lock(48392015)"))
    settings = get_application_settings(session)
    groups = decision_groups(request)
    # Lock all chosen occurrences before any account/fund mutation.
    from app.modules.scheduling.contracts import lock_import_occurrences

    lock_import_occurrences(
        session, {d.occurrence_id for d in request.decisions if d.occurrence_id}
    )
    results: list[dict[str, Any]] = []
    for group in groups:
        decision = group[0]
        try:
            # Preserve historical single-row hashes; group hashes bind every member and field.
            reviewed = (
                decision.model_dump(mode="json")
                if len(group) == 1
                else {"merge_plan_rows": [item.model_dump(mode="json") for item in group]}
            )
            fingerprint = hashlib.sha256(json.dumps(reviewed, sort_keys=True).encode()).hexdigest()
            keys = [source_key(digest, sheet, item.row) for item in group]
            receipts = [find_receipt(session, key) for key in keys]
            if any(receipts):
                if any(r is None or r.decision_hash != fingerprint for r in receipts):
                    raise ValueError("These rows were already imported with a different decision")
                operation_ids = {r.operation_id for r in receipts if r is not None}
                if len(operation_ids) != 1:
                    raise ValueError("Imported group changed")
                operation_id = operation_ids.pop()
                results.extend(
                    dict(row=item.row, operation_id=str(operation_id), reused=True)
                    for item in group
                )
                continue
            total = Decimal(0)
            for item in group:
                try:
                    if item.row <= request.mapping.header_row or item.row > len(rows):
                        raise ValueError("Invalid source row")
                    kind, amount, _, currency = normalize(rows[item.row - 1], request.mapping)
                    payload = item.operation
                    validate_import_date(session, payload.occurred_on)
                    bank_side = (
                        payload.destination_account_id
                        if payload.type.value == "transfer" and kind == "income"
                        else payload.account_id
                    )
                    if item.statement_account_id != bank_side:
                        raise ValueError("Statement account does not match the movement direction")
                    if currency and currency != settings.base_currency:
                        raise ValueError("Statement currency differs from base currency")
                    if Decimal(amount) != payload.amount or payload.type.value not in {
                        kind,
                        "transfer",
                    }:
                        raise ValueError(
                            "Operation must preserve the statement amount and direction"
                        )
                    total += Decimal(amount)
                except (ValueError, RuntimeError) as error:
                    raise ImportDecisionError(item.row, error) from error
            payload = decision.operation
            if len(group) > 1:
                try:
                    # Revalidate the aggregate against the same NUMERIC envelope as any operation.
                    payload = type(payload).model_validate(
                        {**payload.model_dump(), "amount": total}
                    )
                except ValueError as error:
                    raise ImportGroupingError(
                        "Merged amount exceeds the operation limit"
                    ) from error
            if (
                payload.type.value == "transfer"
                and decision.allocate_to_funds
                and decision.existing_id
            ):
                raise ValueError("Existing transfers cannot allocate funds again")
            if decision.action == "existing" and decision.existing_id is None:
                raise ValueError("Choose an existing operation")
            if decision.action == "plan" and (
                decision.occurrence_id is None or decision.occurrence_version is None
            ):
                raise ValueError("Choose a plan")
            if decision.action != "plan" and decision.occurrence_id:
                raise ValueError("Only a planned payment can close an occurrence")
            if decision.action == "new" and (decision.occurrence_id or decision.existing_id):
                raise ValueError("New operation cannot have existing links")
            if decision.existing_id:
                if decision.existing_version is None:
                    raise ValueError("Existing version is required")
                existing = import_existing(session, decision.existing_id, decision.existing_version)
                if (
                    existing.type != payload.type
                    or Decimal(existing.amount) != payload.amount
                    or existing.account_id != payload.account_id
                    or existing.destination_account_id != payload.destination_account_id
                    or existing.occurred_on != payload.occurred_on
                    or existing.category_id != payload.category_id
                    or existing.fund_id != payload.fund_id
                    or (Decimal(existing.fund_amount) if existing.fund_amount else None)
                    != payload.fund_amount
                    or existing.description != payload.description
                ):
                    raise ValueError("Existing fact does not match the reviewed fields")
                operation_id = decision.existing_id
            elif decision.allocate_to_funds:
                if (
                    payload.type.value != "transfer"
                    or payload.destination_account_id is None
                    or payload.fund_id
                ):
                    raise ValueError("Allocation requires an ordinary transfer")
                operation_id = transfer_and_allocate(
                    session,
                    TransferAllocationCreateRequest(
                        occurred_on=payload.occurred_on,
                        amount=payload.amount,
                        description=payload.description,
                        source_account_id=payload.account_id,
                        destination_account_id=payload.destination_account_id,
                    ),
                ).operation_id
            else:
                operation_id = post_import_operation(session, payload)
            if decision.occurrence_id:
                if decision.occurrence_version is None:
                    raise ValueError("Plan version is required")
                confirm_imported_occurrence(
                    session,
                    decision.occurrence_id,
                    decision.occurrence_version,
                    operation_id,
                    payload,
                    decision.allocate_to_funds,
                )
            for item, key in zip(group, keys, strict=True):
                record_receipt(session, key, fingerprint, operation_id)
                results.append(dict(row=item.row, operation_id=str(operation_id), reused=False))
        except (ValueError, RuntimeError) as error:
            raise ImportDecisionError(decision.row, error) from error
    session.flush()
    return dict(results=results)
