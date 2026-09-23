from copy import deepcopy
from uuid import uuid4

import pytest

from app.modules.imports.errors import ImportDecisionError, ImportGroupingError
from app.modules.imports.grouping import decision_groups
from app.modules.imports.schemas import CommitRequest


def request() -> CommitRequest:
    account, category, plan = uuid4(), uuid4(), uuid4()
    return CommitRequest.model_validate(
        {
            "filename": "test.csv",
            "content": "",
            "decisions": [
                dict(
                    row=row,
                    statement_account_id=account,
                    action="plan",
                    occurrence_id=plan,
                    occurrence_version=1,
                    operation=dict(
                        type="expense",
                        occurred_on="2026-09-24",
                        amount=amount,
                        description=str(row),
                        account_id=account,
                        category_id=category,
                    ),
                )
                for row, amount in [(2, "10.1234"), (3, "20.5678")]
            ],
            "merge_plan_rows": [[3, 2]],
        }
    )


def test_group_preserves_source_amounts_and_canonical_membership() -> None:
    payload = request()
    before = deepcopy(payload)
    groups = decision_groups(payload)
    assert [d.row for d in groups[0]] == [2, 3]
    assert [str(d.operation.amount) for d in groups[0]] == ["10.1234", "20.5678"]
    assert payload == before


@pytest.mark.parametrize("groups", [[[2]], [[2, 2]], [[2, 4]], [[2, 3], [2, 3]]])
def test_invalid_membership_is_rejected(groups: list[list[int]]) -> None:
    payload = request()
    payload.merge_plan_rows = groups
    with pytest.raises(ImportGroupingError):
        decision_groups(payload)


@pytest.mark.parametrize("field", ["occurred_on", "account_id", "category_id", "fund_id"])
def test_incompatible_financial_fields_are_rejected(field: str) -> None:
    payload = request()
    from datetime import date

    setattr(
        payload.decisions[1].operation,
        field,
        date(2026, 9, 23) if field == "occurred_on" else uuid4(),
    )
    with pytest.raises(ImportDecisionError) as error:
        decision_groups(payload)
    assert error.value.row == 3
    assert isinstance(error.value.cause, ImportGroupingError)


@pytest.mark.parametrize(
    "field,value",
    [
        ("existing_id", uuid4()),
        ("occurrence_id", uuid4()),
        ("occurrence_version", 2),
        ("action", "new"),
        ("allocate_to_funds", True),
    ],
)
def test_group_cannot_repost_existing_or_mix_plan_decisions(field: str, value: object) -> None:
    payload = request()
    setattr(payload.decisions[1], field, value)
    with pytest.raises(ImportDecisionError):
        decision_groups(payload)


def test_same_plan_requires_explicit_group() -> None:
    payload = request()
    payload.merge_plan_rows = []
    with pytest.raises(ImportDecisionError):
        decision_groups(payload)
