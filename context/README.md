# Context vault

An Obsidian vault holding the *why* behind the portfolio suite: the decisions, constraints
and gotchas that the code and the reports do not record.

**Open it:** Obsidian → *Open folder as vault* → `portfolio_suite\context` (since 2026-09-23 it
lives inside the suite's git repo, so it travels with the code; see [[2026-09-23-vault-in-repo]]).
Everything here is plain markdown, so it stays readable and greppable with or
without the app.

## What goes in here

| Folder | Holds |
|---|---|
| `projects/` | One note per body of work. Status, where the outputs live, what is still open. |
| `decisions/` | Dated decision records. A choice made, the alternatives, and why. Never edited after the fact — supersede instead. |
| `reference/` | Durable facts worth not re-deriving: data schemas, palettes, metric conventions, file paths. |

Start at [[MOC]].

## Conventions

- **One idea per note.** If a note needs two headings that could each stand alone, split it.
- **Link liberally** with `[[wikilinks]]`. A link to a note that does not exist yet is a
  feature — it marks something worth writing.
- **Absolute dates, never relative.** "2026-09-10", not "last Tuesday" — these notes outlive
  the session that wrote them.
- **Decisions are append-only.** To reverse one, write a new note and link back with
  `Supersedes: [[old-note]]`.
- **No secrets.** API tokens belong in `.env`. See [[tech-debt]].

## Why this exists

Each study in the suite took hours of reasoning to set up, and the reasoning does not survive
in the `.py` files. `efficient_core`, `scv_leverage`, the reconstructions and the leverage cost
model all encode judgment calls that are load-bearing for the conclusions and invisible in the
code: which ladder, which window, which bootstrap block length, which financing benchmark,
which regime was left out of a fit. This vault is where those live.
