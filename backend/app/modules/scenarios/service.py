"""Deterministic alternatives and explainable daily risk, never posting commands."""

from collections import defaultdict
from dataclasses import replace
from datetime import date, timedelta
from decimal import Decimal, localcontext
from uuid import UUID

from app.modules.forecasting.contracts import (
    ForecastResponse,
    ProjectionResult,
    ProjectionSnapshot,
    horizon_end,
    project_snapshot,
)
from app.modules.operations.contracts import OperationType
from app.modules.scenarios.schemas import (
    AllocationChange,
    EventChange,
    FundChange,
    ReserveChange,
    RiskAssessment,
    ScenarioBranch,
    ScenarioComparison,
    ScenarioRequest,
    StressWindow,
    SuggestedBoundary,
)
from app.modules.scenarios.snapshot import fingerprint
from app.modules.scheduling.contracts import (
    OccurrenceSourceKind,
    OccurrenceStatus,
    PlannedOccurrence,
)


class ScenarioError(ValueError):
    def __init__(self, code: str, status: int = 422) -> None:
        self.code, self.status = code, status
        super().__init__(code)


def daily_balances(forecast: ForecastResponse) -> list[tuple[date, Decimal]]:
    """Retain the actual starting point and exact daily risk under monthly display."""
    effects: dict[date, Decimal] = defaultdict(Decimal)
    for point in forecast.points:
        for event in point.events:
            effects[event.due_on] += Decimal(event.effect)
    balance = Decimal(forecast.starting_balance)
    values = [(forecast.from_on, balance)]
    on = forecast.from_on
    while on <= forecast.through_on:
        balance += effects[on]
        values.append((on, balance))
        on += timedelta(days=1)
    return values


def assess_risk(forecast: ForecastResponse, threshold: Decimal) -> RiskAssessment:
    windows: list[StressWindow] = []
    active: StressWindow | None = None
    for index, (on, balance) in enumerate(daily_balances(forecast)):
        if balance < threshold:
            if active is None:
                active = StressWindow(
                    from_on=on,
                    through_on=on,
                    recovered_on=None,
                    minimum_balance=format(balance, "f"),
                    minimum_on=on,
                    starts_at_snapshot=index == 0,
                )
            active.through_on = on
            if balance < Decimal(active.minimum_balance):
                active.minimum_balance, active.minimum_on = format(balance, "f"), on
        elif active is not None:
            active.recovered_on = on
            windows.append(active)
            active = None
    if active is not None:
        windows.append(active)
    return RiskAssessment(threshold=format(threshold, "f"), windows=windows)


def suggestion(forecast: ForecastResponse) -> SuggestedBoundary | None:
    sources = [
        event for point in forecast.points for event in point.events if Decimal(event.effect) != 0
    ]
    if not sources:
        return None
    required = max(
        Decimal(0), Decimal(forecast.starting_balance) - Decimal(forecast.minimum_balance)
    )
    return SuggestedBoundary(
        amount=format(required, "f"),
        from_on=forecast.from_on,
        through_on=forecast.through_on,
        event_ids=[item.occurrence_id for item in sources],
    )


def branch(
    result: ProjectionResult, stop_loss: Decimal | None, boundary: SuggestedBoundary | None
) -> ScenarioBranch:
    return ScenarioBranch(
        free=result.free,
        total=result.total,
        zero_risk=assess_risk(result.free, Decimal(0)),
        stop_loss_risk=None if stop_loss is None else assess_risk(result.free, stop_loss),
        suggested_risk=None
        if boundary is None
        else assess_risk(result.free, Decimal(boundary.amount)),
    )


def compare(snapshot: ProjectionSnapshot, request: ScenarioRequest) -> ScenarioComparison:
    # Pin the established calculator precision independently of caller decimal context.
    with localcontext() as precision:
        precision.prec = 28
        return _compare(snapshot, request)


