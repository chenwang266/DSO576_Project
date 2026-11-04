import math

import pandas as pd
import pytest

from src.history import compare_snapshots, persistence_status, rank_shortlist
from src.pricing import segment_metrics
from tests.helpers import DATES, JUNE, MARCH, listings, priced


def _segment(neighbourhood, prices, bedrooms="1", room="Entire home/apt", **fields):
    return priced(prices, neighbourhood_cleansed=neighbourhood, bedrooms=bedrooms, room_type=room, **fields)


def _compare(tmp_path, march, june, min_priced=1, **kwargs):
    data = listings(tmp_path, {MARCH: march, JUNE: june})
    return compare_snapshots(segment_metrics(data, min_priced=min_priced), DATES, **kwargs)


def test_persistence_labels():
    first = pd.Series([10, -5, 10, 0, 10, None, -3.0])
    second = pd.Series([2, -1, -4, 3, None, 5, 0.0])
    assert persistence_status(first, second).tolist() == [
        "Persistent premium", "Persistent discount", "Reversed", "Neutral", "Insufficient evidence",
        "Insufficient evidence", "Neutral"]


def test_june_only_segment_keeps_null_march(tmp_path):
    result = _compare(tmp_path, _segment("A", [100]), _segment("A", [100]) + _segment("New", [300])).set_index(
        "neighbourhood")
    new = result.loc["New"]
    assert math.isnan(new.median_price_usd_march) and math.isnan(new.listing_rows_march)
    assert new.median_price_usd_june == 300
    assert math.isnan(new.change_usd) and math.isnan(new.change_pct)
    assert new.persistence == "Insufficient evidence"
    assert "March: no comparable listings" in new.warnings


def test_change_and_ranking(tmp_path):
    march = (_segment("High", [300, 300]) + _segment("Low", [100, 100]) + _segment("Mid", [250, 250])
             + _segment("Anchor", [200, 200]))  # pooled peer median 225
    june = (_segment("High", [330, 330]) + _segment("Low", [100, 100]) + _segment("Mid", [150, 150])
            + _segment("Anchor", [200, 200]))  # pooled peer median 175
    result = _compare(tmp_path, march, june).set_index("neighbourhood")
    high, low = result.loc["High"], result.loc["Low"]
    assert high.change_usd == 30 and high.change_pct == pytest.approx(10)
    assert high.premium_pct_march == pytest.approx(100 * (300 / 225 - 1))
    assert high.premium_pct_june == pytest.approx(100 * (330 / 175 - 1))
    assert high.persistence == "Persistent premium" and high.review_score == pytest.approx(100 * (300 / 225 - 1))
    assert low.persistence == "Persistent discount" and low.review_score == pytest.approx(100 * (1 - 100 / 175))
    assert result.loc["Mid"].persistence == "Reversed" and math.isnan(result.loc["Mid"].review_score)
    assert result.loc["Anchor"].persistence == "Reversed"
    ranked = rank_shortlist(result.reset_index())
    assert ranked.neighbourhood.tolist() == ["Low", "High"] and ranked["rank"].tolist() == [1, 2]
    assert rank_shortlist(result.reset_index(), "discount").neighbourhood.tolist() == ["Low"]
    assert rank_shortlist(result.reset_index(), "premium").direction.tolist() == ["Premium"]


def test_failed_evidence_threshold(tmp_path):
    result = _compare(tmp_path, _segment("A", [300]) + _segment("B", [100]),
                      _segment("A", [300]) + _segment("B", [100]), min_priced=2)
    assert set(result.persistence) == {"Insufficient evidence"}
    assert result.premium_pct_march.isna().all()
    assert "premium unavailable, local priced count 1 is below the minimum 2" in result.warnings.iloc[0]
    assert rank_shortlist(result).empty and "rank" in rank_shortlist(result).columns  # empty shortlist is valid


def test_deterministic_ties(tmp_path):
    # Identical premiums: order by neighbourhood, then room type, then numerical bedroom order (Studio < 2 < 6+).
    def seg(n, beds, price):
        return _segment(n, [price], bedrooms=beds)
    march = (seg("B", "1", 200) + seg("A", "1", 200) + seg("Z", "1", 100) + seg("Z", "1", 100)
             + seg("A", "0", 200) + seg("Z", "0", 100) + seg("A", "7", 200) + seg("Z", "7", 100)
             + seg("A", "2", 200) + seg("Z", "2", 100))
    result = _compare(tmp_path, march, march)
    ranked = rank_shortlist(result, "premium")
    order = list(zip(ranked.neighbourhood, ranked.bedroom_segment))
    assert order == [("A", "Studio"), ("A", "1 bedroom"), ("A", "2 bedrooms"), ("A", "6+ bedrooms"),
                     ("B", "1 bedroom")]
    assert ranked.review_score.nunique() == 1
    shuffled = rank_shortlist(result.sample(frac=1, random_state=3), "premium")
    assert shuffled.segment_key.tolist() == ranked.segment_key.tolist()


def test_row_warnings(tmp_path):
    march = (_segment("A", [100, 100, None]) + _segment("A", [100], bedrooms="0")
             + _segment("B", [200, 200]) + _segment("B", [200], bedrooms="0"))
    june = (_segment("A", [100, 100]) + _segment("A", [None, None, None], bedrooms="")
            + _segment("B", [200, 200]) + _segment("B", [200], bedrooms="0"))
    result = _compare(tmp_path, march, june, coverage_warning=0.8).set_index(["neighbourhood", "bedroom_segment"])
    a1 = result.loc[("A", "1 bedroom")].warnings
    assert "March local price coverage 66.7% is below the 80.0% warning threshold." in a1
    assert "June local price coverage" not in a1
    assert "Bedroom completeness shift (local neighbourhood/room): unknown-bedroom share 0.0% in March vs 60.0%" in a1
    assert "small sample, 2 priced listings" in a1
    assert "Studio comparisons" in result.loc[("B", "Studio")].warnings
    assert "Studio comparisons" not in result.loc[("B", "1 bedroom")].warnings
    relaxed = _compare(tmp_path, march, june, coverage_warning=0.6).set_index(["neighbourhood", "bedroom_segment"])
    assert "coverage" not in relaxed.loc[("A", "1 bedroom")].warnings
    assert relaxed.loc[("A", "1 bedroom")].priced_rows_march == 2  # counts unchanged by the warning threshold


def test_compare_rejects_mixed_inputs(tmp_path):
    data = listings(tmp_path, {MARCH: _segment("A", [1]), JUNE: _segment("A", [1])})
    mixed = pd.concat([segment_metrics(data, min_priced=1).iloc[:1], segment_metrics(data, min_priced=2).iloc[1:]])
    with pytest.raises(ValueError, match="minimum"):
        compare_snapshots(mixed, DATES)
    with pytest.raises(ValueError, match="direction"):
        rank_shortlist(compare_snapshots(segment_metrics(data, min_priced=1), DATES), "up")
