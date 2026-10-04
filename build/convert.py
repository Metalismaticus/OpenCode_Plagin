#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Конвертер studio: Claude Code (исходник, не трогаем) -> OpenCode V2 (port).

Источник  : ../CLAUDE_Game/plugins/studio      (клон, остаётся как есть)
Назначение: ../studio-glm/.opencode           (порт, будущий отдельный репозиторий)

Что делает:
  agents/*.md           -> .opencode/agents/*.md          (frontmatter V2: mode/model/steps/permissions)
  skills/<n>/SKILL.md   -> .opencode/commands/studio/<n>.md  (frontmatter: description + agent: studio)
  skills/setup/steps/*  -> .opencode/studio/setup-steps/*
  skills/setup/templates-> .opencode/studio/templates/*   (CLAUDE.md -> AGENTS.md)
  reference/*.md        -> .opencode/studio/reference/*
  hooks/*.py            -> .opencode/studio/hooks/*       (hooks.json не переносится — обёртка studio.ts)
  tools/env_check.ps1   -> .opencode/studio/env_check.ps1

Механические замены путей и имён инструментов — в SUBS. Тонкие места
(ASKING.md, session_context.py, selftest.py, setup.md, reference.md, start.md,
templates/AGENTS.md) конвертер только копирует/переименовывает — их доводят
правки ниже в этом файле (PATCHES): список точечных замен, чтобы конвертация
воспроизводима одним запуском. Ручные правки сверх PATCHES — только через новый
элемент PATCHES.

Запуск:  python -X utf8 build/convert.py
"""
import json
import os
import re
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.normpath(os.path.join(HERE, "..", "..", "CLAUDE_Game", "plugins", "studio"))
DST = os.path.normpath(os.path.join(HERE, "..", ".opencode"))

# ---------------------------------------------------------------- модели ----

MODELS = json.load(open(os.path.join(HERE, "models.json"), encoding="utf-8"))
PROVIDER = MODELS["provider"]


def model_id(role):
    return f"{PROVIDER}/{MODELS['roles'][role]}"


# ------------------------------------------------------- substitutions -----

SUBS = [
    # пути внутри текстов протоколов (от базовой папки скилла -> от корня проекта)
    (r'"<базовая папка скилла>/\.\./\.\./hooks/selftest\.py"', '".opencode/studio/hooks/selftest.py"'),
    (r"\.\./\.\./reference/", ".opencode/studio/reference/"),
    (r"\.\./\.\./hooks/selftest\.py", ".opencode/studio/hooks/selftest.py"),
    (r"\.\./\.\./tools/env_check\.ps1", ".opencode/studio/env_check.ps1"),
    (r"\.\./\.\./agents/", ".opencode/agents/"),
    (r"\.\./(\w+)/SKILL\.md", r".opencode/commands/studio/\1.md"),
    (r"`\.\./\.\./\.\./reference/`", "`.opencode/studio/reference/`"),
    (r"`…/skills/setup/templates`", "`.opencode/studio/templates`"),
    # проектный файл инструкций: OpenCode читает AGENTS.md
    (r"CLAUDE\.md", "AGENTS.md"),
    # субагенты: в OpenCode зовутся просто по имени, без префикса плагина
    (r"`studio:(\w+)`;\s+нет такого типа —\s+без\s+префикса", r"`\1`"),
    (r"вызов(а|ов) Agent", r"вызов\1 subagent"),
    # показ картинок: без SendUserFile — путём к файлу
    (r"путём к\s+файлу или `SendUserFile`, потом окно\.", "путём к файлу, потом окно."),
    (r"путь `SendUserFile` с `display: \"render\"`", "путь к файлу"),
    (r"`SendUserFile` с `display: \"render\"`", "путь к файлу"),
    (r"\(если `SendUserFile` — вложением тоже\)", "(вложение к сообщению — тоже)"),
    (r"`SendUserFile`", "путь к файлу"),
    # шаг 12 теперь в команде /studio/setup
    (r"шаг 12 `SKILL\.md`", "шаг 12 `/studio/setup`"),
    (r"`SKILL\.md`,\s+шаг 12", "`/studio/setup`, шаг 12"),
    # имена инструментов в прозе — строчными, как в OpenCode
    (r"\(Read\)", "(read)"),
    (r"\(Grep\)", "(grep)"),
    (r"\(Glob\)", "(glob)"),
    (r"\(Bash\)", "(bash)"),
    # шаги setup-а живут в данных плагина
    # шаги сетапа: точные формы исходника (без генерик-паттернов — те
    # срабатывали дважды на «setup-steps/…»)
    (r"`\.\./setup/templates", "`.opencode/studio/templates"),
    (r"`\.\./setup/steps/", "`.opencode/studio/setup-steps/"),
    (r"`setup/steps/(\w+)\.md`", r"`.opencode/studio/setup-steps/\1.md`"),
    (r"`steps/(\w+)\.md`", r"`.opencode/studio/setup-steps/\1.md`"),
    (r"`steps/<шаг>\.md`", "`.opencode/studio/setup-steps/<шаг>.md`"),
    # хвосты «от базовой папки скилла» — гибко по пробелам и переносам,
    # только сразу после бэктика пути
    (r"`\s+\(\s*от\s+базовой\s+папки\s+скилла\s*\)", "`"),
    (r"`\s+\(\s*от\s+базовой\s+папки\s+скилла(?=;)", "`;"),
    (r"`\s+(?:от|относительно)\s+базовой\s+папки\s+скилла", "`"),
    (r"`\s+(?:от|относительно)\s+базовой\s+папки\s+этого\s+скилла", "`"),
    (r"`\s+\(\s*путь\s+от\s+базовой\s+папки\s+этого\s+скилла\s*\)", "`"),
    (r",\s*путь\s+от\s+базовой\s+папки\s+этого\s+скилла\s*\)", ")"),
    # «<базовая папка скилла>/…» — путь уже переведён, префикс убираем
    (r'"<базовая\s+папка\s+скилла>/', '"'),
    (r"`<базовая\s+папка\s+скилла>/", "`.opencode/studio/"),
]

# тонкие замены по конкретным файлам: (regex, замена) — по якорям, с re.S;
# патч обязан сработать (иначе конвертация падает — защита от тихого пропуска)
PATCHES = {
    # ---- agents/reference.md: вставленные картинки — вложения, а не $TEMP/claude
    "agents/reference.md": [
        (r"«Найди свежие»: вставленные в чат картинки лежат в.*?или назвать путь\.",
         "«Найди свежие»: вставленная в чат картинка приходит вложением к\n"
         "   сообщению — сохранить её байты в `docs/refs/<тема>/owner-<дата>-<n>.png`,\n"
         "   открыть и сверить с описанием — чужую картинку не копировать. Вложения\n"
         "   нет (текст без картинки) — в итоге попросить владельца перетащить файл в\n"
         "   `docs/refs/<тема>/` или назвать путь."),
        (r"полный путь папки шаблонов плагина.*?`\)\.",
         "шаблоны плагина — `.opencode/studio/templates`, библиотека приёмов —\n"
         "`.opencode/studio/reference/LOOK_TECHNIQUES.md`."),
    ],
    # ---- commands/studio/start.md: вызов агентов, повтор упавшего, SendMessage
    "commands/studio/start.md": [
        (r"Агенты — инструментом Agent\s+как `studio:<имя>`; нет такого типа — без префикса\.",
         "Агенты — инструментом subagent по имени (`executor`, `reviewer`,\n"
         "`designer`, `scout`, `assets`, `reference`)."),
        (r"позвать снова тем же сообщением с параметром `model` — модель этого\s+чата; и она недоступна",
         "позвать снова тем же сообщением (модель каждого агента задана в его\n"
         "файле `.opencode/agents/<имя>.md`); и она недоступна"),
        (r"тому же проверяющему \(`SendMessage`; нет — свежему с\s+прежним сообщением\)",
         "тому же проверяющему (продолжение той же дочерней сессии subagent по её\n"
         "sessionID; нет — свежему с прежним сообщением)"),
    ],
    # ---- commands/studio/setup.md: базовая папка скилла -> папка плагина
    "commands/studio/setup.md": [
        (r"Всё нужное — от базовой папки скилла, названной при вызове \(не названа —.*?в папке плагинов\):",
         "Всё нужное — в папке плагина studio (в корне проекта):"),
        (r"- `templates/` — шаблоны документов и `tools/`\.",
         "- `.opencode/studio/templates/` — шаблоны документов и `tools/`."),
    ],
}

# замены, которые применяются ко всем файлам тел ПОСЛЕ SUBS (уточнения формулировок)
POST_SUBS = [
    # агент `reference` (`studio:reference`) уже закрыт SUBS; страховка:
    (r"`studio:reference`", "`reference`"),
    (r"`studio:(\w+)`", r"`\1`"),
]

# реальные имена команд в OpenCode — /studio/<имя>; документы звали их коротко.
# Границы: не после букв/цифр/_//.- (внутри путей и имён) и не перед словом.
CMD_RENAME = [
    (r"(?<![\w/.-])/(start|done|setup|idea|roadmap|fault|order|need|art|music|"
     r"mockup|add|check|parallel|retro|release|board)(?!\w)", r"/studio/\1"),
]


def rename_cmds(text):
    return apply_subs(text, CMD_RENAME)


def apply_subs(text, subs, dotted=False):
    flags = re.S if dotted else 0
    for pat, rep in subs:
        text = re.sub(pat, rep, text, flags=flags)
    return text


def apply_patches(body, patches, where):
    for pat, rep in patches:
        new = re.sub(pat, rep, body, flags=re.S)
        if new == body:
            raise SystemExit(f"PATCH не сработал в {where}: {pat[:70]!r}")
        body = new
    return body


def read(path):
    with open(path, "rb") as f:
        return f.read().decode("utf-8")


def write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(text.encode("utf-8"))


def split_front(text):
    """('---\\n...---\\n', тело) или (None, text)."""
    if not text.startswith("---"):
        return None, text
    end = text.find("\n---", 3)
    if end < 0:
        return None, text
    fm = text[: end + 4]
    body = text[end + 4:]
    return fm, body


def parse_front(fm):
    out = {}
    for line in fm.strip("-\n").splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            out[k.strip()] = v.strip()
    return out


# --------------------------------------------------------------- agents ----

# complement of Claude `tools:` -> V2 deny-правила (всё, что НЕ разрешено)
AGENT_TOOL_DENY = {
    "executor": ["subagent"],
    "reviewer": ["edit", "write", "patch", "subagent", "webfetch", "websearch", "skill"],
    "designer": ["edit", "patch", "subagent", "webfetch", "websearch", "skill"],
    "scout": ["edit", "write", "patch", "subagent", "webfetch", "websearch", "skill", "bash"],
    "assets": ["subagent"],
    "reference": ["subagent", "skill"],
}


def convert_agent(name):
    src = read(os.path.join(SRC, "agents", name + ".md"))
    fm, body = split_front(src)
    meta = parse_front(fm)
    body = apply_subs(body, SUBS)
    body = apply_subs(body, POST_SUBS)
    body = apply_patches(body, PATCHES.get("agents/" + name + ".md", []),
                         "agents/" + name + ".md")
    body = rename_cmds(body)
    desc = rename_cmds(re.sub(r"CLAUDE\.md", "AGENTS.md", meta.get("description", "")))
    lines = ["---", f"description: {desc}",
             "mode: subagent", f"model: {model_id(name)}"]
    if meta.get("maxTurns"):
        lines.append(f"steps: {meta['maxTurns']}")
    denies = AGENT_TOOL_DENY.get(name, ["subagent"])
    if denies:
        lines.append("permissions:")
        for d in denies:
            lines.append(f"  - {{ action: {d}, resource: \"*\", effect: deny }}")
    lines.append("---")
    write(os.path.join(DST, "agents", name + ".md"), "\n".join(lines) + "\n" + body)


# -------------------------------------------------------------- commands ----

def convert_skill(name):
    src = read(os.path.join(SRC, "skills", name, "SKILL.md"))
    fm, body = split_front(src)
    meta = parse_front(fm)
    body = apply_subs(body, SUBS)
    body = apply_subs(body, POST_SUBS)
    body = apply_patches(body, PATCHES.get("commands/studio/" + name + ".md", []),
                         "commands/studio/" + name + ".md")
    body = rename_cmds(body)
    desc = rename_cmds(re.sub(r"CLAUDE\.md", "AGENTS.md", meta.get("description", "")))
    out = ["---", f"description: {desc}",
           "agent: studio", "---", "", body.lstrip("\n")]
    write(os.path.join(DST, "commands", "studio", name + ".md"), "\n".join(out))


# ----------------------------------------------------------------- main ----

def main():
    if not os.path.isdir(SRC):
        raise SystemExit(f"нет источника: {SRC}")
    guard = os.path.join(DST, "agents", "executor-prep.md")
    if os.path.isfile(guard) and "--force" not in sys.argv:
        raise SystemExit(
            "конвертер — бутстреп стадии 1–2. В .opencode уже живёт стадия 3\n"
            "(цепочка executor-prep → executor-code → executor-finish, reviewer-fast\n"
            "и диспетчеризация в commands/studio/start.md): повторный запуск сотрёт\n"
            "её монолитом из исходника. Перегенерация — только осознанно (--force)\n"
            "и с последующим повтором правок стадии 3; правки upstream — руками.")
    for root, _, files in os.walk(os.path.join(SRC, "agents")):
        for f in files:
            if f[:-3] == "executor":
                continue  # заменён цепочкой executor-prep/code/finish (стадия 3)
            convert_agent(f[:-3])
    for entry in os.listdir(os.path.join(SRC, "skills")):
        skill = os.path.join(SRC, "skills", entry, "SKILL.md")
        if os.path.isfile(skill):
            convert_skill(entry)
    # шаги сетапа
    for f in os.listdir(os.path.join(SRC, "skills", "setup", "steps")):
        if f.endswith(".md"):
            t = read(os.path.join(SRC, "skills", "setup", "steps", f))
            t = apply_subs(t, SUBS)
            t = rename_cmds(t)
            write(os.path.join(DST, "studio", "setup-steps", f), t)
    # шаблоны (CLAUDE.md -> AGENTS.md, внутренние пути плагина)
    tpl_src = os.path.join(SRC, "skills", "setup", "templates")
    for root, _, files in os.walk(tpl_src):
        for f in files:
            rel = os.path.relpath(os.path.join(root, f), tpl_src)
            t = read(os.path.join(root, f))
            t = apply_subs(t, [
                (r"reference/COMMITS\.md", ".opencode/studio/reference/COMMITS.md"),
                (r"reference/ASKING\.md", ".opencode/studio/reference/ASKING.md"),
                (r"CLAUDE\.md", "AGENTS.md"),
            ])
            t = rename_cmds(t)
            if f == "CLAUDE.md":
                rel = os.path.join(os.path.dirname(rel), "AGENTS.md")
            write(os.path.join(DST, "studio", "templates", rel), t)
    # reference-документы
    for f in os.listdir(os.path.join(SRC, "reference")):
        t = read(os.path.join(SRC, "reference", f))
        t = apply_subs(t, [(r"CLAUDE\.md", "AGENTS.md")])
        t = rename_cmds(t)
        write(os.path.join(DST, "studio", "reference", f), t)
    patch_asking()
    # хуки и env_check — копией (точечные правки в отдельной функции)
    for f in ("guard_git.py", "session_context.py", "selftest.py"):
        t = read(os.path.join(SRC, "hooks", f))
        write(os.path.join(DST, "studio", "hooks", f), t)
    shutil.copy(os.path.join(SRC, "tools", "env_check.ps1"),
                os.path.join(DST, "studio", "env_check.ps1"))
    patch_hooks()
    print("OK ->", DST)


ASKING_PATCHES = [
    # среда: OpenCode, окно = список (деградация без поломки — правило №1 остаётся)
    (r"Владелец — не программист,\s+работает в приложении Claude для компьютера\.",
     "Владелец — не программист. Среда — OpenCode: **окно вопроса — это\nнумерованный список в чате**, выбор — ответом цифрой или своими словами;\n«или напишите словами» — законная часть каждого вопроса. Все правила ниже\nпро «окно» понимаются так."),
    (r"1\. Любой вопрос с выбором — окном `AskUserQuestion`\.\s+В чат — только короткое\s+пояснение до окна \(≤ 5 строк: длинный текст окно закрывает\) и итог после\.\s+Длинное — в файл, в чат — путь к нему\.",
     "1. Любой вопрос с выбором — окном (списком в чат). До окна — только\n   короткое пояснение (≤ 5 строк) и итог после. Длинное — в файл, в чат —\n   путь к нему."),
    (r"4\. Вопрос самодостаточен \(Desktop не показывает `header`\): номер пункта и суть\s+в тексте вопроса\.\s+Тексты вопросов в одном окне разные — ответы привязаны к\s+тексту\.\s+`header` всё равно нужен: ≤ 12 символов\.",
     "4. Вопрос самодостаточен: номер пункта и суть в тексте вопроса. Тексты\n   вопросов в одном сообщении разные — ответы привязаны к тексту. Короткая\n   шапка (≤ 12 символов) — первой строкой вопроса."),
    (r"Можно выбрать несколько — `multiSelect`\.",
     "Можно выбрать несколько — пометка «(можно несколько)» в вопросе."),
    (r"`Вопрос владельцу \(можно несколько\): …` — вопрос с `multiSelect`;\s+`\(Recommended\)` в таком блоке не обязателен\.",
     "`Вопрос владельцу (можно несколько): …` — вопрос, где владелец может\n    выбрать несколько вариантов сразу; `(Recommended)` в таком блоке не\n    обязателен."),
    (r"10\. Картинки — никогда в окне: сначала путь к файлу \(владелец щёлкает — файл\s+открывается справа во весь размер\) или `SendUserFile` с\s+`display: \"render\"`, если инструмент есть; потом окно\.",
     "10. Картинки — никогда в окне: сначала путь к файлу (владелец открывает\n     его сам, во весь размер); потом окно."),
    (r"## Запасной путь\s+- Окна нет \(ошибка, VS Code, окно не появилось\) — тот же вопрос нумерованным\s+списком текстом плюс «или напишите словами»\.\s+- Пустой ответ или Skip — повторить один раз",
     "## Запасной путь\n\n- Ответ не понят — переспросить один раз, короче.\n- Пустой ответ — повторить один раз"),
]


def patch_asking():
    p = os.path.join(DST, "studio", "reference", "ASKING.md")
    t = read(p)
    t = apply_patches(t, ASKING_PATCHES, "reference/ASKING.md")
    write(p, t)


def patch_hooks():
    """Точечные правки python-скриптов под раскладку OpenCode (формат событий НЕ меняется:
    обёртка studio.ts подаёт им события в исходном формате Claude)."""
    # session_context.py: путь шаблона, AGENTS.md в корне проекта, /studio:start
    p = os.path.join(DST, "studio", "hooks", "session_context.py")
    t = read(p)
    t = t.replace(
        'PLUGIN_TEMPLATE = os.path.join(os.path.dirname(os.path.abspath(__file__)),\n'
        '                               "..", "skills", "setup", "templates", "CLAUDE.md")',
        'PLUGIN_TEMPLATE = os.path.join(os.path.dirname(os.path.abspath(__file__)),\n'
        '                               "..", "templates", "AGENTS.md")')
    t = t.replace(
        'mine = template_version(os.path.join(project_root, "CLAUDE.md"), missing=0)',
        'mine = template_version(os.path.join(project_root, "AGENTS.md"), missing=0)\n'
        '    if not os.path.isfile(os.path.join(project_root, "AGENTS.md")):\n'
        '        mine = template_version(os.path.join(project_root, "CLAUDE.md"), missing=0)')
    t = t.replace('вызвать /studio:start без аргумента — он сверит партию с git.',
                  'владельцу — /studio/start без аргумента (сверит партию с git), '
                  'чат — продолжить по протоколу .opencode/commands/studio/start.md.')
    t = t.replace('Число из метки «шаблон vN» в CLAUDE.md; нет файла — None, нет метки — missing.',
                  'Число из метки «шаблон vN» в AGENTS.md проекта (старый Claude-проект —\n'
                  'CLAUDE.md); нет файла — None, нет метки — missing.')
    t = t.replace('без метки в CLAUDE.md — развёрнут до',
                  'без метки в AGENTS.md (и CLAUDE.md) — развёрнут до')
    t = t.replace('Чат разработки (где звали /start) продолжает по',
                  'Чат разработки (где звали /studio/start) продолжает по')
    t = t.replace('вызовите /setup обновить (пара минут)',
                  'вызовите /studio/setup обновить (пара минут)')
    write(p, t)
    # selftest.py: путь к шаблонным tools и шаблону AGENTS.md
    p = os.path.join(DST, "studio", "hooks", "selftest.py")
    t = read(p)
    t = t.replace('TOOLS = os.path.join(HERE, "..", "skills", "setup", "templates", "tools")',
                  'TOOLS = os.path.join(HERE, "..", "templates", "tools")')
    t = t.replace('write(os.path.join(folder, "CLAUDE.md"), f"<!-- Процесс: плагин studio, {label}. -->\\n")',
                  'write(os.path.join(folder, "AGENTS.md"), f"<!-- Процесс: плагин studio, {label}. -->\\n")')
    t = t.replace('version("CLAUDE.md нет метки", "нет метки", True)',
                  'version("AGENTS.md нет метки", "нет метки", True)')
    t = t.replace('version("CLAUDE.md без метки", "без метки", True)',
                  'version("AGENTS.md без метки", "без метки", True)')
    t = t.replace('version("нет CLAUDE.md", "", False)',
                  'version("нет AGENTS.md", "", False)')
    t = re.sub(
        r'def check_config\(results\):.*?'
        r'results\.append\(\("hooks\.json", "оба хука, python -X utf8", "подключены", got, ok\)\)\n',
        'def check_config(results):\n'
        '    """studio.ts: обёртка подключает оба хука (python -X utf8) и телеметрию, файлы на месте."""\n'
        '    try:\n'
        '        with open(os.path.join(HERE, "..", "..", "plugins", "studio.ts"),\n'
        '                  encoding="utf-8") as f:\n'
        '            wrapper = f.read()\n'
        '        ok = (\'"execute.before"\' in wrapper and "guard_git.py" in wrapper\n'
        '              and \'"prompt"\' in wrapper and "session_context.py" in wrapper\n'
        '              and "-X" in wrapper and "utf8" in wrapper\n'
        '              and "session.usage.updated" in wrapper and "studio-usage.jsonl" in wrapper\n'
        '              and "usage-seen" in wrapper and "flushUsage" in wrapper\n'
        '              and os.path.isfile(GUARD) and os.path.isfile(CONTEXT))\n'
        '        got = "подключены" if ok else "не так"\n'
        '    except Exception as e:  # noqa: BLE001 — любая поломка файла = провал\n'
        '        ok, got = False, f"ошибка: {e}"\n'
        '    results.append(("studio.ts", "оба хука + телеметрия, python -X utf8", "подключены", got, ok))\n',
        t, flags=re.S)
    write(p, t)
    # guard_git.py: одна строка для владельца
    p = os.path.join(DST, "studio", "hooks", "guard_git.py")
    t = read(p)
    t = t.replace('lines.append("См. CLAUDE.md проекта, «Два чата».")',
                  'lines.append("См. AGENTS.md проекта, «Два чата».")')
    write(p, t)


if __name__ == "__main__":
    main()
