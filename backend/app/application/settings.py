"""Cross-module application-settings use cases."""

from decimal import Decimal
from uuid import UUID

from sqlalchemy.orm import Session

from app.modules.accounts.contracts import list_account_identities, lock_account_references
from app.modules.funds.contracts import (
    rebalance_reserve,
    snapshot_dynamic_percentages_as_manual,
    validate_dynamic_targets,
)
from app.modules.scheduling.contracts import has_schedule_data
from app.modules.settings.contracts import (
    ApplicationSettings,
    FundAllocationMode,
    lock_application_settings,
    lock_application_timezone,
    set_fund_allocation_mode,
    update_application_settings,
)


class TimezoneLockedByScheduleError(RuntimeError):
    pass


def replace_fund_allocation_mode(session: Session, mode: FundAllocationMode) -> ApplicationSettings:
    account_ids = {account.id for account in list_account_identities(session)}
    lock_account_references(session, account_ids, allow_archived_ids=account_ids)
    settings = lock_application_settings(session)
    current = FundAllocationMode(settings.fund_allocation_mode)
    if current == mode:
        return settings
    if mode == FundAllocationMode.DYNAMIC:
        validate_dynamic_targets(session)
    else:
        snapshot_dynamic_percentages_as_manual(session)
    updated = set_fund_allocation_mode(settings, mode)
    if mode == FundAllocationMode.DYNAMIC:
        rebalance_reserve(session)
    return updated


def replace_application_settings(
    session: Session,
    *,
    base_currency: str,
    timezone: str,
    default_account_id: UUID | None = None,
    minimum_balance_buffer: Decimal = Decimal(0),
) -> ApplicationSettings:
    current_timezone = lock_application_timezone(session)
    if default_account_id is not None:
        lock_account_references(session, {default_account_id})
    if timezone != current_timezone and has_schedule_data(session):
        raise TimezoneLockedByScheduleError
    return update_application_settings(
        session,
        base_currency=base_currency,
        timezone=timezone,
        default_account_id=default_account_id,
        minimum_balance_buffer=minimum_balance_buffer,
    )
