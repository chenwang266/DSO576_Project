import math

import pandas as pd
import pytest

from src.filters import OptionalFilters, SegmentSelection, apply_optional_filters, available_options
from src.pricing import aggregate, histogram_bins, segment_detail, segment_metrics
from tests.helpers import JUNE, MARCH, listings, priced, raw_row

ENTIRE_1 = dict(room_type="Entire home/apt", bedrooms="1")


def _select(neighbourhood="Hollywood", snapshot=MARCH, bedroom_segment="1 bedroom"):
    return SegmentSelection(snapshot, neighbourhood, "Entire home/apt", bedroom_segment)


def test_counts_coverage_and_context_from_missing_prices(tmp_path):
    rows = priced([100, 200, 300, 400], availability_90="10") + priced([None], availability_90="80")
    summary = aggregate(listings(tmp_path, {MARCH: rows})).iloc[0]
    assert (summary.listing_rows, summary.priced_rows, summary.price_coverage) == (5, 4, 0.8)
    assert summary.availability_90_n == 5  # missing-price listing still contributes context
    assert summary.availability_90_median == 10


@pytest.mark.parametrize("count, small", [(19, True), (20, False)])
def test_small_sample_flag(tmp_path, count, small):
    summary = aggregate(listings(tmp_path, {MARCH: priced(range(100, 100 + count))})).iloc[0]
    assert bool(summary.is_small_sample) is small


def test_numeric_reference_case(tmp_path):
    data = listings(tmp_path, {MARCH: priced([100, 200, None], neighbourhood_cleansed="Hollywood")
                               + priced([300, 400], neighbourhood_cleansed="Venice")})
    detail = segment_detail(data, _select(), min_priced=2)
    local, peer = detail["local"], detail["peer"]
    assert (local["median_price_usd"], local["p25_price_usd"], local["p75_price_usd"]) == (150, 125, 175)
    assert local["price_iqr_usd"] == 50 and local["price_coverage"] == 2 / 3
    assert peer["median_price_usd"] == 250 and peer["listing_rows"] == 5  # inclusive peer pools listings
    assert detail["premium_pct"] == pytest.approx(-40)
    unavailable = segment_detail(data, _select(), min_priced=20)
    assert math.isnan(unavailable["premium_pct"]) and unavailable["premium_status"] == "local_below_minimum"
    assert unavailable["local"]["median_price_usd"] == 150  # raw metrics retained below threshold
    assert any("Premium unavailable" in w for w in unavailable["warnings"])


def test_small_sample_independent_of_adjustable_minimum(tmp_path):
    # Regression for AUDIT-VL-02: the canonical flag stays priced_rows < 20 whatever the user minimum is.
    data = listings(tmp_path, {MARCH: priced(range(100, 120))})
    for minimum in (20, 30):
        metrics = segment_metrics(data, min_priced=minimum).iloc[0]
        assert not metrics.is_small_sample
        assert bool(metrics.sufficient_evidence) is (minimum == 20)


def test_peer_pools_listings_not_neighbourhood_medians(tmp_path):
    data = listings(tmp_path, {MARCH: priced([100], neighbourhood_cleansed="A") + priced([200, 300, 400],
                                                                                         neighbourhood_cleansed="B")})
    detail = segment_detail(data, _select("A"), min_priced=1)
    assert detail["peer"]["median_price_usd"] == 250  # pooled [100,200,300,400], not median(100, 300)=200


def test_segment_metrics_agree_with_detail(tmp_path):
    data = listings(tmp_path, {MARCH: priced([100, 200, None], neighbourhood_cleansed="Hollywood")
                               + priced([300, 400], neighbourhood_cleansed="Venice")
                               + priced([500], neighbourhood_cleansed="Venice", bedrooms="2")})
    metrics = segment_metrics(data, min_priced=2).set_index(["neighbourhood", "bedroom_segment"])
    row = metrics.loc[("Hollywood", "1 bedroom")]
    detail = segment_detail(data, _select(), min_priced=2)
    for col in ("listing_rows", "priced_rows", "price_coverage", "median_price_usd", "p25_price_usd"):
        assert row[col] == detail["local"][col]
    assert row.peer_median_price_usd == detail["peer"]["median_price_usd"]
    assert row.premium_pct == detail["premium_pct"]
    assert math.isnan(metrics.loc[("Venice", "2 bedrooms")].premium_pct)


