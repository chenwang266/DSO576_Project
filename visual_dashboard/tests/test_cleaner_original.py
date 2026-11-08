#!/usr/bin/env python3
"""Synthetic tests for canonical_clean.py; all inputs and outputs are temporary."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import pandas as pd

from scripts import canonical_clean as canonical


def sample_frame(**overrides: object) -> pd.DataFrame:
    """Return a minimally complete raw detailed-listings-like table."""
    data: dict[str, list[object]] = {
        "id": ["1001"],
        "price": ["$125.50"],
        "neighbourhood_cleansed": ["  Hollywood  "],
        "room_type": ["Entire home/apt"],
        "bedrooms": ["1"],
        "availability_30": ["10"],
        "availability_60": ["20"],
        "availability_90": ["30"],
        "availability_365": ["100"],
        "number_of_reviews": ["10"],
        "number_of_reviews_ltm": ["4"],
        "number_of_reviews_l30d": ["1"],
        "review_scores_value": ["4.8"],
        "minimum_nights": ["2"],
        "source": ["city scrape"],
        "last_scraped": ["2026-03-16"],
        "last_review": ["2026-03-01"],
        "reviews_per_month": ["1.25"],
    }
    row_count = max([len(value) for value in overrides.values() if isinstance(value, list)] or [1])
    for key, value in overrides.items():
        data[key] = value if isinstance(value, list) else [value] * row_count
    for key, value in data.items():
        if len(value) == 1 and row_count > 1:
            data[key] = value * row_count
        elif len(value) != row_count:
            raise ValueError(f"Synthetic field {key!r} has {len(value)} values; expected {row_count}")
    return pd.DataFrame(data)


class CanonicalCleanTests(unittest.TestCase):
    def write_input(self, directory: Path, name: str, frame: pd.DataFrame) -> Path:
        path = directory / name
        frame.to_csv(path, index=False)
        return path

    def test_missing_and_malformed_prices_are_preserved_with_statuses(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = self.write_input(Path(temporary), "march.csv", sample_frame(
                id=["1", "2", "3", "4"], price=["", "1e3", "$0.00", "$250.00"]
            ))
            cleaned, _ = canonical.clean_snapshot(path, "2026-03-16")
        self.assertEqual(cleaned["price_status"].tolist(), ["missing", "malformed", "invalid_nonpositive", "valid"])
        self.assertTrue(pd.isna(cleaned.loc[0, "price_usd"]))
        self.assertTrue(pd.isna(cleaned.loc[1, "price_usd"]))
        self.assertEqual(cleaned.loc[3, "price_usd"], 250.0)
        self.assertEqual(cleaned["has_valid_price"].tolist(), [False, False, False, True])

    def test_duplicate_listing_ids_fail(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = self.write_input(Path(temporary), "march.csv", sample_frame(id=["77", "77"], price=["$10", "$20"]))
            with self.assertRaisesRegex(ValueError, "duplicate listing IDs"):
                canonical.clean_snapshot(path, "2026-03-16")

    def test_bedroom_categories_make_zero_and_missing_explicit(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = self.write_input(Path(temporary), "march.csv", sample_frame(
                id=["1", "2", "3", "4", "5", "6"],
                bedrooms=["0", "1", "5", "6", "", "1.5"],
            ))
            cleaned, _ = canonical.clean_snapshot(path, "2026-03-16")
        self.assertEqual(cleaned["bedroom_segment"].tolist(), ["Studio", "1 bedroom", "5 bedroom", "6+ bedrooms", "Unknown", "Unknown"])
        self.assertEqual(cleaned["bedroom_status"].tolist(), ["valid", "valid", "valid", "valid", "missing", "invalid_noninteger"])
        self.assertEqual(cleaned["bedroom_is_zero"].tolist(), [True, False, False, False, False, False])

    def test_missing_metric_values_remain_missing(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = self.write_input(Path(temporary), "march.csv", sample_frame(
                availability_365="", number_of_reviews_ltm="", review_scores_value=""
            ))
            cleaned, _ = canonical.clean_snapshot(path, "2026-03-16")
        self.assertTrue(pd.isna(cleaned.loc[0, "availability_365"]))
        self.assertEqual(cleaned.loc[0, "availability_365_status"], "missing")
        self.assertTrue(pd.isna(cleaned.loc[0, "number_of_reviews_ltm"]))
        self.assertTrue(pd.isna(cleaned.loc[0, "review_scores_value"]))

    def test_canonical_data_types(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = self.write_input(Path(temporary), "march.csv", sample_frame())
            cleaned, _ = canonical.clean_snapshot(path, "2026-03-16")
        self.assertEqual(str(cleaned["listing_id"].dtype), "string")
        self.assertEqual(str(cleaned["price_usd"].dtype), "Float64")
        self.assertEqual(str(cleaned["bedrooms"].dtype), "Int64")
        self.assertEqual(str(cleaned["has_valid_price"].dtype), "boolean")
        self.assertEqual(str(cleaned["review_scores_value"].dtype), "Float64")

    def test_required_columns_are_enforced(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            frame = sample_frame().drop(columns=["review_scores_value"])
            path = self.write_input(Path(temporary), "march.csv", frame)
            with self.assertRaisesRegex(ValueError, "missing required columns"):
                canonical.clean_snapshot(path, "2026-03-16")

    def test_snapshot_consistency(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            march = self.write_input(directory, "march.csv", sample_frame(id="m1"))
            june = self.write_input(directory, "june.csv", sample_frame(id="j1", last_scraped="2026-06-15"))
            with self.assertRaisesRegex(ValueError, "Unsupported snapshot_date"):
                canonical.clean_snapshot(march, "2026-04-01")
            report = canonical.run_pipeline(march, june, directory / "out")
        self.assertEqual([item["snapshot_date"] for item in report["inputs"]], list(canonical.SNAPSHOT_DATES))

    def test_output_schema_and_segment_summary(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            march = self.write_input(directory, "march.csv", sample_frame(id="m1", price="$100"))
            june = self.write_input(directory, "june.csv", sample_frame(id="j1", price="$200", last_scraped="2026-06-15"))
            out = directory / "out"
            canonical.run_pipeline(march, june, out)
            listings = pd.read_csv(out / "canonical_listings_clean.csv")
            segments = pd.read_csv(out / "canonical_price_segments.csv")
        self.assertEqual(list(listings.columns), canonical.LISTING_COLUMNS)
        self.assertEqual(list(segments.columns), canonical.SEGMENT_COLUMNS)
        self.assertEqual(len(listings), 2)
        self.assertTrue((segments["price_iqr_usd"] == 0).all())

    def test_segment_price_coverage_counts_missing_prices(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            path = self.write_input(directory, "march.csv", sample_frame(
                id=["m1", "m2"], price=["$100", ""], bedrooms=["1", "1"]
            ))
            cleaned, _ = canonical.clean_snapshot(path, "2026-03-16")
            segments = canonical.build_segment_summary(cleaned)
        self.assertEqual(int(segments.loc[0, "listing_rows"]), 2)
        self.assertEqual(int(segments.loc[0, "priced_rows"]), 1)
        self.assertEqual(float(segments.loc[0, "price_coverage"]), 0.5)


if __name__ == "__main__":
    unittest.main(verbosity=2)
