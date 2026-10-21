from datetime import date
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.modules.operations.schemas import OperationCreateRequest


class Mapping(BaseModel):
    model_config = ConfigDict(extra="forbid")
    sheet: str = ""
    header_row: int = Field(default=1, ge=1, le=100)
    encoding: Literal["utf-8-sig", "cp1251"] = "utf-8-sig"
    delimiter: Literal["", ";", ",", "\t"] = ""
    amount: int = Field(default=7, ge=0, le=99)
    description: int = Field(default=6, ge=0, le=99)
    source_date: int | None = Field(default=None, ge=0, le=99)
    date_format: (
        Literal[
            "dmy_dot",
            "iso",
            "dmy_slash",
            "dmy_dot_datetime",
            "iso_datetime",
            "dmy_slash_datetime",
        ]
        | None
    ) = None
    direction: int | None = Field(default=12, ge=0, le=99)
    debit: int | None = Field(default=None, ge=0, le=99)
    credit: int | None = Field(default=None, ge=0, le=99)
    currency: int | None = Field(default=8, ge=0, le=99)
    decimal_separator: Literal[".", ","] = "."
    expense_values: str = "Списание,debit,expense"
    income_values: str = "Зачисление,Пополнение,credit,income"


class FileRequest(BaseModel):
    filename: str = Field(max_length=255)
    content: str = Field(max_length=7_000_000)
    mapping: Mapping = Field(default_factory=Mapping)


class PreviewRequest(FileRequest):
    account_id: UUID
    window_days: int = Field(default=3, ge=0, le=3660)


class CandidateRequest(BaseModel):
    account_id: UUID
    fact_date: date
    direction: Literal["income", "expense", "transfer"]
    amount: Decimal = Field(gt=0)
    source_description: str = Field(default="", max_length=4000)
    window_days: int = Field(default=3, ge=0, le=3660)


class Decision(BaseModel):
    statement_account_id: UUID
    row: int = Field(ge=1)
    action: Literal["new", "plan", "existing"]
    operation: OperationCreateRequest
    occurrence_id: UUID | None = None
    occurrence_version: int | None = Field(default=None, ge=1)
    existing_id: UUID | None = None
    existing_version: int | None = Field(default=None, ge=1)
    allocate_to_funds: bool = False


class CommitRequest(FileRequest):
    decisions: list[Decision] = Field(min_length=1)
    merge_plan_rows: list[list[int]] = Field(default_factory=list, max_length=100)


class ProfileRequest(BaseModel):
    @field_validator("name")
    @classmethod
    def nonblank_name(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Profile name is required")
        return value.strip()

    name: str = Field(min_length=1, max_length=120)
    mapping: Mapping

    @model_validator(mode="after")
    def mapped_source_date(self) -> "ProfileRequest":
        if self.mapping.source_date is None:
            raise ValueError("Source date column is required")
        return self
