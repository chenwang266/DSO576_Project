"""Deterministic Module 6 cleaning. Never modifies original CSV files."""
import argparse
import hashlib
import json
from pathlib import Path
import pandas as pd

SOURCES = [('2026-03-16', 'listings 16 March, 2026.csv'),
           ('2026-06-15', 'listings 15 June, 2026.csv')]
NUMERIC = ['accommodates', 'bathrooms', 'bedrooms', 'beds', 'price',
           'minimum_nights', 'maximum_nights', 'availability_30', 'availability_60',
           'availability_90', 'availability_365', 'number_of_reviews',
           'number_of_reviews_ltm', 'number_of_reviews_l30d', 'review_scores_rating',
           'reviews_per_month']
TEXT = ['neighbourhood_cleansed', 'neighbourhood_group_cleansed', 'property_type', 'room_type']
DATES = ['last_scraped', 'first_review', 'last_review', 'calendar_last_scraped']
BOOLS = ['host_is_superhost', 'instant_bookable', 'has_availability']
KEEP = ['id'] + TEXT + NUMERIC + DATES + BOOLS

def sha(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()

def run(source_dir, output_dir):
    source_dir, output_dir = Path(source_dir), Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    audits, frames, original_frames, column_audits, examples = [], [], [], [], []
    for snapshot, filename in SOURCES:
        path = source_dir / filename
        raw = pd.read_csv(path, dtype='string', keep_default_na=False)
        original_frames.append(raw.assign(snapshot_date=snapshot, source_row=range(2, len(raw)+2)))
        d = raw[KEEP].copy()
        audit = {'snapshot_date': snapshot, 'source_file': filename, 'sha256': sha(path),
                 'source_rows': len(raw), 'source_columns': len(raw.columns),
                 'exact_duplicate_rows': int(raw.duplicated().sum()),
                 'repeated_ids_before': int(raw.id.duplicated().sum())}
        for col in KEEP:
            original = d[col].copy()
            before_missing = int(original.eq('').sum())
            s = original.str.strip().replace('', pd.NA)
            failures = 0
            if col in NUMERIC:
                if col == 'price':
                    s = s.str.replace('$', '', regex=False).str.replace(',', '', regex=False)
                converted = pd.to_numeric(s, errors='coerce')
                failures = int((s.notna() & converted.isna()).sum())
                d[col] = converted.astype('Float64')
            elif col in DATES:
                converted = pd.to_datetime(s, format='%Y-%m-%d', errors='coerce')
                failures = int((s.notna() & converted.isna()).sum())
                d[col] = converted.dt.strftime('%Y-%m-%d').astype('string')
            elif col in BOOLS:
                converted = s.str.lower().map({'t': True, 'f': False})
                failures = int((s.notna() & converted.isna()).sum())
                d[col] = converted.astype('boolean')
            else:
                d[col] = s
            changed = original.ne(original.str.strip())
            if changed.any():
                i = changed[changed].index[0]
                examples.append({'snapshot_date': snapshot, 'source_row': int(i+2), 'column': col,
                                 'before': original.loc[i], 'after': str(d.loc[i,col])})
            column_audits.append({'snapshot_date': snapshot, 'column': col,
                'input_type': 'string', 'output_type': str(d[col].dtype),
                'missing_before': before_missing, 'missing_after': int(d[col].isna().sum()),
                'conversion_failures': failures, 'whitespace_changes': int(changed.sum())})
        d['snapshot_date'] = snapshot
        d['source_row'] = range(2, len(d)+2)
        duplicate = raw.duplicated()
        d = d.loc[~duplicate].copy()
        assert d.id.notna().all(), 'Missing identifiers need manual adjudication'
        assert not d.id.duplicated().any(), 'Conflicting duplicate identifiers: do not silently choose'
        # Impossible analytical values become missing and have an explicit flag.
        for col in NUMERIC:
            invalid = d[col].lt(0).fillna(False)
            if col in ['price', 'accommodates', 'minimum_nights', 'maximum_nights']:
                invalid |= d[col].eq(0).fillna(False)
            if col.startswith('availability_'):
                invalid |= d[col].gt(int(col.split('_')[1])).fillna(False)
            if col == 'review_scores_rating':
                invalid |= d[col].gt(5).fillna(False)
            if col not in ['bathrooms', 'price', 'review_scores_rating', 'reviews_per_month']:
                invalid |= d[col].mod(1).ne(0).fillna(False)
            d[f'invalid_{col}'] = invalid
            audit[f'invalid_{col}'] = int(invalid.sum())
            d.loc[invalid, col] = pd.NA
        d['flag_high_price'] = d.price.gt(2000).fillna(False)
        d['flag_long_minimum_stay'] = d.minimum_nights.gt(365).fillna(False)
        d['flag_night_order'] = d.minimum_nights.gt(d.maximum_nights).fillna(False)
        d['flag_availability_order'] = ((d.availability_30 > d.availability_60) |
            (d.availability_60 > d.availability_90) | (d.availability_90 > d.availability_365)).fillna(False)
        d['flag_review_order'] = (d.first_review > d.last_review).fillna(False)
        d['flag_review_after_scrape'] = (d.last_review > d.last_scraped).fillna(False)
        d['flag_unknown_room_type'] = (~d.room_type.isin(['Entire home/apt', 'Private room', 'Shared room', 'Hotel room']))
        d['price_missing'] = d.price.isna()
        d['eligible_price_analysis'] = d.price.notna() & ~d.flag_unknown_room_type
        audit['clean_rows'] = len(d)
        audit['last_scraped_dates'] = sorted(d.last_scraped.dropna().unique().tolist())
        audit['price_sum_parsed_before_domain_rules'] = float(pd.to_numeric(raw.price.str.replace('$','',regex=False).str.replace(',','',regex=False), errors='coerce').sum())
        audit['price_sum_after'] = float(d.price.sum())
        for col in [c for c in d if c.startswith('flag_')]: audit[col] = int(d[col].sum())
        for row in column_audits:
            if row['snapshot_date'] == snapshot:
                row['missing_after'] = int(d[row['column']].isna().sum())
        audits.append(audit)
        frames.append(d)
    clean = pd.concat(frames, ignore_index=True)
    original = pd.concat(original_frames, ignore_index=True)
    assert not clean.duplicated(['snapshot_date','id']).any()
    clean.to_csv(output_dir / 'cleaned_listings.csv', index=False)
    pd.DataFrame(column_audits).to_csv(output_dir / 'column_audit.csv', index=False)
    pd.DataFrame(examples, columns=['snapshot_date','source_row','column','before','after']).to_csv(output_dir / 'text_examples.csv',index=False)
    # Outer 1:1 comparison makes sample attrition explicit.
    march, june = frames
    panel = march[['id','price']].rename(columns={'price':'price_march'}).merge(
        june[['id','price']].rename(columns={'price':'price_june'}), on='id', how='outer',
        validate='one_to_one', indicator=True)
    both = panel._merge.eq('both')
    priced = both & panel.price_march.notna() & panel.price_june.notna()
    merge = {'march_rows': len(march), 'june_rows':len(june), 'outer_rows':len(panel),
             'matched':int(both.sum()), 'march_only':int(panel._merge.eq('left_only').sum()),
             'june_only':int(panel._merge.eq('right_only').sum()), 'matched_with_both_prices':int(priced.sum()),
             'paired_median_price_change':float((panel.loc[priced,'price_june']-panel.loc[priced,'price_march']).median())}
    panel.to_csv(output_dir / 'listing_comparison.csv', index=False)
    grouped = clean.assign(neighbourhood_cleansed=clean.neighbourhood_cleansed.fillna('[Unknown]'),
                           room_type=clean.room_type.fillna('[Unknown]')).groupby(
                           ['snapshot_date','neighbourhood_cleansed','room_type'], dropna=False)
    metrics = grouped.agg(listings=('id','size'), price_n=('price','count'),
        median_price=('price','median'), mean_price=('price','mean'),
        availability_n=('availability_365','count'), mean_availability_365=('availability_365','mean'),
        rating_n=('review_scores_rating','count'), mean_rating=('review_scores_rating','mean')).reset_index()
    metrics.to_csv(output_dir / 'neighbourhood_metrics.csv', index=False)
    assert int(metrics.listings.sum()) == len(clean)
    # Five independently specified transformations, selected from difficult real cases.
    checks=[]
    conditions=[('missing price', original.price.eq(''), 'price', 'retain missing; never invent a zero', None),
                ('currency price', original.price.str.startswith('$'), 'price', 'remove dollar sign and thousands separator', 'money'),
                ('missing rating', original.review_scores_rating.eq(''), 'review_scores_rating', 'retain missing; absence of rating is not a zero score', None),
                ('boolean label', original.host_is_superhost.eq('f'), 'host_is_superhost', 'f means False', False),
                ('high advertised price', pd.to_numeric(original.price.str.replace('$','',regex=False).str.replace(',','',regex=False),errors='coerce').gt(2000), 'price', 'retain extreme positive price and flag it for sensitivity analysis', 'money')]
    chosen=[]
    for label, condition, col, reason, expected in conditions:
        candidates = original.loc[condition]
        candidates = candidates.loc[~candidates.index.isin(chosen)]
        assert len(candidates), f'No candidate for {label}'
        idx = candidates.index[0]; chosen.append(idx); r=original.loc[idx]
        c=clean.loc[(clean.snapshot_date==r.snapshot_date)&(clean.id==r.id)].iloc[0]
        actual=c[col]
        if expected == 'money': expected=float(r[col].replace('$','').replace(',',''))
        passed = bool(pd.isna(actual)) if expected is None else bool(actual==expected)
        if label == 'high advertised price': passed &= bool(c.flag_high_price)
        checks.append({'case':label,'snapshot_date':r.snapshot_date,'id':r.id,'source_row':int(r.source_row),
                      'field':col,'original':r[col],'expected':expected,'actual':None if pd.isna(actual) else actual.item() if hasattr(actual,'item') else actual,
                      'reason':reason,'matches':passed})
    assert all(r['matches'] for r in checks)
    sample_indices=[]
    for r in checks:
        sample_indices.append(clean.index[(clean.snapshot_date==r['snapshot_date'])&(clean.id==r['id'])][0])
    for col in [c for c in clean if c.startswith(('flag_', 'invalid_'))]:
        rows=clean.index[clean[col]]
        if len(rows): sample_indices.append(rows[0])
    sample_indices=list(dict.fromkeys(sample_indices))[:50]
    for frame in frames:
        for idx in clean.index[clean.snapshot_date.eq(frame.snapshot_date.iloc[0])][:25]:
            if idx not in sample_indices and len(sample_indices)<50: sample_indices.append(idx)
    clean.loc[sample_indices].to_csv(output_dir / 'sample_cleaned_50.csv',index=False)
    results={'sources':audits,'merge':merge,'clean_rows':len(clean),'clean_columns':len(clean.columns),
             'all_five_record_checks_pass':True, 'unique_snapshot_id':True,
             'grouped_counts_reconcile':True, 'sample_rows':len(sample_indices),
             'sample_selection':'Five record checks first, then first row of each populated invalid/suspicious flag, then first 25 March and June rows until 50; deterministic, not representative.'}
    (output_dir/'full_data_checks.json').write_text(json.dumps(results,indent=2)+'\n')
    (output_dir/'record_checks.json').write_text(json.dumps(checks,indent=2)+'\n')
    print(json.dumps({'rows':len(clean),'merge':merge,'record_checks':'5/5 passed'},indent=2))
    return results

if __name__ == '__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--source-dir',type=Path,default=Path(__file__).resolve().parents[2])
    parser.add_argument('--output-dir',type=Path,default=Path(__file__).resolve().parents[1]/'data_and_evidence')
    args=parser.parse_args()
    run(args.source_dir,args.output_dir)
