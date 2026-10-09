#!/usr/bin/env python3
"""Check generated protocol retention, model routing and every local skill/entrypoint."""
import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OC = ROOT / '.opencode'

def check():
    errors = []
    lock = json.loads((ROOT / 'build/source-lock.json').read_text(encoding='utf-8'))
    models = json.loads((ROOT / 'build/models.json').read_text(encoding='utf-8'))
    roles = json.loads((ROOT / 'build/roles.json').read_text(encoding='utf-8'))
    overrides = models.get('roles') or {}
    for role in sorted(set(overrides) - set(roles)):
        errors.append(f'Override for unknown role: {role}')
    for role in roles:
        primary = OC / 'agents' / (role + '.md')
        fallback = OC / 'agents' / (role + '-any.md')
        if fallback.is_file():
            errors.append(f'Fallback duplicate must not exist (inheritance is official): {role}-any.md')
        if not primary.is_file():
            errors.append(f'Missing agent file: {role}')
            continue
        text = primary.read_text(encoding='utf-8')
        if role in overrides:
            expected = overrides[role] if '/' in overrides[role] else f"{models['provider']}/{overrides[role]}"
            if f'model: {expected}\n' not in text:
                errors.append(f'Wrong model: {role}')
        elif re.search(r'^model:', text, re.M):
            errors.append(f'Must inherit the chat model (no model: line): {role}')
    if re.search(r'^model:', (OC / 'agents/studio.md').read_text(encoding='utf-8'), re.M):
        errors.append('studio must follow the chat picker')
    for original, spec in lock['protocols'].items():
        for chapter in spec['chapters']:
            path = ROOT / spec['destination'] / chapter['file']
            if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != chapter['sha256']:
                errors.append(f'Original chapter lost or edited: {original} / {chapter["file"]}')
    for file in list((OC / 'agents').glob('*.md')) + list((OC / 'commands/studio').glob('*.md')):
        if len(file.read_text(encoding='utf-8').splitlines()) > 90:
            errors.append(f'Role/entrypoint became a monolith: {file.relative_to(ROOT)}')
    skills = {}
    for file in (OC / 'skills').glob('*/SKILL.md'):
        body = file.read_text(encoding='utf-8')
        match = re.match(r'^---\nname: ([a-z0-9-]+)\ndescription: (.+)\n---\n', body)
        if not match or match[1] != file.parent.name:
            errors.append(f'Bad skill frontmatter: {file}')
        else:
            if match[1] in skills: errors.append(f'Duplicate skill: {match[1]}')
            skills[match[1]] = file
    handwritten = list((OC / 'skills').glob('*/SKILL.md')) + list((OC / 'agents').glob('*.md')) + list((OC / 'commands/studio').glob('*.md'))
    for file in handwritten:
        body = file.read_text(encoding='utf-8')
        for skill in re.findall(r'`(studio-[a-z-]+)`', body):
            if skill not in skills:
                errors.append(f'Unknown skill {skill} in {file.relative_to(ROOT)}')
        for local in re.findall(r'`(\.opencode/[^`\n]+)`', body):
            if any(marker in local for marker in ['<', '*', '…']): continue
            if not (ROOT / local.rstrip('/')).exists():
                errors.append(f'Missing path {local} in {file.relative_to(ROOT)}')
    if len(lock['protocols']) != 23:
        errors.append('The pinned original must retain 6 roles + 17 commands')
    for path in OC.rglob('*'):
        if not path.is_file() or '__pycache__' in path.parts: continue
        body = path.read_text(encoding='utf-8')
        if '\ufffd' in body or '\x00' in body:
            errors.append(f'Invalid text encoding: {path.relative_to(ROOT)}')
    return errors

if __name__ == '__main__':
    errors = check()
    for error in errors: print(error, file=sys.stderr)
    print(f'Integrity: {len(errors)} errors; pinned protocols, roles, routing and skill links checked.')
    sys.exit(bool(errors))
