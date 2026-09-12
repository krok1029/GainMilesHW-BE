# Issue tracker: Local Markdown

Issues and specs for this project live as Markdown files in `.scratch/`.

## Conventions

- One feature per directory: `.scratch/<feature-slug>/`.
- The parent feature spec is `.scratch/<feature-slug>/spec.md`.
- Implementation tickets, when requested, are individual files under `.scratch/<feature-slug>/issues/<NN>-<slug>.md`, numbered from `01`.
- Record triage state with a `Status:` line near the top, using `docs/agents/triage-labels.md`.
- Append issue comments under a `## Comments` heading; do not create a comment log until needed.
- Publishing to the issue tracker means writing the issue/spec at the corresponding local path, not creating an external issue.
- Read tickets directly by their local path. Ticket numbers are scoped to a feature directory.
- Preserve existing issue content and status unless the current task authorizes changing them.

## Current feature

Product catalog API: `.scratch/product-catalog-api/spec.md`.
