#!/usr/bin/env python3
"""Rebuild protocols/templates/hooks from pinned CLAUDE_Game; never overwrite runtime/roles.
Usage: python build/convert.py --source ../CLAUDE_Game
"""
import argparse
import hashlib
import json
import re
import shutil
import subprocess
from pathlib import Path
import platform_adapter as adapter

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
adapter.DST = str(ROOT / '.opencode')
PIN = 'ab79866b43b4bf1fb388826a77265f3a385a46ad'

def split_front(text):
    match = re.match(r'^---\n(.*?)\n---\n(.*)$', text, re.S)
    if not match:
        return {}, text
    return dict(re.findall(r'^([\w-]+):\s*(.*)$', match[1], re.M)), match[2]

def adapt(text, where=None):
    text = adapter.apply_subs(text, adapter.SUBS)
    text = adapter.apply_subs(text, adapter.POST_SUBS)
    if where:
        text = adapter.apply_patches(text, adapter.PATCHES.get(where, []), where)
    text = adapter.rename_cmds(text)
    text = text.replace('AskUserQuestion', 'question').replace('multiSelect', 'multiple')
    text = re.sub(r'(?<![\w/])templates/', '.opencode/studio/templates/', text)
    text = text.replace(
        'приложении это **коннектор, а не плагин**: Customize → Connectors → поиск\n'
        '  «Context7» → Connect (есть инструмент показа коннекторов — показать им\n'
        '  кнопку), потом новый чат; исполнитель сверяет незнакомый API с этой версией',
        'OpenCode это MCP-сервер: предложить владельцу подключить Context7\n'
        '  через MCP-конфигурацию OpenCode по актуальной официальной инструкции;\n'
        '  исполнитель сверяет незнакомый API с этой версией')
    text = text.replace('(у коннектора имя сервера — набор цифр\n  и букв)', '(точное имя инструмента зависит от MCP-сервера)')
    for old, new in [('инструментом Agent', 'инструментом subagent'), ('вызовов Agent', 'вызовов subagent'), ('вызовы Agent', 'вызовы subagent'), ('Agent/Task', 'subagent'), ('`SendMessage`', 'продолжение subagent по sessionID')]:
        text = text.replace(old, new)
    return text

def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.rstrip() + '\n', encoding='utf-8')

def chapters(body):
    points = [m.start() for m in re.finditer(r'^## ', body, re.M)]
    starts = [0] + points + [len(body)]
    return [body[a:b] for a, b in zip(starts, starts[1:]) if body[a:b].strip()]

def protocol(source, relative, kind, name, manifest):
    raw = source.read_text(encoding='utf-8')
    _, body = split_front(raw)
    body = adapt(body, f'agents/{name}.md' if kind == 'agents' else f'commands/studio/{name}.md')
    destination = ROOT / '.opencode/studio/protocols' / kind / name
    if destination.exists():
        shutil.rmtree(destination)  # generated protocol only
    entries = []
    for index, part in enumerate(chapters(body)):
        filename = f'{index:02}.md'
        write(destination / filename, part)
        heading = next((line[3:] for line in part.splitlines() if line.startswith('## ')), 'Вводные правила')
        entries.append({'file': filename, 'heading': heading, 'sha256': hashlib.sha256((part.rstrip() + '\n').encode()).hexdigest()})
    write(destination / 'index.md', '# ' + name + '\n\n'
          'Правила CLAUDE_Game 0.10.6, адаптированные для OpenCode.\n'
          'Читать вводные правила и главу текущей стадии. Номера разделов —\n'
          'главы этой таблицы. Роли и состояние — в skills/runtime.\n\n'
          '| Глава | Файл |\n|---|---|\n' + '\n'.join(
              f"| {e['heading']} | `.opencode/studio/protocols/{kind}/{name}/{e['file']}` |" for e in entries))
    manifest[relative] = {'sha256': hashlib.sha256(raw.encode()).hexdigest(), 'body_sha256': hashlib.sha256(body.encode()).hexdigest(), 'chapters': entries, 'destination': destination.relative_to(ROOT).as_posix()}

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=ROOT.parent / 'CLAUDE_Game')
    args = parser.parse_args()
    source_root = args.source.resolve()
    commit = subprocess.check_output(['git', '-C', str(source_root), 'rev-parse', 'HEAD'], text=True).strip()
    if commit != PIN:
        raise SystemExit(f'Expected source {PIN}, got {commit}. Review upstream changes before changing PIN.')
    source = source_root / 'plugins/studio'
    manifest = {}
    for file in sorted((source / 'agents').glob('*.md')):
        protocol(file, str(file.relative_to(source)), 'agents', file.stem, manifest)
    for file in sorted((source / 'skills').glob('*/SKILL.md')):
        protocol(file, str(file.relative_to(source)), 'commands', file.parent.name, manifest)
    for directory, destination in [('reference', 'reference'), ('skills/setup/steps', 'setup-steps'), ('skills/setup/templates', 'templates')]:
        for file in sorted((source / directory).rglob('*')):
            if not file.is_file():
                continue
            relative = file.relative_to(source / directory)
            if file.name == 'CLAUDE.md':
                relative = relative.with_name('AGENTS.md')
            raw = file.read_text(encoding='utf-8')
            # ASKING's strict platform patches target the original tool names.
            text = adapter.rename_cmds(raw.replace('CLAUDE.md', 'AGENTS.md')) if file.name == 'ASKING.md' else adapt(raw)
            if destination == 'templates':
                text = text.replace('reference/COMMITS.md', '.opencode/studio/reference/COMMITS.md').replace('reference/ASKING.md', '.opencode/studio/reference/ASKING.md')
                if relative.name == 'AGENTS.md':
                    text += ('\n\n## OpenCode: роли и состояние\n\n'
                             'Обычное описание владельца — вход для чата замысла. Технические решения\n'
                             'готовят product/architect; владелец отвечает о поведении, вкусе,\n'
                             'приоритетах и приёмке. Команды — короткие входы в skills, главы процесса\n'
                             'подгружаются по стадии. `studio_workflow` хранит машинное состояние в\n'
                             '`../<проект>.wt/state/`; `docs/BATCH.md` остаётся понятной владельцу партией.\n'
                             'Противоречат друг другу — остановиться и сверить с git.\n'
                             'Контрольный коммит и зелёные проверки не означают приёмку.\n')
            write(ROOT / '.opencode/studio' / destination / relative, text)
    adapter.patch_asking()
    for name in ('guard_git.py', 'session_context.py', 'selftest.py'):
        write(ROOT / '.opencode/studio/hooks' / name, (source / 'hooks' / name).read_text(encoding='utf-8'))
    adapter.patch_hooks()
    shutil.copyfile(source / 'tools/env_check.ps1', ROOT / '.opencode/studio/env_check.ps1')
    test = ROOT / '.opencode/studio/hooks/selftest.py'
    text = test.read_text(encoding='utf-8')
    text = text.replace('wrapper = f.read()', 'wrapper = f.read()\n            for name in ("python.mjs", "telemetry.mjs"):\n                with open(os.path.join(HERE, "..", "runtime", name), encoding="utf-8") as module:\n                    wrapper += module.read()')
    write(test, text)
    write(ROOT / 'build/source-lock.json', json.dumps({'repository': 'Metalismaticus/CLAUDE_Game', 'commit': commit, 'version': '0.10.6', 'protocols': manifest}, ensure_ascii=False, indent=2))
    print(f'Imported {len(manifest)} protocols from CLAUDE_Game {commit[:7]}; roles and runtime untouched.')

if __name__ == '__main__':
    main()
