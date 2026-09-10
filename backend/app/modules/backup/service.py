import hashlib
import json
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import delete, func, select, text
from sqlalchemy.orm import Session

from app import APP_VERSION
from app.modules.accounts.backup import Account
from app.modules.backup.errors import BackupAuthenticationFailed, BackupTooLarge
from app.modules.backup.hermes_v1 import (
    MAX_PLAINTEXT_BACKUP_BYTES,
    HermesV1Reader,
    HermesV1Writer,
    parse_backup_envelope,
)
from app.modules.backup.schemas import (
    AccountMovementRecord,
    AccountRecord,
    BackupCounts,
    BackupData,
    BackupDocument,
    BackupIntegrity,
    BackupPreviewResponse,
    CategoryRecord,
    ExpectedOccurrenceRecord,
    FundEventRecord,
    FundMovementRecord,
    FundRecord,
    FundReserveMovementRecord,
    HermesBackup,
    ImportProfileRecord,
    ImportReceiptRecord,
    OperationRecord,
    RecurringRuleRecord,
    RestoreResponse,
    SettingsRecord,
)
from app.modules.categories.backup import Category
from app.modules.categories.contracts import CategoryType
from app.modules.funds.backup import (
    Fund,
    FundEvent,
    FundEventType,
    FundMovement,
    FundReserveMovement,
)
from app.modules.imports.backup import ImportProfile, ImportReceipt
from app.modules.imports.schemas import Mapping
from app.modules.operations.backup import AccountMovement, FinancialOperation
from app.modules.operations.contracts import OperationType
from app.modules.scheduling.backup import (
    ExpectedOccurrence,
    OccurrenceSourceKind,
    OccurrenceStatus,
    RecurringRule,
)
from app.modules.settings.backup import ApplicationSettings
from app.modules.settings.contracts import normalize_currency, normalize_timezone
from app.modules.settings.models import FundAllocationMode

FORMAT = "hermes-json-backup"
SCHEMA_VERSION = 1
RESTORE_CONFIRMATION = "ЗАМЕНИТЬ ВСЕ ДАННЫЕ"

_TABLES = (
    "import_profiles",
    "import_receipts",
    "application_settings",
    "accounts",
    "categories",
    "financial_operations",
    "account_movements",
    "funds",
    "fund_events",
    "fund_movements",
    "fund_reserve_movements",
    "recurring_rules",
    "expected_occurrences",
)


class BackupIntegrityError(ValueError):
    pass


class BackupInvariantError(ValueError):
    pass


def _lock_tables(session: Session, mode: str) -> None:
    names = ", ".join(_TABLES)
    session.execute(text(f"LOCK TABLE {names} IN {mode} MODE"))


def _record(model: type[Any], row: Any) -> Any:
    return model.model_validate({field: getattr(row, field) for field in model.model_fields})


