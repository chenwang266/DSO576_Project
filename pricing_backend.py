"""Listing-based pricing analysis; no Streamlit dependency or data mutation."""
from pathlib import Path
import hashlib
import pandas as pd

DATES = ('2026-03-16', '2026-06-15')
KEYS = ['neighbourhood', 'room_type', 'bedroom_segment']
BEDROOMS = ['Studio'] + [f'{i} bedroom' for i in range(1, 6)] + ['6+ bedrooms']
CONTEXT = ['availability_90', 'number_of_reviews_ltm', 'review_scores_value', 'minimum_nights']
CAUTION = ('Bedroom completeness/coding differs across snapshots; Studio and other comparisons may be distorted. '
           'Source composition may differ. Availability is not occupancy; reviews are not demand.')

def clean(raw, date):
    required = ['id', 'price', 'neighbourhood_cleansed', 'room_type', 'bedrooms',
                'availability_30', 'availability_60', 'availability_90', 'availability_365',
                'number_of_reviews_ltm', 'number_of_reviews_l30d', 'review_scores_value']
    missing = set(required) - set(raw.columns)
    if missing:
        raise ValueError(f'{date}: missing required columns: {sorted(missing)}')
    d = raw.copy()
    d['listing_id'] = d.id.fillna('').str.strip()
    if d.listing_id.eq('').any() or d.listing_id.duplicated().any():
        raise ValueError(f'{date}: missing or duplicate listing IDs')
    d['snapshot_date'] = date
    d['neighbourhood'] = d.neighbourhood_cleansed.fillna('').str.split().str.join(' ').replace('', 'Unknown')
    rooms = ['Entire home/apt', 'Private room', 'Shared room', 'Hotel room']
    d['room_type'] = d.room_type.str.strip().where(d.room_type.str.strip().isin(rooms), 'Unknown')
    b = pd.to_numeric(d.bedrooms, errors='coerce')
    valid = b.ge(0) & b.mod(1).eq(0)
    d['bedroom_segment'] = b.map(lambda x: 'Studio' if x == 0 else '6+ bedrooms' if x >= 6 else f'{int(x)} bedroom' if pd.notna(x) and x >= 0 else 'Unknown').where(valid, 'Unknown')
    p = d.price.fillna('').str.strip()
    good = p.str.fullmatch(r'\$?(?:\d+|\d{1,3}(?:,\d{3})+)(?:\.\d{1,2})?')
    d['price_usd'] = pd.to_numeric(p.str.replace(r'[$,]', '', regex=True).where(good), errors='coerce')
    d['price_status'] = 'malformed'
    d.loc[p.eq(''), 'price_status'] = 'missing'
    d.loc[good & d.price_usd.le(0), 'price_status'] = 'invalid_nonpositive'
    d.loc[good & d.price_usd.gt(0), 'price_status'] = 'valid'
    d['price_usd'] = d.price_usd.where(d.price_status.eq('valid'))
    for c in ['availability_30', 'availability_60', 'availability_90', 'availability_365',
              'number_of_reviews_ltm', 'number_of_reviews_l30d', 'minimum_nights', 'review_scores_value']:
        v = pd.to_numeric(d[c], errors='coerce') if c in d else pd.Series(float('nan'), index=d.index)
        ok = v.ge(0)
        if c != 'review_scores_value':
            ok &= v.mod(1).eq(0)
        if c.startswith('availability_'):
            ok &= v.le(int(c.split('_')[1]))
        if c == 'review_scores_value':
            ok &= v.le(5)
        d[c] = v.where(ok)
    d['stay'] = d.minimum_nights.map(lambda x: 'Short stay (<30 nights)' if 0 < x < 30 else 'Long stay (30+ nights)' if x >= 30 else 'Unknown')
    d['source'] = d.get('source', pd.Series('Unknown', index=d.index)).fillna('Unknown').replace('', 'Unknown')
    d['eligible_dimensions'] = d.neighbourhood.ne('Unknown') & d.room_type.ne('Unknown') & d.bedroom_segment.ne('Unknown')
    cols = ['listing_id', 'snapshot_date', *KEYS, 'price_usd', 'price_status', 'eligible_dimensions', 'stay', 'source', *CONTEXT]
    if 'last_scraped' in d:
        cols += ['last_scraped']
    return d[cols]

