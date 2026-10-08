#!/usr/bin/env python3
"""Build thin command and role-skill routers from the source chapter manifest."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OC = ROOT / '.opencode'

def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding='utf-8')

def front(name, description, body):
    return f'---\nname: {name}\ndescription: {description}\n---\n\n{body.rstrip()}\n'

def main():
    lock = json.loads((ROOT / 'build/source-lock.json').read_text(encoding='utf-8'))
    descriptions = {
        'start': 'Начать или продолжить разработку по очереди; приёмка только владельцем.',
        'done': 'Показать результат и принять партию по решению владельца.',
        'idea': 'Додумать замысел обычными словами и поставить понятные задачи.',
    }
    for source, spec in lock['protocols'].items():
        if not source.startswith('skills/'):
            continue
        command = source.split('/')[1]
        skill = {'start': 'studio-development', 'done': 'studio-acceptance', 'idea': 'studio-planning'}.get(command, 'studio-' + command)
        write(OC / 'commands/studio' / (command + '.md'), f'---\ndescription: {descriptions.get(command, "Процесс studio — " + command)}\nagent: studio\n---\n\nOwner request: **$ARGUMENTS**\n\nLoad `{skill}` with the skill tool and follow it for this request.\nOnly the current stage\'s protocol chapters belong in context.\nSpeak to the owner in Russian, in product words.\n')
        if command in {'start', 'done', 'idea'}:
            continue  # handwritten machine-aware controllers
        mode = 'concept' if command in {'roadmap', 'fault', 'order', 'need', 'art', 'music', 'mockup'} else 'development'
        binding = f'Bind this primary chat as `{mode}` using studio_workflow.\n'
        if command in {'board', 'setup'}:
            binding = ('Do not change an existing chat mode. Setup without an established mode\nasks whether this is the concept or development chat in owner vocabulary.\n' if command == 'setup' else 'Read-only command: do not bind or change chat mode.\nCall studio_workflow status for the actual next stage and limits.\n')
        paths = '\n'.join(f"- `{spec['destination']}/{chapter['file']}` — {chapter['heading']}" for chapter in spec['chapters'])
        body = f'# /studio/{command}\n\n{binding}\nRead the introductory chapter, then each chapter **when that stage is reached**.\nDo not load all chapters at once; cross-references use this table.\n\n{paths}\n\nOriginal feature rules remain in force. API routing comes from the studio\ncoordinator and role skills; no old instruction may bypass runtime gates.\n'
        if command == 'setup':
            body += ('\nConcept mode stops before creating/launching product scaffolding.\nDevelopment mode creates scaffolding via an executor bootstrap task with\n`batch:"setup"`, `sources:["docs/SETUP-PLAN.md"]` and concrete files/checks.\nRecord start decisions and the first frame, then show the owner per original\nsteps. Existing project files are not overwritten. Delegate code inspection\nto scout/architect; preserve the owner\'s custom AGENTS sections.\n')
        write(OC / 'skills' / ('studio-' + command) / 'SKILL.md', front('studio-' + command, f'Follow the original studio {command} process with stage-local context. Use for /studio/{command}.', body))
    routes = {'studio-ui': 'designer', 'studio-assets': 'assets', 'studio-reference': 'reference'}
    for skill, role in routes.items():
        spec = lock['protocols'][f'agents/{role}.md']
        table = '\n'.join(f"- `{spec['destination']}/{e['file']}` — {e['heading']}" for e in spec['chapters'])
        write(OC / 'skills' / skill / 'SKILL.md', front(skill, f'Run the original studio {role} procedure; load only applicable chapters. Use as {role}.', f'# {role}\n\nRead the introduction, input, prohibitions and report format first.\nThen read the procedure; conditional look/feel/concept chapters only when\nrequested. The coordinator supplies exact source/spec/output paths.\nNever ask the owner technical questions or accept the result.\n\n{table}\n'))
    routes = {'studio-wave': ('05.md', 'Parallel waves'), 'studio-vid': ('06.md', 'Look/feel variants and choice'), 'studio-perf': ('09.md', 'Performance and probe frames')}
    for skill, (chapter, label) in routes.items():
        extra = ''
        if skill == 'studio-wave':
            extra = 'Use scout for wave safety; one task card/worktree per item. The machine\nstate is shared at the main project, not copied into each slot.\n'
        elif skill == 'studio-vid':
            extra = 'Create one task id per stand/base/choice/embedding step. Set owner_result:false\nfor intermediate stand/base/choice cards; embedding is owner_result:true.\nEarlier stages are checkpoints; only the final player result goes to owner acceptance.\nFor acceptance read .opencode/studio/protocols/commands/done/01.md and 02.md before showing frames.\n'
        else:
            extra = 'Measurements follow the original machine/preset protocol. A quick headless\ncheck or model statement is never a measured frame-time result.\n'
        write(OC / 'skills' / skill / 'SKILL.md', front(skill, label + '. Load only when the current studio task needs this branch.', f'# {label}\n\nRead `.opencode/studio/protocols/commands/start/{chapter}`.\nThis chapter preserves the original branch, including failures and rollback.\n{extra}Task transitions use studio_workflow; do not replace them with BATCH labels.\n'))
    for skill, command, chapter in [('studio-obrazec', 'idea', '03.md'), ('studio-concept', 'idea', '08.md')]:
        write(OC / 'skills' / skill / 'SKILL.md', front(skill, 'Analyze a named game/image reference or a global visual concept via the original studio protocol.', f'Read `.opencode/studio/protocols/commands/{command}/{chapter}` when this branch\nis needed. Delegate the analysis to reference; preserve uncertainties and\nowner words. Questions and recording remain with the concept coordinator.\n'))
    print('Built thin command and branch routers; core controllers preserved.')

if __name__ == '__main__':
    main()
