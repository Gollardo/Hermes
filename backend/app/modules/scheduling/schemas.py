from datetime import date, datetime
from decimal import Decimal
from typing import Self
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator

from app.core.validation import Money
from app.modules.operations.contracts import OperationType
from app.modules.scheduling.models import (
    OccurrenceSourceKind,
    OccurrenceStatus,
    RecurrenceFrequency,
)


class RecurringRuleCreateRequest(BaseModel):
    type: OperationType
    frequency: RecurrenceFrequency
    interval: int = Field(default=1, ge=1, le=3)
    weekdays: list[int] | None = None
    start_on: date
    end_on: date | None = None
    amount: Money
    description: str | None = Field(default=None, max_length=2000)
    account_id: UUID
    destination_account_id: UUID | None = None
    category_id: UUID | None = None
    allocate_to_funds: bool = False
    shift_future_on_postpone: bool = False

    @field_validator("description")
    @classmethod
    def normalize_description(cls, value: str | None) -> str | None:
        return value.strip() or None if value is not None else None

    @model_validator(mode="after")
    def validate_shape(self) -> Self:
        if self.type == OperationType.BALANCE_ADJUSTMENT:
            raise ValueError("balance adjustments cannot recur")
        if self.amount <= 0:
            raise ValueError("amount must be positive")
        if self.end_on is not None and self.end_on < self.start_on:
            raise ValueError("end date must not precede start date")
        if self.frequency == RecurrenceFrequency.MONTHLY and self.start_on.day > 28:
            raise ValueError("monthly rules must start on day 1 through 28")
        if self.frequency == RecurrenceFrequency.YEARLY and (
            self.start_on.month == 2 and self.start_on.day == 29
        ):
            raise ValueError("yearly rules cannot start on February 29")
        if self.frequency == RecurrenceFrequency.WEEKLY:
            if not self.weekdays or len(self.weekdays) != len(set(self.weekdays)):
                raise ValueError("weekly rules require unique weekdays")
            if any(day < 1 or day > 7 for day in self.weekdays):
                raise ValueError("weekday must be between 1 and 7")
            self.weekdays.sort()
        elif self.weekdays is not None:
            raise ValueError("weekdays are only valid for weekly rules")
        if (
            self.frequency in {RecurrenceFrequency.DAILY, RecurrenceFrequency.YEARLY}
            and self.interval != 1
        ):
            raise ValueError("daily and yearly rules use interval 1")
        if self.type in {OperationType.INCOME, OperationType.EXPENSE}:
            if self.allocate_to_funds:
                raise ValueError("only transfers can allocate to funds")
            if self.category_id is None or self.destination_account_id is not None:
                raise ValueError("income and expense require category and one account")
        elif (
            self.category_id is not None
            or self.destination_account_id is None
            or self.destination_account_id == self.account_id
        ):
            raise ValueError("transfer requires two different accounts and no category")
        return self


class RecurringRuleUpdateRequest(RecurringRuleCreateRequest):
    active: bool
    version: int = Field(ge=1)


class OneOffPlanCreateRequest(BaseModel):
    type: OperationType
    scheduled_on: date
    amount: Money
    description: str | None = Field(default=None, max_length=2000)
    account_id: UUID
    destination_account_id: UUID | None = None
    category_id: UUID | None = None
    allocate_to_funds: bool = False

    @field_validator("description")
    @classmethod
    def normalize_description(cls, value: str | None) -> str | None:
        return value.strip() or None if value is not None else None

    @model_validator(mode="after")
    def validate_shape(self) -> Self:
        if self.type == OperationType.BALANCE_ADJUSTMENT:
            raise ValueError("balance adjustments cannot be planned")
        if self.amount <= 0:
            raise ValueError("amount must be positive")
        if self.type in {OperationType.INCOME, OperationType.EXPENSE}:
            if self.allocate_to_funds:
                raise ValueError("only transfers can allocate to funds")
            if self.category_id is None or self.destination_account_id is not None:
                raise ValueError("income and expense require category and one account")
        elif (
            self.category_id is not None
            or self.destination_account_id is None
            or self.destination_account_id == self.account_id
        ):
            raise ValueError("transfer requires two different accounts and no category")
        return self


