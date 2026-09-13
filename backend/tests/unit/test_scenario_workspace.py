from copy import deepcopy
from dataclasses import replace
from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import UUID

import pytest
from pydantic import ValidationError

from app.modules.accounts.contracts import AccountIdentity
from app.modules.categories.contracts import CategoryType, ProjectionCategory
from app.modules.forecasting.contracts import ForecastHorizon, ProjectionSnapshot, project_program
from app.modules.funds.contracts import FundResponse
from app.modules.operations.contracts import ExpenseFact, OperationType
from app.modules.scenarios.living_costs import living_cost_events
from app.modules.scenarios.service import ScenarioError
from app.modules.scenarios.workspace_engine import compare_workspace, overlay, solve_workspace
from app.modules.scenarios.workspace_schemas import (
    Decision,
    LivingCost,
    SolveRequest,
    Variant,
    Workspace,
)
from app.modules.scenarios.workspace_snapshot import WorkspaceSnapshot, identity
from app.modules.scheduling.contracts import OccurrenceStatus, PlannedOccurrence
from app.modules.settings.contracts import FundAllocationMode

A, B, C, F, V = (UUID(int=i) for i in range(1, 6))
TODAY = date(2026, 9, 13)


def event(
    key: int,
    amount: str,
    on: date,
    kind: OperationType = OperationType.EXPENSE,
    *,
    account_id: UUID = A,
    rule_id: UUID | None = None,
    category_id: UUID | None = None,
    fund_id: UUID | None = None,
    destination_account_id: UUID | None = None,
    allocate_to_funds: bool = False,
) -> PlannedOccurrence:
    base = PlannedOccurrence(
        id=UUID(int=key),
        rule_id=None,
        due_on=on,
        type=kind,
        amount=Decimal(amount),
        description=str(key),
        account_id=A,
        destination_account_id=None,
        allocate_to_funds=False,
        status=OccurrenceStatus.PENDING,
    )
    return replace(
        base,
        account_id=account_id,
        rule_id=rule_id,
        category_id=category_id,
        fund_id=fund_id,
        destination_account_id=destination_account_id,
        allocate_to_funds=allocate_to_funds,
    )


def source(
    events: tuple[PlannedOccurrence, ...] = (), facts: tuple[ExpenseFact, ...] = ()
) -> WorkspaceSnapshot:
    return WorkspaceSnapshot(
        ProjectionSnapshot(
            today=TODAY,
            through_on=date(2027, 9, 13),
            currency="RUB",
            accounts=(AccountIdentity(A, "Main", False), AccountIdentity(B, "Savings", False)),
            balances=((A, Decimal(100000)), (B, Decimal(0))),
            reserved=(),
            funds=(),
            mode=FundAllocationMode.MANUAL,
            occurrences=events,
            overdue_count=0,
        ),
        (ProjectionCategory(C, "Living", CategoryType.EXPENSE, False),),
        facts,
        frozenset(),
    )


def decision(key: int, amount: str, on: str, **values: object) -> Decision:
    return Decision.model_validate(
        dict(
            id=str(UUID(int=key)),
            action="expense",
            account_id=str(A),
            amount=amount,
            due_on=on,
            **values,
        )
    )


def workspace(s: WorkspaceSnapshot, decisions: list[Decision], **values: object) -> Workspace:
    return Workspace.model_validate(
        dict(
            snapshot_id=identity(s),
            variants=[Variant(id=V, name="Decision", decisions=decisions)],
            **values,
        )
    )


def test_combined_decisions_find_gap_that_each_independent_expense_misses() -> None:
    s = source((event(10, "100000", date(2026, 10, 1), OperationType.INCOME),))
    first, second = decision(20, "60000", "2026-09-20"), decision(21, "50000", "2026-09-22")
    assert compare_workspace(s, workspace(s, [first])).variants[0].feasible
    assert compare_workspace(s, workspace(s, [second])).variants[0].feasible
    before = deepcopy(s)
    result = compare_workspace(s, workspace(s, [first, second])).variants[0]
    assert not result.feasible
    assert result.comparison.alternative.free.minimum_balance == "-10000.0000"
    assert result.comparison.alternative.zero_risk.windows[0].recovered_on == date(2026, 10, 1)
    assert s == before
    assert compare_workspace(s, workspace(s, [first, second])) == compare_workspace(
        s, workspace(s, [second, first])
    )


def test_transfer_is_total_neutral_but_account_shortfall_is_not_hidden() -> None:
    s = source()
    transfer = Decision(
        id=UUID(int=20),
        action="transfer",
        account_id=B,
        destination_account_id=A,
        amount="1",
        due_on=TODAY,
    )
    r = compare_workspace(s, workspace(s, [transfer])).variants[0]
    assert Decimal(r.comparison.ending_total_delta) == 0
    assert not r.feasible
    assert r.accounts[1].minimum_total == "-1"


