"""Read only the two supplied listings extracts; preserve raw files."""
import argparse
import json
import re
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pandas as pd
from src.data_access import ROOT, DATES, ROOMS, fingerprint, settings, validate
from src.pricing import aggregate_segments

REQUIRED = ['id', 'price', 'neighbourhood_cleansed', 'room_type', 'bedrooms',
    'availability_30', 'availability_60', 'availability_90', 'availability_365',
    'number_of_reviews_ltm', 'number_of_reviews_l30d', 'review_scores_value']
OPTIONAL = ['minimum_nights', 'source', 'last_scraped', 'last_review',
            'first_review', 'number_of_reviews', 'reviews_per_month']
USD = re.compile(r'^\$?(?:\d+|\d{1,3}(?:,\d{3})+)(?:\.\d{1,2})?$')


def price(value):
    value = str(value).strip()
    if not value:
        return None, 'missing'
    if re.fullmatch(r'-?\$?\d+(?:\.\d{1,2})?', value):
        number = float(value.replace('$', ''))
        if number <= 0:
            return None, 'invalid_nonpositive'
    if not USD.fullmatch(value):
        return None, 'malformed'
    number = float(value.replace('$', '').replace(',', ''))
    return (number, 'valid') if number > 0 else (None, 'invalid_nonpositive')


def integer(series, maximum=None):
    number = pd.to_numeric(series, errors='coerce')
    valid = number.notna() & number.ge(0) & number.mod(1).eq(0)
    if maximum is not None:
        valid &= number.le(maximum)
    status = pd.Series('invalid', index=series.index)
    status.loc[series.eq('')] = 'missing'
    status.loc[valid] = 'valid'
    return number.where(valid).astype('Int64'), status


def clean(path, date):
    raw = pd.read_csv(path, dtype=str, keep_default_na=False)
    if missing := set(REQUIRED) - set(raw):
        raise ValueError(f'{path}: missing required fields {sorted(missing)}')
    out = pd.DataFrame(index=raw.index)
    out['listing_id'] = raw.id.str.strip().astype('string')
    if out.listing_id.eq('').any() or out.listing_id.duplicated().any():
        raise ValueError(f'{path}: missing or duplicate listing ID')
    out['snapshot_date'] = date
    out['source_file'] = path.name
    out['source_row'] = raw.index + 2
    out['input_sha256'] = fingerprint(path)
    out['price_raw'] = raw.price
    parsed = raw.price.map(price)
    out['price_usd'] = parsed.map(lambda pair: pair[0])
    out['price_status'] = parsed.map(lambda pair: pair[1])
    out['neighbourhood_raw'] = raw.neighbourhood_cleansed
    out['neighbourhood'] = raw.neighbourhood_cleansed.str.split().str.join(' ').replace('', 'Unknown')
    out['room_type_raw'] = raw.room_type
    out['room_type'] = raw.room_type.where(raw.room_type.isin(ROOMS), 'Unknown')
    out['bedrooms_raw'] = raw.bedrooms
    bedrooms, out['bedrooms_status'] = integer(raw.bedrooms)
    out['bedrooms'] = bedrooms.clip(upper=6)
    for col in ['availability_30', 'availability_60', 'availability_90', 'availability_365',
                'number_of_reviews_ltm', 'number_of_reviews_l30d', 'minimum_nights']:
        source = raw[col].str.strip() if col in raw else pd.Series('', index=raw.index)
        maximum = int(col.split('_')[-1]) if col.startswith('availability') else None
        out[col], out[col + '_status'] = integer(source, maximum)
    out['stay'] = 'Unknown'
    out.loc[out.minimum_nights.between(1, 29).fillna(False), 'stay'] = 'Short stay (<30 nights)'
    out.loc[out.minimum_nights.ge(30).fillna(False), 'stay'] = 'Long stay (30+ nights)'
    score = pd.to_numeric(raw.review_scores_value, errors='coerce')
    valid = score.between(0, 5)
    out['review_scores_value'] = score.where(valid)
    out['review_scores_value_status'] = 'invalid'
    out.loc[raw.review_scores_value.eq(''), 'review_scores_value_status'] = 'missing'
    out.loc[valid, 'review_scores_value_status'] = 'valid'
    out['value_score_is_zero'] = valid & score.eq(0)
    for col in OPTIONAL:
        if col != 'minimum_nights':
            out[col] = raw[col] if col in raw else ''
    out['source'] = out.source.str.strip().replace('', 'Unknown')
    out['has_valid_price'] = out.price_status.eq('valid')
    out['valid_dimensions'] = (out.neighbourhood.ne('Unknown') & out.room_type.ne('Unknown') & out.bedrooms.notna())
    out['pricing_eligible'] = out.has_valid_price & out.valid_dimensions
    out['segment_key'] = out.apply(lambda row: json.dumps([row.neighbourhood, row.room_type,
        int(row.bedrooms)], ensure_ascii=False) if row.valid_dimensions else '', axis=1)
    return validate(out)


def main():
    config = settings()
    parser = argparse.ArgumentParser()
    parser.add_argument('--march', type=Path, default=ROOT / config['march'])
    parser.add_argument('--june', type=Path, default=ROOT / config['june'])
    parser.add_argument('--output-dir', type=Path, default=ROOT / config['processed'])
    args = parser.parse_args()
    paths = [args.march.resolve(), args.june.resolve()]
    for path in paths:
        if not path.exists():
            raise FileNotFoundError(f'Supply the authorized listings file at {path}, or set config/project.json.')
    before = {str(path): fingerprint(path) for path in paths}
    frames = [clean(path, date) for path, date in zip(paths, DATES)]
    data = pd.concat(frames, ignore_index=True)
    validate(data)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    listings = args.output_dir / 'canonical_listings_clean.csv'
    segments = args.output_dir / 'canonical_price_segments.csv'
    data.to_csv(listings, index=False)
    aggregate_segments(data).to_csv(segments, index=False)
    after = {str(path): fingerprint(path) for path in paths}
    if before != after:
        raise ValueError('Raw input fingerprints changed')
    report = {'input_sha256': before, 'raw_unchanged': True, 'dates': DATES,
        'rows': len(data), 'columns': list(data.columns),
        'output_sha256': {path.name: fingerprint(path) for path in [listings, segments]},
        'by_snapshot': {date: {'rows': len(frame),
            'price_status': frame.price_status.value_counts().to_dict(),
            'bedrooms_status': frame.bedrooms_status.value_counts().to_dict(),
            'unknown_dimensions': int((~frame.valid_dimensions).sum()),
            'actual_scrape_dates': sorted(frame.last_scraped.unique().tolist())}
            for date, frame in zip(DATES, frames)},
        'policies': 'No price caps, imputation, stay/source exclusions; Unknown bedrooms never Studio.'}
    (args.output_dir / 'canonical_cleaning_report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps({'rows': len(data), 'raw_unchanged': True,
                      'snapshots': {d: len(f) for d, f in zip(DATES, frames)}}, indent=2))


if __name__ == '__main__':
    main()