class OneOffPlanUpdateRequest(OneOffPlanCreateRequest):
    version: int = Field(ge=1)


class RecurringRuleResponse(BaseModel):
    id: UUID
    type: OperationType
    frequency: RecurrenceFrequency
    interval: int
    weekdays: list[int] | None
    start_on: date
    end_on: date | None
    amount: str
    description: str | None
    account_id: UUID
    account_name: str
    destination_account_id: UUID | None
    destination_account_name: str | None
    category_id: UUID | None
    category_name: str | None
    allocate_to_funds: bool
    shift_future_on_postpone: bool
    series_shift_days: int
    active: bool
    version: int
    created_at: datetime
    updated_at: datetime


class ExpectedOccurrenceResponse(BaseModel):
    id: UUID
    source_kind: OccurrenceSourceKind
    rule_id: UUID | None
    scheduled_on: date
    due_on: date
    status: OccurrenceStatus
    manually_modified: bool
    series_shift_days: int
    preserve_from_series_shift: bool
    overdue: bool
    type: OperationType
    amount: str
    description: str | None
    account_id: UUID
    account_name: str
    destination_account_id: UUID | None
    destination_account_name: str | None
    category_id: UUID | None
    category_name: str | None
    allocate_to_funds: bool
    actual_operation_id: UUID | None
    version: int
    created_at: datetime
    updated_at: datetime


class OccurrencePageResponse(BaseModel):
    items: list[ExpectedOccurrenceResponse]
    page: int
    page_size: int
    total: int


class MaterializationResponse(BaseModel):
    horizon_from: date
    horizon_to: date
    created: int
    updated: int
    cancelled: int


class OccurrenceVersionRequest(BaseModel):
    version: int = Field(ge=1)


class OccurrenceConfirmationOperationRequest(BaseModel):
    type: OperationType
    amount: Money
    description: str | None = Field(default=None, max_length=2000)
    account_id: UUID
    destination_account_id: UUID | None = None
    category_id: UUID | None = None
    allocate_to_funds: bool = False

    @field_validator("description")
    @classmethod
    def normalize_description(cls, value: str | None) -> str | None:
        return value.strip() or None if value is not None else None

    @model_validator(mode="after")
    def validate_shape(self) -> Self:
        if self.type == OperationType.BALANCE_ADJUSTMENT:
            raise ValueError("balance adjustments cannot confirm an occurrence")
        if self.amount <= 0:
            raise ValueError("amount must be positive")
        if self.type in {OperationType.INCOME, OperationType.EXPENSE}:
            if self.allocate_to_funds:
                raise ValueError("only transfers can allocate to funds")
            if self.category_id is None or self.destination_account_id is not None:
                raise ValueError("income and expense require category and one account")
        elif (
            self.category_id is not None
            or self.destination_account_id is None
            or self.destination_account_id == self.account_id
        ):
            raise ValueError("transfer requires two different accounts and no category")
        return self


class OccurrenceConfirmRequest(OccurrenceVersionRequest):
    occurred_on: date | None = None
    amount: Money | None = None
    operation: OccurrenceConfirmationOperationRequest | None = None

    @field_validator("amount")
    @classmethod
    def positive_amount(cls, value: Decimal | None) -> Decimal | None:
        if value is not None and value <= 0:
            raise ValueError("amount must be positive")
        return value

    @model_validator(mode="after")
    def validate_override(self) -> Self:
        if self.amount is not None and self.operation is not None:
            raise ValueError("amount and operation cannot be supplied together")
        return self


class OccurrencePostponeRequest(OccurrenceVersionRequest):
    due_on: date
    rule_version: int | None = Field(default=None, ge=1)


class OccurrencePostponeResponse(ExpectedOccurrenceResponse):
    series_shift_applied: bool
    shift_days: int
    shifted_occurrences: int
    preserved_occurrences: int
    rule_version: int


def format_money(value: Decimal) -> str:
    return format(value, ".4f")
