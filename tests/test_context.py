#!/usr/bin/env python3
"""Offline regressions for context readings across compaction and provider sessions."""
import datetime as dt
import json
from pathlib import Path
import tempfile
import unittest
import subprocess
import sys
from types import SimpleNamespace
from unittest.mock import patch

from threadhaven import context as sc


class ContextTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.now = sc.utcnow()

    def claude(self, sid='a', pct=90, current=True):
        return dict(session_id=sid, context_window=dict(context_window_size=1000,
                    used_percentage=pct, current_usage=dict(input_tokens=pct*10,
                    cache_creation_input_tokens=0, cache_read_input_tokens=0,
                    output_tokens=9000) if current else None))

    def rollout(self, rows, sid='codex-a'):
        path = self.root / 'rollout-a.jsonl'
        header = dict(type='session_meta', payload=dict(id=sid))
        path.write_text('\n'.join(json.dumps(x) for x in [header] + rows) + '\n')
        return path

    def count(self, tokens=900, capacity=1000, seconds=0, cumulative=90000000):
        return dict(type='event_msg', timestamp=(self.now+dt.timedelta(seconds=seconds)).isoformat(),
                    payload=dict(type='token_count', info=dict(model_context_window=capacity,
                    last_token_usage=dict(total_tokens=tokens, input_tokens=tokens-10,
                    output_tokens=10, cached_input_tokens=tokens-20),
                    total_token_usage=dict(total_tokens=cumulative))))

    def test_claude_uses_input_only_without_double_counting_output(self):
        sample = sc.claude_sample(self.claude(pct=40), self.now)
        self.assertEqual(sample['used_percentage'], 40)
        self.assertEqual(sample['used_tokens'], 400)

    def test_null_after_compact_overrides_old_high_percentage(self):
        sample = sc.claude_sample(self.claude(current=False), self.now)
        self.assertIsNone(sample['used_percentage'])
        self.assertEqual(sample['status'], 'unknown')

    def test_compaction_fence_invalidates_same_session_old_sample(self):
        sc.record_claude(self.claude(), self.now, self.root)
        sc.mark_compacted('claude', 'a', self.now, self.root)
        self.assertIsNone(sc.read_claude('a', self.root, self.now)['used_percentage'])
        after = self.now + dt.timedelta(seconds=1)
        sc.record_claude(self.claude(pct=20), after, self.root)
        self.assertEqual(sc.read_claude('a', self.root, after)['used_percentage'], 20)

    def test_fence_cannot_be_erased_by_racing_old_statusline(self):
        sc.mark_compacted('claude', 'a', self.now, self.root)
        sc.record_claude(self.claude(), self.now-dt.timedelta(seconds=1), self.root)
        self.assertIsNone(sc.read_claude('a', self.root, self.now)['used_percentage'])

    def test_sessions_do_not_overwrite_each_other(self):
        sc.record_claude(self.claude('a', 90), self.now, self.root)
        sc.record_claude(self.claude('b', 20), self.now, self.root)
        sc.mark_compacted('claude', 'a', self.now, self.root)
        self.assertIsNone(sc.read_claude('a', self.root, self.now)['used_percentage'])
        self.assertEqual(sc.read_claude('b', self.root, self.now)['used_percentage'], 20)

    def test_fresh_legacy_usage_requires_exact_session(self):
        (self.root/'usage.json').write_text(json.dumps(dict(_written=self.now.isoformat(), data=self.claude())))
        self.assertEqual(sc.read_claude('a', self.root, self.now)['used_percentage'], 90)
        self.assertIsNone(sc.read_claude('b', self.root, self.now)['used_percentage'])

    def test_old_usage_is_unknown_not_zero_or_a_warning(self):
        before = self.now - dt.timedelta(seconds=301)
        sc.record_claude(self.claude(), before, self.root)
        sample = sc.read_claude('a', self.root, self.now)
        self.assertEqual(sample['status'], 'stale')
        self.assertIsNone(sample['used_percentage'])

    def test_malformed_legacy_payload_is_unknown(self):
        (self.root/'usage.json').write_text(json.dumps(dict(_written=self.now.isoformat(), data=['broken'])))
        self.assertIsNone(sc.read_claude('a', self.root, self.now)['used_percentage'])
        bad = self.claude(pct=True)
        bad['context_window']['current_usage']['input_tokens'] = True
        self.assertIsNone(sc.claude_sample(bad)['used_percentage'])

    def test_codex_current_count_ignores_lifetime_and_cache_totals(self):
        path = self.rollout([self.count(tokens=400)])
        sample = sc.read_codex('codex-a', path, self.now)
        self.assertEqual(sample['used_percentage'], 40)
        self.assertEqual(sample['used_tokens'], 400)

    def test_codex_compaction_discards_prior_high_count(self):
        boundary = dict(type='compacted', timestamp=self.now.isoformat(),
                        payload=dict(latest_token_usage_record=dict(usage=dict(total_tokens=990))))
        path = self.rollout([self.count(), boundary])
        self.assertIsNone(sc.read_codex('codex-a', path, self.now)['used_percentage'])
        path = self.rollout([self.count(), boundary, self.count(200, seconds=1)])
        self.assertEqual(sc.read_codex('codex-a', path, self.now)['used_percentage'], 20)

    def test_codex_compacted_size_can_have_zero_components(self):
        row = self.count(200)
        row['payload']['info']['last_token_usage'].update(input_tokens=0, output_tokens=0)
        sample = sc.read_codex('codex-a', self.rollout([row]), self.now)
        self.assertEqual(sample['used_tokens'], 200)

    def test_late_precompaction_event_cannot_restore_old_warning(self):
        boundary = dict(type='compacted', timestamp=self.now.isoformat(), payload={})
        path = self.rollout([boundary, self.count(900, seconds=-1)])
        self.assertIsNone(sc.read_codex('codex-a', path, self.now)['used_percentage'])

    def test_invalid_numeric_telemetry_is_not_a_measurement(self):
        for value in (True, float('nan'), float('inf'), 10**1000):
            self.assertFalse(sc.number(value))

    def test_impossible_occupancy_is_unknown(self):
        self.assertIsNone(sc.read_codex('codex-a', self.rollout([self.count(1001)]), self.now)['used_percentage'])
        payload = self.claude(pct=101)
        self.assertIsNone(sc.claude_sample(payload, self.now)['used_percentage'])

    def test_corrupt_saved_claude_sample_does_not_crash(self):
        path = sc.sample_path(self.root, 'claude', 'a')
        path.parent.mkdir(parents=True)
        path.write_text(json.dumps(dict(session_id='a', used_percentage='broken', sampled_at=self.now.isoformat())))
        sample = sc.read_claude('a', self.root, self.now)
        self.assertIsNone(sample['used_percentage'])
        self.assertIn('unknown', sc.describe(sample))

    def test_codex_missing_capacity_never_guesses_model_limit(self):
        path = self.rollout([self.count(), self.count(200, capacity=None)])
        self.assertIsNone(sc.read_codex('codex-a', path, self.now)['used_percentage'])

    def test_codex_identity_mismatch_cannot_read_another_session(self):
        path = self.rollout([self.count()])
        self.assertIsNone(sc.read_codex('wrong', path, self.now)['used_percentage'])

    def test_codex_external_fence_and_stale_sample(self):
        path = self.rollout([self.count()])
        sc.mark_compacted('codex', 'codex-a', self.now, self.root)
        self.assertIsNone(sc.read_context('codex', 'codex-a', path, self.root, self.now)['used_percentage'])
        self.assertEqual(sc.read_codex('codex-a', path, self.now+dt.timedelta(seconds=301))['status'], 'stale')

    def test_tail_bound_and_incomplete_records(self):
        path = self.root/'bounded.jsonl'
        path.write_bytes(b'x'*100000 + b'\n' + json.dumps(self.count()).encode() + b'\n{"unfinished":')
        rows = list(sc.events_tail(path, limit=1024))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['payload']['type'], 'token_count')









if __name__ == '__main__':
    unittest.main()
