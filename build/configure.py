#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Сгенерировать агентов студии по build/roles.json (и build/models.json).

Модели агентов наследуются из выбранного в чате (решение владельца,
октябрь 2026): файлы ролей пишутся БЕЗ строки `model:`. Тонкую маршрутизацию
по ролям владелец вернёт позже сам: роль → модель в `roles` models.json —
тогда configure добавит этой роли строку `model:` (переопределение).

Запуск:  python -X utf8 build/configure.py

Сначала СВЕРЯЕТ и только потом пишет (ошибка не оставляет частично
обновлённую конфигурацию): переопределение из models.json называет только
известные роли; дублей `<роль>-any.md` больше нет — наследование официальное.
"""
import json
import os
import re
import sys
from pathlib import Path

HERE = os.path.dirname(os.path.abspath(__file__))
AGENTS = os.path.normpath(os.path.join(HERE, "..", ".opencode", "agents"))


def main():
    cfg = json.load(open(os.path.join(HERE, "models.json"), encoding="utf-8"))
    provider = cfg.get("provider", "")
    roles = json.load(open(os.path.join(HERE, "roles.json"), encoding="utf-8"))
    overrides = cfg.get("roles") or {}

    # ---- фаза 1: сверка ДО записи ---------------------------------------
    unknown = sorted(set(overrides) - set(roles))
    if unknown:
        print("models.json переопределяет неизвестные роли — НИЧЕГО не записано:",
              file=sys.stderr)
        for role in unknown:
            print(f"  - {role!r} нет в roles.json", file=sys.stderr)
        return 1
    stale = sorted(f for f in os.listdir(AGENTS) if f.endswith("-any.md"))
    if stale:
        print("Дубли -any больше не нужны (наследование официальное); удалить:",
              file=sys.stderr)
        for f in stale:
            print(f"  - .opencode/agents/{f}", file=sys.stderr)
        return 1

    # ---- фаза 2: запись (всё проверено) ---------------------------------
    for role, settings in roles.items():
        permissions = [
            '  - { action: question, resource: "*", effect: deny }',
            '  - { action: subagent, resource: "*", effect: deny }',
            '  - { action: skill, resource: "studio-*", effect: allow }',
        ]
        if not settings['write']:
            permissions.append('  - { action: edit, resource: "*", effect: deny }')
        if not settings['shell']:
            permissions.append('  - { action: shell, resource: "*", effect: deny }')
        model_line = ''
        if role in overrides:
            model = overrides[role]
            model_id = model if '/' in model else f'{provider}/{model}'
            model_line = f'model: {model_id}\n'
        text = ('---\n' + f"description: {settings['description']}\nmode: subagent\n"
                + model_line + f"steps: {settings['steps']}\npermissions:\n"
                + '\n'.join(permissions) + '\n---\n\n'
                + f"You are {role}, responsible only for this role. Load `{settings['skill']}` before work.\n"
                + 'Speak and report in Russian, in the owner\'s product vocabulary.\n'
                + 'No chat history: use the task id and source paths supplied by the coordinator.\n'
                + 'Load only skills/chapters required by the task, not the whole studio.\n'
                + 'Owner words and recorded rejection reasons take precedence over your interpretation.\n'
                + 'Choose technical implementation yourself; questions about taste, scope or acceptance\n'
                + 'go into the «Вопрос владельцу» block for the coordinator. Never ask the owner\n'
                + 'which class, node, shader or algorithm to use. Never accept your own result.\n'
                + 'Do not commit, push, weaken tests or change process baselines.\n')
        Path(AGENTS, role + '.md').write_text(text, encoding='utf-8')
        print(f"{role:14} -> {'модель ' + model_line.strip()[7:] if model_line else 'наследует из чата'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
