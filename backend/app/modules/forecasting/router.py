from datetime import UTC, datetime
from uuid import UUID
from zoneinfo import ZoneInfo

from fastapi import APIRouter, HTTPException

from app.core.database import DatabaseSession
from app.modules.accounts.contracts import AccountReferenceError
from app.modules.forecasting.schemas import (
    ForecastBalanceMode,
    ForecastHorizon,
    ForecastResponse,
    FundForecastResponse,
)
from app.modules.forecasting.service import build_forecast, build_fund_forecast
from app.modules.settings.contracts import application_timezone, get_application_settings

read_router = APIRouter(prefix="/forecast", tags=["forecast"])


@read_router.get("", response_model=ForecastResponse)
def read_forecast(
    session: DatabaseSession,
    horizon: ForecastHorizon = ForecastHorizon.MONTH,
    account_id: UUID | None = None,
    balance_mode: ForecastBalanceMode = ForecastBalanceMode.FREE,
) -> ForecastResponse:
    today = datetime.now(UTC).astimezone(ZoneInfo(application_timezone(session))).date()
    try:
        return build_forecast(
            session,
            today=today,
            horizon=horizon,
            account_id=account_id,
            balance_mode=balance_mode,
            minimum_balance_buffer=get_application_settings(session).minimum_balance_buffer,
        )
    except AccountReferenceError as error:
        raise HTTPException(
            status_code=404,
            detail={"code": "forecast_account_not_found", "message": "Account not found"},
        ) from error


@read_router.get("/funds", response_model=FundForecastResponse)
def read_fund_forecast(
    session: DatabaseSession,
    horizon: ForecastHorizon = ForecastHorizon.MONTH,
) -> FundForecastResponse:
    today = datetime.now(UTC).astimezone(ZoneInfo(application_timezone(session))).date()
    return build_fund_forecast(session, today=today, horizon=horizon)
