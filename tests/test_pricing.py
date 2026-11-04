import pandas as pd
from pricing_backend import metrics, history, shortlist, DATES, CONTEXT

def fixture():
    rows=[]
    for date in DATES:
        for hood, prices in [('A',[100,200,None]), ('B',[300,400])]:
            for price in prices:
                rows.append(dict(snapshot_date=date,neighbourhood=hood,room_type='Entire home/apt',bedroom_segment='1 bedroom',price_usd=price,**{k:1 for k in CONTEXT}))
    return pd.DataFrame(rows)

def test_inclusive_peer_and_threshold():
    m=metrics(fixture(),2)
    r=m[m.neighbourhood.eq('A')].iloc[0]
    assert r.median_price_usd==150 and r.median_price_usd_peer==250
    assert r.p25_price_usd==125 and r.p75_price_usd==175
    assert r.price_coverage==2/3 and r.premium_pct==-40
    assert pd.isna(metrics(fixture(),20).premium_pct.iloc[0])
    assert r.number_of_reviews_ltm_valid_count==3

def test_missing_date_and_ranking():
    d=fixture()
    d=d[~(d.neighbourhood.eq('B') & d.snapshot_date.eq(DATES[0]))]
    h=history(metrics(d,2))
    assert h[h.neighbourhood.eq('B')].persistence.iloc[0]=='Insufficient evidence'
    assert pd.isna(h[h.neighbourhood.eq('B')].median_price_usd_march.iloc[0])

def test_small_sample_fixed():
    d=pd.concat([fixture().iloc[[0]]]*20,ignore_index=True)
    for minimum in [20,30]:
        r=metrics(d,minimum).iloc[0]
        assert not r.is_small_sample
        assert r.sufficient_data == (minimum==20)

def test_warning_threshold_export():
    h=history(metrics(fixture(),2))
    out=shortlist(h,.8)
    assert 'march local coverage' in out[out.neighbourhood.eq('A')].warnings.iloc[0]
    assert 'march local coverage' not in shortlist(h,.6).query("neighbourhood == 'A'").warnings.iloc[0]
