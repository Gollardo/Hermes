from fastapi import APIRouter, HTTPException, Request, Response, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator, model_validator
from sqlalchemy.exc import IntegrityError

from app.application.setup import initialize_application_from_backup, initialize_fresh_application
from app.core.config import Settings
from app.core.database import DatabaseSession
from app.core.http_limits import BackupBodyLimitRoute
from app.modules.auth.contracts import AlreadyInitializedError, IssuedSession, is_initialized
from app.modules.auth.cookies import set_auth_cookies
from app.modules.auth.dependencies import get_runtime_settings
from app.modules.auth.schemas import SessionResponse, SetupRequest, validate_new_master_password
from app.modules.backup.contracts import (
    BackupAuthenticationFailed,
    BackupIntegrityError,
    BackupInvariantError,
    BackupTooLarge,
    InvalidBackupPayload,
    InvalidHermesFile,
    InvalidKdfParameters,
    UnsupportedHermesVersion,
)
from app.modules.categories.contracts import CategoryTemplateLanguage, OnboardingExpenseGroup


class FreshSetupRequest(SetupRequest):
    create_default_categories: bool = False
    category_template_language: CategoryTemplateLanguage = CategoryTemplateLanguage.RU
    onboarding_expense_groups: list[OnboardingExpenseGroup] = Field(default_factory=list)

    @model_validator(mode="after")
    def valid_category_selection(self) -> "FreshSetupRequest":
        if self.onboarding_expense_groups and not self.create_default_categories:
            raise ValueError("Expense groups require default category creation")
        if len(self.onboarding_expense_groups) != len(set(self.onboarding_expense_groups)):
            raise ValueError("Onboarding expense groups must be unique")
        return self


class RestoreSetupRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=False)

    master_password: SecretStr
    backup: dict[str, object]
    backup_password: SecretStr | None = Field(default=None, max_length=1024)

    @field_validator("master_password")
    @classmethod
    def valid_master_password(cls, value: SecretStr) -> SecretStr:
        return validate_new_master_password(value)


class SetupStatusResponse(BaseModel):
    initialized: bool


router = APIRouter(tags=["setup"], route_class=BackupBodyLimitRoute)


@router.get("/setup/status", response_model=SetupStatusResponse)
def setup_status(session: DatabaseSession) -> SetupStatusResponse:
    return SetupStatusResponse(initialized=is_initialized(session))


@router.post("/setup", response_model=SessionResponse, status_code=status.HTTP_201_CREATED)
def fresh_setup(payload: FreshSetupRequest, request: Request, session: DatabaseSession) -> Response:
    settings = get_runtime_settings(request)
    try:
        issued = initialize_fresh_application(
            session,
            settings,
            master_password=payload.master_password.get_secret_value(),
            base_currency=payload.base_currency,
            timezone=payload.timezone,
            create_default_categories=payload.create_default_categories,
            onboarding_expense_groups=payload.onboarding_expense_groups,
            category_template_language=payload.category_template_language,
        )
    except AlreadyInitializedError as error:
        raise already_initialized() from error
    return setup_response(settings, issued)


@router.post("/setup/restore", response_model=SessionResponse, status_code=status.HTTP_201_CREATED)
def restore_setup(
    payload: RestoreSetupRequest, request: Request, session: DatabaseSession
) -> Response:
    settings = get_runtime_settings(request)
    try:
        issued = initialize_application_from_backup(
            session,
            settings,
            master_password=payload.master_password.get_secret_value(),
            backup=payload.backup,
            backup_password=(
                payload.backup_password.get_secret_value()
                if payload.backup_password is not None
                else None
            ),
        )
    except AlreadyInitializedError as error:
        raise already_initialized() from error
    except (BackupIntegrityError, BackupInvariantError, ValueError) as error:
        raise invalid_backup(error) from error
    except IntegrityError as error:
        raise invalid_backup(ValueError("Backup violates a database domain constraint")) from error
    return setup_response(settings, issued)


def setup_response(settings: Settings, issued: IssuedSession) -> Response:
    body = SessionResponse(
        expires_at=issued.row.expires_at,
        idle_timeout_seconds=settings.session_idle_minutes * 60,
    )
    response = JSONResponse(
        status_code=status.HTTP_201_CREATED, content=body.model_dump(mode="json")
    )
    set_auth_cookies(response, settings, issued)
    return response


def already_initialized() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail={"code": "already_initialized", "message": "Setup is already complete"},
    )


def invalid_backup(error: ValueError) -> HTTPException:
    if isinstance(error, BackupTooLarge):
        return HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail={"code": "backup_too_large", "message": str(error)},
        )
    if isinstance(error, BackupAuthenticationFailed):
        return HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "backup_authentication_failed", "message": str(error)},
        )
    codes = {
        UnsupportedHermesVersion: "unsupported_hermes_version",
        InvalidKdfParameters: "invalid_kdf_parameters",
        InvalidBackupPayload: "invalid_backup_payload",
        InvalidHermesFile: "invalid_hermes_file",
    }
    for error_type, code in codes.items():
        if isinstance(error, error_type):
            return HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail={"code": code, "message": str(error)},
            )
    return HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        detail={"code": "invalid_backup", "message": str(error)},
    )
