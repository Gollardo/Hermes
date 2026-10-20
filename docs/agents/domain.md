# Domain docs

## Before exploring

Start with `docs/index.md`. Read the relevant documents under
`docs/architecture/` and `docs/domains/`, then the applicable ADRs under
`docs/decisions/`.

If a root `GLOSSARY.md` exists, use its vocabulary. If it does not exist,
proceed silently; create it only when a real terminology decision is resolved.

## Layout

Hermes is a single-context repository:

```text
/
├── GLOSSARY.md                 # optional, created lazily
├── docs/
│   ├── decisions/              # ADRs
│   ├── architecture/
│   └── domains/
└── src/
```

## Consumer rules

Use defined domain terms consistently. Surface any conflict with an existing
ADR instead of silently overriding it. Planned roadmap items do not approve
detailed designs or override confirmed domain invariants.
