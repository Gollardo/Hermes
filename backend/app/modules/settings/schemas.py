from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, field_validator

from app.core.validation import Money
from app.modules.settings.models import FundAllocationMode
from app.modules.settings.validation import normalize_currency, normalize_timezone


class SettingsResponse(BaseModel):
    base_currency: str
    timezone: str
    default_account_id: UUID | None
    fund_allocation_mode: FundAllocationMode
    minimum_balance_buffer: str
    base_currency_locked: bool
    updated_at: datetime
    application_today: date


class SettingsUpdateRequest(BaseModel):
    base_currency: str
    timezone: str
    default_account_id: UUID | None = None
    minimum_balance_buffer: Money | None = None

    @field_validator("base_currency")
    @classmethod
    def valid_currency(cls, value: str) -> str:
        return normalize_currency(value)

    @field_validator("timezone")
    @classmethod
    def valid_timezone(cls, value: str) -> str:
        return normalize_timezone(value)

    @field_validator("minimum_balance_buffer")
    @classmethod
    def non_negative_buffer(cls, value: Decimal | None) -> Decimal | None:
        if value is not None and value < 0:
            raise ValueError("minimum balance buffer must not be negative")
        return value


class FundAllocationModeUpdateRequest(BaseModel):
    mode: FundAllocationMode
