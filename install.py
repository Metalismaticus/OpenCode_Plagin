#!/usr/bin/env python3
"""Install only this plugin's files, retaining unrelated plugins and configuration."""
import argparse
import datetime
import json
import shutil
import subprocess
import sys
from pathlib import Path

def install(project, source=None):
    source = Path(source or Path(__file__).resolve().parent / '.opencode').resolve()
    project = Path(project).resolve()
    if not project.is_dir() or not source.is_dir():
        raise ValueError('Project and plugin source directories must exist')
    destination = project / '.opencode'
    if destination.resolve() == source:
        raise ValueError('Do not install the plugin over its source checkout')
    destination.mkdir(exist_ok=True)
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    backups = project.parent / (project.name + '.wt') / 'install-backups' / stamp
    manifest = destination / 'studio/install-manifest.json'
    previous = json.loads(manifest.read_text(encoding='utf-8')).get('files', []) if manifest.exists() else []
    owned = []
    written = []
    for file in sorted(source.rglob('*')):
        if not file.is_file() or '__pycache__' in file.parts or file.suffix == '.pyc':
            continue
        relative = file.relative_to(source)
        if relative.as_posix() == 'studio/install-manifest.json':
            continue
        target = destination / relative
        # Preserve both JSON/JSONC configurations, including custom root config.
        if relative.as_posix() == 'opencode.json' and any(p.exists() for p in [destination / 'opencode.json', destination / 'opencode.jsonc', project / 'opencode.json', project / 'opencode.jsonc']):
            continue
        if not target.resolve().is_relative_to(destination.resolve()):
            raise ValueError(f'Destination symlink escapes project: {relative}')
        if target.exists() and target.read_bytes() != file.read_bytes():
            backup = backups / relative
            backup.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(target, backup)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(file, target)
        owned.append(relative.as_posix())
        written.append(target)
    # Only a prior successful install's exact owned paths may be pruned.
    # A first migration never recursively mirrors or deletes .opencode/.
    for name in previous:
        relative = Path(name)
        if relative.is_absolute() or '..' in relative.parts or name in ['opencode.json', 'opencode.jsonc']:
            continue
        target = destination / relative
        if name not in owned and target.is_file() and target.resolve().is_relative_to(destination.resolve()):
            backup = backups / relative
            backup.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(target, backup)
            target.unlink()
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_text(json.dumps({'version': 1, 'files': owned}, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return destination, backups if backups.exists() else None

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('project', type=Path)
    parser.add_argument('--skip-check', action='store_true', help='copy only; default runs the installed quick selftest')
    args = parser.parse_args()
    try:
        destination, backup = install(args.project)
    except (ValueError, OSError, json.JSONDecodeError) as error:
        print(f'ERROR: {error}', file=sys.stderr)
        return 1
    print(f'Installed studio into {destination}')
    if backup:
        print(f'Previous overwritten plugin files: {backup}')
    print('Existing config preserved. Select studio in the chat picker if it is not your default agent.')
    if not args.skip_check:
        result = subprocess.run([sys.executable, '-X', 'utf8', str(destination / 'studio/hooks/selftest.py'), '--quick'], capture_output=True, text=True, encoding='utf-8')
        print(result.stdout.splitlines()[-1] if result.stdout.strip() else result.stderr.strip())
        if result.returncode:
            print('Installed files retained, but selftest failed; do not start development until fixed.', file=sys.stderr)
            return result.returncode
    print('Open a new project chat: /studio/setup. Existing projects: /studio/setup обновить.')
    return 0

if __name__ == '__main__':
    sys.exit(main())
