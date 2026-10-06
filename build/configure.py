#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Перешить модели агентов студии по build/models.json.

ЕДИНСТВЕННОЕ место роутинга — models.json. Поменяли модель/провайдера —
запустите:  python -X utf8 build/configure.py

Сначала СВЕРЯЕТ согласованность и только потом пишет (ошибка не оставляет
частично обновлённую конфигурацию):

  1. каждая роль из models.json имеет файл .opencode/agents/<роль>.md;
  2. в .opencode/agents/ нет лишних агентов ролей, которых нет в models.json
     (например, остатков трёхзвенной цепочки executor-prep/code/finish);
  3. у каждого агента роли есть строка `model:` в frontmatter.

Несогласованность — перечисляются ВСЕ несоответствия, код 1, ни один файл
не трогается. Согласовано — перешиваются строки model, заново генерируются
запасные копии `<роль>-any.md` (тот же протокол, без своей модели — наследуют
модель сессии), осиротевшие -any-копии удаляются.
"""
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
AGENTS = os.path.normpath(os.path.join(HERE, "..", ".opencode", "agents"))

# агенты, живущие вне models.json по правилам процесса
SPECIAL = {"studio"}  # координатор: без своей модели — пикер чата


def generate_fallbacks(agents_dir, roles):
    """Запасные копии <роль>-any: тот же протокол, БЕЗ строки model —
    наследуют модель сессии (координатор зовёт их при недоступности
    основной модели). Генерируются заново при каждом запуске."""
    made = 0
    for role in roles:
        src = os.path.join(agents_dir, role + ".md")
        if not os.path.isfile(src):
            continue
        text = open(src, encoding="utf-8").read()
        no_model = re.sub(r"(?m)^model: .*\n", "", text, count=1)
        no_model = re.sub(
            r"(?m)^(description: .*)$",
            r"\1 · FALLBACK-копия без своей модели — наследует модель сессии (зовёт координатор, когда основная недоступна)",
            no_model, count=1)
        with open(os.path.join(agents_dir, role + "-any.md"), "w",
                  encoding="utf-8", newline="") as f:
            f.write(no_model)
        made += 1
    return made


def main():
    try:
        cfg = json.load(open(os.path.join(HERE, "models.json"), encoding="utf-8"))
    except (OSError, ValueError) as e:
        print(f"models.json не читается: {e}", file=sys.stderr)
        return 1
    provider = cfg.get("provider")
    roles = cfg.get("roles") or {}
    if not provider or not isinstance(roles, dict) or not roles:
        print("models.json: нужны provider и непустой roles", file=sys.stderr)
        return 1

    # ---- фаза 1: сверка ДО записи ---------------------------------------
    problems = []
    for role in roles:
        if not os.path.isfile(os.path.join(AGENTS, role + ".md")):
            problems.append(f"роль {role!r} без файла агента .opencode/agents/{role}.md")
    base_files = {f[:-3] for f in os.listdir(AGENTS) if f.endswith(".md")
                  and not f.endswith("-any.md")}
    for name in sorted(base_files - set(roles) - SPECIAL):
        problems.append(f"агент .opencode/agents/{name}.md не числится ролью в "
                        f"models.json (остаток цепочки executor-prep/code/finish? "
                        f"удалите файл или верните роль)")
    orphan_any = sorted(f for f in os.listdir(AGENTS)
                        if f.endswith("-any.md") and f[:-7] not in roles
                        and f[:-7] not in SPECIAL)
    for role in sorted(roles):
        src = open(os.path.join(AGENTS, role + ".md"), encoding="utf-8").read()
        if not re.search(r"(?m)^model: ", src):
            problems.append(f"у агента {role}.md нет строки model: в frontmatter")
    if problems:
        print("models.json и агенты не согласованы — НИЧЕГО не записано:", file=sys.stderr)
        for p in problems:
            print(f"  - {p}", file=sys.stderr)
        return 1

    # ---- фаза 2: запись (всё проверено) ---------------------------------
    for role, model in roles.items():
        path = os.path.join(AGENTS, role + ".md")
        with open(path, encoding="utf-8") as f:
            text = f.read()
        new = re.sub(r"^model: .*$", f"model: {provider}/{model}",
                     text, count=1, flags=re.M)
        if new != text:
            with open(path, "w", encoding="utf-8", newline="") as f:
                f.write(new)
        print(f"{role:12} -> {provider}/{model}")
    for f in orphan_any:
        os.remove(os.path.join(AGENTS, f))
        print(f"осиротевшая копия удалена: {f}")
    made = generate_fallbacks(AGENTS, roles)
    print(f"fallback-копий сгенерировано: {made}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
