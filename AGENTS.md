# Repository guidance

- Start with [docs/index.md](docs/index.md); architecture and domain ownership
  are described under `docs/architecture/` and `docs/domains/`.
- Before feature work, compare [project status](docs/project-status.md) with the
  intended scope and sequence in [the roadmap](docs/roadmap.md). Planned items
  are not approved detailed designs.
- Update `docs/project-status.md` after a meaningful task changes verified
  capabilities, checks, risks or the next action. Update `docs/roadmap.md` when
  milestone scope, order or completion changes; mark completion only after the
  relevant scenario and checks pass.
- Run locally with `make setup` then `make dev`; production-like Compose uses
  `make up`. Run checks with `make test`, `make lint`, and `make typecheck`.
- Preserve the modular monolith. Do not bypass a module's public boundary to
  import its private internals.
- Never store financial values in `float`; use `Decimal`/`NUMERIC` and precise
  JSON representations.
- In every user-facing interface, display all monetary amounts and percentages
  with spaces between thousand groups and exactly two fractional digits, using
  a comma in the canonical rendered form: `100 000,00` and `12,50%`. This is a
  presentation rule only; never reduce the precision of stored, calculated or
  transferred domain values to satisfy it.
- Round individual displayed values with exact decimal `ROUND_HALF_UP`. When a
  displayed percentage breakdown is exactly 100% on the server, distribute
  visible hundredths by deterministic largest remainder so the displayed parts
  also total `100,00%`; do not mutate the server values.
- Numeric amount and percentage inputs must accept both comma and dot as
  equivalent decimal separators (`1000,50` and `1000.50`) and normalize them to
  the exact decimal representation expected by the API without using `float`.
- Changes to one financial operation must be atomic in one database transaction.
- Cover domain invariants with tests.
- Do not rewrite migrations after they have shipped in a public release.
- Do not add external infrastructure without a recorded justification.
- Mark assumptions explicitly; never present them as owner-approved decisions.
- Never commit secrets.
- Write all project documentation exclusively in English. Translate owner
  decisions into English rather than adding Russian or bilingual passages;
  localized runtime UI copy outside documentation may remain in its target
  language.

## UI/UX rules

- Before creating or changing any UI, read the root [UI/UX contract](DESIGN.md),
  then study the relevant documents under `docs/ui-ux/` and the relevant domain
  documents.
- Use owner-approved UX principles. Until approval, use the principles in
  `docs/ui-ux/` to guide prototypes while preserving their status as product
  hypotheses and distinguishing them from confirmed behavior and future roadmap
  scenarios.
- Reuse established interface patterns; do not introduce a new pattern without
  a demonstrated need.
- Do not treat the preliminary visual direction as an approved design system or
  choose a final design without owner approval.
- Document changes to shared interface patterns and update affected screen
  directions in the same change.

```text
Update documentation in the same change when modifying architecture,
domain invariants, module ownership, data flows or deployment.
```

## Agent skills

### Issue tracker

Issues and specs live in this repository's GitHub Issues and are managed with
`gh`. See `docs/agents/issue-tracker.md`.

### Triage labels

Canonical triage roles use the default GitHub label vocabulary. See
`docs/agents/triage-labels.md`.

### Domain docs

This is a single-context repository. See `docs/agents/domain.md`.
