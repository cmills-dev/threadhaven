#!/usr/bin/env python3
"""Offline recovery scenarios for shared_snapshot; all files live in temporary storage."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from threadhaven import snapshot as ss


class RecoveryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name).resolve()
        self.store = self.root / 'vault'
        self.repo = self.root / 'repo'
        self.repo.mkdir()
        (self.repo / 'result.txt').write_text('original evidence')
        self.state = ss.template()
        self.state.update(goal='Ship the parser', decisions=['Use a local CLI.'],
                          constraints=['Keep the original source.'], progress=['Parser written.'],
                          open=['Run the malformed-input case.'], next_action='Run the malformed-input case.',
                          evidence=[{'kind': 'file', 'ref': 'result.txt', 'claim': 'Current parser output'}],
                          external_actions=[{'description': 'Send launch email', 'status': 'unknown', 'receipt': ''}])

    def tearDown(self):
        self.tmp.cleanup()

    def save(self, provider='codex', base='none', state=None):
        return ss.save(self.store, 'demo', 'parser', provider, provider + '-session', self.repo, base, state or self.state)

    def folder(self):
        return ss.location(self.store, 'demo', 'parser')

    def test_codex_to_claude_to_codex_without_history(self):
        a = self.save()
        r = ss.read_record(self.folder())
        self.assertEqual(r['state']['decisions'], self.state['decisions'])
        self.assertEqual(r['state']['external_actions'][0]['status'], 'unknown')
        s = copy.deepcopy(r['state'])
        s['progress'].append('Malformed input tested by Claude.')
        b = self.save('claude', a['id'], s)
        r = ss.read_record(self.folder())
        self.assertEqual(r['provider'], 'claude')
        self.assertEqual(r['parent'], a['id'])
        self.assertEqual(r['state']['constraints'], self.state['constraints'])
        self.assertEqual(ss.read_record(self.folder(), a['id'])['provider'], 'codex')
        self.assertLess(b['bytes'], ss.MAX_BYTES)

    def test_stale_writer_keeps_winner_and_draft(self):
        a = self.save()
        b = self.save('claude', a['id'])
        draft = copy.deepcopy(self.state)
        draft['open'].append('Codex discovered a second issue.')
        with self.assertRaisesRegex(ss.SnapshotError, 'Stale base'):
            self.save('codex', a['id'], draft)
        self.assertEqual(ss.head(self.folder())['id'], b['id'])
        self.assertIn('Codex discovered a second issue.', draft['open'])
        self.assertEqual(len(list(self.folder().glob('20*.json'))), 2)

    def test_changed_and_missing_evidence_is_visible(self):
        self.save()
        r = ss.read_record(self.folder())
        self.assertIn('UNCHANGED: result.txt', ss.evidence_status(r, self.repo))
        (self.repo / 'result.txt').write_text('later edit')
        self.assertIn('CHANGED: result.txt', ss.evidence_status(r, self.repo))
        (self.repo / 'result.txt').unlink()
        self.assertIn('MISSING_OR_UNREADABLE: result.txt', ss.evidence_status(r, self.repo))

    def test_unverified_url_is_not_live_proof(self):
        self.state['evidence'].append({'kind': 'url', 'ref': 'https://example.com/release', 'claim': 'Release receipt'})
        self.save()
        r = ss.read_record(self.folder())
        self.assertIn('UNVERIFIED_URL: https://example.com/release', ss.evidence_status(r, self.repo))

    def test_corrupt_record_blocks_read_and_overwrite(self):
        a = self.save()
        p = Path(a['path'])
        e = json.loads(p.read_text())
        e['record']['state']['goal'] = 'silently changed'
        p.write_text(json.dumps(e))
        with self.assertRaisesRegex(ss.SnapshotError, 'checksum'):
            ss.read_record(self.folder())
        with self.assertRaisesRegex(ss.SnapshotError, 'checksum'):
            self.save(base=a['id'])

    def test_wrong_pointer_checksum(self):
        self.save()
        p = self.folder() / 'HEAD.json'
        h = json.loads(p.read_text())
        h['sha256'] = '0' * 64
        p.write_text(json.dumps(h))
        with self.assertRaisesRegex(ss.SnapshotError, 'pointer checksum'):
            ss.read_record(self.folder())

    def test_evidence_hashes_cannot_silently_omit_file_checks(self):
        saved = self.save()
        path = Path(saved['path'])
        envelope = json.loads(path.read_text())
        envelope['record']['file_hashes'] = {}
        envelope['sha256'] = ss.digest(ss.encoded(envelope['record']))
        path.write_bytes(ss.encoded(envelope))
        (self.folder() / 'HEAD.json').write_bytes(ss.encoded({'id': saved['id'], 'sha256': envelope['sha256']}))
        with self.assertRaisesRegex(ss.SnapshotError, 'fingerprints'):
            ss.read_record(self.folder())

    def test_busy_lock_preserves_state(self):
        a = self.save()
        (self.folder() / '.write-lock').mkdir()
        with self.assertRaisesRegex(ss.SnapshotError, 'busy'):
            self.save(base=a['id'])
        self.assertEqual(ss.head(self.folder())['id'], a['id'])

    def test_missing_task_read_does_not_create_it(self):
        folder = ss.location(self.store, 'demo', 'missing')
        with self.assertRaises(ss.SnapshotError):
            ss.read_record(folder)
        self.assertFalse(folder.exists())

    def test_paths_stay_within_project(self):
        for ref in ('../outside.txt', '/etc/passwd'):
            with self.subTest(ref=ref), self.assertRaises(ss.SnapshotError):
                ss.file_path(self.repo, ref)
        with self.assertRaises(ss.SnapshotError):
            ss.location(self.store, '../escape', 'demo')

    def test_symlink_evidence_and_store_rejected(self):
        (self.repo / 'link').symlink_to(self.repo / 'result.txt')
        with self.assertRaises(ss.SnapshotError):
            ss.fingerprint(self.repo, 'link')
        alias = self.root / 'alias'
        alias.symlink_to(self.repo)
        with self.assertRaises(ss.SnapshotError):
            ss.location(alias, 'demo', 'parser', True)

    def test_full_transcript_and_unknown_fields_rejected(self):
        self.state['transcript'] = 'lots of history'
        with self.assertRaisesRegex(ss.SnapshotError, 'exactly the fields'):
            self.save()

    def test_large_state_rejected_without_silent_truncation(self):
        self.state['progress'] = ['x' * 600 for _ in range(12)]
        self.state['decisions'] = ['y' * 600 for _ in range(12)]
        with self.assertRaises(ss.SnapshotError):
            self.save()
        self.assertFalse(self.store.exists())

    def test_verified_action_requires_receipt(self):
        self.state['external_actions'][0]['status'] = 'verified'
        with self.assertRaisesRegex(ss.SnapshotError, 'receipt'):
            self.save()

    def test_common_secret_patterns_rejected_without_echo(self):
        self.state['progress'] = ['api_key=' + 'synthetic_fixture_value']
        with self.assertRaisesRegex(ss.SnapshotError, 'Possible credential') as e:
            self.save()
        self.assertNotIn('synthetic_fixture_value', str(e.exception))

    def test_pointer_failure_retains_previous_head(self):
        a = self.save()
        original = ss.atomic_write
        def fail_head(path, data):
            if path.name == 'HEAD.json':
                raise OSError('fixture disk error')
            return original(path, data)
        with patch.object(ss, 'atomic_write', fail_head), self.assertRaises(OSError):
            self.save('claude', a['id'])
        self.assertEqual(ss.read_record(self.folder())['id'], a['id'])
        self.assertEqual(len(list(self.folder().glob('20*.json'))), 2)

    def test_cli_roundtrip_and_due(self):
        draft = self.root / 'draft.json'
        draft.write_bytes(ss.encoded(self.state))
        cli = [sys.executable, str(Path(ss.__file__).resolve()), '--store', str(self.store)]
        args = ['--project', 'demo', '--task', 'parser']
        r = subprocess.run(cli + ['save'] + args + ['--provider', 'codex', '--session', 'fixture', '--base', 'none', '--repo', str(self.repo), '--input', str(draft)], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        for cmd in ('read', 'check', 'history', 'due'):
            extra = ['--repo', str(self.repo)] if cmd in ('read', 'check') else []
            p = subprocess.run(cli + [cmd] + args + extra, capture_output=True, text=True)
            self.assertEqual(p.returncode, 0, p.stderr)
            self.assertTrue(p.stdout)
        self.assertTrue(draft.exists())


if __name__ == '__main__':
    unittest.main(verbosity=2)
