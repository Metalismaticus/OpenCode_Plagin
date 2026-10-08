"""Explicit Claude-to-OpenCode API/path adaptations, separate from workflow generation."""
import os
import re

DST = None  # configured by convert.py

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

POST_SUBS = [
    # агент `reference` (`studio:reference`) уже закрыт SUBS; страховка:
    (r"`studio:reference`", "`reference`"),
    (r"`studio:(\w+)`", r"`\1`"),
]

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

ASKING_PATCHES = [
    # среда: OpenCode; окно = встроенный инструмент question (header/варианты/multiple)
    (r"Владелец — не программист,\s+работает в приложении Claude для компьютера\.",
     "Владелец — не программист. Среда — OpenCode: **окно вопроса — встроенный\n"
     "инструмент `question`**: короткий `header`, вопрос и варианты (label +\n"
     "description «что будет, если выбрать»), `multiple` — выбор нескольких,\n"
     "свободный ответ («напишите словами») доступен всегда. Все правила ниже\n"
     "про «окно» понимаются так."),
    (r"1\. Любой вопрос с выбором — окном `AskUserQuestion`\.\s+В чат — только короткое\s+пояснение до окна \(≤ 5 строк: длинный текст окно закрывает\) и итог после\.\s+Длинное — в файл, в чат — путь к нему\.",
     "1. Любой вопрос с выбором — окном: инструмент `question`. До окна — только\n"
     "   короткое пояснение (≤ 5 строк) и итог после. Длинное — в файл, в чат —\n"
     "   путь к нему."),
    (r"4\. Вопрос самодостаточен \(Desktop не показывает `header`\): номер пункта и суть\s+в тексте вопроса\.\s+Тексты вопросов в одном окне разные — ответы привязаны к\s+тексту\.\s+`header` всё равно нужен: ≤ 12 символов\.",
     "4. Вопрос самодостаточен (`header` — не пересказ вопроса): номер пункта и\n"
     "   суть в тексте вопроса. Тексты вопросов в одном окне разные — ответы\n"
     "   привязаны к тексту. `header` нужен: ≤ 12 символов."),
    (r"Можно выбрать несколько — `multiSelect`\.",
     "Можно выбрать несколько — `multiple` у вопроса."),
    (r"`Вопрос владельцу \(можно несколько\): …` — вопрос с `multiSelect`;\s+`\(Recommended\)` в таком блоке не обязателен\.",
     "`Вопрос владельцу (можно несколько): …` — вопрос с `multiple`; выбрать\n"
     "    можно несколько вариантов сразу; `(Recommended)` в таком блоке не\n"
     "    обязателен."),
    (r"10\. Картинки — никогда в окне: сначала путь к файлу \(владелец щёлкает — файл\s+открывается справа во весь размер\) или `SendUserFile` с\s+`display: \"render\"`, если инструмент есть; потом окно\.",
     "10. Картинки — никогда в окне: сначала путь к файлу (владелец открывает\n"
     "     его сам, во весь размер); потом окно."),
    (r"## Запасной путь\s+- Окна нет \(ошибка, VS Code, окно не появилось\) — тот же вопрос нумерованным\s+списком текстом плюс «или напишите словами»\.\s+- Пустой ответ или Skip — повторить один раз",
     "## Запасной путь\n\n"
     "- Окно не поддержано клиентом или отменено — тот же вопрос нумерованным\n"
     "  списком в чат плюс «или напишите словами».\n"
     "- Пустой ответ или отмена — повторить один раз; снова пусто — как «пока не\n"
     "  знаю»"),
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
