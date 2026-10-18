#!/usr/bin/env python3
"""Read current context telemetry, keeping provider/session/compaction boundaries separate."""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import math
import os
from pathlib import Path
import sys
import tempfile

HEALTH = Path(os.environ.get('THREADHAVEN_CONTEXT', str(Path.home() / '.local/share/threadhaven/telemetry')))
MAX_TAIL = 8 * 1024 * 1024
FRESH_SECONDS = 300


def number(value):
    try:
        return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)
    except OverflowError:
        return False


def instant(value):
    try:
        value = dt.datetime.fromisoformat(str(value).replace('Z', '+00:00'))
        return value if value.tzinfo else None
    except (ValueError, TypeError):
        return None


def utcnow():
    return dt.datetime.now(dt.timezone.utc)


def read_json(path):
    try:
        if path.is_symlink() or path.stat().st_size > 262144:
            return {}
        data = json.loads(path.read_text())
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def atomic_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp = tempfile.mkstemp(prefix='.context-', dir=str(path.parent))
    try:
        with os.fdopen(fd, 'w') as stream:
            json.dump(value, stream, allow_nan=False)
            stream.write('\n')
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp, path)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


def sample_path(health, provider, session):
    key = hashlib.sha256(str(session).encode()).hexdigest()
    return Path(health) / 'context' / provider / (key + '.json')


def empty(provider, session, reason):
    return dict(provider=provider, session_id=session, used_tokens=None, capacity=None,
                used_percentage=None, sampled_at=None, status='unknown', reason=reason,
                source=None, compacted_at=None)


def finish(sample, now=None):
    now = now or utcnow()
    at = instant(sample.get('sampled_at'))
    if sample.get('used_percentage') is None:
        return sample
    if not at or not -5 <= (now - at).total_seconds() <= FRESH_SECONDS:
        sample.update(status='stale', reason='No fresh context sample. Saved percentage is historical.',
                      used_percentage=None, used_tokens=None)
    else:
        sample['status'] = 'measured'
    return sample


def valid_saved_sample(sample, session):
    """Corrupt local telemetry remains unknown instead of becoming a percentage."""
    if sample.get('provider') != 'claude' or sample.get('session_id') != session:
        return False
    if sample.get('status') not in ('unknown', 'stale', 'measured'):
        return False
    if not isinstance(sample.get('reason'), str) or len(sample['reason']) > 1000:
        return False
    if sample.get('source') != 'claude_statusline' or not instant(sample.get('sampled_at')):
        return False
    pct, used, capacity = (sample.get(k) for k in ('used_percentage', 'used_tokens', 'capacity'))
    if capacity is not None and (not number(capacity) or capacity <= 0):
        return False
    if pct is not None and (not number(pct) or not 0 <= pct <= 100):
        return False
    if used is not None and (not number(used) or used < 0 or capacity is None or used > capacity):
        return False
    return True


def claude_sample(data, at=None):
    at = at or utcnow()
    if not isinstance(data, dict):
        return empty('claude', '', 'Invalid Claude context payload.')
    sid = str(data.get('session_id') or '')
    out = empty('claude', sid, 'Awaiting a current usage sample, possibly after compaction.')
    out.update(sampled_at=at.isoformat(), source='claude_statusline')
    cw = data.get('context_window') or {}
    if not isinstance(cw, dict):
        return out
    capacity = cw.get('context_window_size')
    if number(capacity) and capacity > 0:
        out['capacity'] = capacity
    # Claude explicitly clears this object after /compact. A leftover percentage is invalid.
    if 'current_usage' in cw and cw['current_usage'] is None:
        return out
    usage = cw.get('current_usage')
    if isinstance(usage, dict) and out['capacity']:
        values = [usage.get(k) for k in ('input_tokens', 'cache_creation_input_tokens',
                                       'cache_read_input_tokens')]
        if all(number(x) and x >= 0 for x in values) and sum(values) <= capacity:
            out['used_tokens'] = sum(values)
            out['used_percentage'] = 100 * sum(values) / capacity
    if out['used_percentage'] is None:
        pct = cw.get('used_percentage')
        if number(pct) and 0 <= pct <= 100:
            out['used_percentage'] = pct
    if out['used_percentage'] is not None:
        out.update(status='measured', reason='Current input occupancy from Claude statusline.')
    return out


def record_claude(data, now=None, health=HEALTH):
    now = now or utcnow()
    sid = str(data.get('session_id') or '')
    if not sid:
        return
    # Samples and fences are separate files: a racing statusline cannot erase the fence.
    atomic_json(sample_path(health, 'claude', sid), claude_sample(data, now))


def mark_compacted(provider, session, now=None, health=HEALTH):
    if provider not in ('claude', 'codex') or not session:
        return
    path = sample_path(health, provider, session).with_suffix('.boundary.json')
    atomic_json(path, dict(session_id=session, compacted_at=(now or utcnow()).isoformat()))


def provider_from_payload(payload):
    explicit = payload.get('provider')
    if explicit in ('claude', 'codex'):
        return explicit
    path = str(payload.get('transcript_path') or '')
    return 'codex' if '/.codex/' in path or Path(path).name.startswith('rollout-') else 'claude'


