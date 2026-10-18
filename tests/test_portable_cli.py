"""Portable command-line scenarios, independent of any private tracker integration."""
import datetime as dt
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from threadhaven import context, snapshot


class PortableCliTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        self.command = [sys.executable, '-m', 'threadhaven']

    def run_cli(self, *args, data=None):
        return subprocess.run(self.command + list(args), input=data, capture_output=True, text=True)

    def test_module_entrypoint_exposes_version(self):
        result = self.run_cli('--version')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), '0.1.0rc1')

    def test_sample_cli_uses_only_selected_metadata(self):
        payload = {'session_id': 'sample-a', 'private_text': 'not retained', 'context_window': {
            'context_window_size': 1000, 'current_usage': {'input_tokens': 200,
            'cache_creation_input_tokens': 50, 'cache_read_input_tokens': 100, 'output_tokens': 9000}}}
        result = self.run_cli('sample', '--health', str(self.root), data=json.dumps(payload))
        self.assertEqual(result.returncode, 0, result.stderr)
        stored = context.sample_path(self.root, 'claude', 'sample-a').read_text()
        self.assertNotIn('not retained', stored)
        reading = self.run_cli('context', '--provider', 'claude', '--session', 'sample-a', '--health', str(self.root), '--json')
        self.assertEqual(json.loads(reading.stdout)['used_tokens'], 350)

    def test_oversized_sample_is_rejected_without_writes(self):
        result = self.run_cli('sample', '--health', str(self.root), data='x' * 262145)
        self.assertEqual(result.returncode, 2)
        self.assertEqual(list(self.root.iterdir()), [])
        self.assertNotIn('x' * 100, result.stderr)

    def test_invalid_sample_is_bounded_error(self):
        for payload in ('not json', '[]', '{"session_id":""}', json.dumps({'session_id': 'x' * 201})):
            result = self.run_cli('sample', '--health', str(self.root), data=payload)
            self.assertEqual(result.returncode, 2)
            self.assertNotIn('Traceback', result.stderr)
        self.assertEqual(list(self.root.iterdir()), [])

    def test_context_missing_identity_never_creates_sample(self):
        result = self.run_cli('context', '--provider', 'claude', '--session', 'missing', '--health', str(self.root), '--json')
        self.assertEqual(result.returncode, 0)
        self.assertEqual(json.loads(result.stdout)['status'], 'unknown')
        self.assertEqual(list(self.root.iterdir()), [])

    def test_codex_explicit_rollout_and_boundary_end_to_end(self):
        stamp = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(seconds=1)).isoformat()
        transcript = self.root / 'rollout.jsonl'
        rows = [{'type': 'session_meta', 'payload': {'id': 'codex-fixture'}},
                {'type': 'event_msg', 'timestamp': stamp, 'payload': {'type': 'token_count', 'info': {
                    'model_context_window': 1000, 'last_token_usage': {'total_tokens': 250}}}}]
        transcript.write_text('\n'.join(map(json.dumps, rows)) + '\n')
        args = ['context', '--provider', 'codex', '--session', 'codex-fixture', '--transcript', str(transcript), '--health', str(self.root), '--json']
        self.assertEqual(json.loads(self.run_cli(*args).stdout)['used_percentage'], 25)
        self.assertEqual(self.run_cli('boundary', '--provider', 'codex', '--session', 'codex-fixture', '--health', str(self.root)).returncode, 0)
        self.assertIsNone(json.loads(self.run_cli(*args).stdout)['used_percentage'])

    def test_install_conflict_cli_preserves_existing_content(self):
        path = self.root / '.claude/skills/snapshot/SKILL.md'
        path.parent.mkdir(parents=True)
        path.write_text('Custom installation')
        result = self.run_cli('skills', '--home', str(self.root), '--apply')
        self.assertEqual(result.returncode, 2)
        self.assertFalse((self.root / '.agents').exists())
        self.assertEqual(path.read_text(), 'Custom installation')

    def test_two_process_writers_have_one_winner(self):
        store, repo = self.root / 'store', self.root / 'repo'
        repo.mkdir()
        state = snapshot.template()
        original = snapshot.save(store, 'demo', 'race', 'codex', 'initial', repo, 'none', state)
        processes = []
        for label in ('a', 'b'):
            draft = self.root / (label + '.json')
            state['progress'] = [label]
            draft.write_bytes(snapshot.encoded(state))
            args = self.command + ['snapshot', '--store', str(store), 'save', '--project', 'demo', '--task', 'race',
                                   '--repo', str(repo), '--provider', 'codex', '--session', label,
                                   '--base', original['id'], '--input', str(draft)]
            processes.append(subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True))
        for process in processes:
            process.communicate(timeout=15)
        self.assertEqual(sorted(process.returncode for process in processes), [0, 2])
        folder = snapshot.location(store, 'demo', 'race')
        self.assertIn(snapshot.read_record(folder)['state']['progress'], [['a'], ['b']])
        self.assertEqual(len(list(folder.glob('20*.json'))), 2)
        self.assertTrue((self.root / 'a.json').is_file())
        self.assertTrue((self.root / 'b.json').is_file())
