# Module boundaries

## Ownership map

| Module | Owns | Collaborates through |
| --- | --- | --- |
| `auth` | owner credential, password hash, sessions, login throttle | authentication dependency and settings setup contract |
| `settings` | persisted preferences and base-currency lock | explicit settings queries/commands |
| `accounts` | account identity and account rules | account references and balance read contract |
| `categories` | category tree | category reference validation |
| `operations` | posted operations and physical money movements | atomic posting commands and ledger reads |
| `funds` | fund definitions, percentages, virtual movements | fund posting contracts and application coordination with physical ledger reads |
| `scheduling` | recurrence rules and expected occurrences | application-coordinated confirmation through operations and optional funds contracts |
| `forecasting` | future-balance calculations | read contracts from ledger, funds and plans |
| `scenarios` | hypothetical decision drafts, comparisons and optional saved scenarios | forecasting projection and owning modules' public reads |
| `assistant` | optional local intent extraction and grounded explanation | scenarios public contract only; no financial writes |
| `liabilities` | credits and installment plans | planned/payment integration contracts |
| `debts` | `i_owe` and `owed_to_me` obligations | repayment posting contract |
| `reports` | reporting read models | public read contracts only |
| `imports` | parse, map, preview, duplicate candidates | owning modules' validation/write commands |
| `backup` | versioned plaintext/protected export, crypto envelope and restore orchestration | module-owned export/import contracts |

`scenarios`, `assistant`, `liabilities`, `debts` and `imports` are planned
ownership reservations. Only the last three currently have placeholder
packages; none exposes runtime routes, tables or use cases in `0.5.0`. Their
arrows below describe intended dependency direction, not current Python
imports. All other rows are implemented boundaries.

`app.core` owns technical configuration and database lifecycle, not business
rules. `app.api` composes HTTP routes and cross-cutting concerns. Cross-module
commands that share a transaction belong to `app.application`; it owns no tables
and calls only public module contracts.

## Dependency direction

Arrows below mean “uses a public contract of”, not direct access to private
tables.

```mermaid
flowchart TB
    API["API composition"] --> Auth
    API --> Settings
    API --> Application["Application use cases"]
    Application --> Auth
    Application --> Settings
    Application --> Accounts
    Application --> Operations
    Application --> Funds
    Application --> Scheduling
    Auth --> Settings
    API --> Operations
    API --> Funds
    API --> Scheduling
    API --> Reports
    Operations --> Accounts
    Operations --> Categories
    Operations --> Funds
    Funds --> Accounts
    Scheduling --> Operations
    Scheduling --> Accounts
    Scheduling --> Categories
    Scheduling --> Settings
    Liabilities --> Scheduling
    Liabilities --> Operations
    Debts --> Scheduling
    Debts --> Operations
    Forecasting --> Accounts
    Forecasting --> Operations
    Forecasting --> Funds
    Forecasting --> Scheduling
    Forecasting --> Liabilities
    Forecasting --> Debts
    Scenarios --> Forecasting
    Assistant --> Scenarios
    Reports --> Operations
    Reports --> Categories
    Imports --> Operations
    Imports --> Accounts
    Backup --> Modules["All module export/restore contracts"]
```

Authentication guards every API except setup status, fresh setup, first-run
setup restore, login and health. It does not own financial data. Backup may
orchestrate all modules, but must not duplicate their validation rules.

For schema-level round trips, every owning module exposes a narrow `backup.py`
persistence surface. It is separate from ordinary runtime contracts: only
Backup uses it, and the versioned validator enforces the same documented
invariants before any rows are replaced.

Scheduling validates account/category snapshots and the application timezone
through those modules' public contracts. An application use case confirms an
occurrence through Scheduling's locked command, posts through the Operations
contract and, for an explicitly marked transfer, invokes the Funds allocation
contract in the same transaction. Scheduling never writes either ledger
directly.

The application setup use case calls Auth, Categories and Backup only through
their public contracts. Fresh setup commits credential, preferences, optional
category templates and the first session atomically. First-run restore validates
the document and replaces the new settings/data in that same transaction, so a
failed restore cannot leave a partially initialized instance. Any module that
can create the first monetary/account record must call settings' public
currency-lock command in that write transaction; the current Accounts
application use case already does so.
These Python-level commands and validators are exported by
`app.modules.settings.contracts`; HTTP authentication and CSRF dependencies are
composed by `app.api`, so the settings module does not depend on auth internals.

## Boundary rules

- A module owns writes to its state and defines any public commands or reads.
- Cross-module changes that must stay consistent share one database transaction.
- Cross-module orchestration normally belongs to `app.application`. A module
  that owns a source record's lifecycle may call another module's explicit
  public posting contract when the dependency remains one-way; operation-owned
  fund movements use this narrower rule.
- Read-oriented modules may query purpose-built public read models; this does not
  authorize writes around the owner module.
- Avoid generic repository or service abstractions until repeated behaviour
  proves a real need.
- Moving code between modules requires updating this map and related domain docs.

## Open questions

- Whether liabilities and debts remain separate modules once detailed lifecycle
  use cases are designed.
- Which stable public read contracts reporting and forecasting need.
- Whether scenario calculation becomes a separate module or remains an
  application/read-side use case around a pure Forecasting projection.
- How the optional local assistant is packaged without making model runtime,
  vector storage or external infrastructure mandatory for core operation.

## Multilingual foundation ownership

Frontend `i18n` owns catalogs and browser-local presentation state; Core owns the
shared error adapter. API composition sanitizes framework validation metadata.
Categories owns RU/EN first-run templates, invoked by the existing atomic setup
application use case through its public contract. Neither Settings persistence
nor financial-domain ownership changes. See the
[internationalization contract](../ui-ux/internationalization.md).
