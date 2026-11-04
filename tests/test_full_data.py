"""Checks against the real canonical artifacts and raw snapshots. Skipped (not passed) when files are absent."""
import csv
import gzip
import statistics
from functools import lru_cache

import pandas as pd
import pytest

from src.config import load_settings
from src.data_access import fingerprint, load_canonical
from src.history import compare_snapshots, rank_shortlist
from src.pricing import SEGMENT_KEYS, aggregate, segment_metrics

SETTINGS = load_settings()
TEAM_RAW_SHA256 = {  # documented in the team's earlier cleaning report and audits
    "2026-03-16": "ffdef08afe58b62e57cffb9da0f1daa97bf76e223fe98ce9e2022dd330976fc6",
    "2026-06-15": "ebc99e8a5ff2f60cbd91323571c2bdf1f8c2c74fe3ac9669d7c9a24d2294dec5",
}
needs_canonical = pytest.mark.skipif(
    not (SETTINGS.processed_dir / "canonical_listings_clean.csv").exists(), reason="canonical artifacts not generated")
needs_raw = pytest.mark.skipif(not all(s.path.exists() for s in SETTINGS.snapshots), reason="raw snapshots absent")


@lru_cache(maxsize=1)
def canonical():
    return load_canonical(SETTINGS.processed_dir, SETTINGS.dates)


@lru_cache(maxsize=1)
def comparison():
    return compare_snapshots(segment_metrics(canonical().listings, min_priced=20), SETTINGS.dates)


@needs_canonical
def test_reference_counts_recalculated():
    listings = canonical().listings
    expected = {"2026-03-16": (46088, 8910, 2570, 3196), "2026-06-15": (43751, 5565, 9, 9572)}
    for date, (rows, missing_price, zero_bed, missing_bed) in expected.items():
        frame = listings[listings.snapshot_date == date]
        assert len(frame) == rows
        assert frame.price_status.eq("missing").sum() == missing_price
        assert frame.bedrooms.eq(0).sum() == zero_bed
        assert frame.bedrooms_status.eq("missing").sum() == missing_bed


@needs_canonical
@needs_raw
def test_raw_hashes_unchanged():
    report = canonical().report
    for item, snapshot in zip(report["inputs"], SETTINGS.snapshots):
        assert item["sha256_before"] == item["sha256_after"] == fingerprint(snapshot.path)
        assert item["sha256_before"] == TEAM_RAW_SHA256[snapshot.date]


@needs_canonical
def test_segment_file_reconciles_with_backend():
    data = canonical()
    recomputed = aggregate(data.listings, SEGMENT_KEYS).set_index(SEGMENT_KEYS)
    stored = data.segments.set_index(SEGMENT_KEYS)
    assert stored.index.sort_values().equals(recomputed.index.sort_values())
    for col in ("listing_rows", "priced_rows", "price_coverage", "median_price_usd", "p25_price_usd",
                "p75_price_usd", "min_price_usd", "max_price_usd"):
        pd.testing.assert_series_equal(stored[col].astype(float), recomputed.loc[stored.index, col].astype(float),
                                       check_names=False, rtol=0, atol=1e-9)
    assert not {"latitude", "longitude", "host_id", "host_name"} & set(data.listings.columns)


def _oracle(path, neighbourhood, room, beds):
    """Independent recomputation from the raw file using only the standard library."""
    def bucket(text):
        return min(int(text), 6) if text.strip().isdigit() else None
    local, peer, local_listings = [], [], 0
    with gzip.open(path, "rt", newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            hood = " ".join(row["neighbourhood_cleansed"].split())
            if row["room_type"].strip() != room or bucket(row["bedrooms"]) != beds or not hood:
                continue
            price = row["price"].strip().replace("$", "").replace(",", "")
            value = float(price) if price else None
            local_listings += hood == neighbourhood
            if value and value > 0:
                peer.append(value)
                if hood == neighbourhood:
                    local.append(value)
    return local_listings, local, peer


@needs_canonical
@needs_raw
@pytest.mark.parametrize("neighbourhood, room, beds, label", [
    ("Hollywood", "Entire home/apt", 1, "1 bedroom"),
    ("Hollywood Hills West", "Entire home/apt", 6, "6+ bedrooms"),
    ("Venice", "Private room", 1, "1 bedroom"),
])
def test_backend_matches_independent_raw_oracle(neighbourhood, room, beds, label):
    row = comparison().set_index(["neighbourhood", "room_type", "bedroom_segment"]).loc[(neighbourhood, room, label)]
    for snapshot in SETTINGS.snapshots:
        suffix = snapshot.label.lower()
        listings, local, peer = _oracle(snapshot.path, neighbourhood, room, beds)
        assert row[f"listing_rows_{suffix}"] == listings
        assert row[f"priced_rows_{suffix}"] == len(local)
        assert row[f"median_price_usd_{suffix}"] == pytest.approx(statistics.median(local), abs=1e-9)
        assert row[f"peer_median_price_usd_{suffix}"] == pytest.approx(statistics.median(peer), abs=1e-9)
        if len(local) >= 20 and len(peer) >= 20:
            expected = 100 * (statistics.median(local) / statistics.median(peer) - 1)
            assert row[f"premium_pct_{suffix}"] == pytest.approx(expected, abs=1e-9)


@needs_canonical
def test_documented_team_figures():
    c = comparison().set_index(["neighbourhood", "room_type", "bedroom_segment"])
    hollywood = c.loc[("Hollywood", "Entire home/apt", "1 bedroom")]
    assert (hollywood.median_price_usd_march, hollywood.median_price_usd_june) == (162.91, 160.87)
    assert hollywood.change_usd == pytest.approx(-2.04) and round(hollywood.change_pct, 1) == -1.3
    hhw = c.loc[("Hollywood Hills West", "Entire home/apt", "6+ bedrooms")]
    assert (hhw.priced_rows_march, hhw.priced_rows_june) == (47, 46)
    assert hhw.review_score == pytest.approx(81.050175, abs=1e-6)
    ranked = rank_shortlist(comparison()).set_index(["neighbourhood", "room_type", "bedroom_segment"])
    malibu = ranked.loc[("Malibu", "Entire home/apt", "3 bedrooms")]
    assert malibu["rank"] == 5 and "March local price coverage 79.1%" in malibu.warnings
    assert len(rank_shortlist(comparison(), "discount")) == 185
    assert set(comparison().bedroom_segment) <= {"Studio", "1 bedroom", "2 bedrooms", "3 bedrooms", "4 bedrooms",
                                                 "5 bedrooms", "6+ bedrooms"}
    venice = c.loc[("Venice", "Private room", "1 bedroom")]
    assert "Bedroom completeness shift" in venice.warnings
