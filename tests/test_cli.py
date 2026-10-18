import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from threadhaven import cli, context

class CliTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def test_install_and_repeat_preserve_settings(self):
        settings=self.root/'.claude/settings.json'
        settings.parent.mkdir();settings.write_text('{"existing":true}')
        with contextlib.redirect_stdout(io.StringIO()):
            cli.install_skills(self.root,True)
            cli.install_skills(self.root,True)
        for provider in ('.agents','.claude'):
            for name in ('snapshot','context-check'):
                self.assertIn('Threadhaven',(self.root/provider/'skills'/name/'SKILL.md').read_text())
        self.assertEqual(settings.read_text(),'{"existing":true}')

    def test_preview_writes_nothing(self):
        with contextlib.redirect_stdout(io.StringIO()):cli.install_skills(self.root)
        self.assertEqual(list(self.root.iterdir()),[])

    def test_conflict_preflight_preserves_all_skills(self):
        skill=self.root/'.claude/skills/context-check/SKILL.md'
        skill.parent.mkdir(parents=True);skill.write_text('Existing custom skill')
        with self.assertRaises(ValueError):cli.install_skills(self.root,True)
        self.assertEqual(skill.read_text(),'Existing custom skill')
        self.assertFalse((self.root/'.agents').exists())

    def test_symlink_installation_preserved(self):
        dest=self.root/'elsewhere';dest.mkdir()
        (self.root/'.agents').symlink_to(dest,target_is_directory=True)
        with self.assertRaises(ValueError):cli.install_skills(self.root,True)
        self.assertEqual(list(dest.iterdir()),[])

    def test_parent_file_conflict_preflight_writes_no_skills(self):
        (self.root / '.claude').write_text('Existing file')
        with self.assertRaises(ValueError):
            cli.install_skills(self.root, True)
        self.assertEqual((self.root / '.claude').read_text(), 'Existing file')
        self.assertFalse((self.root / '.agents').exists())

    def test_boundary_is_session_specific(self):
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(cli.main(['boundary','--provider','claude','--session','a','--health',str(self.root)]),0)
        path=context.sample_path(self.root,'claude','a').with_suffix('.boundary.json')
        self.assertEqual(json.loads(path.read_text())['session_id'],'a')
        self.assertFalse(context.sample_path(self.root,'claude','b').exists())

    def test_template_cli(self):
        out=io.StringIO()
        with contextlib.redirect_stdout(out):self.assertEqual(cli.main(['snapshot','template']),0)
        self.assertIn('external_actions',json.loads(out.getvalue()))
