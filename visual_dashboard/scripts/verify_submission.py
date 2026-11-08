#!/usr/bin/env python3
"""Independent csv/statistics audit, exports, and measured runtime evidence."""
from __future__ import annotations
import csv
import gzip
import hashlib
import json
import statistics
import sys
import time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import pandas as pd
from src.config import ROOT, DATES, settings
from src.data_access import load_data, fingerprint
from src.history import comparison, shortlist


def raw_audit():
    # Deliberately uses the standard library, not the canonical parsers or pandas.
    evidence=[]
    config=settings()
    for date,key in zip(DATES,('march_path','june_path')):
        path=(ROOT/config[key]).resolve()
        input_hash=hashlib.sha256(path.read_bytes()).hexdigest()
        counts=dict(rows=0,missing_price=0,missing_bedrooms=0,zero_bedrooms=0,private_rows=0,private_unknown_bedrooms=0)
        prices=[];ids=set()
        with gzip.open(path,'rt',encoding='utf-8',newline='') as handle:
            for row in csv.DictReader(handle):
                counts['rows']+=1
                listing_id=row['id'].strip()
                assert listing_id and listing_id not in ids
                ids.add(listing_id)
                if not row['price'].strip():counts['missing_price']+=1
                if not row['bedrooms'].strip():counts['missing_bedrooms']+=1
                if row['bedrooms'].strip() in ['0','0.0']:counts['zero_bedrooms']+=1
                if row['room_type']=='Private room':
                    counts['private_rows']+=1
                    if not row['bedrooms'].strip():counts['private_unknown_bedrooms']+=1
                if row['neighbourhood_cleansed']=='Hollywood' and row['room_type']=='Entire home/apt' and row['bedrooms'].strip() in ['1','1.0'] and row['price'].strip():
                    prices.append(float(row['price'].replace('$','').replace(',','')))
        evidence.append(dict(snapshot=date,sha256=input_hash,**counts,hollywood_1br_priced=len(prices),hollywood_1br_median=statistics.median(prices)))
    return evidence


def main():
    start=time.perf_counter()
    data,report=load_data(ROOT/'data/processed')
    loaded=time.perf_counter()
    c=comparison(data)
    ranked=shortlist(c)
    analyzed=time.perf_counter()
    c['canonical_fingerprint']=fingerprint(ROOT/'data/processed')
    ranked['canonical_fingerprint']=fingerprint(ROOT/'data/processed')
    (ROOT/'reports').mkdir(exist_ok=True)
    c.to_csv(ROOT/'reports/default_segment_comparison.csv',index=False)
    ranked.to_csv(ROOT/'reports/default_review_shortlist.csv',index=False)
    focused=[]
    for name,room,bed in [('Hollywood','Entire home/apt','1 bedroom'),('Malibu','Entire home/apt','3 bedroom'),('Altadena','Entire home/apt','3 bedroom'),('Venice','Private room','1 bedroom'),('Hollywood Hills West','Entire home/apt','6+ bedrooms')]:
        row=c.loc[c.neighbourhood.eq(name)&c.room_type.eq(room)&c.bedroom_segment.eq(bed)].iloc[0]
        focused.append(row)
    pd.DataFrame(focused).to_csv(ROOT/'reports/issue_case_evidence.csv',index=False)
    independent=raw_audit()
    for raw,canonical in zip(independent,report['inputs']):
        assert raw['sha256']==canonical['source_sha256']
        assert raw['rows']==canonical['clean_rows']
        assert raw['missing_price']==canonical['missing_price_rows']
        assert raw['missing_bedrooms']==canonical['missing_bedroom_rows']
        assert raw['zero_bedrooms']==canonical['zero_bedroom_rows']
        actual=c.loc[c.neighbourhood.eq('Hollywood')&c.room_type.eq('Entire home/apt')&c.bedroom_segment.eq('1 bedroom')].iloc[0]
        period='march' if raw['snapshot']==DATES[0] else 'june'
        assert actual[f'median_price_usd_{period}']==raw['hollywood_1br_median']
    results=dict(rows=len(data),known_segments=len(c),ranked_rows=len(ranked),premium_rows=int(ranked.direction.eq('Premium').sum()),discount_rows=int(ranked.direction.eq('Discount').sum()),canonical_fingerprint=fingerprint(ROOT/'data/processed'),timing_seconds=dict(cold_load=loaded-start,default_analysis=analyzed-loaded,cold_load_plus_analysis=analyzed-start),independent_raw_audit=independent,scope='Local supplied full data; no remote merge or team approval implied')
    (ROOT/'reports/validation_results.json').write_text(json.dumps(results,indent=2)+'\n')
    print(json.dumps(results,indent=2))

if __name__=='__main__':main()