def test_edit_amount_and_date_following_series_and_conflict_detection() -> None:
    s = source(
        (
            event(10, "100", date(2026, 9, 15), rule_id=F),
            event(11, "100", date(2026, 9, 22), rule_id=F),
        )
    )
    edit = Decision(
        id=UUID(int=20),
        action="edit",
        occurrence_id=UUID(int=10),
        version=1,
        amount="200.0001",
        due_on=date(2026, 9, 16),
        apply_to="following",
    )
    events = overlay(s, Variant(id=V, name="Series", decisions=[edit]))
    assert [e.due_on for e in events] == [date(2026, 9, 16), date(2026, 9, 23)]
    assert all(e.amount == Decimal("200.0001") for e in events)
    overlap = Decision(id=UUID(int=21), action="exclude", occurrence_id=UUID(int=11), version=1)
    with pytest.raises(ScenarioError, match="scenario_overlap"):
        compare_workspace(s, workspace(s, [edit, overlap]))
    overlap = overlap.model_copy(update={"enabled": False})
    assert compare_workspace(s, workspace(s, [edit, overlap])).variants[0].feasible


def test_exclusion_removes_only_hypothetical_source_and_explains_deletion() -> None:
    s = source((event(10, "100", TODAY),))
    d = Decision(id=UUID(int=20), action="exclude", occurrence_id=UUID(int=10), version=1)
    r = compare_workspace(s, workspace(s, [d])).variants[0]
    assert Decimal(r.comparison.ending_total_delta) == 100
    assert r.comparison.events[0].after_on is None
    assert len(s.projection.occurrences) == 1


def test_recurring_expenses_expand_and_validation_rejects_ambiguous_dates() -> None:
    s = source()
    d = decision(20, "1.0001", "2026-09-14", repeat="weekly", repeat_until="2026-10-05")
    assert len(overlay(s, Variant(id=V, name="Weekly", decisions=[d]))) == 4
    with pytest.raises(ValidationError):
        decision(20, "1", "2026-09-30", repeat="monthly", repeat_until="2026-12-30")


def test_living_envelope_subtracts_actual_and_future_plans_exactly() -> None:
    fact = ExpenseFact(UUID(int=100), A, C, date(2026, 9, 1), Decimal(10000), None)
    planned = event(10, "10000", date(2026, 9, 20), category_id=C)
    s = source((planned,), (fact,))
    cost = LivingCost(
        id=UUID(int=30), account_id=A, category_id=C, mode="manual", monthly_amount="30000.0001"
    )
    events, evidence = living_cost_events(
        s, [cost], s.projection.occurrences, through=date(2026, 9, 30)
    )
    assert sum((e.amount for e in events), Decimal(0)) == Decimal("10000.0001")
    assert evidence[0].planned_offset == "10000"
    assert all(e.origin == "estimate" for e in events)
    assert max(e.amount for e in events) - min(e.amount for e in events) <= Decimal("0.0001")
    without_plan, _ = living_cost_events(s, [cost], (), through=date(2026, 9, 30))
    assert sum((e.amount for e in without_plan), Decimal(0)) == Decimal("20000.0001")


def test_envelopes_do_not_overlap_or_double_count_other_accounts_categories_funds() -> None:
    cost = LivingCost(id=UUID(int=30), account_id=A, category_id=C, monthly_amount="30000")
    s = source((event(10, "30000", date(2026, 9, 20), category_id=C, account_id=B),))
    events, _ = living_cost_events(s, [cost], s.projection.occurrences, through=date(2026, 9, 30))
    assert sum((e.amount for e in events), Decimal(0)) == 30000
    with pytest.raises(ValidationError):
        workspace(s, [], living_costs=[cost, cost.model_copy(update={"id": UUID(int=31)})])


def test_history_estimation_exclusions_and_backtest_do_not_use_future_months() -> None:
    facts = tuple(
        ExpenseFact(UUID(int=100 + m), A, C, date(2026, m, 10), Decimal(m * 1000), None)
        for m in range(3, 9)
    )
    s = source(facts=facts)
    cost = LivingCost(id=UUID(int=30), account_id=A, category_id=C, mode="history")
    _, evidence = living_cost_events(s, [cost], (), through=date(2026, 9, 30))
    e = evidence[0]
    assert e.monthly_amount == "7000.0000"
    assert e.history[-1].predicted == "6000.0000"
    assert e.mean_absolute_error == "2000.0000"
    changed = replace(s, history=facts[:-1] + (replace(facts[-1], amount=Decimal(100000)),))
    _, next_evidence = living_cost_events(changed, [cost], (), through=date(2026, 9, 30))
    assert next_evidence[0].history[-1].predicted == e.history[-1].predicted
    excluded = cost.model_copy(update={"excluded_operation_ids": [facts[-1].id]})
    _, reduced = living_cost_events(s, [excluded], (), through=date(2026, 9, 30))
    assert reduced[0].monthly_amount == "4333.3333"
    assert not e.coverage_verified


