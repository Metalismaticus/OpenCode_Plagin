---
name: studio-parallel
description: Follow the original studio parallel process with stage-local context. Use for /studio/parallel.
---

# /studio/parallel

Bind this primary chat as `development` using studio_workflow.

N is the owner's manual calibration knob, not a verification gate: whenever
N>1 and scout confirms the items are independent, waves run. The guards are
real ones - the disk reserve (slot_pool exit 3 stops the batch), serialized
heavy checks (M, usually 1: machine power and FPS measurements matter more
than concurrency) and scout's independence verdict. After a run, `tidy`
(disk) and `retro` (time per item) tell the owner whether to raise or lower
N; no separate "parallel trial" permission is required.

Read the introductory chapter, then each chapter **when that stage is reached**.
Do not load all chapters at once; cross-references use this table.

- `.opencode/studio/protocols/commands/parallel/00.md` — Вводные правила
- `.opencode/studio/protocols/commands/parallel/01.md` — Без аргумента — показать
- `.opencode/studio/protocols/commands/parallel/02.md` — `N` — сколько пишут
- `.opencode/studio/protocols/commands/parallel/03.md` — `проверки M` — сколько тяжёлых проверок
- `.opencode/studio/protocols/commands/parallel/04.md` — `проверить` — пробный прогон
- `.opencode/studio/protocols/commands/parallel/05.md` — Сохранить

Original feature rules remain in force. API routing comes from the studio
coordinator and role skills; no old instruction may bypass runtime gates.
