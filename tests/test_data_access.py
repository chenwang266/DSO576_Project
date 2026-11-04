import json

import pytest

from src.cleaning import run_cleaning
from src.config import ConfigError, Snapshot, load_settings
from src.data_access import LISTINGS_FILE, CanonicalDataError, combined_fingerprint, load_canonical
from tests.helpers import DATES, JUNE, MARCH, raw_row, write_raw


@pytest.fixture
def canonical_dir(tmp_path):
    march = write_raw(tmp_path / "m.csv", [raw_row(id="0012"), raw_row(id="2", price="")])
    june = write_raw(tmp_path / "j.csv", [raw_row(id="0012", bedrooms="0")])
    run_cleaning((Snapshot("March", MARCH, march), Snapshot("June", JUNE, june)), tmp_path / "out")
    return tmp_path / "out"


def test_typed_round_trip(canonical_dir):
    data = load_canonical(canonical_dir, DATES)
    listings = data.listings
    assert listings.listing_id.tolist() == ["0012", "2", "0012"]
    assert str(listings.listing_id.dtype) == "string"
    for col in ("has_valid_price", "has_valid_dimensions", "pricing_eligible", "value_score_is_zero"):
        assert str(listings[col].dtype) == "boolean"
    assert listings.has_valid_price.tolist() == [True, False, True]
    assert str(listings.bedrooms.dtype) == "Int64"
    assert listings.bedroom_segment.tolist() == ["1 bedroom", "1 bedroom", "Studio"]
    assert len(data.fingerprint) == 64


def test_missing_files_are_actionable(tmp_path):
    with pytest.raises(CanonicalDataError, match="scripts/canonical_clean.py"):
        load_canonical(tmp_path, DATES)


def _rewrite(path, transform):
    lines = path.read_text(encoding="utf-8").splitlines()
    path.write_text("\n".join(transform(lines)) + "\n", encoding="utf-8")


def test_schema_and_key_checks(canonical_dir):
    path = canonical_dir / LISTINGS_FILE
    original = path.read_text(encoding="utf-8")
    _rewrite(path, lambda lines: [lines[0], lines[1], lines[1], *lines[2:]])
    with pytest.raises(CanonicalDataError, match="Duplicate"):
        load_canonical(canonical_dir, DATES)
    path.write_text(original, encoding="utf-8")
    _rewrite(path, lambda lines: [line.split(",", 1)[1] for line in lines])  # drop snapshot_date
    with pytest.raises(CanonicalDataError, match="missing columns"):
        load_canonical(canonical_dir, DATES)
    path.write_text(original.replace(",True,", ",yes,", 1), encoding="utf-8")
    with pytest.raises(CanonicalDataError, match="Boolean"):
        load_canonical(canonical_dir, DATES)
    path.write_text(original, encoding="utf-8")
    with pytest.raises(CanonicalDataError, match="Unexpected snapshot dates"):
        load_canonical(canonical_dir, ("2026-03-16", "2026-12-01"))


def test_fingerprint_changes_with_content(canonical_dir):
    before = combined_fingerprint(canonical_dir)
    path = canonical_dir / LISTINGS_FILE
    path.write_text(path.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    assert combined_fingerprint(canonical_dir) != before


def test_settings_validation(tmp_path):
    settings = load_settings()
    assert settings.dates == DATES and settings.min_priced_count == 20 and settings.coverage_warning == 0.8
    bad = tmp_path / "bad.json"
    for payload, message in [({"snapshots": []}, "exactly two"),
                             ({"snapshots": [{"label": "a", "date": "2026-06-15", "path": "x"},
                                             {"label": "b", "date": "2026-03-16", "path": "y"}]}, "chronological"),
                             ({"snapshots": [{"label": "a", "date": "2026-03-16", "path": "x"},
                                             {"label": "b", "date": "2026-06-15", "path": "y"}],
                               "min_priced_count": 0}, "positive integer")]:
        bad.write_text(json.dumps(payload))
        with pytest.raises(ConfigError, match=message):
            load_settings(bad)