def test_sparse_history_fails_without_substituting_zero() -> None:
    s = source()
    cost = LivingCost(id=UUID(int=30), account_id=A, category_id=C, mode="history")
    with pytest.raises(ScenarioError, match="scenario_history_insufficient"):
        compare_workspace(s, workspace(s, [], living_costs=[cost]))


def test_every_training_month_needs_observed_history_and_backtest_needs_earlier_data() -> None:
    facts = tuple(
        ExpenseFact(UUID(int=100 + m), A, C, date(2026, m, 10), Decimal(3000), None)
        for m in (3, 6, 7, 8)
    )
    cost = LivingCost(id=UUID(int=30), account_id=A, category_id=C, mode="history")
    _, evidence = living_cost_events(source(facts=facts), [cost], (), through=TODAY)
    assert evidence[0].monthly_amount == "3000.0000"
    assert evidence[0].mean_absolute_error is None
    assert all(month.predicted is None for month in evidence[0].history)
    with pytest.raises(ScenarioError, match="scenario_history_insufficient"):
        living_cost_events(source(facts=facts[:-1]), [cost], (), through=TODAY)


def test_todays_posted_expenses_consume_manual_envelope_and_exclusions_are_explicit() -> None:
    fact = ExpenseFact(UUID(int=101), A, C, TODAY, Decimal("9000.0001"), None)
    cost = LivingCost(id=UUID(int=30), account_id=A, category_id=C, monthly_amount="10000")
    events, evidence = living_cost_events(
        source(facts=(fact,)), [cost], (), through=date(2026, 9, 30)
    )
    assert sum((e.amount for e in events), Decimal(0)) == Decimal("999.9999")
    assert evidence[0].mean_absolute_error is None
    excluded = cost.model_copy(update={"excluded_operation_ids": [fact.id]})
    events, _ = living_cost_events(source(facts=(fact,)), [excluded], (), through=date(2026, 9, 30))
    assert sum((e.amount for e in events), Decimal(0)) == Decimal(10000)


def test_virtual_source_explanations_never_link_to_an_unstored_calendar_occurrence() -> None:
    s = source((replace(event(10, "100", TODAY), origin="virtual"),))
    d = Decision(id=UUID(int=20), action="exclude", occurrence_id=UUID(int=10), version=1)
    change = compare_workspace(s, workspace(s, [d])).variants[0].comparison.events[0]
    assert change.source_available is False


@pytest.mark.parametrize("objective", ["maximum_amount", "earliest_date"])
def test_solver_cannot_hide_target_outside_the_selected_horizon(objective: str) -> None:
    s = source()
    d = decision(20, "120000", "2027-01-01")
    request = SolveRequest.model_validate(
        dict(
            workspace=workspace(s, [d]),
            variant_id=V,
            decision_id=d.id,
            objective=objective,
            maximum_amount="200000" if objective == "maximum_amount" else None,
        )
    )
    with pytest.raises(ScenarioError, match="scenario_solver_target"):
        solve_workspace(s, request)


def fund() -> FundResponse:
    now = datetime(2026, 9, 1, tzinfo=UTC)
    return FundResponse(
        id=F,
        name="Goal",
        description=None,
        allocation_percentage="0",
        manual_allocation_percentage="0",
        allocation_mode=FundAllocationMode.DYNAMIC,
        target_amount="50000",
        total_balance="50000",
        remaining_amount="0",
        distribution_status="filled",
        progress_percentage="100",
        archived=False,
        version=1,
        created_at=now,
        updated_at=now,
    )


def test_fund_spending_refills_from_reserve_without_changing_free_cash() -> None:
    s = source()
    s = replace(
        s,
        projection=replace(
            s.projection,
            balances=((A, Decimal(100000)), (B, Decimal(50000))),
            funds=(fund(),),
            mode=FundAllocationMode.DYNAMIC,
            reserved=((A, Decimal(50000)), (B, Decimal(20000))),
            fund_positions=((F, A, Decimal(50000)),),
            reserve_by_account=((B, Decimal(20000)),),
            reserve_total=Decimal(20000),
        ),
    )
    d = decision(20, "10000", "2026-09-20", fund_id=str(F))
    r = compare_workspace(s, workspace(s, [d])).variants[0]
    assert Decimal(r.comparison.ending_free_delta) == 0
    assert Decimal(r.comparison.ending_total_delta) == -10000
    assert Decimal(r.comparison.funds[0].alternative) == 50000
    assert Decimal(r.comparison.reserve.alternative) == 10000
    assert r.feasible


