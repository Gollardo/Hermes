"""Disclosed category envelopes; facts and named future expenses consume the same budget."""

from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal
from uuid import uuid5

from app.modules.operations.contracts import OperationType
from app.modules.scenarios.service import ScenarioError
from app.modules.scenarios.workspace_schemas import EstimateEvidence, EstimateMonth, LivingCost
from app.modules.scenarios.workspace_snapshot import WorkspaceSnapshot, month_shift
from app.modules.scheduling.contracts import (
    OccurrenceSourceKind,
    OccurrenceStatus,
    PlannedOccurrence,
)

UNIT = Decimal("0.0001")


def living_cost_events(
    source: WorkspaceSnapshot,
    costs: list[LivingCost],
    events: tuple[PlannedOccurrence, ...],
    *,
    through: date,
    increase: Decimal = Decimal(0),
) -> tuple[tuple[PlannedOccurrence, ...], list[EstimateEvidence]]:
    today = source.projection.today
    generated: list[PlannedOccurrence] = []
    evidence: list[EstimateEvidence] = []
    for cost in costs:
        excluded = set(cost.excluded_operation_ids)
        facts = [
            f
            for f in source.history
            if f.account_id == cost.account_id
            and f.category_id == cost.category_id
            and f.id not in source.funded_operations
        ]
        if not excluded <= {f.id for f in facts}:
            raise ScenarioError("scenario_history_source")
        observed = facts
        facts = [f for f in facts if f.id not in excluded]
        months = [month_shift(today, i) for i in range(-6, 0)]
        totals = {
            month: sum((f.amount for f in facts if f.on.replace(day=1) == month), Decimal(0))
            for month in months
        }
        if cost.mode == "history":
            if not all(any(m <= f.on < month_shift(m, 1) for f in observed) for m in months[-3:]):
                raise ScenarioError("scenario_history_insufficient")
            monthly = (sum((totals[m] for m in months[-3:]), Decimal(0)) / 3).quantize(
                UNIT, ROUND_HALF_UP
            )
        else:
            assert cost.monthly_amount is not None
            monthly = cost.monthly_amount
        monthly = (monthly * (1 + increase / 100)).quantize(UNIT, ROUND_HALF_UP)
        history: list[EstimateMonth] = []
        errors: list[Decimal] = []
        for i, month in enumerate(months):
            prediction = None
            if (
                cost.mode == "history"
                and i >= 3
                and all(
                    any(m <= f.on < month_shift(m, 1) for f in observed)
                    for m in months[i - 3 : i + 1]
                )
            ):
                prediction = (sum((totals[m] for m in months[i - 3 : i]), Decimal(0)) / 3).quantize(
                    UNIT, ROUND_HALF_UP
                )
                errors.append(abs(prediction - totals[month]))
            history.append(
                EstimateMonth(
                    month=month,
                    actual=str(totals[month]),
                    predicted=str(prediction) if prediction is not None else None,
                )
            )
        residual_total, offset_total = Decimal(0), Decimal(0)
        month = today.replace(day=1)
        while month <= through:
            month_end = month_shift(month, 1) - timedelta(days=1)
            lower = max(today, month)
            remaining_days = (month_end - lower).days + 1
            spent = sum((f.amount for f in facts if month <= f.on <= today), Decimal(0))
            planned = sum(
                (
                    e.amount
                    for e in events
                    if e.type == OperationType.EXPENSE
                    and e.account_id == cost.account_id
                    and e.category_id == cost.category_id
                    and e.fund_id is None
                    and lower <= e.due_on <= month_end
                ),
                Decimal(0),
            )
            remaining = max(Decimal(0), monthly - spent - planned)
            # Assign each 0.0001 deterministically; never lose money by daily rounding.
            units, remainder = divmod(int(remaining / UNIT), remaining_days)
            offset_total += min(max(Decimal(0), monthly - spent), planned)
            for day in range(remaining_days):
                on = lower + timedelta(days=day)
                if on > through:
                    break
                amount = Decimal(units + (1 if day < remainder else 0)) * UNIT
                if amount <= 0:
                    continue
                residual_total += amount
                generated.append(
                    PlannedOccurrence(
                        id=uuid5(cost.id, f"living:{on}"),
                        rule_id=None,
                        due_on=on,
                        type=OperationType.EXPENSE,
                        amount=amount,
                        description=None,
                        account_id=cost.account_id,
                        destination_account_id=None,
                        allocate_to_funds=False,
                        status=OccurrenceStatus.PENDING,
                        source_kind=OccurrenceSourceKind.ONE_OFF,
                        category_id=cost.category_id,
                        origin="estimate",
                    )
                )
            month = month_shift(month, 1)
        evidence.append(
            EstimateEvidence(
                id=cost.id,
                account_id=cost.account_id,
                category_id=cost.category_id,
                mode=cost.mode,
                monthly_amount=str(monthly),
                history=history,
                operation_ids=[f.id for f in facts],
                mean_absolute_error=str(
                    (sum(errors, Decimal(0)) / len(errors)).quantize(UNIT, ROUND_HALF_UP)
                )
                if errors
                else None,
                projected_residual=str(residual_total),
                planned_offset=str(offset_total),
            )
        )
    return tuple(generated), evidence
