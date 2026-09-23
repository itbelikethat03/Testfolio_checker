# 2026-09-23: The vault moves into the portfolio suite repo

Supersedes (location only): [[2026-09-10-obsidian-vault]]

**Decision.** The vault now lives at `C:\Python Datoteke\portfolio_suite\context\` instead of
`C:\Python Datoteke\context\`. Its structure and conventions are unchanged.

## Why

The suite is now a git repository pushed to GitHub, so the user can work from a second
machine (home PC). A vault outside the repo would not travel with the code. The two would
drift, and the home machine would hold code with no record of the reasoning behind it. Every note
in the vault is about this suite, so nothing is orphaned by the move.

## Consequences

- **Open it** in Obsidian with *Open folder as vault* → `portfolio_suite\context`. The old path
  no longer exists.
- It is versioned with the code. A decision note and the commit that implements it can land
  together.
- `context/.obsidian/workspace*.json` is per-machine UI state (open panes, cursor). It is
  git-ignored so the two machines do not fight over it.

## Links

[[MOC]] · [[2026-09-10-obsidian-vault]] · [[portfolio-dashboard]]
