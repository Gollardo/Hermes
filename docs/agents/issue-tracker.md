# Issue tracker: GitHub

Issues and specs for this repository live in GitHub Issues. Use the `gh` CLI
from this clone.

## Conventions

- Create: `gh issue create --title "..." --body "..."`
- Read: `gh issue view <number> --json number,title,body,labels,comments`
- List: `gh issue list --state open`
- Comment: `gh issue comment <number> --body "..."`
- Apply or remove labels: `gh issue edit <number> --add-label "..."` /
  `--remove-label "..."`
- Close: `gh issue close <number> --comment "..."`

The repository is inferred from its Git remote. “Publish to the issue tracker”
means create a GitHub issue; “fetch the relevant ticket” means read that issue.

## Pull requests as a triage surface

**PRs as a request surface: no.**
