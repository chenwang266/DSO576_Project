"""Canonical input validation and deterministic fingerprints; no UI imports."""
import hashlib
import json
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DATES = ['2026-03-16', '2026-06-15']
ROOMS = ['Entire home/apt', 'Private room', 'Shared room', 'Hotel room']
CONTEXT = ['availability_90', 'number_of_reviews_ltm', 'review_scores_value', 'minimum_nights']
KEYS = ['snapshot_date', 'neighbourhood', 'room_type', 'bedrooms']


def fingerprint(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def settings():
    return json.loads((ROOT / 'config/project.json').read_text(encoding='utf-8'))


def processed_dir():
    return (ROOT / settings()['processed']).resolve()


def validate(data):
    required = set(KEYS + CONTEXT + ['listing_id', 'price_usd', 'has_valid_price',
        'pricing_eligible', 'valid_dimensions', 'stay', 'source'])
    if missing := required - set(data):
        raise ValueError(f'Missing canonical columns: {sorted(missing)}. Regenerate canonical files.')
    if data.listing_id.isna().any() or data.listing_id.str.strip().eq('').any():
        raise ValueError('Missing canonical listing IDs')
    if data.duplicated(['snapshot_date', 'listing_id']).any():
        raise ValueError('Duplicate listing-snapshot keys')
    if not data.snapshot_date.isin(DATES).all():
        raise ValueError('Unexpected snapshot date')
    expected_dims = data.neighbourhood.ne('Unknown') & data.room_type.isin(ROOMS) & data.bedrooms.notna()
    expected_price = data.price_usd.notna() & data.price_usd.gt(0)
    if not data.valid_dimensions.eq(expected_dims).all():
        raise ValueError('Invalid dimension flags')
    if not data.has_valid_price.eq(expected_price).all():
        raise ValueError('Invalid price flags')
    if not data.pricing_eligible.eq(expected_dims & expected_price).all():
        raise ValueError('Invalid pricing eligibility flags')
    return data


def load_data(directory=None):
    directory = Path(directory or processed_dir())
    path = directory / 'canonical_listings_clean.csv'
    if not path.exists():
        raise FileNotFoundError('Canonical files missing. Run: uv run python scripts/canonical_clean.py')
    data = pd.read_csv(path, dtype={'listing_id': 'string', 'snapshot_date': 'string',
        'has_valid_price': 'boolean', 'pricing_eligible': 'boolean', 'valid_dimensions': 'boolean',
        'bedrooms': 'Int64'}, keep_default_na=False, na_values=[''])
    return validate(data), json.loads((directory / 'canonical_cleaning_report.json').read_text())
