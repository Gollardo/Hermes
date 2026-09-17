from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Literal, Self
from uuid import UUID

from pydantic import BaseModel, BeforeValidator, Field, field_validator, model_validator

from app.core.validation import Money, parse_decimal
from app.modules.settings.contracts import FundAllocationMode


def parse_percentage(value: object) -> Decimal:
    return parse_decimal(value, scale=4, maximum=Decimal("100"))


Percentage = Annotated[Decimal, BeforeValidator(parse_percentage)]


class FundCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=2000)
    allocation_percentage: Percentage
    target_amount: Money | None = None
    initial_account_id: UUID | None = None
    initial_amount: Money | None = None
    initial_occurred_on: date | None = None

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        if not (name := value.strip()):
            raise ValueError("name must not be blank")
        return name

    @field_validator("description")
    @classmethod
    def normalize_description(cls, value: str | None) -> str | None:
        return value.strip() or None if value is not None else None

    @field_validator("allocation_percentage")
    @classmethod
    def percentage_range(cls, value: Decimal) -> Decimal:
        if value < 0 or value > 100:
            raise ValueError("percentage must be between 0 and 100")
        return value

    @field_validator("target_amount")
    @classmethod
    def positive_target(cls, value: Decimal | None) -> Decimal | None:
        if value is not None and value <= 0:
            raise ValueError("target amount must be positive")
        return value

    @model_validator(mode="after")
    def valid_initial_allocation(self) -> Self:
        values = (self.initial_account_id, self.initial_amount, self.initial_occurred_on)
        if any(value is not None for value in values) and not all(
            value is not None for value in values
        ):
            raise ValueError("initial allocation requires account, amount and date")
        if self.initial_amount is not None and self.initial_amount <= 0:
            raise ValueError("initial allocation must be positive")
        return self


class FundUpdateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=2000)
    allocation_percentage: Percentage
    target_amount: Money | None = None
    version: int = Field(ge=1)

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        if not (name := value.strip()):
            raise ValueError("name must not be blank")
        return name

    @field_validator("description")
    @classmethod
    def normalize_description(cls, value: str | None) -> str | None:
        return value.strip() or None if value is not None else None

    @field_validator("target_amount")
    @classmethod
    def positive_target(cls, value: Decimal | None) -> Decimal | None:
        if value is not None and value <= 0:
            raise ValueError("target amount must be positive")
        return value


class FundLifecycleRequest(BaseModel):
    version: int = Field(ge=1)


class FundResponse(BaseModel):
    id: UUID
    name: str
    description: str | None
    allocation_percentage: str
    manual_allocation_percentage: str
    allocation_mode: FundAllocationMode
    target_amount: str | None
    total_balance: str
    remaining_amount: str | None
    distribution_status: Literal["manual", "active", "filled", "archived"]
    progress_percentage: str | None
    archived: bool
    version: int
    created_at: datetime
    updated_at: datetime


class FundPositionResponse(BaseModel):
    fund_id: UUID
    fund_name: str
    account_id: UUID
    account_name: str
    balance: str


class AccountCoverageResponse(BaseModel):
    depreciation_reserved_balance: str = "0"
    account_id: UUID
    account_name: str
    physical_balance: str
    reserved_balance: str
    fund_reserved_balance: str
    reserve_balance: str
    free_balance: str
    archived: bool


class FundSummaryResponse(BaseModel):
    depreciation_reserved: str = "0"
    funds: list[FundResponse]
    positions: list[FundPositionResponse]
    accounts: list[AccountCoverageResponse]
    active_percentage: str
    allocation_mode: FundAllocationMode
    total_reserved: str
    total_fund_reserved: str
    total_reserve: str
    total_free: str


class AllocationPreviewRequest(BaseModel):
    account_id: UUID
    amount: Money

    @field_validator("amount")
    @classmethod
    def positive_amount(cls, value: Decimal) -> Decimal:
        if value <= 0:
            raise ValueError("amount must be positive")
        return value


class AllocationItem(BaseModel):
    fund_id: UUID
    amount: Money
    allocation_percentage: str | None = None

    @field_validator("amount")
    @classmethod
    def non_negative_amount(cls, value: Decimal) -> Decimal:
        if value < 0:
            raise ValueError("allocation cannot be negative")
        return value


class AllocationPreviewResponse(BaseModel):
    account_id: UUID
    amount: str
    allocations: list[AllocationItem]
    allocated_amount: str
    unallocated_amount: str
    reserve_amount: str
    free_before: str
    free_after: str


