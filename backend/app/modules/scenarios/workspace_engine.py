"""Compose decision sets, compare futures and solve bounded exact constraints."""

from dataclasses import replace
from datetime import timedelta
from decimal import ROUND_HALF_UP, Decimal, localcontext
from uuid import UUID, uuid5

from app.modules.forecasting.contracts import ProgramResult, horizon_end, project_program
from app.modules.operations.contracts import OperationType
from app.modules.scenarios.living_costs import UNIT, living_cost_events
from app.modules.scenarios.schemas import (
    AllocationChange,
    EventChange,
    FundChange,
    ReserveChange,
    ScenarioComparison,
)
from app.modules.scenarios.service import ScenarioError, assess_risk, branch, suggestion
from app.modules.scenarios.workspace_schemas import (
    AccountRisk,
    Decision,
    EstimateEvidence,
    FundingIssue,
    SolveRequest,
    SolveResult,
    Variant,
    VariantResult,
    Workspace,
    WorkspaceResult,
)
from app.modules.scenarios.workspace_snapshot import WorkspaceSnapshot, identity
from app.modules.scheduling.contracts import (
    OccurrenceSourceKind,
    OccurrenceStatus,
    PlannedOccurrence,
    scenario_recurrence_dates,
)


def validate_sources(source: WorkspaceSnapshot, workspace: Workspace) -> None:
    if identity(source) != workspace.snapshot_id:
        raise ScenarioError("scenario_stale", 409)
    accounts = {a.id: a for a in source.projection.accounts}
    categories = {c.id: c for c in source.categories}
    if workspace.scope_account_id is not None and workspace.scope_account_id not in accounts:
        raise ScenarioError("scenario_account")
    for cost in workspace.living_costs:
        if cost.account_id not in accounts or accounts[cost.account_id].archived:
            raise ScenarioError("scenario_account")
        category = categories.get(cost.category_id)
        if category is None or category.archived or category.type.value != "expense":
            raise ScenarioError("scenario_category")


def overlay(source: WorkspaceSnapshot, variant: Variant) -> tuple[PlannedOccurrence, ...]:
    snapshot = source.projection
    original = {e.id: e for e in snapshot.occurrences}
    events = dict(original)
    touched: set[UUID] = set()
    accounts = {a.id: a for a in snapshot.accounts}
    categories = {c.id: c for c in source.categories}
    funds = {f.id for f in snapshot.funds}
    for d in variant.decisions:
        if not d.enabled:
            continue
        if d.due_on and not snapshot.today <= d.due_on <= snapshot.through_on:
            raise ScenarioError("scenario_date")
        if d.repeat_until and d.repeat_until > snapshot.through_on:
            raise ScenarioError("scenario_date")
        if d.action in {"edit", "exclude"}:
            before = original.get(d.occurrence_id) if d.occurrence_id else None
            if before is None or before.version != d.version:
                raise ScenarioError("scenario_source", 409)
            selected = [before]
            if d.apply_to == "following":
                if before.rule_id is None:
                    raise ScenarioError("scenario_series")
                selected = [
                    e
                    for e in original.values()
                    if e.rule_id == before.rule_id
                    and (e.scheduled_on or e.due_on) >= (before.scheduled_on or before.due_on)
                ]
            for event in selected:
                if event.id in touched:
                    raise ScenarioError("scenario_overlap")
                touched.add(event.id)
                if d.action == "exclude":
                    events.pop(event.id)
                else:
                    due = event.due_on + (d.due_on - before.due_on if d.due_on else timedelta())
                    if not snapshot.today <= due <= snapshot.through_on:
                        raise ScenarioError("scenario_date")
                    events[event.id] = replace(
                        event,
                        due_on=due,
                        amount=d.amount if d.amount is not None else event.amount,
                        origin="scenario",
                    )
            continue
        for account in [d.account_id] + (
            [d.destination_account_id] if d.destination_account_id else []
        ):
            if account not in accounts or accounts[account].archived:
                raise ScenarioError("scenario_account")
        if d.category_id is not None:
            c = categories.get(d.category_id)
            if c is None or c.archived or c.type.value != d.action:
                raise ScenarioError("scenario_category")
        if d.fund_id and d.fund_id not in funds:
            raise ScenarioError("scenario_fund")
        assert d.account_id and d.amount is not None and d.due_on
        dates = (
            [d.due_on]
            if d.repeat == "once"
            else scenario_recurrence_dates(
                frequency=d.repeat, start=d.due_on, end=d.repeat_until or d.due_on
            )
        )
        for on in dates:
            event_id = uuid5(d.id, on.isoformat())
            if event_id in events:
                raise ScenarioError("scenario_overlap")
            events[event_id] = PlannedOccurrence(
                id=event_id,
                rule_id=None,
                due_on=on,
                type=OperationType(d.action),
                amount=d.amount,
                description=d.description or None,
                account_id=d.account_id,
                destination_account_id=d.destination_account_id,
                allocate_to_funds=d.allocate_to_funds,
                status=OccurrenceStatus.PENDING,
                source_kind=OccurrenceSourceKind.ONE_OFF,
                category_id=d.category_id,
                fund_id=d.fund_id,
                origin="scenario",
            )
    stressed: list[PlannedOccurrence] = []
    for event in events.values():
        amount, due = event.amount, event.due_on
        if event.type == OperationType.EXPENSE:
            amount = (amount * (1 + variant.expense_increase_percent / 100)).quantize(
                UNIT, ROUND_HALF_UP
            )
        elif event.type == OperationType.INCOME:
            due += timedelta(days=variant.income_delay_days)
        stressed.append(
            replace(
                event,
                amount=amount,
                due_on=due,
                origin="scenario"
                if amount != event.amount or due != event.due_on
                else event.origin,
            )
        )
    if len(stressed) > 10000:
        raise ScenarioError("scenario_event_limit")
    return tuple(stressed)


