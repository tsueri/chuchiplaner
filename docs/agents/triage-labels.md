# Triage label vocabulary

The `triage` skill moves incoming issues through a state machine using these
labels. Each canonical role maps to a label whose string equals its name.

| Role              | Label              | Meaning |
|-------------------|--------------------|---------|
| `needs-triage`    | `needs-triage`     | Maintainer needs to evaluate |
| `needs-info`      | `needs-info`       | Waiting on reporter |
| `ready-for-agent` | `ready-for-agent`  | Fully specified, AFK-ready (an agent can pick it up with no human context) |
| `ready-for-human` | `ready-for-human`  | Needs human implementation |
| `wontfix`         | `wontfix`          | Will not be actioned |

## Current state on the repo

`ready-for-agent` and `wontfix` already exist on the repo. `needs-triage`,
`needs-info`, and `ready-for-human` will be created by the triage skill on first
use (via `gh label create`).

## When a label is missing

If `gh issue edit --add-label` fails with "label not found", create it first:

```bash
gh label create <name> --color "<hex>" --description "<short description>"
```