class AllocationCreateRequest(AllocationPreviewRequest):
    occurred_on: date
    description: str | None = Field(default=None, max_length=2000)
    allocations: list[AllocationItem] = Field(default_factory=list)

    @field_validator("description")
    @classmethod
    def normalize_description(cls, value: str | None) -> str | None:
        return value.strip() or None if value is not None else None

    @model_validator(mode="after")
    def unique_funds(self) -> Self:
        ids = [item.fund_id for item in self.allocations]
        if len(ids) != len(set(ids)):
            raise ValueError("each fund may occur once")
        return self


class RedistributionCreateRequest(BaseModel):
    occurred_on: date
    fund_id: UUID
    source_account_id: UUID
    destination_account_id: UUID
    amount: Money
    description: str | None = Field(default=None, max_length=2000)

    @field_validator("description")
    @classmethod
    def normalize_description(cls, value: str | None) -> str | None:
        return value.strip() or None if value is not None else None

    @model_validator(mode="after")
    def validate_shape(self) -> Self:
        if self.source_account_id == self.destination_account_id:
            raise ValueError("accounts must differ")
        if self.amount <= 0:
            raise ValueError("amount must be positive")
        return self


class FundTransferCreateRequest(BaseModel):
    occurred_on: date
    source_fund_id: UUID
    destination_fund_id: UUID
    account_id: UUID
    amount: Money
    description: str | None = Field(default=None, max_length=2000)

    @field_validator("description")
    @classmethod
    def normalize_description(cls, value: str | None) -> str | None:
        return value.strip() or None if value is not None else None

    @model_validator(mode="after")
    def validate_shape(self) -> Self:
        if self.source_fund_id == self.destination_fund_id:
            raise ValueError("funds must differ")
        if self.amount <= 0:
            raise ValueError("amount must be positive")
        return self


class TransferAllocationCreateRequest(BaseModel):
    occurred_on: date
    source_account_id: UUID
    destination_account_id: UUID
    fund_id: UUID | None = None
    amount: Money
    description: str | None = Field(default=None, max_length=2000)

    @field_validator("description")
    @classmethod
    def normalize_description(cls, value: str | None) -> str | None:
        return value.strip() or None if value is not None else None

    @model_validator(mode="after")
    def validate_shape(self) -> Self:
        if self.source_account_id == self.destination_account_id:
            raise ValueError("accounts must differ")
        if self.amount <= 0:
            raise ValueError("amount must be positive")
        return self


class FundMovementResponse(BaseModel):
    fund_id: UUID
    fund_name: str
    account_id: UUID
    account_name: str
    amount: str


class FundEventResponse(BaseModel):
    id: UUID
    type: Literal[
        "allocation",
        "redistribution",
        "fund_transfer",
        "reserve_distribution",
        "reserve_release",
        "fund_release",
        "expense",
        "transfer",
    ]
    occurred_on: date
    description: str | None
    movements: list[FundMovementResponse]
    reserve_movements: list["FundReserveMovementResponse"] = []
    caused_by_operation_id: UUID | None = None
    created_at: datetime


class TransferAllocationResponse(BaseModel):
    operation_id: UUID
    allocation: FundEventResponse


class FundReserveMovementResponse(BaseModel):
    account_id: UUID
    account_name: str
    amount: str


class FundReserveReleaseRequest(BaseModel):
    account_id: UUID
    amount: Money
    occurred_on: date
    description: str | None = Field(default=None, max_length=2000)

    @field_validator("description")
    @classmethod
    def normalize_description(cls, value: str | None) -> str | None:
        return value.strip() or None if value is not None else None

    @field_validator("amount")
    @classmethod
    def positive_amount(cls, value: Decimal) -> Decimal:
        if value <= 0:
            raise ValueError("amount must be positive")
        return value


class FundHistoryResponse(BaseModel):
    items: list[FundEventResponse]
    page: int
    page_size: int
    total: int


class FundReleaseRequest(FundReserveReleaseRequest):
    request_id: UUID
    fund_id: UUID
    destination_account_id: UUID | None = None

    @model_validator(mode="after")
    def normalize_same_account(self) -> Self:
        if self.destination_account_id == self.account_id:
            self.destination_account_id = None
        return self


class FundReleaseResponse(BaseModel):
    operation_id: UUID | None
    release: FundEventResponse
