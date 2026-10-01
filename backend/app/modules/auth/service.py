from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from math import ceil

from sqlalchemy import delete, func, or_, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.modules.auth.models import AuthSession, ClientLoginThrottle, LoginThrottle, OwnerCredential
from app.modules.auth.security import (
    hash_password,
    hash_token,
    new_opaque_token,
    password_hash_needs_upgrade,
    tokens_match,
    verify_password,
)
from app.modules.settings.contracts import initialize_settings


class AlreadyInitializedError(RuntimeError):
    pass


class PasswordWorkBusyError(RuntimeError):
    pass


class LoginStatus(StrEnum):
    SUCCESS = "success"
    INVALID = "invalid"
    BLOCKED = "blocked"
    BUSY = "busy"


PASSWORD_WORK_LOCK = 0x4845524D41555448
MAX_CLIENT_THROTTLES = 4096


def _try_password_work(session: Session) -> bool:
    return bool(
        session.scalar(text("SELECT pg_try_advisory_xact_lock(:key)"), {"key": PASSWORD_WORK_LOCK})
    )


def admit_setup_work(session: Session) -> None:
    """Bound first-run hashing/decryption across all application workers."""
    if not _try_password_work(session):
        raise PasswordWorkBusyError
    # A competing setup may commit between the early check and admission.
    if is_initialized(session):
        raise AlreadyInitializedError


@dataclass(frozen=True)
class IssuedSession:
    row: AuthSession
    session_token: str
    csrf_token: str


@dataclass(frozen=True)
class LoginResult:
    status: LoginStatus
    issued_session: IssuedSession | None = None
    retry_after_seconds: int | None = None


def is_initialized(session: Session) -> bool:
    return session.scalar(select(OwnerCredential.id).limit(1)) is not None


def _issue_session(session: Session, settings: Settings) -> IssuedSession:
    now = datetime.now(UTC)
    session_token = new_opaque_token()
    csrf_token = new_opaque_token()
    row = AuthSession(
        token_hash=hash_token(session_token),
        owner_id=1,
        csrf_token_hash=hash_token(csrf_token),
        created_at=now,
        last_activity_at=now,
        expires_at=now + timedelta(days=settings.session_lifetime_days),
    )
    session.add(row)
    return IssuedSession(row=row, session_token=session_token, csrf_token=csrf_token)


def setup_owner(
    session: Session,
    settings: Settings,
    *,
    master_password: str,
    base_currency: str,
    timezone: str,
) -> IssuedSession:
    if is_initialized(session):
        raise AlreadyInitializedError
    now = datetime.now(UTC)
    session.add(
        OwnerCredential(
            id=1,
            password_hash=hash_password(master_password),
            created_at=now,
            password_changed_at=now,
        )
    )
    throttle = session.get(LoginThrottle, 1)
    if throttle is None:
        session.add(LoginThrottle(id=1, failed_count=0))
    else:
        throttle.failed_count = 0
        throttle.window_started_at = None
        throttle.blocked_until = None
    initialize_settings(session, base_currency=base_currency, timezone=timezone)
    issued = _issue_session(session, settings)
    try:
        session.flush()
    except IntegrityError as error:
        raise AlreadyInitializedError from error
    return issued


def _get_locked_throttle(session: Session) -> LoginThrottle:
    throttle = session.get(LoginThrottle, 1, with_for_update=True)
    if throttle is None:
        throttle = LoginThrottle(id=1, failed_count=0)
        session.add(throttle)
        session.flush()
    return throttle


def _blocked_seconds(throttle: LoginThrottle | ClientLoginThrottle, now: datetime) -> int | None:
    if throttle.blocked_until is None or throttle.blocked_until <= now:
        return None
    return max(1, ceil((throttle.blocked_until - now).total_seconds()))


def _record_failed_login(
    throttle: LoginThrottle | ClientLoginThrottle, now: datetime, settings: Settings
) -> None:
    window = timedelta(minutes=settings.login_failure_window_minutes)
    if throttle.window_started_at is None or now - throttle.window_started_at >= window:
        throttle.failed_count = 1
        throttle.window_started_at = now
    else:
        throttle.failed_count += 1
    if throttle.failed_count >= settings.login_failure_limit:
        throttle.blocked_until = now + timedelta(minutes=settings.login_block_minutes)


