# Issue tracker

Issues for this repo live in GitHub Issues on
[github.com:tsueri/chuchiplaner](https://github.com/tsueri/chuchiplaner/issues).

## How to interact

The `gh` CLI is the only supported interface. Authentication is already configured
under the `tsueri` GitHub account.

- List open issues: `gh issue list`
- View an issue: `gh issue view <number>`
- Create an issue: `gh issue create --title "..." --body "..." --label "..."`
- Apply a label: `gh issue edit <number> --add-label "<label>"`
- Comment: `gh issue comment <number> --body "..."`
- Close: `gh issue close <number>`

The `to-prd`, `to-issues`, `triage`, and `qa` skills all read from and write to
this tracker through the `gh` CLI.
