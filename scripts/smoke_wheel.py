#!/usr/bin/env python3
"""Build twice, validate archives, then exercise an installed wheel outside source."""
import base64
import csv
import hashlib
import io
import json
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile
import venv
import zipfile

from build_release import ROOT, VERSION, build


def run(command, cwd, **kwargs):
    result = subprocess.run(command, cwd=str(cwd), capture_output=True, text=True, **kwargs)
    if result.returncode:
        raise RuntimeError('Command failed: ' + ' '.join(map(str, command)) + '\n' + result.stdout + result.stderr)
    return result.stdout


def main():
    with tempfile.TemporaryDirectory(prefix='threadhaven-wheel-') as temporary:
        root = Path(temporary).resolve()
        first = build(root / 'first')
        second = build(root / 'second')
        assert [p.read_bytes() for p in first] == [p.read_bytes() for p in second], 'Build is not reproducible'
        wheel = first[0]
        with zipfile.ZipFile(wheel) as archive:
            names = archive.namelist()
            assert len(names) == len(set(names))
            record = next(name for name in names if name.endswith('.dist-info/RECORD'))
            for name, digest, length in csv.reader(io.StringIO(archive.read(record).decode())):
                if name == record:
                    continue
                data = archive.read(name)
                actual = base64.urlsafe_b64encode(hashlib.sha256(data).digest()).rstrip(b'=').decode()
                assert digest == 'sha256=' + actual and len(data) == int(length), name
            assert sum(name.endswith('/SKILL.md') for name in names) == 5
            assert not any('__pycache__' in name or name.endswith('.pyc') for name in names)
        with zipfile.ZipFile(first[1]) as archive:
            source_names = archive.namelist()
        with tarfile.open(first[2], 'r:gz') as archive:
            assert sorted(source_names) == sorted(archive.getnames())
        assert any(name.endswith('/examples/demo.py') for name in source_names)
        assert all(not Path(name).is_absolute() and '..' not in Path(name).parts for name in source_names)
        environment = root / 'environment'
        venv.EnvBuilder(with_pip=True).create(environment)
        python = environment / ('Scripts/python.exe' if sys.platform == 'win32' else 'bin/python')
        outside = root / 'outside-source'
        outside.mkdir()
        run([str(python), '-m', 'pip', 'install', '--no-index', '--disable-pip-version-check', str(wheel)], outside)
        print(run([str(python), '-I', '-c', 'import threadhaven; from importlib.metadata import version; assert threadhaven.__version__ == version("threadhaven"); print(threadhaven.__file__)'], outside).strip())
        assert run([str(python), '-I', '-m', 'threadhaven', '--version'], outside).strip() == VERSION
        print(run([str(python), '-I', str(ROOT / 'examples/demo.py')], outside).strip())
        home = outside / 'home'
        run([str(python), '-I', '-m', 'threadhaven', 'skills', '--home', str(home), '--apply'], outside)
        assert len(list(home.glob('*/skills/*/SKILL.md'))) == 10
        template = json.loads(run([str(python), '-I', '-m', 'threadhaven', 'snapshot', 'template'], outside))
        assert set(template) == {'goal', 'progress', 'decisions', 'constraints', 'open', 'next_action', 'evidence', 'external_actions'}
        result = json.loads(run([str(python), '-I', '-m', 'threadhaven', 'context', '--provider', 'claude', '--session', 'wheel-smoke', '--health', str(outside / 'health'), '--json'], outside))
        assert result['status'] == 'unknown' and result['used_percentage'] is None
        assert not (outside / 'health').exists()
        print('PASS: reproducible archives, wheel RECORD, clean installation, skills, recovery demo and context CLI.')


if __name__ == '__main__':
    main()
