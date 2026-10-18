"""Local command interface. Every provider uses the same storage engine."""
import argparse
import json
from pathlib import Path
import sys
from importlib import resources
from . import __version__, snapshot, context


def install_skills(home, apply=False):
    home = home.resolve()
    targets = []
    for name in ('snapshot', 'context-check'):
        body = resources.files('threadhaven').joinpath('skills', name, 'SKILL.md').read_text(encoding='utf-8')
        for base in ('.agents', '.claude'):
            path = home / base / 'skills' / name / 'SKILL.md'
            if any(p.is_symlink() for p in [path, *path.parents] if p != home.parent):
                raise ValueError('Existing symlink installation is preserved: ' + str(path))
            if any(p.exists() and not p.is_dir() for p in path.parents):
                raise ValueError('Existing non-directory installation path is preserved: ' + str(path))
            if path.exists() and path.read_text(encoding='utf-8') != body:
                raise ValueError('Existing skill is preserved: ' + str(path))
            targets.append((path, body))
    # Preflight all destinations before writing any skill.
    for path, body in targets:
        if apply:
            path.parent.mkdir(parents=True, exist_ok=True)
            snapshot.atomic_write(path, body.encode('utf-8'))
        print(('installed: ' if apply else 'would install: ') + str(path))


def main(argv=None):
    args = list(sys.argv[1:] if argv is None else argv)
    if args and args[0] == 'snapshot':
        return snapshot.main(args[1:])
    if args and args[0] == 'context':
        return context.main(args[1:])
    p = argparse.ArgumentParser(description='Threadhaven: keep small checked task handovers across Codex and Claude.')
    p.add_argument('--version', action='version', version=__version__)
    sub = p.add_subparsers(dest='command')
    sub.add_parser('snapshot', help='template, save, read, check, history and due')
    sub.add_parser('context', help='read provider context telemetry')
    s = sub.add_parser('skills', help='preview or install skill files, preserving existing installations')
    s.add_argument('--home', type=Path, default=Path.home())
    s.add_argument('--apply', action='store_true')
    s = sub.add_parser('sample', help='record one Claude statusline sample from standard input')
    s.add_argument('--health', type=Path, default=context.HEALTH)
    s = sub.add_parser('boundary', help='invalidate samples when native compaction completes')
    s.add_argument('--provider', required=True, choices=('claude', 'codex'))
    s.add_argument('--session', required=True)
    s.add_argument('--health', type=Path, default=context.HEALTH)
    a = p.parse_args(args)
    try:
        if a.command == 'skills':
            install_skills(a.home.expanduser().absolute(), a.apply)
        elif a.command == 'sample':
            raw = sys.stdin.buffer.read(262145)
            if len(raw) > 262144:
                raise ValueError('Sample exceeds 256 KiB.')
            data = json.loads(raw)
            if not isinstance(data, dict) or not isinstance(data.get('session_id'), str) or not data['session_id'].strip() or len(data['session_id']) > 200:
                raise ValueError('Sample requires a session ID.')
            context.record_claude(data, health=a.health)
            print('Context sample recorded.')
        elif a.command == 'boundary':
            if not a.session.strip() or len(a.session) > 200:
                raise ValueError('Use a non-empty bounded session ID.')
            context.mark_compacted(a.provider, a.session, health=a.health)
            print('Previous context sample invalidated.')
        else:
            p.print_help()
        return 0
    except (ValueError, OSError):
        # Input errors can contain private content. Keep the diagnostic generic.
        print('threadhaven: input or installation conflict. Existing skills are preserved. Check paths and input format.', file=sys.stderr)
        return 2
