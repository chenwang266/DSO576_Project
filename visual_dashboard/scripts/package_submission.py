#!/usr/bin/env python3
"""Package the visual revision, including its aggregate-only Site source."""
import argparse
import hashlib
import json
import zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
OMIT={'.venv','.git','__pycache__','.pytest_cache','.DS_Store','node_modules'}
parser=argparse.ArgumentParser();parser.add_argument('--archive-name',default='DSO576_Final_Visual_Submission.zip');args=parser.parse_args()
if Path(args.archive_name).name!=args.archive_name:raise ValueError('Archive name must be a basename')

def inventory():
    files={str(p.relative_to(ROOT)):p for p in ROOT.rglob('*') if p.is_file() and not set(p.relative_to(ROOT).parts)&OMIT}
    site=ROOT/'site'
    if not site.is_dir():
        site=ROOT.parent/'site'
        if site.is_dir():
            files.update({'site/'+str(p.relative_to(site)):p for p in site.rglob('*') if p.is_file() and not set(p.relative_to(site).parts)&OMIT})
    return files

files=inventory()
source_hashes={rel:hashlib.sha256(p.read_bytes()).hexdigest() for rel,p in sorted(files.items()) if Path(rel).parts[0] not in {'data','reports','reference'}}
digest=hashlib.sha256(json.dumps(source_hashes,sort_keys=True).encode()).hexdigest()
manifest={'description':'Submitted source/config/docs and Site aggregates; canonical data has separate provenance; Site source commit is recorded in site_deployment.json','source_digest':digest,'files':source_hashes}
(ROOT/'reports/source_manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
files=inventory();archive=ROOT.parent/args.archive_name
with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as zipped:
    for rel,path in sorted(files.items()):zipped.write(path,Path(ROOT.name)/rel)
with zipfile.ZipFile(archive) as zipped:
    assert zipped.testzip() is None
    assert not any('/.venv/' in n or '/.git/' in n or '/__pycache__/' in n for n in zipped.namelist())
sha=hashlib.sha256(archive.read_bytes()).hexdigest()
archive.with_name(archive.name+'.sha256').write_text(sha+'  '+archive.name+'\n')
print(json.dumps({'archive':str(archive),'bytes':archive.stat().st_size,'files':len(files),'sha256':sha,'source_digest':digest},indent=2))
