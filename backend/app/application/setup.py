from sqlalchemy.orm import Session

from app.core.config import Settings
from app.modules.auth.contracts import IssuedSession, setup_owner
from app.modules.backup.contracts import open_backup, preview_backup, restore_backup
from app.modules.categories.contracts import (
    CategoryTemplateLanguage,
    OnboardingExpenseGroup,
    create_onboarding_categories,
)


def initialize_fresh_application(
    session: Session,
    settings: Settings,
    *,
    master_password: str,
    base_currency: str,
    timezone: str,
    create_default_categories: bool,
    onboarding_expense_groups: list[OnboardingExpenseGroup],
    category_template_language: CategoryTemplateLanguage = CategoryTemplateLanguage.RU,
) -> IssuedSession:
    """Create access state and optional owner-selected directories in one transaction."""
    issued = setup_owner(
        session,
        settings,
        master_password=master_password,
        base_currency=base_currency,
        timezone=timezone,
    )
    if create_default_categories:
        create_onboarding_categories(
            session, onboarding_expense_groups, language=category_template_language
        )
    return issued


def initialize_application_from_backup(
    session: Session,
    settings: Settings,
    *,
    master_password: str,
    backup: dict[str, object],
    backup_password: str | None,
) -> IssuedSession:
    """Validate and restore a fresh instance without committing a partial setup."""
    document = open_backup(backup, backup_password)
    preview_backup(document)
    issued = setup_owner(
        session,
        settings,
        master_password=master_password,
        base_currency=document.data.settings.base_currency,
        timezone=document.data.settings.timezone,
    )
    restore_backup(session, document)
    return issued
