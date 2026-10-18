#!/usr/bin/env python3
"""Build a deterministic pure-Python wheel and source archives without build dependencies."""
import base64
import csv
import hashlib
import io
from pathlib import Path
import tarfile
import zipfile
import gzip
ROOT=Path(__file__).resolve().parents[1]
VERSION='0.1.0rc1'
NAME='threadhaven-'+VERSION
INFO='threadhaven-'+VERSION+'.dist-info'

def sha(data):return hashlib.sha256(data).hexdigest()
def build(output=None):
    out=Path(output) if output is not None else ROOT/'dist'
    out.mkdir(parents=True,exist_ok=True)
    files={str(p.relative_to(ROOT)).replace('\\','/'):p.read_bytes() for p in sorted((ROOT/'threadhaven').rglob('*')) if p.is_file() and '__pycache__' not in p.parts and p.suffix!='.pyc'}
    files[INFO+'/METADATA']=(f'Metadata-Version: 2.1\nName: threadhaven\nVersion: {VERSION}\nSummary: Small checked task handovers for Codex and Claude Code\nRequires-Python: >=3.9\nLicense: MIT\nDescription-Content-Type: text/markdown\n\n'+(ROOT/'README.md').read_text()).encode()
    files[INFO+'/WHEEL']=b'Wheel-Version: 1.0\nGenerator: threadhaven-release\nRoot-Is-Purelib: true\nTag: py3-none-any\n'
    files[INFO+'/entry_points.txt']=b'[console_scripts]\nthreadhaven = threadhaven.cli:main\n'
    files[INFO+'/LICENSE']=(ROOT/'LICENSE').read_bytes()
    rows=[]
    for n,data in sorted(files.items()):
        rows.append([n,'sha256='+base64.urlsafe_b64encode(hashlib.sha256(data).digest()).rstrip(b'=').decode(),str(len(data))])
    rows.append([INFO+'/RECORD','',''])
    rec=io.StringIO(newline='');csv.writer(rec,lineterminator='\n').writerows(rows);files[INFO+'/RECORD']=rec.getvalue().encode()
    whl=out/(NAME+'-py3-none-any.whl')
    with zipfile.ZipFile(whl,'w',compression=zipfile.ZIP_DEFLATED) as z:
        for n,data in sorted(files.items()):
            zi=zipfile.ZipInfo(n,(2026,10,18,0,0,0));zi.compress_type=zipfile.ZIP_DEFLATED;zi.external_attr=0o644<<16;z.writestr(zi,data)
    source={}
    for name in ['README.md','LICENSE','pyproject.toml','.gitignore','CHANGELOG.md','CONTRIBUTING.md']:
        source[name]=(ROOT/name).read_bytes()
    for folder in ['threadhaven','tests','scripts','docs','examples','.github']:
        for p in sorted((ROOT/folder).rglob('*')):
            if p.is_file() and '__pycache__' not in p.parts and p.suffix!='.pyc':source[p.relative_to(ROOT).as_posix()]=p.read_bytes()
    archive=out/(NAME+'.zip')
    with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_DEFLATED) as z:
        for n,data in sorted(source.items()):
            zi=zipfile.ZipInfo(NAME+'/'+n,(2026,10,18,0,0,0));zi.compress_type=zipfile.ZIP_DEFLATED;zi.external_attr=0o644<<16;z.writestr(zi,data)
    tarpath=out/(NAME+'.tar.gz')
    with tarpath.open('wb') as stream, gzip.GzipFile(fileobj=stream,mode='wb',filename='',mtime=0) as gz,tarfile.open(fileobj=gz,mode='w') as t:
        for n,data in sorted(source.items()):
            ti=tarfile.TarInfo(NAME+'/'+n);ti.size=len(data);ti.mode=0o644;ti.mtime=0;t.addfile(ti,io.BytesIO(data))
    (out/'SHA256SUMS.txt').write_text(''.join(sha(p.read_bytes())+'  '+p.name+'\n' for p in [whl,archive,tarpath]))
    for p in [whl,archive,tarpath]:print(p.name, p.stat().st_size, sha(p.read_bytes()))
    return [whl,archive,tarpath]
if __name__=='__main__':build()
