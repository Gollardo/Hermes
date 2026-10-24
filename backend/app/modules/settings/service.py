from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.settings.models import ApplicationSettings, FundAllocationMode


class SettingsNotInitializedError(RuntimeError):
    pass


class BaseCurrencyLockedError(RuntimeError):
    pass


def lock_application_timezone(session: Session) -> str:
    """Serialize schedule creation with timezone changes."""
    settings = session.scalar(
        select(ApplicationSettings).where(ApplicationSettings.id == 1).with_for_update()
    )
    if settings is None:
        raise SettingsNotInitializedError
    return settings.timezone


def initialize_settings(session: Session, *, base_currency: str, timezone: str) -> None:
    if session.get(ApplicationSettings, 1) is not None:
        raise RuntimeError("Application settings already exist")
    now = datetime.now(UTC)
    session.add(
        ApplicationSettings(
            id=1,
            base_currency=base_currency,
            timezone=timezone,
            fund_allocation_mode=FundAllocationMode.MANUAL,
            minimum_balance_buffer=Decimal(0),
            default_account_id=None,
            base_currency_locked_at=None,
            created_at=now,
            updated_at=now,
        )
    )


def get_application_settings(session: Session) -> ApplicationSettings:
    settings = session.get(ApplicationSettings, 1)
    if settings is None:
        raise SettingsNotInitializedError
    return settings


def application_timezone(session: Session) -> str:
    """Return the configured IANA timezone through the module's public contract."""
    return get_application_settings(session).timezone


def application_today(session: Session, *, now: datetime | None = None) -> date:
    """Return the financial calendar date in the configured application timezone."""
    instant = now or datetime.now(UTC)
    return instant.astimezone(ZoneInfo(application_timezone(session))).date()


def fund_allocation_mode(session: Session) -> FundAllocationMode:
    """Return the persisted global allocation policy through the public contract."""
    return FundAllocationMode(get_application_settings(session).fund_allocation_mode)


def lock_application_settings(session: Session) -> ApplicationSettings:
    settings = session.scalar(
        select(ApplicationSettings).where(ApplicationSettings.id == 1).with_for_update()
    )
    if settings is None:
        raise SettingsNotInitializedError
    return settings


def set_fund_allocation_mode(
    settings: ApplicationSettings, mode: FundAllocationMode
) -> ApplicationSettings:
    settings.fund_allocation_mode = mode
    settings.updated_at = datetime.now(UTC)
    return settings


def update_application_settings(
    session: Session,
    *,
    base_currency: str,
    timezone: str,
    default_account_id: UUID | None = None,
    minimum_balance_buffer: Decimal = Decimal(0),
) -> ApplicationSettings:
    settings = session.scalar(
        select(ApplicationSettings).where(ApplicationSettings.id == 1).with_for_update()
    )
    if settings is None:
        raise SettingsNotInitializedError
    if settings.base_currency_locked_at is not None and base_currency != settings.base_currency:
        raise BaseCurrencyLockedError
    settings.base_currency = base_currency
    settings.timezone = timezone
    settings.default_account_id = default_account_id
    settings.minimum_balance_buffer = minimum_balance_buffer
    settings.updated_at = datetime.now(UTC)
    return settings


def clear_default_account_if_matches(session: Session, account_id: UUID) -> None:
    """Clear a default-account reference before the account becomes unavailable."""
    settings = session.scalar(
        select(ApplicationSettings).where(ApplicationSettings.id == 1).with_for_update()
    )
    if settings is None:
        raise SettingsNotInitializedError
    if settings.default_account_id == account_id:
        settings.default_account_id = None
        settings.updated_at = datetime.now(UTC)


def lock_base_currency(session: Session) -> None:
    """Public contract for the first financial-data write transaction."""
    settings = session.scalar(
        select(ApplicationSettings).where(ApplicationSettings.id == 1).with_for_update()
    )
    if settings is None:
        raise SettingsNotInitializedError
    if settings.base_currency_locked_at is None:
        now = datetime.now(UTC)
        settings.base_currency_locked_at = now
        settings.updated_at = now
