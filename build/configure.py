#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Перешить модели агентов студии по build/models.json.

ЕДИНСТВЕННОЕ место роутинга — models.json. Поменяли модель/провайдера —
запустите:  python -X utf8 build/configure.py

Проходит по .opencode/agents/<роль>.md, в frontmatter заменяет строку
`model: …` на модель роли из models.json. Новой роли нужен файл агента.
"""
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
AGENTS = os.path.normpath(os.path.join(HERE, "..", ".opencode", "agents"))


def main():
    cfg = json.load(open(os.path.join(HERE, "models.json"), encoding="utf-8"))
    provider = cfg["provider"]
    missing = []
    for role, model in cfg["roles"].items():
        path = os.path.join(AGENTS, role + ".md")
        if not os.path.isfile(path):
            missing.append(role)
            continue
        with open(path, encoding="utf-8") as f:
            text = f.read()
        new = re.sub(r"^model: .*$", f"model: {provider}/{model}",
                     text, count=1, flags=re.M)
        if new != text:
            with open(path, "w", encoding="utf-8", newline="") as f:
                f.write(new)
        print(f"{role:12} -> {provider}/{model}")
    if missing:
        print("нет файлов агентов:", ", ".join(missing), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
