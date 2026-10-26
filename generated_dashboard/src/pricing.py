"""All price and context calculations. No interface or hidden mutable state."""
import numpy as np
import pandas as pd
from src.data_access import KEYS, CONTEXT
from src.filters import filter_listings


def summary(population):
    eligible_dimensions = population.loc[population.valid_dimensions]
    prices = eligible_dimensions.loc[eligible_dimensions.pricing_eligible, 'price_usd'].dropna()
    n, priced = len(eligible_dimensions), len(prices)
    result = {'listing_rows': n, 'priced_rows': priced,
        'price_coverage': priced / n if n else np.nan,
        'median_price_usd': prices.median(),
        'p25_price_usd': prices.quantile(.25), 'p75_price_usd': prices.quantile(.75),
        'min_price_usd': prices.min(), 'max_price_usd': prices.max()}
    result['price_iqr_usd'] = result['p75_price_usd'] - result['p25_price_usd']
    for col in CONTEXT:
        values = eligible_dimensions[col].dropna()
        result[col + '_median'] = values.median() if len(values) else np.nan
        result[col + '_n'] = len(values)
    return result


def aggregate_segments(data, min_priced=20):
    base = data.loc[data.valid_dimensions].copy()
    records = []
    for keys, frame in base.groupby(KEYS, observed=True, sort=True):
        values = dict(zip(KEYS, keys))
        values.update(summary(frame))
        values['is_small_sample'] = values['priced_rows'] < min_priced
        records.append(values)
    columns = KEYS + list(summary(data.iloc[:0])) + ['is_small_sample']
    return pd.DataFrame(records, columns=columns)


def detail(data, *, snapshot, neighbourhood, room_type, bedrooms, stay=None, source=None, min_priced=20):
    if min_priced < 1:
        raise ValueError('Minimum priced count must be positive')
    options = dict(snapshot=snapshot, room_type=room_type, bedrooms=bedrooms, stay=stay, source=source)
    peer_rows = filter_listings(data, **options)
    local_rows = filter_listings(peer_rows, neighbourhood=neighbourhood)
    local, peer = summary(local_rows), summary(peer_rows)
    sufficient = local['priced_rows'] >= min_priced and peer['priced_rows'] >= min_priced
    premium = (100 * (local['median_price_usd'] / peer['median_price_usd'] - 1)
               if sufficient and peer['median_price_usd'] > 0 else np.nan)
    return {'local': local, 'peer': peer, 'premium_pct': premium,
        'sufficient_data': sufficient, 'local_rows': local_rows}


def segment_metrics(data, *, min_priced=20, stay=None, source=None):
    base = filter_listings(data, stay=stay, source=source)
    local = aggregate_segments(base, min_priced)
    peer_keys = ['snapshot_date', 'room_type', 'bedrooms']
    records = []
    for keys, frame in base.loc[base.valid_dimensions].groupby(peer_keys, observed=True, sort=True):
        row = dict(zip(peer_keys, keys))
        row.update({'peer_' + key: val for key, val in summary(frame).items()})
        records.append(row)
    peer_columns = peer_keys + ['peer_' + key for key in summary(base.iloc[:0])]
    peers = pd.DataFrame(records, columns=peer_columns)
    if local.empty:
        for col in peer_columns[len(peer_keys):] + ['premium_pct', 'sufficient_data']:
            local[col] = pd.Series(dtype='float64')
        return local
    merged = local.merge(peers, on=peer_keys, how='left', validate='many_to_one')
    merged['sufficient_data'] = merged.priced_rows.ge(min_priced) & merged.peer_priced_rows.ge(min_priced)
    merged['premium_pct'] = (100 * (merged.median_price_usd / merged.peer_median_price_usd - 1)).where(
        merged.sufficient_data & merged.peer_median_price_usd.gt(0))
    return merged


def histogram(values):
    prices = pd.Series(values, dtype='float64').dropna()
    if prices.empty:
        return pd.DataFrame(columns=['left', 'right', 'count'])
    bins = 1 if prices.min() == prices.max() else 20
    counts, edges = np.histogram(prices, bins=bins)
    return pd.DataFrame({'left': edges[:-1], 'right': edges[1:], 'count': counts})
