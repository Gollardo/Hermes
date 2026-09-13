"""Bounded scenario programs. All money crosses the API as exact decimal strings."""

from datetime import date, datetime
from decimal import Decimal
from typing import Literal, Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.core.validation import Money
from app.modules.forecasting.contracts import ForecastHorizon
from app.modules.scenarios.schemas import ScenarioComparison, StressWindow


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Decision(StrictModel):
    id: UUID
    action: Literal["expense", "income", "transfer", "edit", "exclude"]
    enabled: bool = True
    description: str = Field(default="", max_length=200)
    account_id: UUID | None = None
    destination_account_id: UUID | None = None
    category_id: UUID | None = None
    fund_id: UUID | None = None
    allocate_to_funds: bool = False
    amount: Money | None = None
    due_on: date | None = None
    repeat: Literal["once", "daily", "weekly", "monthly", "yearly"] = "once"
    repeat_until: date | None = None
    occurrence_id: UUID | None = None
    version: int | None = Field(default=None, ge=1)
    apply_to: Literal["one", "following"] = "one"

    @model_validator(mode="after")
    def shape(self) -> Self:
        if self.amount is not None and self.amount <= 0:
            raise ValueError("amount must be positive")
        if self.action in {"edit", "exclude"}:
            if self.occurrence_id is None or self.version is None:
                raise ValueError("a versioned occurrence is required")
            if any(
                (
                    self.account_id,
                    self.destination_account_id,
                    self.category_id,
                    self.fund_id,
                    self.allocate_to_funds,
                    self.repeat != "once",
                    self.repeat_until,
                )
            ):
                raise ValueError("source changes cannot change funding or recurrence")
            if self.action == "edit" and self.amount is None and self.due_on is None:
                raise ValueError("edit requires amount or date")
            if self.action == "exclude" and (self.amount is not None or self.due_on is not None):
                raise ValueError("excluded events cannot also be edited")
        else:
            if self.account_id is None or self.amount is None or self.due_on is None:
                raise ValueError("new events require account, amount and date")
            if self.occurrence_id or self.version or self.apply_to != "one":
                raise ValueError("new events cannot reference an occurrence")
            if self.action == "transfer":
                if (
                    not self.destination_account_id
                    or self.destination_account_id == self.account_id
                ):
                    raise ValueError("transfer requires two different accounts")
                if self.category_id or self.fund_id:
                    raise ValueError("transfer has no category or expense fund")
            elif self.destination_account_id or self.allocate_to_funds:
                raise ValueError("only transfers have destination/allocation")
            if self.fund_id and self.action != "expense":
                raise ValueError("only expenses consume a fund")
            if self.repeat == "once":
                if self.repeat_until:
                    raise ValueError("one-off event cannot have a repeat end")
            elif self.repeat_until is None or self.repeat_until < self.due_on:
                raise ValueError("recurrence requires an inclusive end")
            if self.repeat == "monthly" and self.due_on.day > 28:
                raise ValueError("monthly recurrence starts on days 1–28")
            if self.repeat == "yearly" and (self.due_on.month, self.due_on.day) == (2, 29):
                raise ValueError("yearly recurrence cannot start on leap day")
        return self


class LivingCost(StrictModel):
    id: UUID
    account_id: UUID
    category_id: UUID
    mode: Literal["manual", "history"] = "manual"
    monthly_amount: Money | None = None
    excluded_operation_ids: list[UUID] = Field(default_factory=list, max_length=100)

    @model_validator(mode="after")
    def shape(self) -> Self:
        if self.mode == "manual":
            if self.monthly_amount is None or self.monthly_amount < 0:
                raise ValueError("manual living costs require a nonnegative monthly amount")
        elif self.monthly_amount is not None:
            raise ValueError("historical estimates cannot silently use a manual amount")
        if len(set(self.excluded_operation_ids)) != len(self.excluded_operation_ids):
            raise ValueError("duplicate exclusions")
        return self


