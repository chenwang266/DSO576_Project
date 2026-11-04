import json

import pandas as pd
import pytest

from scripts.canonical_clean import main as cli_main
from src.cleaning import CleaningError, parse_price, run_cleaning
from src.config import Snapshot
from src.data_access import (LISTINGS_FILE, REPORT_FILE, SEGMENTS_FILE, fingerprint, load_canonical,
                             validate_listings)
from tests.helpers import DATES, JUNE, MARCH, RAW_FIELDS, clean_rows, raw_row, write_raw


@pytest.mark.parametrize("text, expected", [
    ("$1,234.56", (1234.56, "valid")), ("$85.00", (85.0, "valid")), ("120", (120.0, "valid")),
    ("  $9.5 ", (9.5, "valid")), ("$12,345", (12345.0, "valid")), ("", (None, "missing")), ("   ", (None, "missing")),
    ("$0.00", (None, "invalid_nonpositive")), ("-$5.00", (None, "invalid_nonpositive")),
    ("$-5", (None, "invalid_nonpositive")), ("$1,23.00", (None, "malformed")), ("abc", (None, "malformed")),
    ("€50", (None, "malformed")), ("$5.001", (None, "malformed")), ("$1 000", (None, "malformed")),
    ("--5", (None, "malformed")), ("$100,000,000.00", (100000000.0, "valid")),
])
def test_price_parsing(text, expected):
    assert parse_price(text) == expected


def test_field_rules(tmp_path):
    rows = [
        raw_row(id=" 007 ", price="$0.00", bedrooms="0", neighbourhood_cleansed="  Echo   Park ", minimum_nights="0"),
        raw_row(id="008", price="bad", bedrooms="", room_type="Castle", minimum_nights="30"),
        raw_row(id="009", price="", bedrooms="7", neighbourhood_cleansed="", minimum_nights="abc"),
        raw_row(id="010", bedrooms="-1", availability_30="31", availability_90="-2", review_scores_value="0"),
        raw_row(id="011", bedrooms="2.5", review_scores_value="5.5", number_of_reviews_ltm="x"),
        raw_row(id="012", price="$99,999.99", bedrooms="6", review_scores_value="", minimum_nights="29"),
    ]
    out = clean_rows(tmp_path, rows).set_index("listing_id")
    assert list(out.index) == ["007", "008", "009", "010", "011", "012"]  # trimmed exact strings, leading zeros kept
    assert out.loc["007", "price_status"] == "invalid_nonpositive" and pd.isna(out.loc["007", "price_usd"])
    assert out.loc["008", "price_status"] == "malformed" and out.loc["008", "price_raw"] == "bad"
    assert out.loc["009", "price_status"] == "missing"
    assert out.loc["012", "price_usd"] == 99999.99  # extreme price kept, not capped
    assert out.loc["007", "bedroom_segment"] == "Studio" and out.loc["007", "bedrooms_status"] == "valid"
    assert out.loc["008", "bedroom_segment"] == "Unknown" and out.loc["008", "bedrooms_status"] == "missing"
    assert out.loc["009", "bedroom_segment"] == "6+ bedrooms" and out.loc["009", "bedrooms"] == 7
    assert out.loc["010", "bedroom_segment"] == "Unknown" and out.loc["010", "bedrooms_status"] == "out_of_range"
    assert out.loc["011", "bedroom_segment"] == "Unknown" and out.loc["011", "bedrooms_status"] == "malformed"
    assert out.loc["007", "neighbourhood"] == "Echo Park" and out.loc["007", "neighbourhood_raw"] == "  Echo   Park "
    assert out.loc["009", "neighbourhood"] == "Unknown"
    assert out.loc["008", "room_type"] == "Unknown" and out.loc["008", "room_type_raw"] == "Castle"
    assert [out.loc[i, "stay_category"] for i in ["007", "008", "009", "012"]] == [
        "Unknown", "Long stay (30+ nights)", "Unknown", "Short stay (<30 nights)"]
    assert out.loc["010", "availability_30_status"] == "out_of_range" and pd.isna(out.loc["010", "availability_30"])
    assert out.loc["010", "availability_90_status"] == "out_of_range"
    assert bool(out.loc["010", "value_score_is_zero"]) and out.loc["010", "review_scores_value"] == 0
    assert out.loc["011", "review_scores_value_status"] == "out_of_range"
    assert out.loc["012", "review_scores_value_status"] == "missing"
    assert out.loc["011", "number_of_reviews_ltm_status"] == "malformed"
    eligible = out.pricing_eligible.astype(bool)
    assert eligible.to_dict() == {"007": False, "008": False, "009": False, "010": False, "011": False, "012": True}
    assert out.segment_key.isna().to_dict() == {"007": False, "008": True, "009": True, "010": True, "011": True,
                                                "012": False}
    assert not {"host_name", "latitude", "longitude"} & set(out.columns)
    validate_listings(out.reset_index())