def _compare(snapshot: ProjectionSnapshot, request: ScenarioRequest) -> ScenarioComparison:
    identity = fingerprint(snapshot)
    if identity != request.snapshot_id:
        raise ScenarioError("scenario_stale", 409)
    accounts = {item.id: item for item in snapshot.accounts}
    if request.scope_account_id is not None and request.scope_account_id not in accounts:
        raise ScenarioError("scenario_account", 404)
    if request.due_on is not None and not snapshot.today <= request.due_on <= snapshot.through_on:
        raise ScenarioError("scenario_date")
    before: PlannedOccurrence | None = None
    if request.action in {"expense", "income"}:
        if request.account_id not in accounts or accounts[request.account_id].archived:
            raise ScenarioError("scenario_account")
        assert request.account_id is not None and request.amount is not None and request.due_on
        # Synthetic events never replenish funds. Keep their same-day ordering stable.
        synthetic_id = UUID(int=0)
        while any(item.id == synthetic_id for item in snapshot.occurrences):
            synthetic_id = UUID(int=synthetic_id.int + 1)
        after = PlannedOccurrence(
            id=synthetic_id,
            rule_id=None,
            due_on=request.due_on,
            type=OperationType(request.action),
            amount=request.amount,
            description=None,
            account_id=request.account_id,
            destination_account_id=None,
            allocate_to_funds=False,
            status=OccurrenceStatus.PENDING,
            source_kind=OccurrenceSourceKind.ONE_OFF,
        )
    else:
        before = next(
            (item for item in snapshot.occurrences if item.id == request.occurrence_id), None
        )
        if before is None or before.version != request.version:
            raise ScenarioError("scenario_source", 409)
        after = replace(
            before,
            amount=request.amount if request.amount is not None else before.amount,
            due_on=request.due_on if request.due_on is not None else before.due_on,
        )
    if request.scope_account_id is not None and request.scope_account_id not in {
        after.account_id,
        after.destination_account_id,
    }:
        raise ScenarioError("scenario_scope")
    events = tuple(item for item in snapshot.occurrences if item.id != after.id) + (after,)
    through = horizon_end(snapshot.today, request.horizon)
    baseline = project_snapshot(
        snapshot, through_on=through, horizon=request.horizon, account_id=request.scope_account_id
    )
    alternative = project_snapshot(
        snapshot,
        through_on=through,
        horizon=request.horizon,
        account_id=request.scope_account_id,
        occurrences=events,
        changed_id=after.id,
    )
    boundary = suggestion(baseline.free)
    original_allocations = {
        item.occurrence_id: sum(item.amounts.values(), Decimal(0)) for item in baseline.funds.events
    }
    new_allocations = {
        item.occurrence_id: sum(item.amounts.values(), Decimal(0))
        for item in alternative.funds.events
    }
    original_fund_events = {item.occurrence_id: item for item in baseline.funds.events}
    new_fund_events = {item.occurrence_id: item for item in alternative.funds.events}
    changed = {after.id} | {
        key
        for key in original_allocations.keys() | new_allocations.keys()
        if original_fund_events.get(key) != new_fund_events.get(key)
    }
    source_by_id = {item.id: item for item in snapshot.occurrences}
    alternatives = {item.id: item for item in events}
    changes: list[EventChange] = []
    for key in sorted(changed):
        original, modified = source_by_id.get(key), alternatives[key]
        original_fund, new_fund = original_fund_events.get(key), new_fund_events.get(key)
        original_parts = original_fund.amounts if original_fund else {}
        new_parts = new_fund.amounts if new_fund else {}
        changes.append(
            EventChange(
                occurrence_id=key,
                description=modified.description,
                before_on=None if original is None else original.due_on,
                after_on=modified.due_on,
                before_amount=None if original is None else format(original.amount, "f"),
                after_amount=format(modified.amount, "f"),
                hypothetical=key == after.id,
                baseline_reserve=format(
                    original_fund.reserve_amount if original_fund else Decimal(0), "f"
                ),
                alternative_reserve=format(
                    new_fund.reserve_amount if new_fund else Decimal(0), "f"
                ),
                allocations=[
                    AllocationChange(
                        fund_id=fund.id,
                        name=fund.name,
                        baseline=format(original_parts.get(fund.id, Decimal(0)), "f"),
                        alternative=format(new_parts.get(fund.id, Decimal(0)), "f"),
                    )
                    for fund in snapshot.funds
                    if fund.id in original_parts or fund.id in new_parts
                ],
                baseline_allocation=format(original_allocations.get(key, Decimal(0)), "f"),
                alternative_allocation=format(new_allocations.get(key, Decimal(0)), "f"),
            )
        )
    assumptions = [
        "materialized_plans_only",
        "overdue_excluded",
        "daily_closing",
        "free_money_expense",
        "global_fund_sequence",
        "not_a_posting_guarantee",
    ]
    if after.due_on > through:
        assumptions.append("change_outside_horizon")
    if boundary is None:
        assumptions.append("insufficient_boundary_evidence")
    baseline_reserve = sum(
        (item.reserve_amount for item in baseline.funds.events), snapshot.reserve_total
    )
    alternative_reserve = sum(
        (item.reserve_amount for item in alternative.funds.events), snapshot.reserve_total
    )
    return ScenarioComparison(
        snapshot_id=identity,
        currency=snapshot.currency,
        baseline=branch(baseline, request.stop_loss, boundary),
        alternative=branch(alternative, request.stop_loss, boundary),
        ending_free_delta=format(
            Decimal(alternative.free.ending_balance) - Decimal(baseline.free.ending_balance), "f"
        ),
        minimum_free_delta=format(
            Decimal(alternative.free.minimum_balance) - Decimal(baseline.free.minimum_balance), "f"
        ),
        ending_total_delta=format(
            Decimal(alternative.total.ending_balance) - Decimal(baseline.total.ending_balance), "f"
        ),
        suggested_boundary=boundary,
        reserve=ReserveChange(
            starting=format(snapshot.reserve_total, "f"),
            baseline=format(baseline_reserve, "f"),
            alternative=format(alternative_reserve, "f"),
            delta=format(alternative_reserve - baseline_reserve, "f"),
        ),
        funds=[
            FundChange(
                fund_id=item.id,
                name=item.name,
                starting=format(baseline.funds.starting_balances[item.id], "f"),
                baseline=format(baseline.funds.ending_balances[item.id], "f"),
                alternative=format(alternative.funds.ending_balances[item.id], "f"),
                delta=format(
                    alternative.funds.ending_balances[item.id]
                    - baseline.funds.ending_balances[item.id],
                    "f",
                ),
            )
            for item in snapshot.funds
        ],
        events=changes,
        assumptions=assumptions,
    )