class Variant(StrictModel):
    id: UUID
    name: str = Field(min_length=1, max_length=120)
    decisions: list[Decision] = Field(default_factory=list, max_length=50)
    expense_increase_percent: Money = Field(default=Decimal(0))
    income_delay_days: int = Field(default=0, ge=0, le=90)

    @field_validator("name")
    @classmethod
    def name_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("name is required")
        return value.strip()

    @model_validator(mode="after")
    def shape(self) -> Self:
        if not 0 <= self.expense_increase_percent <= 100:
            raise ValueError("expense stress must be between zero and 100 percent")
        if len({d.id for d in self.decisions}) != len(self.decisions):
            raise ValueError("duplicate decision identities")
        return self


class Workspace(StrictModel):
    snapshot_id: str = Field(pattern=r"^[a-f0-9]{64}$")
    horizon: ForecastHorizon = ForecastHorizon.MONTH
    scope_account_id: UUID | None = None
    stop_loss: Money = Field(default=Decimal(0))
    living_costs: list[LivingCost] = Field(default_factory=list, max_length=10)
    variants: list[Variant] = Field(min_length=1, max_length=5)

    @model_validator(mode="after")
    def shape(self) -> Self:
        if self.stop_loss < 0:
            raise ValueError("minimum buffer must be nonnegative")
        if len({v.id for v in self.variants}) != len(self.variants):
            raise ValueError("duplicate variant identities")
        if len({c.id for c in self.living_costs}) != len(self.living_costs):
            raise ValueError("duplicate estimate identities")
        if len({(c.account_id, c.category_id) for c in self.living_costs}) != len(
            self.living_costs
        ):
            raise ValueError("living cost envelopes cannot overlap")
        return self


class SaveWorkspace(StrictModel):
    name: str = Field(min_length=1, max_length=120)
    workspace: Workspace
    version: int | None = Field(default=None, ge=1)

    @field_validator("name")
    @classmethod
    def name_not_blank(cls, value: str) -> str:
        return Variant.name_not_blank(value)


class SavedWorkspace(StrictModel):
    id: UUID
    name: str
    version: int
    workspace: Workspace
    created_at: datetime
    updated_at: datetime


class EstimateMonth(StrictModel):
    month: date
    actual: str
    predicted: str | None = None


class EstimateEvidence(StrictModel):
    id: UUID
    account_id: UUID
    category_id: UUID
    mode: str
    monthly_amount: str
    history: list[EstimateMonth]
    operation_ids: list[UUID]
    mean_absolute_error: str | None
    coverage_verified: bool = False
    projected_residual: str
    planned_offset: str


class AccountRisk(StrictModel):
    account_id: UUID
    name: str
    minimum_free: str
    minimum_total: str
    windows: list[StressWindow]


class FundingIssue(StrictModel):
    event_id: UUID
    account_id: UUID
    fund_id: UUID
    on: date
    shortfall: str


class VariantResult(StrictModel):
    id: UUID
    name: str
    comparison: ScenarioComparison
    accounts: list[AccountRisk]
    funding_issues: list[FundingIssue]
    estimates: list[EstimateEvidence]
    feasible: bool
    required_buffer: str


class WorkspaceResult(StrictModel):
    snapshot_id: str
    variants: list[VariantResult]
    baseline_estimates: list[EstimateEvidence]


class SolveRequest(StrictModel):
    workspace: Workspace
    variant_id: UUID
    decision_id: UUID
    objective: Literal["maximum_amount", "earliest_date"]
    maximum_amount: Money | None = None

    @model_validator(mode="after")
    def shape(self) -> Self:
        if self.objective == "maximum_amount":
            if self.maximum_amount is None or self.maximum_amount <= 0:
                raise ValueError("an explicit positive search ceiling is required")
        elif self.maximum_amount is not None:
            raise ValueError("date search has no amount ceiling")
        return self


class SolveResult(StrictModel):
    status: Literal["found", "no_solution"]
    amount: str | None = None
    due_on: date | None = None
    evaluated: int
    result: VariantResult | None = None
