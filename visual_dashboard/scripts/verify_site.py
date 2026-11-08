#!/usr/bin/env python3
"""Check browser evidence gates/ranking/exports against canonical Python metrics."""
import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from src.config import ROOT
from src.data_access import load_data
from src.history import comparison,shortlist

parser=argparse.ArgumentParser();parser.add_argument('--site',type=Path,required=True);parser.add_argument('--node',default='node');args=parser.parse_args()
frame,_=load_data(ROOT/'data/processed')
site=args.site.resolve();catalog=json.loads((site/'dist/assets/catalog.json').read_text())
checks=[]
for i,stay in enumerate(catalog['stays']):
    for j,source in enumerate(catalog['sources']):
        for minimum,coverage in [(20,.8),(30,.8),(20,.75)]:
            c=comparison(frame,None if i==0 else stay,None if j==0 else source,minimum,coverage)
            ranked=shortlist(c)
            fields=['neighbourhood','room_type','bedroom_segment','premium_pct_march','premium_pct_june','review_score','persistence_status','sufficient_data_march','sufficient_data_june','is_small_sample_march','is_small_sample_june','median_price_usd_march','median_price_usd_june','price_coverage_march','price_coverage_june']
            records=c[fields].astype(object).where(c[fields].notna(),None).to_dict('records')
            checks.append({'bundle':f'{i}-{j}','minimum':minimum,'coverage':coverage,'rows':records,'ranked':[list(r) for r in ranked[['neighbourhood','room_type','bedroom_segment']].itertuples(index=False,name=None)]})
with tempfile.TemporaryDirectory() as temp:
    expected=Path(temp)/'expected.json';expected.write_text(json.dumps(checks,allow_nan=False,default=lambda x:x.item()))
    result=subprocess.run([args.node,str(site/'verify-data.mjs'),str(expected)],capture_output=True,text=True)
    print(result.stdout)
    if result.returncode:print(result.stderr,file=sys.stderr);raise SystemExit(result.returncode)
    (ROOT/'reports/site_parity.json').write_text(result.stdout)
