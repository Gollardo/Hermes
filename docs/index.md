# Hermes engineering documentation

This documentation records durable architectural knowledge, domain language,
invariants and operating procedures. It intentionally avoids speculative API,
DTO and table catalogues.

## Planning and current state

- [Project status](project-status.md) records the factual, currently verified
  state, active milestone, known limitations, risks and next recommended action.
- [Roadmap](roadmap.md) records the intended sequence and scope of milestones. It
  is not a calendar commitment or a substitute for detailed domain design.
- [Changelog](../CHANGELOG.md) records the versioned change history.
- [Project overview](../README.md), [security policy](../SECURITY.md) and
  [contribution guide](../CONTRIBUTING.md) are the public release-facing entry
  points.

Start development work by comparing the requested change with both documents.
When a meaningful change alters implemented capabilities, verification results,
risks or the next action, update the project status in the same change. Update
the roadmap only when milestone scope, order or completion changes, and mark an
item complete only after its stated user scenario and checks are complete.

Architecture and domain documents remain authoritative for confirmed decisions
and invariants. A planned roadmap item does not override them or resolve an open
question by itself.

## Architecture

- [Overview](architecture/overview.md)
- [Module boundaries](architecture/module-boundaries.md)
- [Data flows](architecture/data-flow.md)
- [Deployment](architecture/deployment.md)

## Domains

- [Authentication](domains/authentication.md)
- [Application settings](domains/settings.md)
- [Accounts](domains/accounts.md)
- [Operations](domains/operations.md)
- [Categories](domains/categories.md)
- [Virtual funds](domains/funds.md)
- [Scheduling](domains/scheduling.md)
- [Forecasting](domains/forecasting.md)
- [Financial scenarios](domains/scenarios.md)
- [Reports](domains/reports.md)
- [Liabilities and debts](domains/liabilities-and-debts.md)
- [Import and export](domains/import-export.md)

## UI/UX foundation

- [Vision](ui-ux/vision.md)
- [Design principles](ui-ux/design-principles.md)
- [Preliminary visual direction](ui-ux/visual-direction.md)
- [Information architecture](ui-ux/information-architecture.md)
- Screen directions:
  [dashboard](ui-ux/screens/dashboard.md),
  [operation entry](ui-ux/screens/operation-entry.md),
  [funds](ui-ux/screens/funds.md),
  [calendar](ui-ux/screens/calendar.md),
  [forecast](ui-ux/screens/forecast.md),
  [Oracle · What if?](ui-ux/screens/scenarios.md),
  [reports](ui-ux/screens/reports.md),
  [transactions](ui-ux/screens/transactions.md)
- [Internationalization contract and translation guide](ui-ux/internationalization.md)
- [Open UI/UX questions](ui-ux/open-questions.md)

These documents record research-backed product hypotheses and interface rules.
They do not override confirmed domain invariants or constitute an approved
design system.

## Decisions and operations

- [ADR registry and candidates](decisions/README.md)
- [Local development](operations/local-development.md)
- [Deployment runbook](operations/deployment.md)
- [Backup and restore](operations/backup-and-restore.md)
- [Release lifecycle](operations/release.md)
- [Multilingual production-backup acceptance](operations/multilingual-acceptance-2026-09-09.md)

Each document distinguishes owner-confirmed rules, initialization decisions,
assumptions, open questions and future work where those categories apply.
