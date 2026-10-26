"""Independent audit cases written after the initial app implementation.

Small cases are synthetic test inputs, not LA market evidence.
"""
import json
import math
from pathlib import Path
from statistics import median
import pandas as pd
import pytest
from src.data_access import DATES, KEYS
from src.pricing import detail, segment_metrics, histogram
from src.history import snapshot_comparison, ranked_review_list
from scripts.canonical_clean import clean, price, integer


def fixture_data():
    rows = []
    for date, groups in [(DATES[0], {'Hollywood': [100., 200., None], 'Other': [300., 400.]}),
                         (DATES[1], {'Hollywood': [150., 250., None], 'Other': [350., 450.],
                                     'JuneOnly': [90., 110.]})]:
        for name, values in groups.items():
            for i, value in enumerate(values):
                rows.append(dict(listing_id=f'{date}-{name}-{i}', snapshot_date=date,
                    neighbourhood=name, room_type='Entire home/apt', bedrooms=1,
                    price_usd=value, has_valid_price=value is not None,
                    pricing_eligible=value is not None, valid_dimensions=True,
                    availability_90=90 if value is None else 30, number_of_reviews_ltm=2,
                    review_scores_value=4., minimum_nights=2, stay='Short stay (<30 nights)', source='city scrape'))
    data = pd.DataFrame(rows)
    data['listing_id'] = data.listing_id.astype('string')
    return data


def test_independent_price_definition_and_context():
    data = fixture_data()
    result = detail(data, snapshot=DATES[0], neighbourhood='Hollywood', room_type='Entire home/apt', bedrooms=1, min_priced=2)
    local, peer = result['local'], result['peer']
    assert local['median_price_usd'] == median([100, 200]) == 150
    assert local['p25_price_usd'] == 125
    assert local['p75_price_usd'] == 175
    assert local['price_iqr_usd'] == 50
    assert local['listing_rows'] == 3 and local['priced_rows'] == 2
    assert local['price_coverage'] == 2 / 3
    assert peer['median_price_usd'] == median([100, 200, 300, 400]) == 250
    assert result['premium_pct'] == pytest.approx(-40)
    assert local['availability_90_n'] == 3  # Missing price still contributes context.
    assert local['availability_90_median'] == 30
    empty = detail(data, snapshot=DATES[0], neighbourhood='Absent', room_type='Entire home/apt', bedrooms=1)
    assert empty['local']['listing_rows'] == 0
    assert math.isnan(empty['local']['price_coverage'])


def test_change_and_outer_join_independent():
    data = fixture_data()
    result = snapshot_comparison(segment_metrics(data, min_priced=2)).set_index('neighbourhood')
    a = result.loc['Hollywood']
    baseline, current = median([100, 200]), median([150, 250])
    assert a.change_usd == current - baseline == 50
    assert a.change_pct == pytest.approx(100 * (current - baseline) / baseline)
    only = result.loc['JuneOnly']
    assert pd.isna(only.median_price_usd_march)
    assert pd.isna(only.change_usd) and pd.isna(only.change_pct)
    assert only.persistence == 'Insufficient evidence'
    shuffled = snapshot_comparison(segment_metrics(data.sample(frac=1, random_state=42), min_priced=2)).set_index('neighbourhood')
    pd.testing.assert_frame_equal(result, shuffled)


@pytest.mark.parametrize('baseline,current,amount,pct', [
    (150., 120., -30., -20.), (150., 150., 0., 0.),
    (0., 200., 200., None), (-10., 200., 210., None), (None, 200., None, None)])
def test_baseline_guards(baseline, current, amount, pct):
    metrics = segment_metrics(fixture_data(), min_priced=2)
    metrics = metrics.loc[metrics.neighbourhood.eq('Hollywood')].copy()
    metrics.loc[metrics.snapshot_date.eq(DATES[0]), 'median_price_usd'] = baseline
    metrics.loc[metrics.snapshot_date.eq(DATES[1]), 'median_price_usd'] = current
    row = snapshot_comparison(metrics).iloc[0]
    assert pd.isna(row.change_usd) if amount is None else row.change_usd == amount
    assert pd.isna(row.change_pct) if pct is None else row.change_pct == pytest.approx(pct)


@pytest.mark.parametrize('m,j,status,score', [(10, 20, 'Persistent premium', 10),
    (-10, -20, 'Persistent discount', 10), (10, -20, 'Reversed', None),
    (0, 20, 'Neutral', None), (None, 20, 'Insufficient evidence', None)])
def test_persistence_and_score(m, j, status, score):
    metrics = segment_metrics(fixture_data(), min_priced=2)
    metrics = metrics.loc[metrics.neighbourhood.eq('Hollywood')].copy()
    metrics.loc[metrics.snapshot_date.eq(DATES[0]), 'premium_pct'] = m
    metrics.loc[metrics.snapshot_date.eq(DATES[1]), 'premium_pct'] = j
    result = snapshot_comparison(metrics)
    assert result.iloc[0].persistence == status
    assert pd.isna(result.iloc[0].review_score) if score is None else result.iloc[0].review_score == score
    assert len(ranked_review_list(result)) == (0 if score is None else 1)


