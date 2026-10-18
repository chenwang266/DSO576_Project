"""Pure dataframe analysis for the pricing-review dashboard; no UI dependencies."""
from pathlib import Path
import argparse
import pandas as pd

KEYS = ['snapshot_date', 'neighbourhood_cleansed', 'room_type', 'bedrooms']
PEERS = ['snapshot_date', 'room_type', 'bedrooms']
CONTEXT = ['availability_90', 'number_of_reviews_ltm', 'review_scores_value', 'minimum_nights']


def load_data(path):
    data = pd.read_csv(path, dtype={'id': 'string'}, low_memory=False)
    required = set(KEYS + CONTEXT + ['id', 'price', 'property_type', 'accommodates'])
    if required - set(data):
        raise ValueError(f'Missing required columns: {sorted(required - set(data))}')
    if data.duplicated(['snapshot_date', 'id']).any():
        raise ValueError('Duplicate listing-snapshot keys')
    return data


def filter_listings(data, *, snapshot=None, neighbourhood=None, room_type=None,
                    bedrooms=None, property_type=None, accommodates=None,
                    exclude_high_prices=False):
    """None means no filter. Zero bedrooms means a studio, never unknown."""
    result = data
    for col, value in [('snapshot_date', snapshot), ('neighbourhood_cleansed', neighbourhood),
                       ('room_type', room_type), ('bedrooms', bedrooms),
                       ('property_type', property_type), ('accommodates', accommodates)]:
        if value is not None:
            result = result.loc[result[col].eq(value)]
    if exclude_high_prices:
        result = result.loc[result.price.isna() | result.price.le(2000)]
    return result.copy()


def _aggregate(data, keys):
    # Unknown bedrooms are retained in the source table but cannot define peers.
    data = data.dropna(subset=keys)
    price = data.price.where(data.price.gt(0))
    data = data.assign(price=price)
    agg = dict(listings=('id', 'size'), price_n=('price', 'count'),
               median_price=('price', 'median'),
               q1_price=('price', lambda x: x.quantile(.25, interpolation='linear')),
               q3_price=('price', lambda x: x.quantile(.75, interpolation='linear')))
    for col in CONTEXT:
        agg[f'{col}_n'] = (col, 'count')
        agg[f'median_{col}'] = (col, 'median')
    return data.groupby(keys, observed=True, sort=True).agg(**agg).reset_index()


def segment_metrics(data, *, min_priced=20, property_type=None, accommodates=None,
                    exclude_high_prices=False):
    """Local segments and LA peers; peers include the selected neighborhood.

    Optional refinements and outlier sensitivity apply equally to both groups.
    min_priced is a provisional review threshold, not statistical significance.
    """
    if min_priced < 1:
        raise ValueError('min_priced must be positive')
    base = filter_listings(data, property_type=property_type, accommodates=accommodates,
                           exclude_high_prices=exclude_high_prices)
    local = _aggregate(base, KEYS)
    peer = _aggregate(base, PEERS)
    peer = peer.rename(columns={c: f'peer_{c}' for c in peer if c not in PEERS})
    result = local.merge(peer, on=PEERS, how='left', validate='many_to_one')
    result['sufficient_data'] = (result.price_n.ge(min_priced) &
                                 result.peer_price_n.ge(min_priced))
    result['premium_pct'] = ((result.median_price / result.peer_median_price - 1) * 100).where(
        result.sufficient_data & result.peer_median_price.gt(0))
    return result


def snapshot_comparison(metrics, march='2026-03-16', june='2026-06-15'):
    """Repeated cross-sectional comparison, not a matched-listing price effect."""
    keys = KEYS[1:]
    left = metrics.loc[metrics.snapshot_date.eq(march)].drop(columns='snapshot_date')
    right = metrics.loc[metrics.snapshot_date.eq(june)].drop(columns='snapshot_date')
    result = left.merge(right, on=keys, how='outer', suffixes=('_march', '_june'),
                        validate='one_to_one')
    m, j = result.premium_pct_march, result.premium_pct_june
    eligible = m.notna() & j.notna()
    result['persistent_pattern'] = eligible & ((m.gt(0) & j.gt(0)) | (m.lt(0) & j.lt(0)))
    result['median_price_change'] = result.median_price_june - result.median_price_march
    result['median_price_change_pct'] = (100 * result.median_price_change /
                                         result.median_price_march).where(result.median_price_march.gt(0))
    # Conservative magnitude: smaller absolute premium across the two snapshots.
    result['review_score'] = pd.concat([m.abs(), j.abs()], axis=1).min(axis=1).where(
        result.persistent_pattern)
    return result


def ranked_review_list(comparison):
    """Persistent premiums/discounts only; context is displayed, not weighted."""
    result = comparison.loc[comparison.persistent_pattern].copy()
    result = result.sort_values(['review_score', 'neighbourhood_cleansed', 'room_type', 'bedrooms'],
                                 ascending=[False, True, True, True]).reset_index(drop=True)
    result.insert(0, 'rank', range(1, len(result) + 1))
    return result


def export_analysis(data, output_dir, **options):
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    metrics = segment_metrics(data, **options)
    comparison = snapshot_comparison(metrics)
    ranked = ranked_review_list(comparison)
    for name, frame in [('segment_metrics', metrics), ('segment_comparison', comparison),
                         ('ranked_review_list', ranked)]:
        frame.to_csv(output_dir / f'{name}.csv', index=False)
    return metrics, comparison, ranked


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--data', type=Path, default=Path(__file__).resolve().parents[1] /
                        'module6_submission/data_and_evidence/cleaned_listings.csv')
    parser.add_argument('--output-dir', type=Path, default=Path(__file__).resolve().parent / 'outputs')
    parser.add_argument('--min-priced', type=int, default=20)
    args = parser.parse_args()
    export_analysis(load_data(args.data), args.output_dir, min_priced=args.min_priced)
