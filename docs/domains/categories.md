# Categories

## Owner-confirmed rules

Categories may contain subcategories. Release `0.1.0-alpha.2` supports exactly
two levels in both API and UI: `category → subcategory`. Arbitrary depth is not
claimed and can be reconsidered only with a UI and migration strategy.

Every new `income` and `expense` operation requires an active category of the
matching type.

On a fresh first run, the owner may select any subset of the documented expense
templates. Setup creates each selected root with its five children and creates
the five base income roots. Selecting no expense template is valid. Template
creation is a one-time convenience, not a permanent special category type; all
created nodes immediately follow the ordinary tree and archive invariants.

## Boundary and invariants

Categories owns tree structure and category lifecycle. Operations may reference
a category through a public identifier and validation contract. The tree must
not contain cycles, and a node cannot be its own ancestor; these are necessary
technical invariants implied by any tree model.

While an operation references a category, its `income`/`expense` type is part of
historical classification and cannot change. The application-layer update use
case checks the operations-owned public history contract while holding the same
category advisory lock used by new postings. Name, description, parent and
archive state remain editable under their normal rules.

## Assumptions

- A pure transfer is normally uncategorized.
- Deleting a category with historical operations should not silently erase
  classification history.

These behaviours have not been confirmed by the owner.

## Release 0.1.0-alpha.2 decisions

- Income and expense categories are separate typed trees.
- A parent must be active and have the same type as its child.
- A parent must be a root; creating a third level is rejected.
- Changing a category cannot introduce a cycle or make existing children type-incompatible.
- Changing the type of a category currently referenced by a financial operation is rejected.
- A category with active children cannot be archived; archive children first.
- A child cannot be restored while its parent remains archived.
- Archived categories remain readable. The public operations validation contract rejects them
  for new postings but can explicitly allow them while resolving historical operations.
- Category deletion, merge and reassignment are outside this release; lifecycle is archival.
- Tree mutations and new-operation reference validation share a PostgreSQL
  transaction-level advisory lock, preventing concurrent cycle/archive races.

## Open questions

- Merge and reassignment behavior.
- Category ordering, icons and colors; these are presentation concerns and not
  part of the current foundation.

## Localized first-run templates

Fresh setup accepts `category_template_language` (`ru` or `en`, default `ru`).
Categories owns both template catalogs; the application setup use case invokes
its public creation contract in the same transaction as owner/settings/session
creation. Unsupported languages fail validation before writes. Template language
is not persisted as a category property. Created, edited and restored names are
ordinary user data and are never renamed by interface-language changes. No
financial values, category identities or tree rules depend on language.
