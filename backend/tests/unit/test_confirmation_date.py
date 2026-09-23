from datetime import UTC, date, datetime
from decimal import Decimal
from unittest.mock import Mock, patch
from uuid import uuid4

import pytest

from app.modules.operations.contracts import FutureOperationDateError, OperationType
from app.modules.scheduling.models import ExpectedOccurrence, OccurrenceSourceKind, OccurrenceStatus
from app.modules.scheduling.service import _today, confirm_occurrence


def test_application_date_uses_timezone_at_utc_midnight_boundary() -> None:
    with (
        patch("app.modules.scheduling.service.application_timezone", return_value="Europe/Moscow"),
        patch("app.modules.scheduling.service.datetime") as clock,
    ):
        clock.now.return_value = datetime(2026, 9, 24, 21, 30, tzinfo=UTC)
        assert _today(Mock()) == date(2026, 9, 25)


@pytest.mark.parametrize("kind", list(OccurrenceSourceKind))
@pytest.mark.parametrize("chosen", [date(2026, 9, 23), date(2026, 9, 24), date(2026, 9, 25)])
def test_selected_date_reaches_poster_without_moving_plan(
    kind: OccurrenceSourceKind,
    chosen: date,
) -> None:
    occurrence = ExpectedOccurrence(
        id=uuid4(),
        source_kind=kind,
        status=OccurrenceStatus.PENDING,
        version=1,
        due_on=date(2026, 9, 24),
        scheduled_on=date(2026, 9, 24),
        type=OperationType.EXPENSE,
        amount=Decimal("1.2345"),
        account_id=uuid4(),
        category_id=uuid4(),
        allocate_to_funds=False,
        manually_modified=False,
    )
    poster = Mock(return_value=uuid4())
    with (
        patch("app.modules.scheduling.service._get_occurrence", return_value=occurrence),
        patch("app.modules.scheduling.service._occurrence_response"),
    ):
        confirm_occurrence(
            Mock(),
            occurrence.id,
            expected_version=1,
            poster=poster,
            occurred_on=chosen,
            today=date(2026, 9, 25),
        )
    assert poster.call_args.args[0].occurred_on == chosen
    assert occurrence.due_on == occurrence.scheduled_on == date(2026, 9, 24)


def test_future_date_fails_before_posting() -> None:
    occurrence = ExpectedOccurrence(
        id=uuid4(),
        source_kind=OccurrenceSourceKind.ONE_OFF,
        status=OccurrenceStatus.PENDING,
        version=1,
        due_on=date(2026, 9, 24),
        type=OperationType.EXPENSE,
        amount=Decimal("1"),
        account_id=uuid4(),
        category_id=uuid4(),
        allocate_to_funds=False,
    )
    poster = Mock()
    with (
        patch("app.modules.scheduling.service._get_occurrence", return_value=occurrence),
        pytest.raises(FutureOperationDateError),
    ):
        confirm_occurrence(
            Mock(),
            occurrence.id,
            expected_version=1,
            poster=poster,
            occurred_on=date(2026, 9, 26),
            today=date(2026, 9, 25),
        )
    poster.assert_not_called()
    assert occurrence.status == OccurrenceStatus.PENDING
