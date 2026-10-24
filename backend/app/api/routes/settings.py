from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from fastapi import APIRouter, HTTPException, status

from app.application.settings import (
    TimezoneLockedByScheduleError,
    replace_application_settings,
    replace_fund_allocation_mode,
)
from app.core.database import DatabaseSession
from app.modules.accounts.contracts import AccountReferenceError
from app.modules.funds.contracts import DynamicFundTargetsRequiredError
from app.modules.settings.contracts import ApplicationSettings
from app.modules.settings.schemas import (
    FundAllocationModeUpdateRequest,
    SettingsResponse,
    SettingsUpdateRequest,
)
from app.modules.settings.service import BaseCurrencyLockedError, get_application_settings

read_router = APIRouter(prefix="/settings", tags=["settings"])
write_router = APIRouter(prefix="/settings", tags=["settings"])


def _response(settings: ApplicationSettings) -> SettingsResponse:
    return SettingsResponse(
        base_currency=settings.base_currency,
        timezone=settings.timezone,
        default_account_id=settings.default_account_id,
        fund_allocation_mode=settings.fund_allocation_mode,
        minimum_balance_buffer=f"{settings.minimum_balance_buffer:.4f}",
        base_currency_locked=settings.base_currency_locked_at is not None,
        updated_at=settings.updated_at,
        application_today=datetime.now(UTC).astimezone(ZoneInfo(settings.timezone)).date(),
    )


@read_router.get("", response_model=SettingsResponse)
def read_settings(session: DatabaseSession) -> SettingsResponse:
    return _response(get_application_settings(session))


@write_router.put("", response_model=SettingsResponse)
def replace_settings(
    payload: SettingsUpdateRequest,
    session: DatabaseSession,
) -> SettingsResponse:
    try:
        current = get_application_settings(session)
        settings = replace_application_settings(
            session,
            base_currency=payload.base_currency,
            timezone=payload.timezone,
            default_account_id=payload.default_account_id,
            minimum_balance_buffer=(
                current.minimum_balance_buffer
                if payload.minimum_balance_buffer is None
                else payload.minimum_balance_buffer
            ),
        )
    except AccountReferenceError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "invalid_default_account",
                "message": "Default account is unavailable",
            },
        ) from error
    except BaseCurrencyLockedError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "base_currency_locked",
                "message": "Base currency cannot change after financial data exists",
            },
        ) from error
    except TimezoneLockedByScheduleError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "timezone_locked_by_schedule",
                "message": "Timezone cannot change after recurring rules exist",
            },
        ) from error
    return _response(settings)


@write_router.put("/fund-allocation-mode", response_model=SettingsResponse)
def replace_allocation_mode(
    payload: FundAllocationModeUpdateRequest,
    session: DatabaseSession,
) -> SettingsResponse:
    try:
        return _response(replace_fund_allocation_mode(session, payload.mode))
    except AccountReferenceError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "invalid_account_reference",
                "message": "An account changed while fund allocation mode was updated",
            },
        ) from error
    except DynamicFundTargetsRequiredError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "dynamic_fund_targets_required",
                "message": "Every non-archived fund needs a target in dynamic mode",
            },
        ) from error
