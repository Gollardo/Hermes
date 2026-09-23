from datetime import date
from decimal import Decimal
from uuid import UUID

from sqlalchemy.orm import Session

from app.application.transfer_allocation import transfer_and_allocate
from app.modules.funds.contracts import TransferAllocationCreateRequest
from app.modules.operations.contracts import ScheduledOperationDraft, post_scheduled_operation
from app.modules.scheduling.contracts import (
    OccurrenceConfirmationDraft,
    OccurrenceConfirmationOverride,
    confirm_occurrence,
)
from app.modules.scheduling.schemas import (
    ExpectedOccurrenceResponse,
    OccurrenceConfirmationOperationRequest,
)


def confirm_expected_occurrence(
    session: Session,
    occurrence_id: UUID,
    *,
    expected_version: int,
    amount: Decimal | None,
    occurred_on: date | None = None,
    operation: OccurrenceConfirmationOperationRequest | None = None,
) -> ExpectedOccurrenceResponse:
    """Confirm one occurrence and all its financial effects in the caller transaction."""

    def post(draft: OccurrenceConfirmationDraft) -> UUID:
        if draft.allocate_to_funds:
            if draft.destination_account_id is None:
                raise ValueError("fund allocation requires a transfer destination")
            result = transfer_and_allocate(
                session,
                TransferAllocationCreateRequest(
                    occurred_on=draft.occurred_on,
                    amount=draft.amount,
                    description=draft.description,
                    source_account_id=draft.account_id,
                    destination_account_id=draft.destination_account_id,
                ),
            )
            return result.operation_id
        return post_scheduled_operation(
            session,
            ScheduledOperationDraft(
                type=draft.type,
                occurred_on=draft.occurred_on,
                amount=draft.amount,
                description=draft.description,
                account_id=draft.account_id,
                destination_account_id=draft.destination_account_id,
                category_id=draft.category_id,
            ),
        )

    return confirm_occurrence(
        session,
        occurrence_id,
        expected_version=expected_version,
        amount=amount,
        occurred_on=occurred_on,
        override=(
            OccurrenceConfirmationOverride(**operation.model_dump())
            if operation is not None
            else None
        ),
        poster=post,
    )
