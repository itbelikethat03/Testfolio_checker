# 2026-09-10 — An Obsidian vault for project context

**Decision.** Keep durable project context in `C:\Python Datoteke\context`, structured as an
Obsidian vault, and install the Obsidian app to browse it.

## Why a vault rather than scattered notes

`C:\Python Datoteke` is a collection of standalone scripts with no git repo, so there is no
commit history to carry intent. The two leverage studies each encode dozens of judgment calls
— which bond ladder, which bootstrap block length, which window — that are load-bearing for
their conclusions and invisible in the code. `REPORT.md` explains the findings; nothing
explained the *choices* until this vault.

Obsidian was chosen over a single long notes file because the useful structure here is a
graph, not a sequence: [[chart-palette]] is referenced by three projects, [[data-schemas]] by
two, and [[tech-debt]] cuts across everything. Backlinks make "what depends on this?"
answerable.

## Why plain markdown either way

The vault is plain markdown with `[[wikilinks]]`, and the `.obsidian` folder holds only
config. **Nothing here requires the app to be readable** — `grep`, an editor, or any agent
reads these files directly. Installing Obsidian buys the graph view, backlinks panel and
search UI for a human reader; it is not a dependency.

Obsidian 1.13.7 installed via `winget install Obsidian.Obsidian` to
`C:\Users\moravec\AppData\Local\Programs\Obsidian`.

## Structure

Three folders, chosen because they have genuinely different lifecycles:

- `projects/` — **mutable.** Reflects current state; edited as work progresses.
- `decisions/` — **append-only.** A record of what was decided when, and why. Reversing a
  decision means writing a new note with `Supersedes: [[old]]`, never editing the old one.
  Dated filenames, so chronology is visible in the file list.
- `reference/` — **slowly mutable.** Durable facts worth not re-deriving: schemas, palettes,
  metric conventions.

`MOC.md` is the index and the intended entry point. It deliberately lists a few notes that do
not exist yet — an unresolved `[[wikilink]]` is a to-do that costs nothing to leave.

## What does not go here

- Anything the code already records. Structure, function signatures and file layout are
  better read from source than duplicated into prose that will drift.
- Anything session-specific. If it stops being true next week, it does not belong.
- Secrets, of any kind. See [[tech-debt]].

## Links

- [[MOC]] · [[2026-09-10-combining-two-studies]] · [[portfolio-dashboard]]
