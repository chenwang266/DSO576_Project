from streamlit.testing.v1 import AppTest
from src.config import ROOT


def test_app_defaults_snapshot_independence_and_reset():
    at=AppTest.from_file(str(ROOT/'app.py'),default_timeout=30).run()
    assert not at.exception
    assert at.selectbox(key='snapshot').value=='2026-06-15'
    assert at.selectbox(key='neighbourhood').value=='Hollywood'
    before=at.metric[5].value
    at.selectbox(key='snapshot').set_value('2026-03-16').run()
    assert not at.exception
    assert at.metric[5].value==before
    at.selectbox(key='neighbourhood').set_value('Venice').run()
    assert not at.exception
    at.button[0].click().run()
    assert at.selectbox(key='snapshot').value=='2026-06-15'
    assert at.selectbox(key='neighbourhood').value=='Hollywood'
    assert not at.exception


def test_altadena_ui_and_empty_shortlist():
    at=AppTest.from_file(str(ROOT/'app.py'),default_timeout=30).run()
    at.selectbox(key='neighbourhood').set_value('Altadena')
    at.selectbox(key='bedroom').set_value('3 bedroom')
    at.number_input(key='minimum').set_value(30).run()
    assert not at.exception
    assert at.metric[4].value=='Unavailable'
    comp=at.dataframe[3].value
    # Evidence is also checked independently through backend tests.
    assert any('current minimum' in w.value for w in at.warning)
    at.number_input(key='minimum').set_value(10000).run()
    assert not at.exception
    assert any('No persistent segments' in x.value for x in at.info)


def test_shared_filters_direction_and_shortlist_scope():
    at=AppTest.from_file(str(ROOT/'app.py'),default_timeout=30).run()
    at.selectbox(key='stay').set_value('Short stay (<30 nights)')
    at.selectbox(key='source').set_value('city scrape')
    at.radio(key='direction').set_value('Discount').run()
    assert not at.exception
    captions=[c.value for c in at.caption]
    evidence_count=next(c for c in captions if 'qualifying segments' in c)
    at.selectbox(key='neighbourhood').set_value('Venice')
    at.selectbox(key='room').set_value('Private room').run()
    assert not at.exception
    assert at.selectbox(key='stay').value=='Short stay (<30 nights)'
    assert at.selectbox(key='source').value=='city scrape'
    assert evidence_count in [c.value for c in at.caption]


def test_compact_shortlist_preserves_row_specific_coverage_warning():
    at=AppTest.from_file(str(ROOT/'app.py'),default_timeout=30).run()
    assert not at.exception
    compact=next(item.value for item in at.dataframe if {'Segment','rank','warnings'}.issubset(item.value.columns))
    row=compact.loc[compact.Segment.str.startswith('Malibu') & compact.Segment.str.endswith('3 BR')].iloc[0]
    assert 'March local price coverage 79.1% is below the 80%' in row.warnings
