from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.core.validation import Money
from app.modules.depreciation.calculation import inflation_target, month_index


class PurchaseCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=120)
    cost: Money = Field(gt=0)
    purchase_month: str = Field(pattern=r"^\d{4}-(0[1-9]|1[0-2])$")
    months: int = Field(ge=1, le=600, strict=True)
    inflation: Money = Field(ge=0, le=100)

    @field_validator("name")
    @classmethod
    def trim_name(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Name must not be blank")
        return value.strip()

    @model_validator(mode="after")
    def validate_target(self) -> "PurchaseCreate":
        if month_index(self.purchase_month) + self.months > 9999 * 12 + 11:
            raise ValueError("End month exceeds supported range")
        inflation_target(self.cost, self.inflation, self.months)
        return self


class ContributionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    request_id: UUID
    version: int = Field(ge=1, strict=True)
    account_id: UUID
    source_account_id: UUID | None = None
    amount: Money = Field(gt=0)
    action: Literal["contribute", "release"] = "contribute"

    @model_validator(mode="after")
    def valid_source(self) -> "ContributionCreate":
        if self.source_account_id == self.account_id:
            raise ValueError("Use reservation for the same account")
        if self.action == "release" and self.source_account_id is not None:
            raise ValueError("Release stays on the physical account")
        return self


class LifecycleRequest(BaseModel):
    version: int = Field(ge=1, strict=True)


class MonthResponse(BaseModel):
    month: str
    planned: str
    actual: str
    remaining: str
    state: str


class PositionResponse(BaseModel):
    account_id: UUID
    account_name: str
    balance: str


class ContributionResponse(BaseModel):
    id: UUID
    month: str
    action: str
    amount: str
    account_id: UUID
    operation_id: UUID | None
    created_at: datetime


class PurchaseResponse(BaseModel):
    id: UUID
    name: str
    cost: str
    purchase_month: str
    months: int
    inflation: str
    target: str
    balance: str
    remaining: str
    end_month: str
    current_month: str
    status: str
    version: int
    schedule: list[MonthResponse]
    positions: list[PositionResponse]
    history: list[ContributionResponse]
