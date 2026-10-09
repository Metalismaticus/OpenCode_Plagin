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
from pathlib import Path

HERE = os.path.dirname(os.path.abspath(__file__))
AGENTS = os.path.normpath(os.path.join(HERE, "..", ".opencode", "agents"))


def generate_fallbacks(agents_dir, roles):
    """Запасные копии <роль>-any: тот же протокол, БЕЗ строки model —
    наследуют модель сессии (координатор зовёт их при недоступности
    основной модели). Генерируются заново при каждом запуске configure."""
    import re as _re
    made = 0
    for role in roles:
        src = os.path.join(agents_dir, role + ".md")
        if not os.path.isfile(src):
            continue
        text = open(src, encoding="utf-8").read()
        no_model = _re.sub(r"(?m)^model: .*\n", "", text, count=1)
        no_model = _re.sub(
            r"(?m)^(description: .*)$",
            r"\1 · FALLBACK-копия без своей модели — наследует модель сессии (зовёт координатор, когда основная недоступна)",
            no_model, count=1)
        dst = os.path.join(agents_dir, role + "-any.md")
        with open(dst, "w", encoding="utf-8", newline="") as f:
            f.write(no_model)
        made += 1
    return made


def main():
    cfg = json.load(open(os.path.join(HERE, "models.json"), encoding="utf-8"))
    provider = cfg["provider"]
    roles = json.load(open(os.path.join(HERE, "roles.json"), encoding="utf-8"))
    extra = sorted(set(cfg['roles']) - set(roles))
    gone = sorted(set(roles) - set(cfg['roles']))
    if extra or gone:
        raise SystemExit('roles.json and models.json must name exactly the same roles: '
                         f'models.json extra {extra or "—"}, roles.json extra {gone or "—"} '
                         '(no agent file was touched)')
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
        model = cfg['roles'][role]
        model_id = model if '/' in model else f'{provider}/{model}'
        text = ('---\n' + f"description: {settings['description']}\nmode: subagent\nmodel: {model_id}\nsteps: {settings['steps']}\npermissions:\n" + '\n'.join(permissions) + '\n---\n\n'
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
    missing = []
    for role, model in cfg["roles"].items():
        path = os.path.join(AGENTS, role + ".md")
        if not os.path.isfile(path):
            missing.append(role)
            continue
        with open(path, encoding="utf-8") as f:
            text = f.read()
        model_id = model if '/' in model else f'{provider}/{model}'
        new = re.sub(r"^model: .*$", f"model: {model_id}",
                     text, count=1, flags=re.M)
        if new != text:
            with open(path, "w", encoding="utf-8", newline="") as f:
                f.write(new)
        print(f"{role:12} -> {model_id}")
    if missing:
        print("нет файлов агентов:", ", ".join(missing), file=sys.stderr)
        return 1
    made = generate_fallbacks(AGENTS, cfg["roles"].keys())
    print(f"fallback-копий сгенерировано: {made}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
