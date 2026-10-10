---
name: studio-implement
description: Implement exactly one studio task card, with reconnaissance, applicable failing proof, scoped changes, checks and a structured result. Use as executor.
---

# Implement one card

Get the named task from `studio_workflow {action:"get", id:...}`; call `begin`.
Use the card's worktree for every edit, run and source read.
Read the original executor chapters in `.opencode/studio/protocols/agents/executor/`:
`00.md`, `01.md`, `05.md`, `06.md`, then `02.md` (implementation procedure).
These retain code health ratchets, player-input tests, snapshots, no weakening,
honest red/not-applicable proof and «Решено за вас».
Bootstrap exception: a card with batch "setup" uses SETUP-PLAN, AGENTS and
the source setup finale instead of a not-yet-created BATCH/queue. Create only
the agreed scaffold and first frame; do not start gameplay features.

Only `[вид]`, `[ui]` or another visible criterion needs `03.md` (look protocol).
Only `[вид]`/`[ощущение]` needs `04.md` (base, variant techniques, embedding).
For Godot use `studio-godot`; a shader also needs `studio-godot-shaders`.
A procedure finding a required new file means scope growth, not a stop:
keep working, write the file into your report `files` and «Решено за вас»,
and finish the whole plan in this session. If `submit` is rejected for
out-of-scope files, that is the coordinator's amendment to make (amend_scope)
- your work stays on disk; the resumed submission is quick. Never edit files
unrelated to the task: that remains out of scope.

Keep the conversation light: read only the card's files and the scout map
(coordinator puts it into `references`); before opening a file whole, grep it
for the symbols you need; do not paste whole files into your replies - name
paths and line ranges. A long conversation re-reads itself every step and
costs the owner real money.

Round 2–3: fix only the stored reviewer notes or owner's rework, do not restart.
The runtime supplies the exact round, so never reset the counter in the card.
During rounds run the item's own scoped checks; the full run is engine
`verify`'s job and happens once after approval — do not duplicate it.
Do not commit, change documents/passports, raise baselines or accept the item.
The source chapters' original report labels still serve BATCH and the owner.
Then call `submit` with the structured report from task-card.md:
files, summary, red_proof, checks, how_to_see, decisions and limitations;
visible items also need artifact paths and visual_review (or an honest
«вид не проверен»). The runtime checks the actual scope and captures the digest.
The report describes facts; passing a schema is not a substitute for inspection.
