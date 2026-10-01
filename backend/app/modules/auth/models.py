from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, SmallInteger, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class OwnerCredential(Base):
    __tablename__ = "auth_owner_credentials"
    __table_args__ = (CheckConstraint("id = 1", name="ck_auth_owner_singleton"),)

    id: Mapped[int] = mapped_column(SmallInteger, primary_key=True, default=1)
    password_hash: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    password_changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class AuthSession(Base):
    __tablename__ = "auth_sessions"
    __table_args__ = (
        CheckConstraint("expires_at > created_at", name="ck_auth_session_positive_lifetime"),
        CheckConstraint(
            "last_activity_at >= created_at AND last_activity_at < expires_at",
            name="ck_auth_session_activity_within_lifetime",
        ),
    )

    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    owner_id: Mapped[int] = mapped_column(
        SmallInteger,
        ForeignKey("auth_owner_credentials.id", ondelete="CASCADE"),
        nullable=False,
        default=1,
    )
    csrf_token_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_activity_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )


class LoginThrottle(Base):
    __tablename__ = "auth_login_throttle"
    __table_args__ = (
        CheckConstraint("id = 1", name="ck_auth_login_throttle_singleton"),
        CheckConstraint("failed_count >= 0", name="ck_auth_login_throttle_failed_count"),
    )

    id: Mapped[int] = mapped_column(SmallInteger, primary_key=True, default=1)
    failed_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    window_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    blocked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    next_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ClientLoginThrottle(Base):
    __tablename__ = "auth_client_login_throttle"
    __table_args__ = (
        CheckConstraint("failed_count >= 0", name="ck_auth_client_throttle_failed_count"),
    )

    client_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    failed_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    window_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    blocked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
