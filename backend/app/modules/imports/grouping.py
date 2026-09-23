"""Pure preparation of explicitly reviewed source-row groups."""

from app.modules.imports.errors import ImportDecisionError, ImportGroupingError
from app.modules.imports.schemas import CommitRequest, Decision


def decision_groups(request: CommitRequest) -> list[list[Decision]]:
    by_row = {decision.row: decision for decision in request.decisions}
    if len(by_row) != len(request.decisions):
        raise ValueError("A source row can be selected only once")
    membership: dict[int, list[Decision]] = {}
    for rows in request.merge_plan_rows:
        if (
            len(rows) < 2
            or len(rows) > 200
            or len(set(rows)) != len(rows)
            or any(row not in by_row or row in membership for row in rows)
        ):
            raise ImportGroupingError("Choose distinct selected rows for each group")
        group = [by_row[row] for row in sorted(rows)]
        first = group[0]
        for item in group:
            if (
                item.action != "plan"
                or item.occurrence_id is None
                or item.occurrence_id != first.occurrence_id
                or item.occurrence_version != first.occurrence_version
                or item.statement_account_id != first.statement_account_id
                or item.existing_id is not None
                or item.allocate_to_funds
                or item.operation.type.value not in {"income", "expense"}
                or item.operation.model_dump(exclude={"amount", "description"})
                != first.operation.model_dump(exclude={"amount", "description"})
            ):
                raise ImportDecisionError(
                    item.row,
                    ImportGroupingError(
                        "A group requires one plan, date, account, category and fund; "
                        "existing facts and transfers cannot be merged"
                    ),
                )
            membership[item.row] = group
    result = []
    seen_rows: set[int] = set()
    seen_plans = set()
    for item in request.decisions:
        if item.row in seen_rows:
            continue
        group = membership.get(item.row, [item])
        if item.occurrence_id is not None and item.occurrence_id in seen_plans:
            raise ImportDecisionError(
                item.row,
                ImportGroupingError("Explicitly merge all selected rows for the same plan"),
            )
        seen_plans.add(item.occurrence_id)
        seen_rows.update(member.row for member in group)
        result.append(group)
    return result
