"""Purchase lifecycle coordinates public Funds/Operations commands in one transaction."""

import hashlib
from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.modules.accounts.contracts import list_account_identities, lock_account_references
from app.modules.depreciation.calculation import (
    inflation_target,
    month_index,
    month_label,
    schedule,
)
from app.modules.depreciation.models import DepreciationPurchase, DepreciationReceipt
from app.modules.depreciation.schemas import (
    ContributionCreate,
    ContributionResponse,
    MonthResponse,
    PositionResponse,
    PurchaseCreate,
    PurchaseResponse,
)
from app.modules.funds.contracts import (
    archive_fund,
    create_managed_fund,
    managed_fund_snapshot,
    post_managed_fund,
    reserved_balance,
)
from app.modules.operations.contracts import (
    PhysicalTransferDraft,
    account_balance,
    post_physical_transfer,
)
from app.modules.settings.contracts import application_timezone, lock_base_currency


class DepreciationError(RuntimeError):
    def __init__(self, code: str, status: int = 409):
        self.code = code
        self.status = status


def application_today(session: Session) -> str:
    return datetime.now(ZoneInfo(application_timezone(session))).date().isoformat()


def _lock_accounts(session: Session) -> None:
    ids = {account.id for account in list_account_identities(session)}
    lock_account_references(session, ids, allow_archived_ids=ids)


def _purchase(session: Session, purchase_id: UUID) -> DepreciationPurchase:
    purchase = session.scalar(
        select(DepreciationPurchase).where(DepreciationPurchase.id == purchase_id).with_for_update()
    )
    if purchase is None:
        raise DepreciationError("depreciation_not_found", 404)
    return purchase


def response(session: Session, purchase: DepreciationPurchase) -> PurchaseResponse:
    fund, positions, events = managed_fund_snapshot(session, purchase.fund_id)
    current = application_today(session)[:7]
    target = inflation_target(purchase.cost, purchase.inflation, purchase.months)
    movements: dict[str, Decimal] = {}
    history = []
    for event in sorted(events, key=lambda e: (e.occurred_on, e.created_at, e.id), reverse=True):
        amount = sum((Decimal(m.amount) for m in event.movements), Decimal(0))
        month = event.occurred_on.strftime("%Y-%m")
        movements[month] = movements.get(month, Decimal(0)) + amount
        history.append(
            ContributionResponse(
                id=event.id,
                month=month,
                action="contribute" if amount > 0 else "release",
                amount=format(abs(amount), "f"),
                account_id=event.movements[0].account_id,
                operation_id=event.caused_by_operation_id,
                created_at=event.created_at,
            )
        )
    balance = Decimal(fund.total_balance)
    end = month_label(month_index(purchase.purchase_month) + purchase.months)
    status = (
        "archived"
        if fund.archived
        else "funded"
        if balance >= target
        else "expired"
        if current > end
        else "active"
    )
    return PurchaseResponse(
        id=purchase.id,
        name=fund.name,
        cost=format(purchase.cost, "f"),
        purchase_month=purchase.purchase_month,
        months=purchase.months,
        inflation=format(purchase.inflation, "f"),
        target=format(target, "f"),
        balance=fund.total_balance,
        remaining=format(max(target - balance, Decimal(0)), "f"),
        end_month=end,
        current_month=current,
        status=status,
        version=purchase.version,
        schedule=[
            MonthResponse(**row)
            for row in schedule(
                target, purchase.purchase_month, purchase.months, current, movements
            )
        ],
        positions=[
            PositionResponse(
                account_id=p.account_id, account_name=p.account_name, balance=p.balance
            )
            for p in positions
        ],
        history=history,
    )


def list_purchases(session: Session) -> list[PurchaseResponse]:
    _lock_accounts(session)
    purchases = session.scalars(
        select(DepreciationPurchase)
        .order_by(DepreciationPurchase.created_at, DepreciationPurchase.id)
        .with_for_update(read=True)
    ).all()
    return [response(session, purchase) for purchase in purchases]


def create_purchase(session: Session, payload: PurchaseCreate) -> PurchaseResponse:
    # Definition-only creation needs no account locks or physical movements.
    lock_base_currency(session)
    if payload.purchase_month > application_today(session)[:7]:
        raise DepreciationError("depreciation_future_purchase")
    target = inflation_target(payload.cost, payload.inflation, payload.months)
    fund_id = create_managed_fund(session, payload.name, target)
    purchase = DepreciationPurchase(
        fund_id=fund_id,
        cost=payload.cost,
        purchase_month=payload.purchase_month,
        months=payload.months,
        inflation=payload.inflation,
        created_at=datetime.now(UTC),
        version=1,
    )
    session.add(purchase)
    session.flush()
    return response(session, purchase)


def contribute(
    session: Session, purchase_id: UUID, payload: ContributionCreate
) -> PurchaseResponse:
    # Request lock precedes account/purchase locks; retries cannot post twice across purchases.
    session.execute(
        text("SELECT pg_advisory_xact_lock(:key)"),
        {"key": int.from_bytes(payload.request_id.bytes[:8], "big", signed=True)},
    )
    _lock_accounts(session)
    purchase = _purchase(session, purchase_id)
    fingerprint = hashlib.sha256(
        (str(purchase_id) + payload.model_dump_json()).encode()
    ).hexdigest()
    receipt = session.get(DepreciationReceipt, payload.request_id)
    if receipt is not None:
        if receipt.fingerprint != fingerprint or receipt.purchase_id != purchase_id:
            raise DepreciationError("depreciation_conflict")
        return response(session, purchase)
    if purchase.version != payload.version:
        raise DepreciationError("depreciation_conflict")
    ids = {payload.account_id}
    if payload.source_account_id:
        ids.add(payload.source_account_id)
    lock_account_references(session, ids)
    from datetime import date

    today = date.fromisoformat(application_today(session))
    operation_id = None
    if payload.source_account_id:
        operation_id = post_physical_transfer(
            session,
            PhysicalTransferDraft(
                occurred_on=today,
                amount=payload.amount,
                description=None,
                source_account_id=payload.source_account_id,
                destination_account_id=payload.account_id,
            ),
        )
    amount = payload.amount if payload.action == "contribute" else -payload.amount
    event_id = post_managed_fund(
        session,
        fund_id=purchase.fund_id,
        account_id=payload.account_id,
        amount=amount,
        occurred_on=today,
        request_id=payload.request_id,
        free=account_balance(session, payload.account_id)
        - reserved_balance(session, payload.account_id),
        operation_id=operation_id,
    )
    session.add(
        DepreciationReceipt(
            id=payload.request_id,
            purchase_id=purchase_id,
            event_id=event_id,
            fingerprint=fingerprint,
        )
    )
    purchase.version += 1
    session.flush()
    return response(session, purchase)


def archive_purchase(session: Session, purchase_id: UUID, version: int) -> PurchaseResponse:
    _lock_accounts(session)
    purchase = _purchase(session, purchase_id)
    if purchase.version != version:
        raise DepreciationError("depreciation_conflict")
    fund, _, _ = managed_fund_snapshot(session, purchase.fund_id)
    archive_fund(
        session, purchase.fund_id, restore=False, expected_version=fund.version, allow_managed=True
    )
    purchase.version += 1
    session.flush()
    return response(session, purchase)
