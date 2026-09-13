from datetime import date
from enum import StrEnum
from typing import Literal
from uuid import UUID

from pydantic import BaseModel

from app.modules.operations.contracts import OperationType
from app.modules.scheduling.contracts import OccurrenceSourceKind, OccurrenceStatus
from app.modules.settings.contracts import FundAllocationMode


class ForecastScope(StrEnum):
    ALL = "all"
    ACCOUNT = "account"


class ForecastHorizon(StrEnum):
    TWO_WEEKS = "two_weeks"
    MONTH = "month"
    QUARTER = "quarter"
    HALF_YEAR = "half_year"
    YEAR = "year"


class ForecastGranularity(StrEnum):
    DAY = "day"
    MONTH = "month"


class ForecastBalanceMode(StrEnum):
    FREE = "free"
    TOTAL = "total"


class ForecastEventResponse(BaseModel):
    origin: Literal["plan", "scenario", "estimate", "virtual"] = "plan"
    occurrence_id: UUID
    rule_id: UUID | None
    source_kind: OccurrenceSourceKind
    due_on: date
    type: OperationType
    status: OccurrenceStatus
    description: str | None
    account_id: UUID
    account_name: str
    destination_account_id: UUID | None
    destination_account_name: str | None
    amount: str
    effect: str


class ForecastPointResponse(BaseModel):
    period_from: date
    on: date
    opening_balance: str
    change: str
    closing_balance: str
    events: list[ForecastEventResponse]


class ForecastResponse(BaseModel):
    balance_mode: ForecastBalanceMode
    scope: ForecastScope
    account_id: UUID | None
    account_name: str | None
    horizon: ForecastHorizon
    granularity: ForecastGranularity
    from_on: date
    through_on: date
    starting_balance: str
    ending_balance: str
    minimum_balance: str
    minimum_on: date
    first_negative_on: date | None
    first_negative_balance: str | None
    expected_income: str
    expected_expense: str
    overdue_excluded_count: int
    points: list[ForecastPointResponse]


class FundForecastPointResponse(BaseModel):
    period_from: date
    on: date
    change: str
    balance: str


class FundForecastSeriesResponse(BaseModel):
    fund_id: UUID
    fund_name: str
    allocation_percentage: str
    ending_allocation_percentage: str
    starting_balance: str
    ending_balance: str
    points: list[FundForecastPointResponse]


class FundForecastAllocationItemResponse(BaseModel):
    fund_id: UUID
    allocation_percentage: str
    amount: str


class FundForecastAllocationEventResponse(BaseModel):
    occurrence_id: UUID
    due_on: date
    incoming_amount: str
    allocated_amount: str
    reserve_amount: str
    executable: bool
    allocations: list[FundForecastAllocationItemResponse]


class FundForecastResponse(BaseModel):
    allocation_mode: FundAllocationMode
    horizon: ForecastHorizon
    granularity: ForecastGranularity
    from_on: date
    through_on: date
    planned_transfer_total: str
    planned_allocation_total: str
    unallocated_total: str
    starting_reserve: str
    ending_reserve: str
    blocked_allocation_count: int
    allocation_events: list[FundForecastAllocationEventResponse]
    series: list[FundForecastSeriesResponse]
