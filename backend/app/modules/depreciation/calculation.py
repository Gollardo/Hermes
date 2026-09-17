"""Pure month-based replacement saving calculations; no ledger side effects."""

from decimal import ROUND_DOWN, ROUND_HALF_UP, Decimal, localcontext

QUANTUM = Decimal("0.0001")
MAXIMUM = Decimal("9999999999999999.9999")


def month_index(value: str) -> int:
    year, month = map(int, value.split("-"))
    if not 1 <= year <= 9999 or not 1 <= month <= 12:
        raise ValueError("Invalid month")
    return year * 12 + month - 1


def month_label(index: int) -> str:
    year, month = divmod(index, 12)
    return f"{year:04d}-{month + 1:02d}"


def inflation_target(cost: Decimal, inflation: Decimal, months: int) -> Decimal:
    if cost <= 0 or not 0 <= inflation <= 100 or not 1 <= months <= 600:
        raise ValueError("Invalid replacement saving parameters")
    with localcontext() as context:
        context.prec = 60
        result = (cost * (1 + inflation / 100) ** (Decimal(months) / 12)).quantize(
            QUANTUM, rounding=ROUND_HALF_UP
        )
    if result > MAXIMUM:
        raise ValueError("Inflation-adjusted target exceeds the money limit")
    return result


def schedule(
    target: Decimal,
    purchase_month: str,
    months: int,
    current_month: str,
    movements: dict[str, Decimal],
) -> list[dict[str, str]]:
    start = month_index(purchase_month) + 1
    current = month_index(current_month)
    # Contributions in/before the purchase month are opening savings, not new expenses.
    saved = sum(
        (amount for month, amount in movements.items() if month_index(month) < start), Decimal(0)
    )
    rows = []
    for offset in range(months):
        index = start + offset
        month = month_label(index)
        remaining = max(target - saved, Decimal(0))
        planned = (remaining / (months - offset)).quantize(QUANTUM, rounding=ROUND_DOWN)
        actual = movements.get(month, Decimal(0))
        rows.append(
            {
                "month": month,
                "planned": format(planned, "f"),
                "actual": format(actual, "f"),
                "remaining": format(max(planned - actual, Decimal(0)), "f"),
                "state": "closed"
                if index < current
                else "current"
                if index == current
                else "future",
            }
        )
        # Past/current facts stay authoritative. Future rows assume the displayed plan.
        saved += actual if index <= current else planned
    return rows
