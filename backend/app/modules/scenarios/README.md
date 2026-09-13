# Scenarios

Owns structured decision workspaces, independent alternatives, ordinary-spending
assumptions, constraints, bounded exact searches and explicitly saved input
metadata. `workspace_snapshot.py` consumes public financial reads inside Core's
read-only repeatable-read transaction; `workspace_engine.py` composes inputs and
calls `forecasting.contracts.project_program`. `living_costs.py` owns the disclosed
monthly envelope/estimation policy. No module path posts financial data.

`persistence.py` owns versioned CRUD for `saved_scenarios`; `backup.py` exposes
only its persistence model and structural validator to Backup. The old
`snapshot.py`/`service.py` comparison contract remains compatible. API composition
supplies authentication and CSRF.

See [Scenarios](../../../../docs/domains/scenarios.md),
[ADR 0006](../../../../docs/decisions/0006-deterministic-oracle.md) and
[ADR 0007](../../../../docs/decisions/0007-oracle-decision-workspaces.md).