def read_claude(session, health=HEALTH, now=None):
    now = now or utcnow()
    saved = read_json(sample_path(health, 'claude', session))
    if not valid_saved_sample(saved, session):
        # Compatibility with an older statusline, only for this session and a fresh envelope.
        raw = read_json(Path(health) / 'usage.json')
        data = raw.get('data') or {}
        if not isinstance(data, dict):
            data = {}
        at = instant(raw.get('_written'))
        saved = claude_sample(data, at) if at and data.get('session_id') == session else {}
    if not saved:
        saved = empty('claude', session, 'No sample for this Claude session.')
    fence = read_json(sample_path(health, 'claude', session).with_suffix('.boundary.json'))
    boundary = instant(fence.get('compacted_at')) if fence.get('session_id') == session else None
    at = instant(saved.get('sampled_at'))
    if boundary:
        saved['compacted_at'] = boundary.isoformat()
        if not at or at <= boundary:
            saved.update(status='unknown', used_tokens=None, used_percentage=None,
                         reason='Compaction completed. Awaiting a new context sample.')
    return finish(saved, now)


def events_tail(path, limit=MAX_TAIL):
    """Bound memory and discard partial lines. Transcript text is never returned or stored."""
    try:
        with Path(path).open('rb') as stream:
            stream.seek(0, 2)
            size = stream.tell()
            stream.seek(max(0, size - limit))
            raw = stream.read(limit)
            if size > limit:
                raw = raw.partition(b'\n')[2]
    except OSError:
        return
    for line in raw.splitlines():
        try:
            data = json.loads(line)
            if isinstance(data, dict):
                yield data
        except (ValueError, UnicodeError):
            continue


def read_codex(session, transcript, now=None):
    out = empty('codex', session, 'No current Codex token_count sample with a reported capacity.')
    if not transcript:
        return out
    identity = None
    # Verify identity from the first record as a tail can omit session_meta.
    try:
        with Path(transcript).open('rb') as stream:
            first = json.loads(stream.readline(262144))
        if first.get('type') == 'session_meta':
            identity = (first.get('payload') or {}).get('id')
    except (OSError, ValueError, AttributeError):
        return out
    if identity != session:
        out['reason'] = 'Transcript identity does not match this Codex session.'
        return out
    for event in events_tail(transcript):
        payload = event.get('payload') or {}
        if not isinstance(payload, dict):
            continue
        if event.get('type') == 'compacted':
            out = empty('codex', session, 'Compaction completed. Awaiting a new context sample.')
            out['compacted_at'] = event.get('timestamp')
            # latest_token_usage_record here describes the compaction request, not its result.
        elif event.get('type') == 'event_msg' and payload.get('type') == 'token_count':
            info = payload.get('info') or {}
            if not isinstance(info, dict):
                continue
            last = info.get('last_token_usage') or {}
            capacity = info.get('model_context_window')
            used = last.get('total_tokens') if isinstance(last, dict) else None
            boundary = instant(out.get('compacted_at'))
            sampled = instant(event.get('timestamp'))
            if boundary and (not sampled or sampled <= boundary):
                continue
            if number(capacity) and capacity > 0 and number(used) and 0 <= used <= capacity:
                out.update(used_tokens=used, capacity=capacity, used_percentage=100 * used / capacity,
                           sampled_at=event.get('timestamp'), source='codex_token_count',
                           reason='Latest runtime context estimate, not lifetime billing tokens.')
            else:
                # A newer unknown sample invalidates an earlier measurement.
                out.update(used_tokens=None, capacity=None, used_percentage=None, status='unknown',
                           sampled_at=event.get('timestamp'), source='codex_token_count',
                           reason='Latest Codex sample lacks usable current tokens or capacity.')
    return finish(out, now)


def find_codex(session, home=None):
    # Require an exact, bounded filename identity, with no traversal or arbitrary glob input.
    if not session or len(session) > 100 or any(c not in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-' for c in session):
        return None
    paths = list(((home or Path.home()) / '.codex/sessions').glob('*/*/*/rollout-*-' + session + '.jsonl'))
    return max(paths, key=lambda p: p.stat().st_mtime) if paths else None


def read_context(provider, session, transcript=None, health=HEALTH, now=None):
    if provider == 'claude':
        return read_claude(session, health, now)
    sample = read_codex(session, transcript or find_codex(session), now)
    fence = read_json(sample_path(health, provider, session).with_suffix('.boundary.json'))
    boundary = instant(fence.get('compacted_at')) if fence.get('session_id') == session else None
    at = instant(sample.get('sampled_at'))
    if boundary and (not at or at <= boundary):
        sample.update(status='unknown', used_tokens=None, used_percentage=None,
                      compacted_at=boundary.isoformat(),
                      reason='Compaction completed. Awaiting a new context sample.')
    return sample


def describe(sample):
    name = 'Codex' if sample['provider'] == 'codex' else 'Claude'
    pct = sample.get('used_percentage')
    if pct is None:
        return name + ' context: ' + sample['status'] + '. ' + sample['reason']
    label = 'context estimate' if sample['provider'] == 'codex' else 'context'
    text = f"{name} {label}: {pct:.1f}%"
    if sample.get('used_tokens') is not None and sample.get('capacity'):
        text += f" ({sample['used_tokens']:,.0f}/{sample['capacity']:,.0f} tokens)"
    text += f". Sampled {sample['sampled_at']}."
    if pct >= 80:
        text += ' Save changed tasks with snapshot and checkpoint when a fuller handover is needed.'
    return text


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--provider', required=True, choices=('claude', 'codex'))
    ap.add_argument('--session', required=True)
    ap.add_argument('--transcript', type=Path)
    ap.add_argument('--json', action='store_true')
    ap.add_argument('--health', type=Path, default=HEALTH)
    args = ap.parse_args(argv)
    if not args.session.strip() or len(args.session) > 200:
        ap.error('Use a non-empty session ID of at most 200 characters.')
    result = read_context(args.provider, args.session, args.transcript, health=args.health)
    print(json.dumps(result, allow_nan=False) if args.json else describe(result))
    return 0


if __name__ == '__main__':
    sys.exit(main())