def test_missing_optional_fields_stay_unavailable(tmp_path):
    fields = [f for f in RAW_FIELDS if f not in {"minimum_nights", "source", "reviews_per_month", "number_of_reviews"}]
    out = clean_rows(tmp_path, [raw_row()], fields=fields)
    assert out.minimum_nights_status.iloc[0] == "unavailable" and out.stay_category.iloc[0] == "Unknown"
    assert out.source_category.iloc[0] == "Unknown" and pd.isna(out.source_raw.iloc[0])
    assert out.reviews_per_month_status.iloc[0] == "unavailable" and pd.isna(out.reviews_per_month.iloc[0])


@pytest.mark.parametrize("rows, fields, message", [
    ([raw_row(id="1"), raw_row(id=" 1")], None, "duplicate listing ids"),
    ([raw_row(id="  ")], None, "missing listing id"),
    ([raw_row()], [f for f in RAW_FIELDS if f != "bedrooms"], "missing required fields"),
])
def test_hard_failures(tmp_path, rows, fields, message):
    with pytest.raises(CleaningError, match=message):
        clean_rows(tmp_path, rows, fields=fields)


def _raw_pair(tmp_path, gz=True):
    suffix = ".csv.gz" if gz else ".csv"
    march = write_raw(tmp_path / f"march{suffix}", [raw_row(id="1", price="$100.00"), raw_row(id="2", price=""),
                                                    raw_row(id="3", bedrooms="")])
    june = write_raw(tmp_path / f"june{suffix}", [raw_row(id="1", price="$120.00"), raw_row(id="4", price="$80.00")])
    return (Snapshot("March", MARCH, march), Snapshot("June", JUNE, june))


@pytest.mark.parametrize("gz", [True, False])
def test_run_cleaning_end_to_end(tmp_path, gz):
    snapshots = _raw_pair(tmp_path, gz)
    raw_hashes = [fingerprint(s.path) for s in snapshots]
    report = run_cleaning(snapshots, tmp_path / "out")
    assert [fingerprint(s.path) for s in snapshots] == raw_hashes
    assert all(item["unchanged"] for item in report["inputs"])
    assert report["row_counts"] == {"total": 5, MARCH: 3, JUNE: 2}
    data = load_canonical(tmp_path / "out", DATES)
    assert len(data.listings) == 5 and data.listings.listing_id.dtype == "string"
    seg = data.segments.set_index("snapshot_date")
    assert seg.loc[MARCH, "listing_rows"] == 2 and seg.loc[MARCH, "priced_rows"] == 1  # Unknown bedroom excluded
    assert seg.loc[MARCH, "price_coverage"] == 0.5 and bool(seg.loc[MARCH, "is_small_sample"])
    comparable = data.listings[data.listings.has_valid_dimensions.astype(bool)].groupby("snapshot_date").size()
    assert data.segments.groupby("snapshot_date").listing_rows.sum().to_dict() == comparable.to_dict()
    assert report["snapshots"][0]["bedrooms"]["status"] == {"missing": 1, "valid": 2}


def test_cleaning_is_reproducible(tmp_path):
    snapshots = _raw_pair(tmp_path)
    run_cleaning(snapshots, tmp_path / "a")
    run_cleaning(snapshots, tmp_path / "b")
    for name in (LISTINGS_FILE, SEGMENTS_FILE, REPORT_FILE):
        assert (tmp_path / "a" / name).read_bytes() == (tmp_path / "b" / name).read_bytes()


def test_missing_input_gives_setup_guidance(tmp_path, capsys):
    snapshots = (Snapshot("March", MARCH, tmp_path / "absent.csv.gz"), Snapshot("June", JUNE, tmp_path / "x.csv"))
    with pytest.raises(CleaningError, match="No substitute data is downloaded"):
        run_cleaning(snapshots, tmp_path / "out")
    code = cli_main(["--march", str(tmp_path / "absent.csv.gz"), "--june", str(tmp_path / "x.csv"),
                     "--output-dir", str(tmp_path / "out")])
    assert code == 2 and "not found" in capsys.readouterr().err
    assert not (tmp_path / "out").exists()


def test_cli_writes_artifacts(tmp_path):
    march, june = _raw_pair(tmp_path)
    assert cli_main(["--march", str(march.path), "--june", str(june.path), "--output-dir", str(tmp_path / "o")]) == 0
    report = json.loads((tmp_path / "o" / REPORT_FILE).read_text())
    assert report["outputs"][LISTINGS_FILE]["rows"] == 5
