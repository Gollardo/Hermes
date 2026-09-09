import pytest
from pydantic import ValidationError

from app.api.routes.setup import FreshSetupRequest
from app.modules.categories.templates import (
    DEFAULT_INCOME_CATEGORIES,
    ENGLISH_EXPENSE_CATEGORIES,
    ENGLISH_INCOME_CATEGORIES,
    ONBOARDING_EXPENSE_CATEGORIES,
    CategoryTemplateLanguage,
    OnboardingExpenseGroup,
)


def test_template_catalogs_cover_the_same_tree_without_changing_group_identity() -> None:
    assert (
        set(ENGLISH_EXPENSE_CATEGORIES)
        == set(ONBOARDING_EXPENSE_CATEGORIES)
        == set(OnboardingExpenseGroup)
    )
    assert len(ENGLISH_INCOME_CATEGORIES) == len(DEFAULT_INCOME_CATEGORIES) == 5
    for group in OnboardingExpenseGroup:
        russian, english = ONBOARDING_EXPENSE_CATEGORIES[group], ENGLISH_EXPENSE_CATEGORIES[group]
        assert len(russian[1]) == len(english[1]) == 5
        assert all(name.strip() for name in (english[0], *english[1]))
        assert len(set(english[1])) == 5


def test_setup_language_defaults_to_russian_and_rejects_unknown_languages() -> None:
    payload = dict(master_password="test-master-password", base_currency="RUB", timezone="UTC")
    assert FreshSetupRequest(**payload).category_template_language == CategoryTemplateLanguage.RU
    assert (
        FreshSetupRequest(**payload, category_template_language="en").category_template_language
        == CategoryTemplateLanguage.EN
    )
    with pytest.raises(ValidationError):
        FreshSetupRequest(**payload, category_template_language="de")
