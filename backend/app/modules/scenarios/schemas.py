from datetime import date
from typing import Literal, Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.core.validation import Money
from app.modules.forecasting.contracts import ForecastHorizon, ForecastResponse


class ScenarioRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    action: Literal["expense", "income", "amount", "move"]
    horizon: ForecastHorizon = ForecastHorizon.MONTH
    scope_account_id: UUID | None = None
    snapshot_id: str = Field(pattern=r"^[a-f0-9]{64}$")
    account_id: UUID | None = None
    occurrence_id: UUID | None = None
    version: int | None = Field(default=None, ge=1)
    amount: Money | None = None
    due_on: date | None = None
    stop_loss: Money | None = None

    @model_validator(mode="after")
    def shape(self) -> Self:
        if self.stop_loss is not None and self.stop_loss < 0:
            raise ValueError("stop loss must be nonnegative")
        if self.action in {"expense", "income"}:
            if self.account_id is None or self.amount is None or self.due_on is None:
                raise ValueError("new events require account, amount and date")
            if self.occurrence_id is not None or self.version is not None:
                raise ValueError("new events cannot replace a plan")
        else:
            if self.occurrence_id is None or self.version is None or self.account_id is not None:
                raise ValueError("changes require one versioned source occurrence")
            if self.action == "amount" and (self.amount is None or self.due_on is not None):
                raise ValueError("amount change requires only a new amount")
            if self.action == "move" and (self.due_on is None or self.amount is not None):
                raise ValueError("date change requires only a new date")
        if self.amount is not None and self.amount <= 0:
            raise ValueError("amount must be positive")
        return self


class AccountChoice(BaseModel):
    id: UUID
    name: str
    archived: bool


class PlanChoice(BaseModel):
    id: UUID
    version: int
    due_on: date
    amount: str
    type: str
    description: str | None
    account_id: UUID
    account_name: str
    destination_account_id: UUID | None
    destination_account_name: str | None
    allocate_to_funds: bool


class ScenarioContext(BaseModel):
    snapshot_id: str
    today: date
    maximum_on: date
    currency: str
    accounts: list[AccountChoice]
    plans: list[PlanChoice]
    overdue_excluded_count: int
    source_policy: Literal["materialized_plans_only"] = "materialized_plans_only"


class StressWindow(BaseModel):
    from_on: date
    through_on: date
    recovered_on: date | None
    minimum_balance: str
    minimum_on: date
    starts_at_snapshot: bool = False


class RiskAssessment(BaseModel):
    threshold: str
    windows: list[StressWindow]


class SuggestedBoundary(BaseModel):
    amount: str
    method: Literal["known_plan_drawdown"] = "known_plan_drawdown"
    from_on: date
    through_on: date
    event_ids: list[UUID]


class ScenarioBranch(BaseModel):
    free: ForecastResponse
    total: ForecastResponse
    zero_risk: RiskAssessment
    stop_loss_risk: RiskAssessment | None
    suggested_risk: RiskAssessment | None


class FundChange(BaseModel):
    fund_id: UUID
    name: str
    starting: str
    baseline: str
    alternative: str
    delta: str


class ReserveChange(BaseModel):
    starting: str
    baseline: str
    alternative: str
    delta: str


class AllocationChange(BaseModel):
    fund_id: UUID
    name: str
    baseline: str
    alternative: str


class EventChange(BaseModel):
    occurrence_id: UUID
    description: str | None
    before_on: date | None
    after_on: date
    before_amount: str | None
    after_amount: str
    baseline_allocation: str
    alternative_allocation: str
    hypothetical: bool
    baseline_reserve: str
    alternative_reserve: str
    allocations: list[AllocationChange]


class ScenarioComparison(BaseModel):
    snapshot_id: str
    currency: str
    baseline: ScenarioBranch
    alternative: ScenarioBranch
    ending_free_delta: str
    minimum_free_delta: str
    ending_total_delta: str
    suggested_boundary: SuggestedBoundary | None
    reserve: ReserveChange
    funds: list[FundChange]
    events: list[EventChange]
    assumptions: list[str]