def test_optional_filters_recalculate_from_listings(tmp_path):
    rows = (priced([100, 200], minimum_nights="2", source="city scrape")
            + priced([1000], minimum_nights="30", source="city scrape")
            + priced([50], minimum_nights="2", source="previous scrape"))
    data = listings(tmp_path, {MARCH: rows})
    full = segment_metrics(data, min_priced=1).iloc[0]
    short = segment_metrics(data, OptionalFilters(stay="Short stay (<30 nights)"), min_priced=1).iloc[0]
    both = segment_metrics(data, OptionalFilters("Short stay (<30 nights)", "city scrape"), min_priced=1).iloc[0]
    assert (full.listing_rows, full.median_price_usd) == (4, 150)
    assert (short.listing_rows, short.median_price_usd) == (3, 100)
    assert (both.listing_rows, both.median_price_usd) == (2, 150)
    assert len(apply_optional_filters(data, OptionalFilters(stay="Long stay (30+ nights)"))) == 1


def test_unknown_bedrooms_excluded_and_never_studio(tmp_path):
    data = listings(tmp_path, {MARCH: priced([100], bedrooms="0") + priced([999], bedrooms="")})
    metrics = segment_metrics(data, min_priced=1)
    assert metrics.bedroom_segment.tolist() == ["Studio"] and metrics.listing_rows.tolist() == [1]
    assert metrics.local_unknown_bedroom_share.iloc[0] == 0.5
    options = available_options(data)
    assert options["bedroom_segments"] == ["Studio"] and "Unknown" not in options["bedroom_segments"]
    detail = segment_detail(data, _select(bedroom_segment="Studio"), min_priced=1)
    assert any("Studio" in w for w in detail["warnings"])
    assert any("unknown bedrooms: 50.0%" in w for w in detail["warnings"])


def test_empty_segment_reports_reasons_not_zeros(tmp_path):
    data = listings(tmp_path, {MARCH: priced([100])})
    detail = segment_detail(data, _select("Nowhere"), min_priced=1)
    local = detail["local"]
    assert local["listing_rows"] == 0 and math.isnan(local["price_coverage"]) and math.isnan(local["median_price_usd"])
    assert detail["premium_status"] == "no_local_prices" and detail["histogram"].empty
    assert "No comparable listings" in detail["warnings"][0]
    only_missing = segment_detail(listings(tmp_path, {MARCH: priced([None, None])}), _select(), min_priced=1)
    assert only_missing["local"]["price_coverage"] == 0 and math.isnan(only_missing["local"]["median_price_usd"])


def test_nonpositive_peer_median_cannot_occur_but_is_handled():
    from src.pricing import premium
    value, status = premium([100], [0], [30], [30], 20)
    assert math.isnan(value[0]) and status[0] == "peer_median_nonpositive"


def test_histogram_bins():
    bins = histogram_bins(range(1, 101))
    assert len(bins) == 20 and bins["count"].sum() == 100
    assert bins.right.iloc[-1] - bins.left.iloc[0] == 99
    constant = histogram_bins([75, 75, 75])
    assert len(constant) == 1 and constant["count"].iloc[0] == 3
    assert histogram_bins([]).empty and histogram_bins(pd.Series([None], dtype=float)).empty


def test_inputs_not_mutated(tmp_path):
    data = listings(tmp_path, {MARCH: priced([100, 200]), JUNE: priced([150])})
    snapshot = data.copy(deep=True)
    segment_metrics(data, OptionalFilters(stay="Short stay (<30 nights)"))
    segment_detail(data, _select())
    pd.testing.assert_frame_equal(data, snapshot)


def test_invalid_minimum_rejected(tmp_path):
    data = listings(tmp_path, {MARCH: [raw_row()]})
    with pytest.raises(ValueError):
        segment_metrics(data, min_priced=0)
