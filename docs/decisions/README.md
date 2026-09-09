# Architecture Decision Records

ADR records a durable decision with meaningful alternatives and consequences.
Create one when a choice changes architecture, data semantics, deployment or a
cross-module contract. Do not manufacture past meetings or mark a proposal as
accepted without an explicit project-owner decision.

## Release implementation decisions

- [ADR 0001: Financial posting model for 0.1.0-alpha.3](0001-financial-posting-model.md)
  records the posting model and the owner-confirmed non-negative balance policy
  for the current release; overdraft remains a separate future design.
- [ADR 0002: Virtual fund ledger and allocation policy](0002-virtual-fund-ledger.md)
  records the owner-confirmed virtual posting, coverage, rounding and archive
  model for the current release.
- [ADR 0003: Recurring rules and expected occurrences](0003-recurring-rules-and-occurrences.md)
  records the owner-confirmed recurrence limits, materialization, rule-edit and
  confirmation policies for the current release.
- [ADR 0004: Encrypted Hermes backup envelope](0004-encrypted-backup-envelope.md)
  records the owner-confirmed two-level key architecture, protected V1 format,
  legacy JSON compatibility and untrusted-file limits.

## Template for a future ADR

```markdown
# ADR-NNN: Short decision title

- Status: proposed | accepted | superseded | rejected
- Date: YYYY-MM-DD
- Decision owners: names or roles that actually participated

## Context

What forces and constraints require a decision? Separate confirmed facts from
assumptions.

## Decision

What is chosen and what is explicitly not chosen?

## Alternatives considered

List credible alternatives and why they were not selected.

## Consequences

Positive, negative, operational and migration consequences.

## Open questions

Anything intentionally deferred.
```

## Remaining architecture questions

The old discovery candidates duplicated implemented contracts and used numbering
that conflicted with the ADR files above. They are replaced by the focused
register below. This cleanup does not retroactively approve a new ADR.

| Area | Current source of truth | Still unresolved |
| --- | --- | --- |
| Modular monolith | [Module boundaries](../architecture/module-boundaries.md) | Automated private-boundary enforcement, stable cross-module read contracts and criteria for revisiting deployment boundaries |
| PostgreSQL | [Deployment](../architecture/deployment.md) and [release baseline](../operations/release.md) | Broader version/extension support policy |
| Authentication | [Authentication domain](../domains/authentication.md) | Password recovery and long-term session/idle/throttle policy |
| Frontend delivery | [Deployment architecture](../architecture/deployment.md) | Measured static-serving limits, cache/compression policy and further proxy/CSP review |
| Ledger and funds | ADR 0001/0002 above | Measured balance caching, reconciliation and future lifecycle extensions |
| Recurrence | ADR 0003 above | Richer expressions, background materialization and timezone migration |
| Backup | [Import/export](../domains/import-export.md) and ADR 0004 | Compatibility beyond payload schema 1, signing and streaming |

## Future ADR candidates

### Deterministic what-if scenario boundary

Product direction is confirmed; detailed design is not accepted. Structured
hypothetical changes should use the same coherent snapshot and exact projection
rules as the baseline, remain read-only and require an explicit plan-draft flow.
Alternatives include temporary-plan mutation or cloned financial tables; neither
is approved. Resolve the initial command set, snapshot/version strategy,
persistence and Forecasting/Scenarios ownership split before implementation.

### Optional local assistant boundary

The owner confirmed the safety and non-AI fallback direction. An optional local
adapter may produce a reviewable draft and grounded explanation; deterministic
services own calculations. Runtime/model packaging, resource budget, updates,
evaluation and any semantic retrieval still need design. Mandatory models,
external AI services and direct model-to-ledger tools are not approved defaults.
