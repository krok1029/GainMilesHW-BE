# Domain Docs

This project has one context: the product catalog.

## Read before exploring

- Read the root `CONTEXT.md` glossary and use its Product, Code, Category, Size, Color, Inventory, and Variant vocabulary.
- Read relevant ADRs under `docs/adr/` when that directory exists. If it does not exist, proceed without creating placeholder ADRs.
- The existing schema, architecture, and API design documents are under `doc/`; read the documents relevant to the task.
- The parent specification is tracked in `.scratch/product-catalog-api/spec.md`.

## Consumer rules

- Keep `CONTEXT.md` a domain glossary rather than an implementation spec.
- Create ADRs only when a meaningful architectural decision warrants one.
- Explicitly surface conflicts with an existing ADR or accepted requirement rather than silently replacing the decision.
- Do not create additional domain contexts unless the project actually develops independently modeled domains.