def _canonical_content(document: BackupDocument) -> bytes:
    # Schema v1 gained optional fields over time. Preserve the canonical shape
    # of an older document instead of hashing Pydantic defaults it never held.
    content = document.model_dump(mode="json", exclude={"integrity"}, exclude_unset=True)
    return json.dumps(content, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def _digest(document: BackupDocument) -> str:
    return hashlib.sha256(_canonical_content(document)).hexdigest()


def verify_integrity(document: BackupDocument) -> None:
    if document.integrity.digest != _digest(document):
        raise BackupIntegrityError("Backup checksum does not match its contents")


def seal_backup(document: BackupDocument) -> BackupDocument:
    """Return the document with a checksum matching its canonical content."""
    document.integrity.digest = _digest(document)
    return document


def _all(session: Session, model: type[Any]) -> list[Any]:
    return list(session.scalars(select(model).order_by(model.id)).all())


def create_backup(session: Session) -> BackupDocument:
    _lock_tables(session, "SHARE")
    settings = session.get(ApplicationSettings, 1)
    if settings is None:
        raise BackupInvariantError("Application settings are missing")
    data = BackupData(
        import_profiles=[_record(ImportProfileRecord, row) for row in _all(session, ImportProfile)],
        import_receipts=[_record(ImportReceiptRecord, row) for row in _all(session, ImportReceipt)],
        settings=_record(SettingsRecord, settings),
        accounts=[_record(AccountRecord, row) for row in _all(session, Account)],
        categories=[_record(CategoryRecord, row) for row in _all(session, Category)],
        operations=[_record(OperationRecord, row) for row in _all(session, FinancialOperation)],
        account_movements=[
            _record(AccountMovementRecord, row) for row in _all(session, AccountMovement)
        ],
        funds=[_record(FundRecord, row) for row in _all(session, Fund)],
        fund_events=[_record(FundEventRecord, row) for row in _all(session, FundEvent)],
        fund_movements=[_record(FundMovementRecord, row) for row in _all(session, FundMovement)],
        fund_reserve_movements=[
            _record(FundReserveMovementRecord, row) for row in _all(session, FundReserveMovement)
        ],
        recurring_rules=[_record(RecurringRuleRecord, row) for row in _all(session, RecurringRule)],
        expected_occurrences=[
            _record(ExpectedOccurrenceRecord, row) for row in _all(session, ExpectedOccurrence)
        ],
    )
    document = BackupDocument(
        format=FORMAT,
        schema_version=SCHEMA_VERSION,
        app_version=APP_VERSION,
        exported_at=datetime.now(UTC),
        data=data,
        integrity=BackupIntegrity(digest="0" * 64),
    )
    return seal_backup(document)


def create_hermes_backup(session: Session, master_password: str) -> HermesBackup:
    return HermesV1Writer().write(master_password, create_backup(session))


def open_backup(raw: dict[str, Any], backup_password: str | None = None) -> BackupDocument:
    envelope = parse_backup_envelope(raw)
    if isinstance(envelope, BackupDocument):
        if len(envelope.model_dump_json(exclude_unset=True).encode("utf-8")) > (
            MAX_PLAINTEXT_BACKUP_BYTES
        ):
            raise BackupTooLarge("Legacy backup exceeds the 50 MiB limit")
        return envelope
    if backup_password is None or not backup_password:
        raise BackupAuthenticationFailed("Incorrect password or corrupted backup.")
    payload = HermesV1Reader().read(backup_password, envelope)
    return seal_backup(
        BackupDocument(
            format=FORMAT,
            schema_version=payload.schema_version,
            app_version=payload.app_version,
            exported_at=payload.exported_at,
            data=payload.data,
            integrity=BackupIntegrity(digest="0" * 64),
        )
    )


def preview_backup_envelope(
    raw: dict[str, Any], backup_password: str | None = None
) -> BackupPreviewResponse:
    format_name = raw.get("format")
    result = preview_backup(open_backup(raw, backup_password))
    if format_name == "hermes":
        return result.model_copy(update={"format": "hermes"})
    return result


def restore_backup_envelope(
    session: Session, raw: dict[str, Any], backup_password: str | None = None
) -> RestoreResponse:
    return restore_backup(session, open_backup(raw, backup_password))


def _counts(data: BackupData) -> BackupCounts:
    return BackupCounts(**{name: len(getattr(data, name)) for name in BackupCounts.model_fields})


def preview_backup(document: BackupDocument) -> BackupPreviewResponse:
    verify_integrity(document)
    validate_document(document.data)
    return BackupPreviewResponse(
        format=document.format,
        schema_version=document.schema_version,
        app_version=document.app_version,
        exported_at=document.exported_at,
        counts=_counts(document.data),
        base_currency=document.data.settings.base_currency,
        timezone=document.data.settings.timezone,
        integrity_verified=True,
    )


def validate_document(data: BackupData) -> None:
    for profile in data.import_profiles:
        Mapping.model_validate(profile.mapping)
    for records, metadata_key in (
        (data.import_profiles, "name"),
        (data.import_receipts, "source_key"),
    ):
        if len({getattr(r, metadata_key) for r in records}) != len(records) or len(
            {r.id for r in records}
        ) != len(records):
            raise BackupInvariantError("Duplicate import metadata")
    normalize_currency(data.settings.base_currency)
    normalize_timezone(data.settings.timezone)
    account_ids = {item.id for item in data.accounts}
    category_ids = {item.id for item in data.categories}
    operation_ids = {item.id for item in data.operations}
    fund_ids = {item.id for item in data.funds}
    event_ids = {item.id for item in data.fund_events}
    identifiers = [
        [item.id for item in data.accounts],
        [item.id for item in data.categories],
        [item.id for item in data.operations],
        [item.id for item in data.account_movements],
        [item.id for item in data.funds],
        [item.id for item in data.fund_events],
        [item.id for item in data.fund_movements],
        [item.id for item in data.fund_reserve_movements],
        [item.id for item in data.recurring_rules],
        [item.id for item in data.expected_occurrences],
    ]
    if any(len(items) != len(set(items)) for items in identifiers):
        raise BackupInvariantError("Backup contains duplicate identifiers")
    if any(not item.name.strip() for item in data.accounts):
        raise BackupInvariantError("Entity names must not be blank")
    if any(not item.name.strip() for item in data.categories):
        raise BackupInvariantError("Entity names must not be blank")
    if any(not item.name.strip() for item in data.funds):
        raise BackupInvariantError("Entity names must not be blank")
    if any(
        item.allocation_percentage < 0 or item.allocation_percentage > 100 for item in data.funds
    ):
        raise BackupInvariantError("Fund percentage is outside 0 through 100")
    if (
        data.settings.fund_allocation_mode == FundAllocationMode.MANUAL
        and sum(
            (item.allocation_percentage for item in data.funds if item.archived_at is None),
            Decimal(0),
        )
        > 100
    ):
        raise BackupInvariantError("Active fund percentages exceed 100")
    if data.settings.fund_allocation_mode == FundAllocationMode.DYNAMIC and any(
        item.archived_at is None and item.target_amount is None for item in data.funds
    ):
        raise BackupInvariantError("Dynamic allocation requires targets for all active funds")
    if data.accounts and data.settings.base_currency_locked_at is None:
        raise BackupInvariantError("Base currency must be locked when accounts exist")
    if data.settings.default_account_id is not None:
        account_by_id = {item.id: item for item in data.accounts}
        default_account = account_by_id.get(data.settings.default_account_id)
        if default_account is None:
            raise BackupInvariantError("Default account reference is missing")
        if default_account.archived_at is not None:
            raise BackupInvariantError("Default account must be active")
    if any(
        item.parent_id is not None and item.parent_id not in category_ids
        for item in data.categories
    ):
        raise BackupInvariantError("Category parent is missing")
    category_by_id = {item.id: item for item in data.categories}
    for category in data.categories:
        if category.parent_id is None:
            continue
        parent = category_by_id[category.parent_id]
        if parent.parent_id is not None or parent.type != category.type or parent.id == category.id:
            raise BackupInvariantError("Category tree shape is invalid")
        if category.archived_at is None and parent.archived_at is not None:
            raise BackupInvariantError("An active category has an archived parent")
    if any(
        item.operation_id not in operation_ids or item.account_id not in account_ids
        for item in data.account_movements
    ):
        raise BackupInvariantError("Account movement reference is missing")
    if any(item.amount == 0 for item in data.account_movements):
        raise BackupInvariantError("Account movements must be non-zero")
    operation_by_id = {item.id: item for item in data.operations}
    category_type_by_id = {item.id: item.type for item in data.categories}
    movements_by_operation: dict[Any, list[AccountMovementRecord]] = {
        operation_id: [] for operation_id in operation_ids
    }
    for movement in data.account_movements:
        movements_by_operation[movement.operation_id].append(movement)
    for operation_id, operation in operation_by_id.items():
        movements = movements_by_operation[operation_id]
        account_movement_ids = [movement.account_id for movement in movements]
        if len(account_movement_ids) != len(set(account_movement_ids)):
            raise BackupInvariantError("An operation moves the same account more than once")
        if operation.type == OperationType.TRANSFER:
            if (
                operation.category_id is not None
                or len(movements) != 2
                or sum((item.amount for item in movements), Decimal(0)) != 0
                or {item.amount > 0 for item in movements} != {True, False}
            ):
                raise BackupInvariantError("Transfer movements are not balanced")
        elif operation.type in {OperationType.INCOME, OperationType.EXPENSE}:
            expected_type = (
                CategoryType.INCOME
                if operation.type == OperationType.INCOME
                else CategoryType.EXPENSE
            )
            expected_positive = operation.type == OperationType.INCOME
            if (
                operation.category_id is None
                or category_type_by_id.get(operation.category_id) != expected_type
                or len(movements) != 1
                or (movements[0].amount > 0) != expected_positive
            ):
                raise BackupInvariantError("Income or expense operation shape is invalid")
        elif (
            operation.category_id is not None
            or operation.reason is None
            or not operation.reason.strip()
            or len(movements) != 1
        ):
            raise BackupInvariantError("Balance adjustment shape is invalid")
    if any(
        item.fund_id not in fund_ids
        or item.account_id not in account_ids
        or (item.operation_id is None) == (item.event_id is None)
        or (item.operation_id is not None and item.operation_id not in operation_ids)
        or (item.event_id is not None and item.event_id not in event_ids)
        for item in data.fund_movements
    ):
        raise BackupInvariantError("Fund movement reference or source is invalid")
    if any(item.amount == 0 for item in data.fund_movements):
        raise BackupInvariantError("Fund movements must be non-zero")
    if any(
        item.account_id not in account_ids or item.event_id not in event_ids or item.amount == 0
        for item in data.fund_reserve_movements
    ):
        raise BackupInvariantError("Fund reserve movement is invalid")
    reserve_keys = [(item.event_id, item.account_id) for item in data.fund_reserve_movements]
    if len(reserve_keys) != len(set(reserve_keys)):
        raise BackupInvariantError("A reserve event moves the same account more than once")
    if any(
        event.caused_by_operation_id is not None
        and (
            event.caused_by_operation_id not in operation_ids
            or (
                event.type == FundEventType.ALLOCATION
                and operation_by_id[event.caused_by_operation_id].type != OperationType.TRANSFER
            )
            or event.type not in {FundEventType.ALLOCATION, FundEventType.RESERVE_DISTRIBUTION}
        )
        for event in data.fund_events
    ):
        raise BackupInvariantError("Fund event cause is invalid")
    movement_keys = [
        (item.operation_id, item.fund_id, item.account_id)
        if item.operation_id is not None
        else (item.event_id, item.fund_id, item.account_id)
        for item in data.fund_movements
    ]
    if len(movement_keys) != len(set(movement_keys)):
        raise BackupInvariantError("A fund source moves the same position more than once")
    fund_movements_by_event: dict[Any, list[FundMovementRecord]] = {
        event_id: [] for event_id in event_ids
    }
    reserve_movements_by_event: dict[Any, list[FundReserveMovementRecord]] = {
        event_id: [] for event_id in event_ids
    }
    fund_movements_by_operation: dict[Any, list[FundMovementRecord]] = {
        operation_id: [] for operation_id in operation_ids
    }
    for fund_movement in data.fund_movements:
        if fund_movement.event_id is not None:
            fund_movements_by_event[fund_movement.event_id].append(fund_movement)
        else:
            assert fund_movement.operation_id is not None
            fund_movements_by_operation[fund_movement.operation_id].append(fund_movement)
    for reserve_movement in data.fund_reserve_movements:
        reserve_movements_by_event[reserve_movement.event_id].append(reserve_movement)
    for event in data.fund_events:
        event_movements = fund_movements_by_event[event.id]
        event_reserve_movements = reserve_movements_by_event[event.id]
        if event.type == FundEventType.ALLOCATION:
            if (not event_movements and not event_reserve_movements) or (
                any(item.amount <= 0 for item in event_movements)
                or any(item.amount <= 0 for item in event_reserve_movements)
                or len(
                    {item.account_id for item in event_movements}
                    | {item.account_id for item in event_reserve_movements}
                )
                != 1
            ):
                raise BackupInvariantError("Fund allocation event is empty or negative")
            if event.caused_by_operation_id is not None:
                operation = operation_by_id[event.caused_by_operation_id]
                positive_movement = next(
                    item for item in movements_by_operation[operation.id] if item.amount > 0
                )
                allocated_amount = sum((item.amount for item in event_movements), Decimal(0)) + sum(
                    (item.amount for item in event_reserve_movements), Decimal(0)
                )
                if (
                    event.occurred_on != operation.occurred_on
                    or event.description != operation.description
                    or any(
                        item.account_id != positive_movement.account_id
                        for item in event_movements + event_reserve_movements
                    )
                    or allocated_amount > positive_movement.amount
                ):
                    raise BackupInvariantError("Transfer allocation cause is invalid")
        elif event.type == FundEventType.REDISTRIBUTION:
            if (
                len(event_movements) != 2
                or len({item.fund_id for item in event_movements}) != 1
                or len({item.account_id for item in event_movements}) != 2
                or sum((item.amount for item in event_movements), Decimal(0)) != 0
                or event_reserve_movements
            ):
                raise BackupInvariantError("Fund redistribution is not balanced")
        elif event.type == FundEventType.FUND_TRANSFER and (
            len(event_movements) != 2
            or len({item.fund_id for item in event_movements}) != 2
            or len({item.account_id for item in event_movements}) != 1
            or sum((item.amount for item in event_movements), Decimal(0)) != 0
            or event_reserve_movements
        ):
            raise BackupInvariantError("Fund transfer is not balanced")
        elif event.type == FundEventType.RESERVE_DISTRIBUTION:
            if (
                not event_movements
                or not event_reserve_movements
                or any(item.amount <= 0 for item in event_movements)
                or any(item.amount >= 0 for item in event_reserve_movements)
                or sum((item.amount for item in event_movements), Decimal(0))
                + sum((item.amount for item in event_reserve_movements), Decimal(0))
                != 0
            ):
                raise BackupInvariantError("Fund reserve distribution is not balanced")
        elif event.type == FundEventType.RESERVE_RELEASE and (
            event_movements
            or not event_reserve_movements
            or any(item.amount >= 0 for item in event_reserve_movements)
        ):
            raise BackupInvariantError("Fund reserve release is invalid")
    for operation_id, operation_fund_movements in fund_movements_by_operation.items():
        if not operation_fund_movements:
            continue
        operation = operation_by_id[operation_id]
        physical = movements_by_operation[operation_id]
        if operation.type == OperationType.EXPENSE:
            if (
                len(operation_fund_movements) != 1
                or len(physical) != 1
                or operation_fund_movements[0].account_id != physical[0].account_id
                or operation_fund_movements[0].amount != physical[0].amount
            ):
                raise BackupInvariantError("Fund expense does not match physical expense")
        elif operation.type == OperationType.TRANSFER:
            if (
                len(operation_fund_movements) != 2
                or len({item.fund_id for item in operation_fund_movements}) != 1
                or {item.account_id for item in operation_fund_movements}
                != {item.account_id for item in physical}
                or sum((item.amount for item in operation_fund_movements), Decimal(0)) != 0
                or any(
                    next(
                        item.amount
                        for item in operation_fund_movements
                        if item.account_id == physical_item.account_id
                    )
                    * physical_item.amount
                    <= 0
                    or abs(
                        next(
                            item.amount
                            for item in operation_fund_movements
                            if item.account_id == physical_item.account_id
                        )
                    )
                    > abs(physical_item.amount)
                    for physical_item in physical
                )
            ):
                raise BackupInvariantError("Fund transfer does not match physical transfer")
        else:
            raise BackupInvariantError("This operation type cannot move a fund")
    for items in (data.recurring_rules, data.expected_occurrences):
        if any(
            item.account_id not in account_ids
            or (
                item.destination_account_id is not None
                and item.destination_account_id not in account_ids
            )
            or (item.category_id is not None and item.category_id not in category_ids)
            for item in items
        ):
            raise BackupInvariantError("Scheduling reference is missing")
        for item in items:
            expected_category_type = (
                CategoryType.INCOME if item.type == OperationType.INCOME else CategoryType.EXPENSE
            )
            if item.amount <= 0 or item.type == OperationType.BALANCE_ADJUSTMENT:
                raise BackupInvariantError("Scheduled operation amount or type is invalid")
            if item.type in {OperationType.INCOME, OperationType.EXPENSE}:
                if (
                    item.category_id is None
                    or category_type_by_id.get(item.category_id) != expected_category_type
                    or item.destination_account_id is not None
                ):
                    raise BackupInvariantError("Scheduled income or expense shape is invalid")
            elif (
                item.category_id is not None
                or item.destination_account_id is None
                or item.destination_account_id == item.account_id
            ):
                raise BackupInvariantError("Scheduled transfer shape is invalid")
    rule_ids = {item.id for item in data.recurring_rules}
    if any(
        (rule.end_on is not None and rule.end_on < rule.start_on)
        or (rule.frequency.value == "monthly" and rule.start_on.day > 28)
        or (
            rule.frequency.value == "yearly"
            and rule.start_on.month == 2
            and rule.start_on.day == 29
        )
        for rule in data.recurring_rules
    ):
        raise BackupInvariantError("Recurring rule date range is invalid")
    for occurrence in data.expected_occurrences:
        if (
            occurrence.source_kind == OccurrenceSourceKind.RECURRING
            and occurrence.rule_id not in rule_ids
        ):
            raise BackupInvariantError("Occurrence rule is missing")
        if (
            (occurrence.status == OccurrenceStatus.CONFIRMED)
            != (occurrence.actual_operation_id is not None)
            or (
                occurrence.source_kind == OccurrenceSourceKind.RECURRING
                and (
                    occurrence.status == OccurrenceStatus.POSTPONED
                    and not occurrence.manually_modified
                )
            )
            or (
                occurrence.source_kind == OccurrenceSourceKind.RECURRING
                and occurrence.status == OccurrenceStatus.PENDING
                and occurrence.manually_modified
            )
            or (
                occurrence.source_kind == OccurrenceSourceKind.RECURRING
                and occurrence.preserve_from_series_shift
                and (
                    occurrence.status != OccurrenceStatus.CANCELLED or occurrence.manually_modified
                )
            )
            or (
                occurrence.source_kind == OccurrenceSourceKind.RECURRING
                and occurrence.status
                not in {OccurrenceStatus.POSTPONED, OccurrenceStatus.CONFIRMED}
                and occurrence.due_on
                != occurrence.scheduled_on + timedelta(days=occurrence.series_shift_days)
            )
        ):
            raise BackupInvariantError("Expected occurrence state is invalid")
    actual_operation_ids = [
        item.actual_operation_id
        for item in data.expected_occurrences
        if item.actual_operation_id is not None
    ]
    if len(actual_operation_ids) != len(set(actual_operation_ids)) or any(
        item.actual_operation_id is not None and item.actual_operation_id not in operation_ids
        for item in data.expected_occurrences
    ):
        raise BackupInvariantError("Occurrence reference is missing")
    occurrence_keys = [
        (item.rule_id, item.scheduled_on)
        for item in data.expected_occurrences
        if item.source_kind == OccurrenceSourceKind.RECURRING
    ]
    if len(occurrence_keys) != len(set(occurrence_keys)):
        raise BackupInvariantError("A rule has duplicate expected dates")

    account_balances = {account_id: Decimal(0) for account_id in account_ids}
    for movement in data.account_movements:
        account_balances[movement.account_id] += movement.amount
    if any(amount < 0 for amount in account_balances.values()):
        raise BackupInvariantError("An account would have a negative balance")

    fund_positions: dict[tuple[Any, Any], Decimal] = {}
    for fund_position_movement in data.fund_movements:
        key = (fund_position_movement.fund_id, fund_position_movement.account_id)
        fund_positions[key] = fund_positions.get(key, Decimal(0)) + fund_position_movement.amount
    if any(amount < 0 for amount in fund_positions.values()):
        raise BackupInvariantError("An individual fund position would be negative")
    reserved_by_account = {account_id: Decimal(0) for account_id in account_ids}
    fund_totals = {fund_id: Decimal(0) for fund_id in fund_ids}
    for (fund_id, account_id), amount in fund_positions.items():
        reserved_by_account[account_id] += amount
        fund_totals[fund_id] += amount
    reserve_positions = {account_id: Decimal(0) for account_id in account_ids}
    for reserve_position_movement in data.fund_reserve_movements:
        reserve_positions[reserve_position_movement.account_id] += reserve_position_movement.amount
    if any(amount < 0 for amount in reserve_positions.values()):
        raise BackupInvariantError("A fund reserve position would be negative")
    for account_id, amount in reserve_positions.items():
        reserved_by_account[account_id] += amount
    if any(
        amount > account_balances[account_id] for account_id, amount in reserved_by_account.items()
    ):
        raise BackupInvariantError("Fund positions exceed physical balance")
    if any(fund.archived_at is not None and fund_totals[fund.id] != 0 for fund in data.funds):
        raise BackupInvariantError("An archived fund would have a non-zero balance")


def _insert(session: Session, model: type[Any], records: list[Any]) -> None:
    session.add_all(model(**record.model_dump()) for record in records)
    session.flush()


def _insert_categories(session: Session, records: list[CategoryRecord]) -> None:
    roots = [record for record in records if record.parent_id is None]
    children = [record for record in records if record.parent_id is not None]
    _insert(session, Category, roots)
    _insert(session, Category, children)


def restore_backup(session: Session, document: BackupDocument) -> RestoreResponse:
    verify_integrity(document)
    validate_document(document.data)
    _lock_tables(session, "ACCESS EXCLUSIVE")
    for model in (
        ImportReceipt,
        ImportProfile,
        ExpectedOccurrence,
        RecurringRule,
        FundReserveMovement,
        FundMovement,
        FundEvent,
        Fund,
        AccountMovement,
        FinancialOperation,
        Category,
        Account,
    ):
        session.execute(delete(model))
    settings = session.get(ApplicationSettings, 1)
    if settings is None:
        raise BackupInvariantError("Target settings are missing")
    settings_values = document.data.settings.model_dump()
    default_account_id = settings_values.pop("default_account_id")
    settings.default_account_id = None
    for field, value in settings_values.items():
        setattr(settings, field, value)
    _insert(session, ImportProfile, document.data.import_profiles)
    _insert(session, ImportReceipt, document.data.import_receipts)
    _insert(session, Account, document.data.accounts)
    settings.default_account_id = default_account_id
    _insert_categories(session, document.data.categories)
    _insert(session, FinancialOperation, document.data.operations)
    _insert(session, AccountMovement, document.data.account_movements)
    _insert(session, Fund, document.data.funds)
    _insert(session, FundEvent, document.data.fund_events)
    _insert(session, FundMovement, document.data.fund_movements)
    _insert(session, FundReserveMovement, document.data.fund_reserve_movements)
    _insert(session, RecurringRule, document.data.recurring_rules)
    _insert(session, ExpectedOccurrence, document.data.expected_occurrences)
    session.flush()
    validate_restored_state(session)
    return RestoreResponse(restored=True, counts=_counts(document.data))


def validate_restored_state(session: Session) -> None:
    negative = session.execute(
        select(AccountMovement.account_id, func.sum(AccountMovement.amount))
        .group_by(AccountMovement.account_id)
        .having(func.sum(AccountMovement.amount) < 0)
    ).first()
    if negative:
        raise BackupInvariantError("An account would have a negative balance")
    reserved: dict[Any, Decimal] = {
        row[0]: Decimal(row[1])
        for row in session.execute(
            select(FundMovement.account_id, func.sum(FundMovement.amount)).group_by(
                FundMovement.account_id
            )
        )
    }
    for account_id, amount in session.execute(
        select(
            FundReserveMovement.account_id,
            func.sum(FundReserveMovement.amount),
        ).group_by(FundReserveMovement.account_id)
    ):
        reserved[account_id] = reserved.get(account_id, Decimal(0)) + Decimal(amount)
    physical: dict[Any, Decimal] = {
        row[0]: Decimal(row[1])
        for row in session.execute(
            select(AccountMovement.account_id, func.sum(AccountMovement.amount)).group_by(
                AccountMovement.account_id
            )
        )
    }
    if any(
        amount < 0 or amount > physical.get(account_id, Decimal(0))
        for account_id, amount in reserved.items()
    ):
        raise BackupInvariantError("Fund positions are negative or exceed physical balance")
    negative_position = session.execute(
        select(
            FundMovement.fund_id,
            FundMovement.account_id,
            func.sum(FundMovement.amount),
        )
        .group_by(FundMovement.fund_id, FundMovement.account_id)
        .having(func.sum(FundMovement.amount) < 0)
    ).first()
    if negative_position:
        raise BackupInvariantError("An individual fund position would be negative")
    archived_balance = session.execute(
        select(Fund.id, func.sum(FundMovement.amount))
        .join(FundMovement, FundMovement.fund_id == Fund.id)
        .where(Fund.archived_at.is_not(None))
        .group_by(Fund.id)
        .having(func.sum(FundMovement.amount) != 0)
    ).first()
    if archived_balance:
        raise BackupInvariantError("An archived fund would have a non-zero balance")
    settings = session.get(ApplicationSettings, 1)
    if settings is None:
        raise BackupInvariantError("Target settings are missing")
    if settings.fund_allocation_mode == FundAllocationMode.MANUAL:
        active_percentage = session.scalar(
            select(func.coalesce(func.sum(Fund.allocation_percentage), 0)).where(
                Fund.archived_at.is_(None)
            )
        )
        if Decimal(active_percentage or 0) > Decimal("100"):
            raise BackupInvariantError("Active fund percentages exceed 100")
    if settings.fund_allocation_mode == FundAllocationMode.DYNAMIC:
        missing_target = session.scalar(
            select(Fund.id).where(Fund.archived_at.is_(None), Fund.target_amount.is_(None)).limit(1)
        )
        if missing_target is not None:
            raise BackupInvariantError("Dynamic allocation requires targets for all active funds")
