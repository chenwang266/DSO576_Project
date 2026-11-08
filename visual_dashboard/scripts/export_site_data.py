#!/usr/bin/env python3
"""Export aggregate-only evidence from the canonical Python backend for Sites."""
import argparse
import hashlib
import json
import shutil
import sys
from pathlib import Path
import pandas as pd
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from src.config import ROOT
from src.data_access import load_data, fingerprint
from src.filters import optional_filters, valid_dimensions
from src.history import comparison
from src.pricing import histogram, KEYS
from plotly.offline import get_plotlyjs


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',required=True,type=Path);args=parser.parse_args()
    out=args.output;out.mkdir(parents=True,exist_ok=True)
    frame,report=load_data(ROOT/'data/processed')
    stays=[None]+sorted(frame.stay_type.unique());sources=[None]+sorted(frame.source.unique())
    catalog={'fingerprint':fingerprint(ROOT/'data/processed'),'stays':[s or 'All stays' for s in stays],'sources':[s or 'All sources' for s in sources],'bundles':{},'quality':report['inputs'],'neighborhoods':sorted(frame.loc[frame.neighbourhood_is_known,'neighbourhood'].unique()),'rooms':sorted(frame.loc[frame.room_type_is_known,'room_type'].unique())}
    for i,stay in enumerate(stays):
        for j,source in enumerate(sources):
            compared=comparison(frame,stay,source,min_priced=1)
            # The backend defines premiums/status/score at minimum 1; client only
            # suppresses unavailable evidence for a higher user threshold.
            data={'columns':list(compared.columns),'data':compared.astype(object).where(pd.notna(compared),None).values.tolist()}
            eligible=valid_dimensions(optional_filters(frame,stay,source))
            bins={}
            for key,group in eligible.groupby(['snapshot_date']+KEYS,sort=True):
                values=group.price_usd.dropna()
                hist=histogram(values)
                if not hist.empty:
                    bins['|'.join(key)]=[float(hist.left.iloc[0]),float(hist.right.iloc[-1]),hist['count'].astype(int).tolist()]
            payload={'columns':data['columns'],'rows':data['data'],'histograms':bins}
            filename=f'evidence-{i}-{j}.json';(out/filename).write_text(json.dumps(payload,separators=(',',':'),ensure_ascii=False,allow_nan=False,default=lambda value:value.item()))
            catalog['bundles'][f'{i}-{j}']=filename
    (out/'catalog.json').write_text(json.dumps(catalog,separators=(',',':'),ensure_ascii=False))
    (out/'plotly.min.js').write_text(get_plotlyjs())
    print(json.dumps({'bundles':len(catalog['bundles']),'rows':len(frame),'output':str(out),'fingerprint':catalog['fingerprint']}))

if __name__=='__main__':main()
