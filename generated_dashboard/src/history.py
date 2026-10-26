import numpy as np
import pandas as pd
from src.data_access import KEYS, DATES


def snapshot_comparison(metrics):
    keys = KEYS[1:]
    march = metrics.loc[metrics.snapshot_date.eq(DATES[0])].drop(columns='snapshot_date')
    june = metrics.loc[metrics.snapshot_date.eq(DATES[1])].drop(columns='snapshot_date')
    result = march.merge(june, on=keys, how='outer', suffixes=('_march', '_june'), validate='one_to_one')
    m, j = result.premium_pct_march, result.premium_pct_june
    result['persistence'] = 'Insufficient evidence'
    both = m.notna() & j.notna()
    result.loc[both & m.gt(0) & j.gt(0), 'persistence'] = 'Persistent premium'
    result.loc[both & m.lt(0) & j.lt(0), 'persistence'] = 'Persistent discount'
    result.loc[both & ((m.gt(0) & j.lt(0)) | (m.lt(0) & j.gt(0))), 'persistence'] = 'Reversed'
    result.loc[both & (m.eq(0) | j.eq(0)), 'persistence'] = 'Neutral'
    result['change_usd'] = result.median_price_usd_june - result.median_price_usd_march
    result['change_pct'] = (100 * result.change_usd / result.median_price_usd_march).where(
        result.median_price_usd_march.gt(0))
    persistent = result.persistence.isin(['Persistent premium', 'Persistent discount'])
    result['review_score'] = pd.concat([m.abs(), j.abs()], axis=1).min(axis=1).where(persistent)
    return result


def ranked_review_list(comparison, direction='Both'):
    choices = {'Both': ['Persistent premium', 'Persistent discount'],
               'Premium': ['Persistent premium'], 'Discount': ['Persistent discount']}
    result = comparison.loc[comparison.persistence.isin(choices[direction])].copy()
    result = result.sort_values(['review_score', 'neighbourhood', 'room_type', 'bedrooms'],
        ascending=[False, True, True, True]).reset_index(drop=True)
    result.insert(0, 'rank', range(1, len(result) + 1))
    return result
