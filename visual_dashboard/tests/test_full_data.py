import hashlib
from pathlib import Path
import pandas as pd
import pytest
from src.history import comparison, shortlist
from src.pricing import snapshot_summary
from src.config import ROOT
from scripts.canonical_clean import build_segment_summary

@pytest.fixture(scope='module')
def compared(full_data):
    return comparison(full_data)

def segment(table,neighbourhood,room,bedroom):
    return table.loc[table.neighbourhood.eq(neighbourhood)&table.room_type.eq(room)&table.bedroom_segment.eq(bedroom)].iloc[0]

def test_full_reference_counts(full_data):
    expected={'2026-03-16':(46088,8910,2570,3196),'2026-06-15':(43751,5565,9,9572)}
    for date, counts in expected.items():
        f=full_data.loc[full_data.snapshot_date.eq(date)]
        assert (len(f),f.price_status.eq('missing').sum(),f.bedroom_is_zero.sum(),f.bedroom_status.eq('missing').sum())==counts
    assert not full_data.duplicated(['snapshot_date','listing_id']).any()

def test_all_canonical_aggregates_reconcile(full_data):
    expected=pd.read_csv(ROOT/'data/processed/canonical_price_segments.csv')
    actual=build_segment_summary(full_data)
    pd.testing.assert_frame_equal(expected,actual,check_dtype=False,rtol=1e-12)
    shared=snapshot_summary(full_data)
    keys=['snapshot_date','neighbourhood','room_type','bedroom_segment']
    check=expected.merge(shared,on=keys,suffixes=('_canonical','_shared'))
    assert len(check)==len(expected)
    for name in ['listing_rows','priced_rows','price_coverage','median_price_usd','p25_price_usd','p75_price_usd','price_iqr_usd','is_small_sample']:
        pd.testing.assert_series_equal(check[name+'_canonical'],check[name+'_shared'],check_names=False,check_dtype=False,rtol=1e-12)

def test_ws01_bedroom_warning(compared):
    row=segment(compared,'Venice','Private room','1 bedroom')
    assert row.peer_unknown_bedroom_share_june>0.6
    assert 'bedroom completeness warning' in row.warnings
    hollywood=segment(compared,'Hollywood','Entire home/apt','1 bedroom')
    assert 'bedroom completeness warning' not in hollywood.warnings
    assert hollywood.local_unknown_bedroom_share_june - hollywood.local_unknown_bedroom_share_march > .14
    assert 'Local bedroom completeness deteriorated' in hollywood.warnings

def test_ws02_6plus(compared):
    row=segment(compared,'Hollywood Hills West','Entire home/apt','6+ bedrooms')
    assert (row.priced_rows_march,row.priced_rows_june)==(47,46)
    assert row.review_score==pytest.approx(81.050175,abs=1e-6)

def test_ws03_status_direction_filters(compared,full_data):
    ranked=shortlist(compared,'Discount')
    assert len(ranked)>0 and ranked.premium_pct_march.lt(0).all() and ranked.premium_pct_june.lt(0).all()
    assert compared.persistence_status.eq('Reversed').any()
    for stay,source in [('Short stay (<30 nights)',None),(None,'city scrape'),('Long stay (30+ nights)','city scrape')]:
        c=comparison(full_data,stay,source)
        r=segment(c,'Hollywood','Entire home/apt','1 bedroom')
        raw=full_data.loc[full_data.snapshot_date.eq('2026-06-15')&full_data.neighbourhood.eq('Hollywood')&full_data.room_type.eq('Entire home/apt')&full_data.bedroom_segment.eq('1 bedroom')]
        if stay:raw=raw.loc[raw.stay_type.eq(stay)]
        if source:raw=raw.loc[raw.source.eq(source)]
        assert r.median_price_usd_june==raw.price_usd.median()

def test_vl01_row_coverage_and_export(compared,full_data):
    r=segment(shortlist(compared),'Malibu','Entire home/apt','3 bedroom')
    assert (r.priced_rows_march,r.listing_rows_march)==(68,86)
    assert 'March local price coverage 79.1% is below the 80%' in r.warnings
    looser=segment(comparison(full_data,coverage_warning=.75),'Malibu','Entire home/apt','3 bedroom')
    assert 'March local price coverage' not in looser.warnings
    assert '79.1%' in pd.DataFrame([r]).to_csv(index=False)

def test_vl02_altadena_fixed_flag(full_data):
    for minimum in [20,30]:
        row=segment(comparison(full_data,min_priced=minimum),'Altadena','Entire home/apt','3 bedroom')
        assert row.priced_rows_june==20 and not row.is_small_sample_june
        assert row.sufficient_data_june==(minimum==20)
        assert pd.isna(row.premium_pct_june)==(minimum==30)

def test_rl01_hollywood_change(compared):
    row=segment(compared,'Hollywood','Entire home/apt','1 bedroom')
    assert row.median_price_usd_march==162.91
    assert row.median_price_usd_june==160.87
    assert row.change_usd==pytest.approx(-2.04)

def test_studio_warning(compared):
    assert compared.loc[compared.bedroom_segment.eq('Studio'),'warnings'].str.contains('Studio coding warning').all()