def project(
    source: WorkspaceSnapshot,
    workspace: Workspace,
    events: tuple[PlannedOccurrence, ...],
    increase: Decimal = Decimal(0),
) -> tuple[ProgramResult, list[EstimateEvidence]]:
    through = horizon_end(source.projection.today, workspace.horizon)
    estimates, evidence = living_cost_events(
        source, workspace.living_costs, events, through=through, increase=increase
    )
    if len(events) + len(estimates) > 10000:
        raise ScenarioError("scenario_event_limit")
    return project_program(
        source.projection,
        events + estimates,
        horizon=workspace.horizon,
        through_on=through,
        scope=workspace.scope_account_id,
    ), evidence


def result_for(
    source: WorkspaceSnapshot,
    workspace: Workspace,
    variant: Variant,
    baseline: ProgramResult,
    alternative: ProgramResult,
    events: tuple[PlannedOccurrence, ...],
    evidence: list[EstimateEvidence],
) -> VariantResult:
    before, after = baseline.projection, alternative.projection
    boundary = suggestion(before.free)
    old = {e.id: e for e in source.projection.occurrences}
    new = {e.id: e for e in events}
    old_alloc = {e.occurrence_id: e for e in before.funds.events}
    new_alloc = {e.occurrence_id: e for e in after.funds.events}
    changes: list[EventChange] = []
    for key in sorted(old.keys() | new.keys()):
        a, b = old.get(key), new.get(key)
        if a == b and old_alloc.get(key) == new_alloc.get(key):
            continue
        oa, na = old_alloc.get(key), new_alloc.get(key)
        op, np = oa.amounts if oa else {}, na.amounts if na else {}
        changed_event = b or a
        assert changed_event is not None
        changes.append(
            EventChange(
                occurrence_id=key,
                description=changed_event.description,
                before_on=a.due_on if a else None,
                after_on=b.due_on if b else None,
                before_amount=str(a.amount) if a else None,
                after_amount=str(b.amount) if b else None,
                baseline_allocation=str(sum(op.values(), Decimal(0))),
                alternative_allocation=str(sum(np.values(), Decimal(0))),
                hypothetical=a != b,
                source_available=a is not None and a.origin == "plan",
                baseline_reserve=str(oa.reserve_amount if oa else 0),
                alternative_reserve=str(na.reserve_amount if na else 0),
                allocations=[
                    AllocationChange(
                        fund_id=f.id,
                        name=f.name,
                        baseline=str(op.get(f.id, 0)),
                        alternative=str(np.get(f.id, 0)),
                    )
                    for f in source.projection.funds
                    if f.id in op or f.id in np
                ],
            )
        )
    assumptions = [
        "complete_read_only_schedule",
        "overdue_excluded",
        "daily_closing",
        "global_fund_sequence",
        "not_a_posting_guarantee",
    ]
    if workspace.living_costs:
        assumptions += ["living_cost_envelopes", "history_coverage_unverified"]
    if any(e.due_on > after.free.through_on for e in events if old.get(e.id) != e):
        assumptions.append("change_outside_horizon")
    comparison = ScenarioComparison(
        snapshot_id=workspace.snapshot_id,
        currency=source.projection.currency,
        baseline=branch(before, workspace.stop_loss, boundary),
        alternative=branch(after, workspace.stop_loss, boundary),
        ending_free_delta=str(
            Decimal(after.free.ending_balance) - Decimal(before.free.ending_balance)
        ),
        minimum_free_delta=str(
            Decimal(after.free.minimum_balance) - Decimal(before.free.minimum_balance)
        ),
        ending_total_delta=str(
            Decimal(after.total.ending_balance) - Decimal(before.total.ending_balance)
        ),
        suggested_boundary=boundary,
        reserve=ReserveChange(
            starting=str(source.projection.reserve_total),
            baseline=str(baseline.reserve_end),
            alternative=str(alternative.reserve_end),
            delta=str(alternative.reserve_end - baseline.reserve_end),
        ),
        funds=[
            FundChange(
                fund_id=f.id,
                name=f.name,
                starting=f.total_balance,
                baseline=str(before.funds.ending_balances[f.id]),
                alternative=str(after.funds.ending_balances[f.id]),
                delta=str(after.funds.ending_balances[f.id] - before.funds.ending_balances[f.id]),
            )
            for f in source.projection.funds
        ],
        events=changes,
        assumptions=assumptions,
    )
    accounts = [
        AccountRisk(
            account_id=a.id,
            name=a.name,
            minimum_free=alternative.accounts[a.id][0].minimum_balance,
            minimum_total=alternative.accounts[a.id][1].minimum_balance,
            windows=assess_risk(alternative.accounts[a.id][0], Decimal(0)).windows,
        )
        for a in source.projection.accounts
    ]
    return VariantResult(
        id=variant.id,
        name=variant.name,
        comparison=comparison,
        accounts=accounts,
        funding_issues=[
            FundingIssue(
                event_id=i.event_id,
                account_id=i.account_id,
                fund_id=i.fund_id,
                on=i.on,
                shortfall=str(i.shortfall),
            )
            for i in alternative.funding_issues
        ],
        estimates=evidence,
        feasible=is_feasible(alternative, workspace),
        required_buffer=str(
            max(Decimal(0), workspace.stop_loss - Decimal(after.free.minimum_balance))
        ),
    )


