# Domain docs

This repo uses a single-domain layout. Skills that read the project's language
and past architectural decisions look in two places:

- `CONTEXT.md` at the repo root — the domain glossary and architecture map.
- `docs/adr/` at the repo root — numbered architectural decision records.

## Consumer rules

- Skills MUST read `CONTEXT.md` before making domain-level claims (e.g. naming
  a new entity, choosing between alternatives that already have a canonical
  term).
- Skills MUST check `docs/adr/` for prior decisions in the area they are
  touching. If a relevant ADR exists, the skill should either respect it or
  flag a contradiction.
- When a new term is resolved during a session, the skill should update
  `CONTEXT.md` inline rather than batching changes.
- ADRs are written only for decisions that are hard to reverse, surprising
  without context, and the result of a real trade-off.

## Layout

```
/
├── CONTEXT.md
└── docs/
    ├── adr/
    └── agents/        ← this folder
```
