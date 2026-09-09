# Contributing

Hermes is in its stable `1.x` release line. Keep changes small, explicit and
supported by tests or documentation appropriate to their risk.

## Environment

Install Python 3.13, Node.js 22, npm, Docker and Docker Compose. Then:

```bash
cp .env.example .env
make setup
make test
make lint
make typecheck
```

See [local development](docs/operations/local-development.md) for all commands
and troubleshooting notes.

## Branches and pull requests

Create a focused branch from `main`. A pull request should explain the problem,
the chosen approach, verification performed, migration impact and any deferred
work. Do not combine unrelated refactors with a behavioural change.

Before implementation, compare the change with the
[current project status](docs/project-status.md) and the intended milestone in
the [roadmap](docs/roadmap.md). The roadmap defines direction and release scope;
it does not replace design work or resolve open decisions.

Use Conventional Commits, for example `feat(accounts): add account creation`,
`fix(funds): reject over-allocation`, or `docs: clarify restore procedure`.

## Quality requirements

- Add unit tests for domain invariants and integration tests for boundaries such
  as HTTP and PostgreSQL transactions.
- Run `make test`, `make lint` and `make typecheck` before review.
- Never use binary floating point for money. Use Python `Decimal`, PostgreSQL
  `NUMERIC` and decimal strings at JSON boundaries when precision could be lost.
- Update documentation in the same change when architecture, ownership,
  invariants, flows or deployment changes.
- Update `docs/project-status.md` when the factual implementation state,
  verification results, known risks or next action changes. Update the roadmap
  when milestone scope, order or completion changes, and do not mark an item
  complete until its user scenario and required checks are complete.

## Database migrations

Generate revisions with `make migration name="describe change"`, inspect the
generated SQL carefully and test both a clean upgrade and an upgrade from the
previous release. After a migration has appeared in a public release, add a new
revision instead of rewriting it.

## Architecture decisions

Routine implementation details belong in code and relevant documentation. For a
choice with durable, cross-cutting consequences, start from the template in
[the ADR registry](docs/decisions/README.md), submit it as `proposed`, and record
alternatives and unresolved questions without inventing prior consensus.

## Translations

Follow the [internationalization and translation guide](docs/ui-ux/internationalization.md).
Catalogs must have matching keys and parameters and preserve financial meaning.
Run `npm run i18n:check --prefix frontend` and verify both interface languages
before proposing a translation change.
