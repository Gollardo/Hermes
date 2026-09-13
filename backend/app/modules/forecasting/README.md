# Forecasting

Owns read-side calculations that combine actual balances with expected future
movements. It does not post or mutate financial operations.

`service.calculate_forecast` is the deterministic pure calculation boundary.
`service.build_forecast` composes public contracts from Accounts, Operations and
Scheduling. The module owns no tables: projections are calculated on request and
returned as exact decimal strings.

`contracts.project_snapshot` is the public detached projection boundary used by
Oracle. It returns free money, physical totals and sequential fund allocations
from one source dataset, including dynamic overflow assigned to reserve. The
legacy HTTP builders retain their existing shared-lock source policy.

`contracts.project_program` extends that calculation for composed Oracle inputs:
explicit fund expenses, chronological reserve refill, per-account free/physical
results and funding failures. Scenarios supplies ordinary-spending estimates as
provenance-labelled events; Forecasting does not fit a historical model.
