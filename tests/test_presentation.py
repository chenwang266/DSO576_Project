import io
import math

import pandas as pd

from src import charts
from src import presentation as fmt
from src.filters import OptionalFilters
from src.history import compare_snapshots, rank_shortlist
from src.pricing import histogram_bins, segment_metrics
from tests.helpers import DATES, JUNE, MARCH, listings, priced

VIEW = fmt.ViewSettings(DATES, ("March", "June"), OptionalFilters(), 2, 0.8, 20, 0.1, "abc123")


def _segment(neighbourhood, prices, bedrooms="1"):
    return priced(prices, neighbourhood_cleansed=neighbourhood, bedrooms=bedrooms)


def _comparison(tmp_path):
    march = _segment("High", [300, 300]) + _segment("Low", [100, 100]) + _segment("Mid", [100 / 3, 250])
    june = _segment("High", [310, 290]) + _segment("Low", [90, 110]) + _segment("Mid", [250, 250])
    data = listings(tmp_path, {MARCH: march, JUNE: june})
    return compare_snapshots(segment_metrics(data, min_priced=2), DATES)


def test_formatting_rules():
    assert fmt.fmt_usd(1234.5) == "$1,234.50"
    assert fmt.fmt_usd(float("nan")) == fmt.UNAVAILABLE
    assert fmt.fmt_pct(-40.04, signed=True) == "-40.0%"
    assert fmt.fmt_pct(12.34, signed=True) == "+12.3%" and fmt.fmt_pct(79.06) == "79.1%"
    assert fmt.fmt_pct(None) == fmt.UNAVAILABLE
    assert fmt.fmt_share(2 / 3) == "66.7%"
    assert fmt.fmt_share(float("nan")) == fmt.UNAVAILABLE
    assert fmt.fmt_usd_change(-2.04) == "-$2.04" and fmt.fmt_usd_change(3) == "+$3.00"
    assert fmt.fmt_number(4.80) == "4.8" and fmt.fmt_number(30.0) == "30" and fmt.fmt_number(0) == "0"
    assert fmt.fmt_count(pd.NA) == "0" and fmt.fmt_count(1234) == "1,234"


def test_shortlist_display_keeps_order_and_text_direction_labels(tmp_path):
    shortlist = rank_shortlist(_comparison(tmp_path))
    display = fmt.shortlist_display(shortlist, ("March", "June"))
    assert display.Rank.tolist() == shortlist["rank"].tolist()
    assert display.Segment.tolist() == [fmt.segment_label(n, r, b) for n, r, b in
                                        shortlist[["neighbourhood", "room_type", "bedroom_segment"]].itertuples(
                                            index=False)]
    assert set(display.Direction) <= {"▲ Premium", "▼ Discount"}  # direction is not conveyed by colour alone
    assert not display.isna().any().any()


def test_shortlist_export_full_precision_with_settings(tmp_path):
    shortlist = rank_shortlist(_comparison(tmp_path))
    exported = pd.read_csv(io.BytesIO(fmt.to_csv_bytes(fmt.shortlist_export(shortlist, VIEW, "both"))))
    assert len(exported) == len(shortlist)
    for column in ("canonical_fingerprint", "march_nominal_date", "june_nominal_date", "stay_filter",
                   "source_filter", "min_priced_count", "coverage_warning_threshold", "shortlist_direction",
                   "peer_definition", "listing_rows_march", "priced_rows_june", "peer_priced_rows_march",
                   "warnings", "review_score"):
        assert column in exported.columns, column
    assert exported.min_priced_count.unique().tolist() == [2]
    assert exported.review_score.tolist() == shortlist.review_score.tolist()  # exact round trip, no rounding
    assert exported.premium_pct_march.tolist() == shortlist.premium_pct_march.tolist()


def test_empty_shortlist_exports_header_only(tmp_path):
    empty = rank_shortlist(_comparison(tmp_path)).iloc[0:0]
    exported = pd.read_csv(io.BytesIO(fmt.to_csv_bytes(fmt.shortlist_export(empty, VIEW, "premium"))))
    assert exported.empty and "rank" in exported.columns


def test_evidence_export(tmp_path):
    comparison = _comparison(tmp_path)
    row = comparison.loc[comparison.neighbourhood.eq("Mid")].iloc[0].to_dict()
    evidence = fmt.evidence_export(row, VIEW, ("Mid", "Entire home/apt", "1 bedroom"), ["a warning"], "June")
    values = dict(zip(evidence.field, evidence.value))
    assert values["median_price_usd_march"] == row["median_price_usd_march"]  # full precision kept
    assert values["min_priced_count"] == 2 and values["neighbourhood"] == "Mid"
    assert ("detail warnings (June)", "warning", "a warning") in evidence.itertuples(index=False, name=None)
    missing = fmt.evidence_export(None, VIEW, ("Nowhere", "Entire home/apt", "1 bedroom"))
    assert "No comparable listings" in missing.value.iloc[-1]


def test_methodology_mentions_policies_and_peer_definition():
    report = {"snapshots": [{"label": "March", "nominal_date": MARCH, "rows": 5,
                             "actual_scrape_dates": {"2026-03-16": 2, "2026-03-18": 3},
                             "price_status": {"missing": 1, "valid": 4}, "pricing_eligible": 3,
                             "bedrooms": {"segments": {"Unknown": 1}, "known_share": 0.8, "zero_bedrooms": 0}}]}
    text = fmt.methodology_markdown(report, VIEW)
    assert "Inside Airbnb" in text and "including the selected neighbourhood" in text
    assert "2026-03-16 to 2026-03-18" in text and "1 unknown-bedroom" in text
    assert "not statistical significance" in text


def test_charts_handle_empty_and_unavailable():
    assert charts.price_histogram(histogram_bins([]), float("nan"), "t") is None
    constant = charts.price_histogram(histogram_bins([100, 100]), 100.0, "t")
    assert len(constant.data[0].x) == 1
    row = {"premium_pct_march": float("nan"), "premium_pct_june": -40.0,
           "median_price_usd_march": float("nan"), "median_price_usd_june": 150.0,
           "p25_price_usd_june": 125.0, "p75_price_usd_june": 175.0, "peer_median_price_usd_june": 250.0,
           "peer_p25_price_usd_june": 225.0, "peer_p75_price_usd_june": 275.0}
    premiums = charts.comparison_premiums(row, ("March", "June"), ("march", "june"))
    assert list(premiums.data[0].text) == ["Unavailable", "-40.0%"]
    assert premiums.data[0].y[0] is None  # never drawn as zero
    prices = charts.comparison_prices(row, ("March", "June"), ("march", "june"))
    assert list(prices.data[0].x) == ["June"] and math.isclose(prices.data[0].error_y.array[0], 25.0)
