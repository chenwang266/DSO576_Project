"""Independent full-data assertions against original inputs and exported files."""
import argparse
import json
from pathlib import Path
import pandas as pd

def validate(source_dir, output_dir):
    source_dir, output_dir=Path(source_dir),Path(output_dir)
    clean=pd.read_csv(output_dir/'cleaned_listings.csv',dtype={'id':'string'}, low_memory=False)
    assert not clean.duplicated(['snapshot_date','id']).any()
    raw_ids=[]
    for date,name in [('2026-03-16','listings 16 March, 2026.csv'),('2026-06-15','listings 15 June, 2026.csv')]:
        raw=pd.read_csv(source_dir/name,dtype='string',keep_default_na=False)
        exported=clean.loc[clean.snapshot_date.eq(date)]
        assert len(exported)==len(raw.drop_duplicates())
        assert set(exported.id)==set(raw.id)
        raw_ids.append(set(raw.id))
        values=raw.price.str.removeprefix('$').str.replace(',','',regex=False)
        expected=pd.to_numeric(values,errors='coerce')
        expected=expected.where(expected.gt(0))
        lookup=exported.set_index('id').price
        actual=raw.id.map(lookup)
        assert expected.isna().equals(actual.isna())
        assert (expected.dropna().astype(float).to_numpy()==actual.dropna().to_numpy()).all()
        expected_value=pd.to_numeric(raw.review_scores_value.str.strip(),errors='coerce')
        expected_value=expected_value.where(expected_value.between(0,5))
        actual_value=raw.id.map(exported.set_index('id').review_scores_value)
        assert expected_value.isna().equals(actual_value.isna())
        assert (expected_value.dropna().astype(float).to_numpy()==actual_value.dropna().to_numpy()).all()
    for col,horizon in [('availability_30',30),('availability_60',60),('availability_90',90),('availability_365',365),('review_scores_rating',5),('review_scores_value',5)]:
        assert clean[col].dropna().between(0,horizon).all()
    panel=pd.read_csv(output_dir/'listing_comparison.csv',dtype={'id':'string'}, low_memory=False)
    assert panel.id.is_unique and set(panel.id)==raw_ids[0]|raw_ids[1]
    assert panel._merge.eq('both').sum()==len(raw_ids[0]&raw_ids[1])
    metrics=pd.read_csv(output_dir/'neighbourhood_metrics.csv')
    assert metrics.listings.sum()==len(clean)
    assert metrics.price_n.sum()==clean.price.notna().sum()
    sample=pd.read_csv(output_dir/'sample_cleaned_50.csv',dtype={'id':'string'}, low_memory=False)
    assert len(sample)<=50 and list(sample.columns)==list(clean.columns)
    assert sample.merge(clean,on=['snapshot_date','id'],validate='one_to_one').shape[0]==len(sample)
    checks=json.loads((output_dir/'record_checks.json').read_text())
    assert len(checks)==5 and all(x['matches'] for x in checks)
    result={'status':'PASS','records_checked':len(clean),
            'checks':['source/output row and ID reconciliation','all exported prices equal independently parsed source prices',
                      'all exported value ratings equal independently parsed source values', 'numeric bounds','outer-merge union and intersection','group and price denominators',
                      'sample size, columns, and key membership','five record results']}
    (output_dir/'independent_validation.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))
    return result

if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--source-dir',type=Path,default=Path(__file__).resolve().parents[2])
    p.add_argument('--output-dir',type=Path,default=Path(__file__).resolve().parents[1]/'data_and_evidence')
    a=p.parse_args();validate(a.source_dir,a.output_dir)
