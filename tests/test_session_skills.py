"""Session skills: files parse, named commands exist, and the scripted round trip works."""
import contextlib
import io
import json
from pathlib import Path
import re
import shlex
import subprocess
import sys
import tempfile
import unittest
from threadhaven import cli, snapshot

SKILLS = Path(__file__).resolve().parents[1] / 'threadhaven' / 'skills'
SESSION = ('initiate', 'checkpoint', 'close')
SUBCOMMANDS = {'template', 'save', 'read', 'check', 'history', 'due'}


def front_matter(text):
    match = re.match(r'---\nname: (\S+)\ndescription: (.+)\n---\n', text)
    return match.groups() if match else None


class SessionSkillTests(unittest.TestCase):
    def test_skill_files_exist_and_parse(self):
        for name in SESSION:
            text = (SKILLS / name / 'SKILL.md').read_text(encoding='utf-8')
            parsed = front_matter(text)
            self.assertIsNotNone(parsed, name)
            self.assertEqual(parsed[0], name)
            self.assertIn('/' + name, text)
            self.assertIn('$' + name, text)
            self.assertIn(name, cli.SKILLS)

    def test_named_commands_are_real_subcommands(self):
        for name in SESSION:
            text = (SKILLS / name / 'SKILL.md').read_text(encoding='utf-8')
            used = set(re.findall(r'threadhaven snapshot (\w+)', text))
            self.assertTrue(used, name)
            self.assertLessEqual(used, SUBCOMMANDS, name)
            for sub in used:
                done = subprocess.run([sys.executable, '-m', 'threadhaven', 'snapshot', sub, '--help'],
                                      capture_output=True, text=True)
                self.assertEqual(done.returncode, 0, sub)

    def test_every_command_line_parses_with_the_real_parser(self):
        samples = {'PROVIDER': 'claude', 'PROJECT': 'demo', 'TASK': 'parser', 'REPOSITORY': '.',
                   'SESSION_ID': 's1', 'BASE_ID': 'none', 'DRAFT_JSON': 'draft.json', 'SAVED_ID': 'x'}
        parser = snapshot.build_parser()
        for name in SESSION:
            text = (SKILLS / name / 'SKILL.md').read_text(encoding='utf-8')
            lines = re.findall(r'`(threadhaven snapshot [^`]+)`', text)
            self.assertTrue(lines, name)
            for line in lines:
                words = [samples.get(word, word) for word in shlex.split(line)[2:]]
                try:
                    with contextlib.redirect_stderr(io.StringIO()):
                        parser.parse_args(words)
                except SystemExit:
                    self.fail(name + ' has a command line the CLI rejects: ' + line)

    def test_skills_are_generic(self):
        for name in SESSION:
            text = (SKILLS / name / 'SKILL.md').read_text(encoding='utf-8')
            for private in ('/Users/', 'MASTER.md', 'life tracker', '_meta'):
                self.assertNotIn(private, text)

    def test_installation_includes_session_skills(self):
        with tempfile.TemporaryDirectory() as temp:
            home = Path(temp)
            with contextlib.redirect_stdout(io.StringIO()):
                cli.install_skills(home, True)
            for base in ('.agents', '.claude'):
                for name in SESSION:
                    self.assertTrue((home / base / 'skills' / name / 'SKILL.md').is_file())


class RoundTripTests(unittest.TestCase):
    """Run the commands that checkpoint, close and initiate name, in order."""

    def run_cli(self, *args):
        done = subprocess.run([sys.executable, '-m', 'threadhaven', 'snapshot', '--store', str(self.store), *args],
                              capture_output=True, text=True)
        self.assertEqual(done.returncode, 0, done.stderr)
        return done.stdout

    def save(self, provider, base, goal):
        state = json.loads(self.run_cli('template'))
        state['goal'] = goal
        state['next_action'] = 'Resume at the parser'
        state['evidence'] = [{'kind': 'file', 'ref': 'notes.txt', 'claim': 'Working notes'}]
        draft = self.root / 'draft.json'
        draft.write_text(json.dumps(state))
        out = self.run_cli('save', '--project', 'demo', '--task', 'parser', '--provider', provider,
                           '--session', provider + '-1', '--repo', str(self.repo), '--base', base,
                           '--input', str(draft))
        return json.loads(out)['id']

    def test_checkpoint_close_initiate_round_trip(self):
        with tempfile.TemporaryDirectory() as temp:
            self.root = Path(temp).resolve()
            self.store, self.repo = self.root / 'store', self.root / 'repo'
            self.repo.mkdir()
            (self.repo / 'notes.txt').write_text('notes')
            first = self.save('claude', 'none', 'Finish the parser')
            second = self.save('claude', first, 'Finish the parser, step two')
            args = ('--project', 'demo', '--task', 'parser', '--repo', str(self.repo))
            read = self.run_cli('read', *args)
            checked = json.loads(self.run_cli('check', *args))
            self.assertIn('Snapshot ID: ' + second, read)
            self.assertIn('step two', read)
            self.assertEqual(checked['id'], second)
            self.assertEqual(checked['integrity'], 'verified')
            self.assertEqual(self.run_cli('history', '--project', 'demo', '--task', 'parser').split()[0], second)
            # A receiving provider reads the same newest ID and detects changed evidence.
            (self.repo / 'notes.txt').write_text('changed')
            stale = json.loads(self.run_cli('check', *args))
            self.assertEqual(stale['id'], second)
            self.assertIn('CHANGED: notes.txt', stale['evidence'])


if __name__ == '__main__':
    unittest.main()
