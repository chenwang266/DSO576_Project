import importlib
import math
import sys
import pandas as pd
import pytest
from scripts.canonical_clean import clean_snapshot, parse_price, parse_integer, run_pipeline
from tests.test_cleaner_original import sample_frame
from src.filters import optional_filters
from src.pricing import snapshot_summary, histogram
from src.history import comparison, persistence, shortlist
from src.data_access import load_data, fingerprint


def make_clean(tmp_path, rows):
    raw=sample_frame(**rows)
    path=tmp_path/'fixture.csv'
    raw.to_csv(path,index=False)
    return clean_snapshot(path,'2026-03-16')[0]

def test_spec_numeric_and_inclusive_peer(tmp_path):
    frame=make_clean(tmp_path,dict(id=['1','2','3','4','5'],neighbourhood_cleansed=['Local']*3+['Other']*2,price=['100','200','','300','400'],availability_90=['10','20','90','30','40']))
    row=snapshot_summary(frame,2).query("neighbourhood=='Local'").iloc[0]
    assert row.listing_rows==3 and row.priced_rows==2
    assert row.price_coverage==pytest.approx(2/3)
    assert (row.median_price_usd,row.p25_price_usd,row.p75_price_usd)==(150,125,175)
    assert row.peer_median_price_usd==250 and row.premium_pct==pytest.approx(-40)
    assert row.availability_90_valid_n==3 and row.availability_90_median==20
    assert pd.isna(snapshot_summary(frame,20).query("neighbourhood=='Local'").iloc[0].premium_pct)

def test_four_prices_one_missing(tmp_path):
    frame=make_clean(tmp_path,dict(id=list('12345'),price=['100','200','300','400','']))
    row=snapshot_summary(frame).iloc[0]
    assert (row.listing_rows,row.priced_rows,row.price_coverage)==(5,4,.8)

@pytest.mark.parametrize('n,expected',[(19,True),(20,False)])
def test_fixed_small_sample_independent_of_minimum(tmp_path,n,expected):
    frame=make_clean(tmp_path,dict(id=list(map(str,range(n)))))
    for threshold in [1,20,30]:
        row=snapshot_summary(frame,threshold).iloc[0]
        assert bool(row.is_small_sample)==expected
        assert bool(row.sufficient_data)==(n>=threshold)

@pytest.mark.parametrize('m,j,status',[(1,2,'Persistent premium'),(-1,-2,'Persistent discount'),(-1,2,'Reversed'),(0,2,'Neutral'),(2,0,'Neutral'),(0,0,'Neutral'),(math.nan,2,'Insufficient evidence')])
def test_persistence(m,j,status):
    assert persistence(m,j)==status

def test_outer_join_missing_date(tmp_path):
    frame=make_clean(tmp_path,dict(id=['1','2'],price=['100','200'],neighbourhood_cleansed=['Both','June only']))
    june=frame.copy(); june['snapshot_date']='2026-06-15'
    combined=pd.concat([frame.iloc[:1],june])
    row=comparison(combined,min_priced=1).query("neighbourhood=='June only'").iloc[0]
    assert pd.isna(row.median_price_usd_march) and pd.isna(row.change_usd)
    assert row.persistence_status=='Insufficient evidence'

def test_ranking_ties_and_direction():
    frame=pd.DataFrame([dict(neighbourhood=n,room_type='Entire home/apt',bedroom_segment=b,persistence_status=s,direction=d,review_score=score) for n,b,s,d,score in [('A','6+ bedrooms','Persistent premium','Premium',10),('A','2 bedroom','Persistent premium','Premium',10),('B','1 bedroom','Persistent discount','Discount',20),('Z','1 bedroom','Reversed','Unavailable',None)]])
    ranked=shortlist(frame)
    assert list(ranked.neighbourhood)==['B','A','A']
    assert list(ranked.bedroom_segment)==['1 bedroom','2 bedroom','6+ bedrooms']
    assert len(shortlist(frame,'Discount'))==1
    assert shortlist(frame.iloc[3:]).empty
    with pytest.raises(ValueError): shortlist(frame,'invalid')

def test_histogram_full_range_and_constant():
    values=[1,2,3,4,99999]
    bins=histogram(values)
    assert len(bins)==20 and bins['count'].sum()==5
    assert bins.left.min()==1 and bins.right.max()==99999
    assert len(histogram([100,100]))==1 and histogram([]).empty

@pytest.mark.parametrize('token,status', [('-10','invalid_nonpositive'),('$0.00','invalid_nonpositive'),('1e3','malformed'),('$1,234.56','valid'),('12,34','malformed'),('USD 100','malformed'),('','missing'),('$120abc','malformed')])
def test_strict_prices(token,status):
    _,statuses=parse_price(pd.Series([token],dtype='string'))
    assert statuses.iloc[0]==status

def test_optional_missing_ids_and_invalid_dimensions(tmp_path):
    raw=sample_frame(id=['00012345678901234567890'],bedrooms='',room_type='treehouse',minimum_nights='0',availability_90='91',review_scores_value='7').drop(columns=['source','minimum_nights','last_scraped'])
    path=tmp_path/'raw.csv';raw.to_csv(path,index=False)
    frame,_=clean_snapshot(path,'2026-03-16')
    assert frame.listing_id.iloc[0]=='00012345678901234567890'
    assert frame.room_type.iloc[0]=='Unknown' and frame.bedroom_segment.iloc[0]=='Unknown'
    assert frame.source.iloc[0]=='Unknown' and frame.stay_type.iloc[0]=='Unknown'
    assert pd.isna(frame.availability_90.iloc[0]) and pd.isna(frame.review_scores_value.iloc[0])
    assert not frame.pricing_eligible.iloc[0]
    assert comparison(frame).empty
    raw['id']=' ';raw.to_csv(path,index=False)
    with pytest.raises(ValueError,match='missing listing IDs'):clean_snapshot(path,'2026-03-16')

def test_reproducibility_hashes_and_tamper(tmp_path):
    path=tmp_path/'raw.csv';sample_frame().to_csv(path,index=False)
    a,b=tmp_path/'a',tmp_path/'b'
    r1=run_pipeline(path,path,a);r2=run_pipeline(path,path,b)
    assert r1==r2
    assert fingerprint(a)==fingerprint(b)
    data,_=load_data(a)
    assert data.listing_id.iloc[0]=='1001'
    (a/'canonical_listings_clean.csv').write_text('broken')
    with pytest.raises(ValueError,match='Integrity mismatch'):load_data(a)

def test_backend_does_not_import_streamlit():
    import subprocess
    result=subprocess.run([sys.executable,'-c',"import sys; from src import data_access,filters,pricing,history,charts; assert 'streamlit' not in sys.modules"],capture_output=True,text=True)
    assert result.returncode==0,result.stderr


def test_fingerprint_detects_same_length_report_change(tmp_path):
    path=tmp_path/'raw.csv';sample_frame().to_csv(path,index=False)
    out=tmp_path/'out';run_pipeline(path,path,out)
    before=fingerprint(out)
    report=out/'canonical_cleaning_report.json'
    text=report.read_text()
    changed=text.replace('canonical_clean.py','canonical_other.py')
    assert changed!=text
    report.write_text(changed)
    assert fingerprint(out)!=before


def test_missing_data_and_invalid_settings_fail_visibly(tmp_path):
    from src.config import validate_thresholds
    with pytest.raises(ValueError,match='Run the canonical cleaning command'):fingerprint(tmp_path)
    with pytest.raises(ValueError):validate_thresholds(0,.8)
    with pytest.raises(ValueError):validate_thresholds(20,1.1)