def login(
    session: Session, settings: Settings, *, master_password: str, client_key: str
) -> LoginResult:
    if not _try_password_work(session):
        return LoginResult(LoginStatus.BUSY, retry_after_seconds=1)
    now = datetime.now(UTC)
    admission = _get_locked_throttle(session)
    # Anonymous callers cannot change the sensitive-action failure counters.
    cutoff = now - timedelta(minutes=settings.login_failure_window_minutes)
    session.execute(
        delete(ClientLoginThrottle).where(
            ClientLoginThrottle.window_started_at < cutoff,
            or_(
                ClientLoginThrottle.blocked_until.is_(None),
                ClientLoginThrottle.blocked_until <= now,
            ),
        )
    )
    key = hash_token("login-client:" + client_key)
    throttle = session.get(ClientLoginThrottle, key, with_for_update=True)
    if throttle is not None and (blocked_seconds := _blocked_seconds(throttle, now)):
        return LoginResult(LoginStatus.BLOCKED, retry_after_seconds=blocked_seconds)
    if admission.next_login_at is not None and admission.next_login_at > now:
        return LoginResult(LoginStatus.BUSY, retry_after_seconds=1)
    if throttle is None:
        throttle = ClientLoginThrottle(client_hash=key, failed_count=0, window_started_at=now)
        if (
            session.scalar(select(func.count()).select_from(ClientLoginThrottle)) or 0
        ) < MAX_CLIENT_THROTTLES:
            session.add(throttle)
        # At capacity, retain known blocks and still allow a correct owner
        # password. New sources use the serialized global work budget without
        # growing persistent state or creating a blanket owner lockout.
    admission.next_login_at = now + timedelta(milliseconds=settings.login_admission_interval_ms)

    owner = session.get(OwnerCredential, 1)
    if owner is None or not verify_password(owner.password_hash, master_password):
        _record_failed_login(throttle, now, settings)
        blocked_seconds = _blocked_seconds(throttle, now)
        if blocked_seconds is not None:
            return LoginResult(LoginStatus.BLOCKED, retry_after_seconds=blocked_seconds)
        return LoginResult(LoginStatus.INVALID)

    throttle.failed_count = 0
    throttle.window_started_at = now
    throttle.blocked_until = None
    if password_hash_needs_upgrade(owner.password_hash):
        owner.password_hash = hash_password(master_password)
    idle_cutoff = now - timedelta(minutes=settings.session_idle_minutes)
    session.execute(
        delete(AuthSession).where(
            or_(AuthSession.expires_at <= now, AuthSession.last_activity_at <= idle_cutoff)
        )
    )
    return LoginResult(LoginStatus.SUCCESS, issued_session=_issue_session(session, settings))


def find_authenticated_session(
    session: Session, settings: Settings, token: str
) -> AuthSession | None:
    now = datetime.now(UTC)
    auth_session = session.scalar(
        select(AuthSession).where(
            AuthSession.token_hash == hash_token(token), AuthSession.expires_at > now
        )
    )
    if auth_session is None:
        return None
    if now - auth_session.last_activity_at >= timedelta(minutes=settings.session_idle_minutes):
        return None
    return auth_session


def touch_authenticated_session(auth_session: AuthSession) -> None:
    auth_session.last_activity_at = min(
        datetime.now(UTC), auth_session.expires_at - timedelta(microseconds=1)
    )


def csrf_is_valid(auth_session: AuthSession, csrf_token: str) -> bool:
    return tokens_match(auth_session.csrf_token_hash, csrf_token)


def reauthenticate_owner(session: Session, settings: Settings, password: str) -> LoginResult:
    """Rate-limit and verify a password for a sensitive authenticated action."""
    now = datetime.now(UTC)
    throttle = _get_locked_throttle(session)
    if blocked_seconds := _blocked_seconds(throttle, now):
        return LoginResult(LoginStatus.BLOCKED, retry_after_seconds=blocked_seconds)
    owner = session.get(OwnerCredential, 1)
    if owner is None or not verify_password(owner.password_hash, password):
        _record_failed_login(throttle, now, settings)
        blocked_seconds = _blocked_seconds(throttle, now)
        if blocked_seconds is not None:
            return LoginResult(LoginStatus.BLOCKED, retry_after_seconds=blocked_seconds)
        return LoginResult(LoginStatus.INVALID)
    throttle.failed_count = 0
    throttle.window_started_at = None
    throttle.blocked_until = None
    if password_hash_needs_upgrade(owner.password_hash):
        owner.password_hash = hash_password(password)
    return LoginResult(LoginStatus.SUCCESS)


def logout_other_sessions(session: Session, auth_session: AuthSession) -> None:
    session.execute(delete(AuthSession).where(AuthSession.token_hash != auth_session.token_hash))


def logout_current(session: Session, auth_session: AuthSession) -> None:
    session.delete(auth_session)


def logout_all(session: Session) -> None:
    session.execute(delete(AuthSession))


def change_master_password(
    session: Session,
    auth_session: AuthSession,
    settings: Settings,
    *,
    current_password: str,
    new_master_password: str,
) -> LoginResult:
    result = reauthenticate_owner(session, settings, current_password)
    if result.status is not LoginStatus.SUCCESS:
        return result
    owner = session.get(OwnerCredential, 1)
    assert owner is not None
    owner.password_hash = hash_password(new_master_password)
    owner.password_changed_at = datetime.now(UTC)
    session.execute(delete(AuthSession).where(AuthSession.token_hash != auth_session.token_hash))
    return result
