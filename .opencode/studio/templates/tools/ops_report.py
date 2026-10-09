#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ops_report — сводка телеметрии операций студии.

Читает `<проект>.wt/usage/studio-ops.jsonl` (пишут run_check.py и
slot_pool.py) и показывает эффект изменений:

- длительность подготовки слотов (slot_prep) и переиспользование
  (slot_acquire reused/created);
- проверки: сколько, какие режимы, длительность, эскалации affected→full,
  повторные запуски с причинами;
- используемый каталог сборки (target_dir);
- нехватки диска (disk_stop) и их причины;
- назначение/освобождение слотов.

СУММАРНОЕ время операций ≠ ФАКТИЧЕСКОЕ время: при параллельном исполнении
операции идут одновременно — сводка показывает обе: сумму dur_ms по событиям
и размах (последнее − первое) по часам. Никаких секретов: в файле только
перечисленные поля.

Запуск: python -X utf8 tools/ops_report.py [--root <путь>] [--since <ISO-дата>]
"""
import argparse
import datetime
import json
import os
import sys

sys.dont_write_bytecode = True  # инструменты не пачкают проект/слот кэшем байткода
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import studio_ops as ops  # noqa: E402


def main(argv=None):
    ops.utf8_stdio()
    ap = argparse.ArgumentParser(add_help=False, description="сводка телеметрии операций")
    ap.add_argument("--root", help="корень проекта (по умолчанию — ищется вверх)")
    ap.add_argument("--since", help="события с этой ISO-даты (например, со «Снята …»)")
    try:
        args = ap.parse_args(argv)
    except SystemExit as e:
        return e.code if isinstance(e.code, int) and e.code else ops.EXIT_BAD
    try:
        root = ops.norm(args.root) if args.root else ops.find_root()
        if root is None or not os.path.isdir(root):
            raise ops.OpError(ops.EXIT_BAD, "корень проекта не найден: назовите --root")
        root = ops.main_root(root)
        events = ops.read_events(root)
    except ops.OpError as e:
        print(f"ошибка: {e.msg}", file=sys.stderr)
        return e.code
    if not events:
        print(f"телеметрии нет: {ops.ops_log(root)}")
        return ops.EXIT_OK
    if args.since:
        events = [e for e in events if e.get("t", "") >= args.since]
    if not events:
        print("после фильтра --since событий нет")
        return ops.EXIT_OK

    def ts(e):
        try:
            return datetime.datetime.fromisoformat(e["t"])
        except (KeyError, ValueError):
            return None

    times = [ts(e) for e in events]
    times = [t for t in times if t]
    wall = (times[-1] - times[0]).total_seconds() if len(times) > 1 else 0.0
    dur_sum = sum(e.get("dur_ms") or e.get("prep_ms") or 0 for e in events) / 1000.0

    kinds = {}
    for e in events:
        kinds[e["kind"]] = kinds.get(e["kind"], 0) + 1
    print(f"событий: {len(events)} · с {events[0].get('t')} по {events[-1].get('t')}")
    print(f"суммарное время операций: {dur_sum:.0f} с · фактическое (размах): "
          f"{wall:.0f} с — при параллельной работе операции идут одновременно")
    print("по видам: " + ", ".join(f"{k} × {v}" for k, v in sorted(kinds.items())))

    acq = [e for e in events if e["kind"] == "slot_acquire"]
    if acq:
        reused = sum(1 for e in acq if e.get("reused"))
        created = sum(1 for e in acq if e.get("created"))
        print(f"слоты: назначений {len(acq)} · переиспользовано {reused} · создано {created}"
              + (f" (предел превышен бы — создай больше копий)" if created > 2 else ""))
    preps = [e for e in events if e["kind"] == "slot_prep"]
    if preps:
        ms = [e.get("prep_ms") or 0 for e in preps]
        print(f"подготовка слота: {len(preps)} раз · {min(ms)}–{max(ms)} мс (worktree add)")
    runs = [e for e in events if e["kind"] == "check_run"]
    if runs:
        by_mode = {}
        for e in runs:
            by_mode.setdefault(e.get("mode"), []).append(e)
        for mode, evs in sorted(by_mode.items(), key=lambda kv: str(kv[0])):
            ms = [e.get("dur_ms") or 0 for e in evs]
            esc = [e for e in evs if e.get("escalated")]
            reruns = [e for e in evs if e.get("rerun_reason")]
            line = (f"проверки {mode}: {len(evs)} прогонов · {sum(ms)} мс · "
                    f"сборка {evs[0].get('target_dir')}")
            if esc:
                line += f" · эскалаций на full: {len(esc)}"
            if reruns:
                line += f" · повторов: {len(reruns)} ({'; '.join(e.get('rerun_reason') for e in reruns)})"
            print(line)
    stops = [e for e in events if e["kind"] == "disk_stop"]
    if stops:
        for e in stops:
            print(f"остановка по диску: свободно {e.get('free_gb')} ГБ < резерв "
                  f"{e.get('reserve_gb')} ГБ ({e.get('what') or e.get('mode')})")
    bc = [e for e in events if e["kind"] == "batch_check"]
    if bc:
        bad = sum(1 for e in bc if not e.get("ok"))
        print(f"batch_check: {len(bc)} прогонов · красных {bad}")
    return ops.EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