def load_data(root):
    frames, report = [], []
    for date in DATES:
        path = Path(root) / f'listings-{date}.csv.gz'
        if not path.is_file():
            raise FileNotFoundError(f'Add the supplied LA snapshot at {path}. No substitute data will be downloaded.')
        before = hashlib.sha256(path.read_bytes()).hexdigest()
        d = clean(pd.read_csv(path, dtype=str, keep_default_na=False), date)
        if hashlib.sha256(path.read_bytes()).hexdigest() != before:
            raise ValueError('Raw file changed during loading')
        frames.append(d)
        report.append({'snapshot_date': date, 'rows': len(d), 'unknown_bedrooms': int(d.bedroom_segment.eq('Unknown').sum()),
                       'price_statuses': d.price_status.value_counts().to_dict(), 'sha256': before,
                       'actual_scrape_dates': sorted(d.last_scraped.unique().tolist()) if 'last_scraped' in d else []})
    return pd.concat(frames, ignore_index=True), report

def filter_data(d, stay='All', source='All'):
    return d.loc[(True if stay == 'All' else d.stay.eq(stay)) & (True if source == 'All' else d.source.eq(source)) & d.eligible_dimensions]

def summarize(d, keys):
    g = d.groupby(keys, observed=True)
    out = g.price_usd.agg(listing_rows='size', priced_rows='count', median_price_usd='median', min_price_usd='min', max_price_usd='max')
    out['p25_price_usd'] = g.price_usd.quantile(.25)
    out['p75_price_usd'] = g.price_usd.quantile(.75)
    out['price_iqr_usd'] = out.p75_price_usd - out.p25_price_usd
    out['price_coverage'] = out.priced_rows / out.listing_rows
    out['is_small_sample'] = out.priced_rows < 20
    for c in CONTEXT:
        out[c + '_median'] = g[c].median()
        out[c + '_valid_count'] = g[c].count()
    return out.reset_index()

def metrics(d, minimum=20):
    local = summarize(d, ['snapshot_date', *KEYS])
    peer = summarize(d, ['snapshot_date', 'room_type', 'bedroom_segment'])
    joined = local.merge(peer, on=['snapshot_date', 'room_type', 'bedroom_segment'], suffixes=('', '_peer'), validate='many_to_one')
    joined['sufficient_data'] = joined.priced_rows.ge(minimum) & joined.priced_rows_peer.ge(minimum)
    joined['premium_pct'] = (100 * (joined.median_price_usd / joined.median_price_usd_peer - 1)).where(joined.sufficient_data & joined.median_price_usd_peer.gt(0))
    return joined

def history(m):
    a = m[m.snapshot_date.eq(DATES[0])].drop(columns='snapshot_date')
    b = m[m.snapshot_date.eq(DATES[1])].drop(columns='snapshot_date')
    h = a.merge(b, on=KEYS, how='outer', suffixes=('_march', '_june'), validate='one_to_one')
    p, q = h.premium_pct_march, h.premium_pct_june
    h['persistence'] = 'Insufficient evidence'
    both = p.notna() & q.notna()
    h.loc[both & (p.eq(0) | q.eq(0)), 'persistence'] = 'Neutral'
    h.loc[both & p.mul(q).lt(0), 'persistence'] = 'Reversed'
    h.loc[both & p.gt(0) & q.gt(0), 'persistence'] = 'Persistent premium'
    h.loc[both & p.lt(0) & q.lt(0), 'persistence'] = 'Persistent discount'
    h['score'] = pd.concat([p.abs(), q.abs()], axis=1).min(axis=1).where(h.persistence.isin(['Persistent premium', 'Persistent discount']))
    h['change_usd'] = h.median_price_usd_june - h.median_price_usd_march
    h['change_pct'] = (100 * h.change_usd / h.median_price_usd_march).where(h.median_price_usd_march.gt(0))
    return h

def warnings(row, coverage):
    notes = []
    for suffix in ('', '_march', '_june'):
        for peer in ('', '_peer'):
            col = 'price_coverage' + peer + suffix
            value = row.get(col)
            if pd.notna(value) and value < coverage:
                notes.append(f'{suffix.strip("_") or "Selected snapshot"} {"peer" if peer else "local"} coverage {value:.1%} below {coverage:.0%}')
    return '; '.join(notes + [CAUTION])

def shortlist(h, coverage=.8, direction='Both'):
    out = h[h.score.notna()].copy()
    if direction != 'Both':
        out = out[out.persistence.eq('Persistent ' + direction.lower())]
    out['_bedroom_order'] = out.bedroom_segment.map({b:i for i,b in enumerate(BEDROOMS)})
    out = out.sort_values(['score', 'neighbourhood', 'room_type', '_bedroom_order'], ascending=[False, True, True, True]).drop(columns='_bedroom_order').reset_index(drop=True)
    out.insert(0, 'rank', range(1, len(out) + 1))
    out['warnings'] = out.apply(lambda r: warnings(r, coverage), axis=1) if len(out) else pd.Series(dtype=str)
    return out