def test_fund_shortfall_is_explicit_and_never_authorizes_free_money_fallback() -> None:
    s = source()
    s = replace(
        s,
        projection=replace(
            s.projection,
            funds=(fund(),),
            mode=FundAllocationMode.DYNAMIC,
            reserved=((A, Decimal(50000)),),
            fund_positions=((F, A, Decimal(50000)),),
        ),
    )
    d = decision(20, "60000", "2026-09-20", fund_id=str(F))
    r = compare_workspace(s, workspace(s, [d])).variants[0]
    assert not r.feasible
    assert r.funding_issues[0].shortfall == "10000.0000"
    assert Decimal(r.comparison.funds[0].alternative) == 0


def test_downstream_allocation_observes_fund_spending_and_overflow() -> None:
    expense = event(20, "10000", date(2026, 9, 20), fund_id=F)
    transfer = event(
        21,
        "15000",
        date(2026, 9, 21),
        OperationType.TRANSFER,
        destination_account_id=B,
        allocate_to_funds=True,
    )
    s = replace(
        source().projection,
        funds=(fund(),),
        mode=FundAllocationMode.DYNAMIC,
        reserved=((A, Decimal(50000)),),
        fund_positions=((F, A, Decimal(50000)),),
    )
    r = project_program(
        s,
        (expense, transfer),
        horizon=ForecastHorizon.MONTH,
        through_on=date(2026, 10, 13),
        scope=None,
    )
    assert r.projection.funds.ending_balances[F] == 50000
    assert r.reserve_end == 5000
    assert Decimal(r.projection.free.ending_balance) == 35000


def test_solver_maximum_is_exact_and_next_unit_breaks_constraint() -> None:
    s = source()
    d = decision(20, "60000", "2026-09-20")
    w = workspace(s, [d], stop_loss="40000.0001")
    r = solve_workspace(
        s,
        SolveRequest(
            workspace=w,
            variant_id=V,
            decision_id=d.id,
            objective="maximum_amount",
            maximum_amount="100000",
        ),
    )
    assert r.status == "found"
    assert r.amount == "59999.9999"
    assert r.result is not None and r.result.feasible
    assert r.evaluated <= 31
    bigger = d.model_copy(update={"amount": Decimal(r.amount) + Decimal("0.0001")})
    assert (
        not compare_workspace(s, workspace(s, [bigger], stop_loss="40000.0001"))
        .variants[0]
        .feasible
    )


def test_solver_date_finds_first_recovery_and_never_moves_past_horizon() -> None:
    s = source((event(10, "100000", date(2026, 10, 1), OperationType.INCOME),))
    d = decision(20, "120000", "2026-09-20")
    r = solve_workspace(
        s,
        SolveRequest(
            workspace=workspace(s, [d]), variant_id=V, decision_id=d.id, objective="earliest_date"
        ),
    )
    assert r.due_on == date(2026, 10, 1)
    s = source()
    r = solve_workspace(
        s,
        SolveRequest(
            workspace=workspace(s, [d]), variant_id=V, decision_id=d.id, objective="earliest_date"
        ),
    )
    assert r.status == "no_solution"


def test_solver_rejects_non_monotone_envelope_target() -> None:
    s = source()
    d = decision(20, "10", "2026-09-20", category_id=str(C))
    cost = LivingCost(id=UUID(int=30), account_id=A, category_id=C, monthly_amount="30000")
    with pytest.raises(ScenarioError, match="scenario_solver_target"):
        solve_workspace(
            s,
            SolveRequest(
                workspace=workspace(s, [d], living_costs=[cost]),
                variant_id=V,
                decision_id=d.id,
                objective="maximum_amount",
                maximum_amount="100000",
            ),
        )


def test_stress_delays_income_and_changes_estimates_without_mutating_baseline() -> None:
    s = source((event(10, "1000", date(2026, 9, 20), OperationType.INCOME),))
    cost = LivingCost(id=UUID(int=30), account_id=A, category_id=C, monthly_amount="30000")
    w = workspace(s, [], living_costs=[cost])
    w.variants[0].expense_increase_percent = Decimal(10)
    w.variants[0].income_delay_days = 30
    r = compare_workspace(s, w)
    assert r.baseline_estimates[0].monthly_amount == "30000.0000"
    assert r.variants[0].estimates[0].monthly_amount == "33000.0000"
    assert "change_outside_horizon" in r.variants[0].comparison.assumptions


@pytest.mark.parametrize("value", [1.1, "NaN", "-1", "1.00001"])
def test_money_contract_rejects_invalid_values(value: object) -> None:
    with pytest.raises(ValidationError):
        Decision.model_validate(
            dict(id=str(V), action="expense", account_id=str(A), amount=value, due_on=str(TODAY))
        )