def is_feasible(result: ProgramResult, workspace: Workspace) -> bool:
    return (
        Decimal(result.projection.free.minimum_balance) >= workspace.stop_loss
        and not result.funding_issues
        and all(
            Decimal(free.minimum_balance) >= 0 and Decimal(total.minimum_balance) >= 0
            for free, total in result.accounts.values()
        )
    )


def compare_workspace(source: WorkspaceSnapshot, workspace: Workspace) -> WorkspaceResult:
    with localcontext() as ctx:
        ctx.prec = 28
        validate_sources(source, workspace)
        baseline, evidence = project(source, workspace, source.projection.occurrences)
        results = []
        for variant in workspace.variants:
            events = overlay(source, variant)
            alternative, ve = project(source, workspace, events, variant.expense_increase_percent)
            results.append(
                result_for(source, workspace, variant, baseline, alternative, events, ve)
            )
        return WorkspaceResult(
            snapshot_id=workspace.snapshot_id, variants=results, baseline_estimates=evidence
        )


def solve_workspace(source: WorkspaceSnapshot, request: SolveRequest) -> SolveResult:
    with localcontext() as ctx:
        ctx.prec = 28
        return _solve(source, request)


def _solve(source: WorkspaceSnapshot, request: SolveRequest) -> SolveResult:
    workspace = request.workspace
    validate_sources(source, workspace)
    variant = next((v for v in workspace.variants if v.id == request.variant_id), None)
    d = (
        next((d for d in variant.decisions if d.id == request.decision_id), None)
        if variant
        else None
    )
    if (
        variant is None
        or d is None
        or not d.enabled
        or d.action != "expense"
        or d.fund_id
        or d.due_on is None
        or d.due_on > horizon_end(source.projection.today, workspace.horizon)
        or any(
            c.account_id == d.account_id and c.category_id == d.category_id
            for c in workspace.living_costs
        )
        or (request.objective == "earliest_date" and d.repeat != "once")
    ):
        raise ScenarioError("scenario_solver_target")
    baseline, _ = project(source, workspace, source.projection.occurrences)
    evaluated = 0

    def evaluate(
        decision: Decision,
    ) -> tuple[Variant, ProgramResult, tuple[PlannedOccurrence, ...], list[EstimateEvidence]]:
        nonlocal evaluated
        candidate = variant.model_copy(
            update={
                "decisions": [decision if item.id == d.id else item for item in variant.decisions]
            }
        )
        events = overlay(source, candidate)
        result, evidence = project(source, workspace, events, candidate.expense_increase_percent)
        evaluated += 1
        return candidate, result, events, evidence

    found = None
    chosen = None
    if request.objective == "maximum_amount":
        assert request.maximum_amount is not None
        low, high = 1, int(request.maximum_amount / UNIT)
        while low <= high:
            middle = (low + high) // 2
            candidate = d.model_copy(update={"amount": Decimal(middle) * UNIT})
            current = evaluate(candidate)
            if is_feasible(current[1], workspace):
                found, chosen, low = current, candidate, middle + 1
            else:
                high = middle - 1
    else:
        assert d.due_on is not None
        through = horizon_end(source.projection.today, workspace.horizon)
        for offset in range((through - d.due_on).days + 1):
            candidate = d.model_copy(update={"due_on": d.due_on + timedelta(days=offset)})
            current = evaluate(candidate)
            if is_feasible(current[1], workspace):
                found, chosen = current, candidate
                break
    if found is None or chosen is None:
        return SolveResult(status="no_solution", evaluated=evaluated)
    v, alternative, events, evidence = found
    return SolveResult(
        status="found",
        amount=str(chosen.amount),
        due_on=chosen.due_on,
        evaluated=evaluated,
        result=result_for(source, workspace, v, baseline, alternative, events, evidence),
    )
