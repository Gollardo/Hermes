from datetime import date
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.modules.funds.schemas import FundReleaseRequest


def test_release_normalizes_same_account_without_losing_precision() -> None:
    account = uuid4()
    payload = FundReleaseRequest(
        request_id=uuid4(),
        fund_id=uuid4(),
        account_id=account,
        destination_account_id=account,
        amount="12.3456",
        occurred_on=date.today(),
        description="  compensation  ",
    )
    assert payload.destination_account_id is None
    assert str(payload.amount) == "12.3456"
    assert payload.description == "compensation"


@pytest.mark.parametrize("amount", ["0", "-1", "1.00001", 1.2, "NaN", "Infinity"])
def test_release_rejects_invalid_money(amount: object) -> None:
    with pytest.raises(ValidationError):
        FundReleaseRequest.model_validate(
            dict(
                request_id=uuid4(),
                fund_id=uuid4(),
                account_id=uuid4(),
                amount=amount,
                occurred_on=date.today(),
            )
        )
