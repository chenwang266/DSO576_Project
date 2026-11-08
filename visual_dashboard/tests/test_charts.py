import numpy as np
import pandas as pd
import pytest
from src.charts import (price_band,price_comparison,premium_comparison,context_comparison,evidence_coverage,bedroom_completeness,priority_bars,persistence_map,pattern_counts)
from src.history import comparison,shortlist

@pytest.fixture(scope='module')
def evidence(full_data):
    return comparison(full_data)

def select(table,name='Hollywood',room='Entire home/apt',bed='1 bedroom'):
    return table.loc[table.neighbourhood.eq(name)&table.room_type.eq(room)&table.bedroom_segment.eq(bed)].iloc[0]

def test_price_bands_are_observed_quartiles_not_uncertainty(evidence):
    row=select(evidence)
    fig=price_band(row,'june')
    assert list(fig.data[0].x)==[row.p25_price_usd_june,row.p75_price_usd_june]
    assert fig.data[1].x[0]==row.median_price_usd_june
    history=price_comparison(row)
    assert history.data[0].error_y.array[0]==row.p75_price_usd_march-row.median_price_usd_march
    assert history.data[0].error_y.arrayminus[0]==row.median_price_usd_march-row.p25_price_usd_march


def test_coverage_chart_reconciles_and_moves_threshold(evidence):
    row=select(evidence,'Malibu',bed='3 bedroom')
    for threshold in [.8,.75]:
        fig=evidence_coverage(row,threshold=threshold)
        assert fig.data[0].x[0]==pytest.approx(100*68/86)
        assert fig.data[0].customdata[0]==[68,86,18]
        assert np.array(fig.data[0].x)+np.array(fig.data[1].x)==pytest.approx([100]*4)
        assert fig.layout.shapes[0].x0==100*threshold


def test_context_retains_units_and_observation_counts(evidence):
    row=select(evidence);fig=context_comparison(row,'june')
    assert fig.data[0].y[0]==64 and fig.data[1].y[0]==55
    assert fig.data[0].customdata[0]==482
    assert fig.data[4].y[0]==row.value_score_median_june
    assert fig.layout.yaxis3.range==(0,5.55)
    bedroom=bedroom_completeness(row)
    assert bedroom.data[0].y[1]==100*row.local_unknown_bedroom_share_june


def test_priority_order_and_signed_premiums_are_preserved(evidence):
    ranked=shortlist(evidence,'Discount');fig=priority_bars(ranked,5)
    assert len(fig.data[0].y)==5
    assert list(fig.data[0].x)==list(ranked.head(5).premium_pct_march)
    assert all(x<0 for x in fig.data[1].x)
    assert fig.data[0].customdata[0][0]==1


def test_pattern_map_does_not_turn_missing_premiums_into_zero(evidence):
    fig=persistence_map(evidence)
    actual=sum(len(trace.x) for trace in fig.data)
    expected=len(evidence.dropna(subset=['premium_pct_march','premium_pct_june']))
    assert actual==expected
    counts=pattern_counts(evidence)
    assert sum(counts.data[0].x)==len(evidence)


def test_empty_charts_and_failed_premium_have_explicit_states(evidence):
    blank=evidence.iloc[0:0]
    assert len(priority_bars(blank).data)==0
    assert len(persistence_map(blank).data)==0
    row=select(evidence).copy();row['premium_pct_march']=None;row['premium_pct_june']=None
    assert len(premium_comparison(row).data)==0
    assert 'unavailable' in premium_comparison(row).layout.annotations[0].text