def test_threshold_and_histogram():
    base = fixture_data().iloc[[0]].copy()
    for count in [19, 20]:
        data = pd.concat([base.assign(listing_id=str(i)) for i in range(count)], ignore_index=True)
        metrics = segment_metrics(data)
        assert bool(metrics.iloc[0].is_small_sample) == (count < 20)
        assert bool(pd.isna(metrics.iloc[0].premium_pct)) == (count < 20)
    assert len(histogram([100, 100])) == 1
    bins = histogram([100, 150, 200, None])
    assert len(bins) == 20 and bins['count'].sum() == 3
    assert histogram([]).empty
    assert segment_metrics(fixture_data(), source='Absent').empty
    assert ranked_review_list(snapshot_comparison(segment_metrics(fixture_data()))).empty


def test_shared_filters_and_no_mutation():
    data = fixture_data()
    before = data.copy(deep=True)
    extra = data.iloc[[0]].assign(listing_id='extra', source='other', stay='Long stay (30+ nights)', price_usd=10000)
    combined = pd.concat([data, extra], ignore_index=True)
    expected = segment_metrics(data, min_priced=2)
    actual = segment_metrics(combined, min_priced=2, source='city scrape', stay='Short stay (<30 nights)')
    pd.testing.assert_frame_equal(expected, actual)
    pd.testing.assert_frame_equal(data, before)


def test_deterministic_ties_and_direction():
    comparison = snapshot_comparison(segment_metrics(fixture_data(), min_priced=2))
    row = comparison.loc[comparison.neighbourhood.eq('Hollywood')].iloc[[0]].copy()
    rows = []
    for name, bedroom in [('Z', 2), ('A', 10), ('A', 2)]:
        rows.append(row.assign(neighbourhood=name, bedrooms=bedroom, review_score=10., persistence='Persistent premium'))
    ranked = ranked_review_list(pd.concat(rows, ignore_index=True))
    assert list(zip(ranked.neighbourhood, ranked.bedrooms)) == [('A', 2), ('A', 10), ('Z', 2)]
    assert ranked_review_list(pd.concat(rows), 'Discount').empty


def test_cleaner_edge_cases(tmp_path):
    assert price('$1,234.50') == (1234.5, 'valid')
    assert price('12,34') == (None, 'malformed')
    assert price('0') == (None, 'invalid_nonpositive')
    assert price('') == (None, 'missing')
    raw = pd.DataFrame({'id': ['9007199254740993', '2', '3'], 'price': ['$100', '', '$200'],
        'neighbourhood_cleansed': [' Hollywood ', 'Hollywood', 'Hollywood'],
        'room_type': ['Entire home/apt'] * 3, 'bedrooms': ['0', '', '2.5'],
        'availability_30': ['30', '31', '1'], 'availability_60': ['30'] * 3,
        'availability_90': ['30'] * 3, 'availability_365': ['30'] * 3,
        'number_of_reviews_ltm': ['2'] * 3, 'number_of_reviews_l30d': ['1'] * 3,
        'review_scores_value': ['0', '5', '6']})
    path = tmp_path / 'raw.csv'
    raw.to_csv(path, index=False)
    result = clean(path, DATES[0])
    assert result.listing_id.iloc[0] == '9007199254740993'
    assert result.bedrooms.iloc[0] == 0 and pd.isna(result.bedrooms.iloc[1])
    assert pd.isna(result.bedrooms.iloc[2])
    assert pd.isna(result.availability_30.iloc[1])
    assert result.value_score_is_zero.iloc[0]
    assert pd.isna(result.review_scores_value.iloc[2])
    assert result.stay.eq('Unknown').all()
    raw.id = ['1', '1', '3']
    raw.to_csv(path, index=False)
    with pytest.raises(ValueError, match='duplicate'):
        clean(path, DATES[0])


def test_actual_app_comparison_interactions(tmp_path, monkeypatch):
    from streamlit.testing.v1 import AppTest
    data = fixture_data()
    data.to_csv(tmp_path / 'canonical_listings_clean.csv', index=False)
    (tmp_path / 'canonical_cleaning_report.json').write_text(json.dumps({'by_snapshot': {'test': 'Synthetic audit fixture, not LA observations'}}))
    monkeypatch.setenv('LA_DASHBOARD_DATA', str(tmp_path))
    app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / 'app.py')).run(timeout=60)
    assert not app.exception
    def values():
        return {item.label: item.value for item in app.metric}
    assert values()['March median'] == '$150.00'
    assert values()['June median'] == '$200.00'
    assert values()['Median change (USD)'] == '$50.00'
    assert values()['Median change (%)'] == '33.3%'
    app.selectbox(key='snapshot').set_value(DATES[0]).run(timeout=60)
    assert not app.exception
    assert values()['Local median'] == '$150.00'
    assert values()['June median'] == '$200.00'  # Snapshot switch must not change history.
    app.selectbox(key='neighbourhood').set_value('JuneOnly').run(timeout=60)
    assert not app.exception
    assert values()['March median'] == 'Unavailable'
    assert values()['June median'] == '$100.00'
    assert values()['Median change (%)'] == 'Unavailable'
    app.selectbox(key='neighbourhood').set_value('Other').run(timeout=60)
    assert values()['Median change (USD)'] == '$50.00'
    assert values()['Median change (%)'] == '14.3%'
    app.selectbox(key='snapshot').set_value(DATES[1]).run(timeout=60)
    assert values()['Local median'] == '$400.00'
    app.button[0].click().run(timeout=60)
    assert not app.exception
    assert app.selectbox(key='neighbourhood').value == 'Hollywood'
    assert values()['Median change (%)'] == '33.3%'
