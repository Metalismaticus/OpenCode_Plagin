import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('studio_install', ROOT / 'install.py')
installer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(installer)

class Installation(unittest.TestCase):
    def fixture(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        root = Path(folder.name)
        source = root / 'source'
        project = root / 'Игра с пробелом'
        (source / 'agents').mkdir(parents=True)
        (source / 'agents/studio.md').write_text('new coordinator', encoding='utf-8')
        (source / 'opencode.json').write_text('{"default_agent":"studio"}', encoding='utf-8')
        (project / '.opencode/plugins').mkdir(parents=True)
        (project / '.opencode/plugins/my-own.ts').write_text('untouched', encoding='utf-8')
        return source, project

    def test_preserve_unrelated_plugins_and_existing_jsonc(self):
        source, project = self.fixture()
        config = project / '.opencode/opencode.jsonc'
        config.write_text('// owner settings\n{"default_agent":"custom"}', encoding='utf-8')
        installer.install(project, source)
        self.assertEqual((project / '.opencode/plugins/my-own.ts').read_text(), 'untouched')
        self.assertFalse((project / '.opencode/opencode.json').exists())
        self.assertIn('custom', config.read_text())

    def test_changed_files_are_backed_up_and_owned_stale_files_pruned(self):
        source, project = self.fixture()
        installer.install(project, source)
        (source / 'agents/studio.md').write_text('next version', encoding='utf-8')
        destination, backup = installer.install(project, source)
        self.assertEqual((backup / 'agents/studio.md').read_text(), 'new coordinator')
        (source / 'agents/studio.md').unlink()
        installer.install(project, source)
        self.assertFalse((destination / 'agents/studio.md').exists())
        self.assertTrue((destination / 'plugins/my-own.ts').exists())

    def test_default_config_is_installed_once(self):
        source, project = self.fixture()
        destination, _ = installer.install(project, source)
        self.assertEqual(json.loads((destination / 'opencode.json').read_text())['default_agent'], 'studio')
        installer.install(project, source)
        self.assertTrue((destination / 'opencode.json').exists())

    def test_root_config_is_preserved(self):
        source, project = self.fixture()
        (project / 'opencode.json').write_text('{"model":"owner/model"}')
        destination, _ = installer.install(project, source)
        self.assertFalse((destination / 'opencode.json').exists())

    def test_install_over_source_is_rejected(self):
        source, project = self.fixture()
        with self.assertRaises(ValueError):
            installer.install(project, project / '.opencode')

if __name__ == '__main__':
    unittest.main()
