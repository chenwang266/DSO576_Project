#!/usr/bin/env python3
"""Create a conservative analysis-ready LA Airbnb listing dataset.

This module reads the March 16 and June 15, 2026 Inside Airbnb detailed
listings snapshots as read-only inputs.  It writes only to an explicitly
provided output directory.  The canonical grain is one listing in one
snapshot, identified by (snapshot_date, listing_id).

Usage:
    python3 canonical_clean.py --march PATH --june PATH --output-dir PATH
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Iterable

import pandas as pd


SNAPSHOT_DATES = ("2026-03-16", "2026-06-15")
ROOM_TYPES = {
    "entire home/apt": "Entire home/apt",
    "private room": "Private room",
    "shared room": "Shared room",
    "hotel room": "Hotel room",
}

# These are required because the dashboard needs all of them.  Failing early is
# safer than publishing a dashboard with silently absent context.
REQUIRED_COLUMNS = {
    "id",
    "price",
    "neighbourhood_cleansed",
    "room_type",
    "bedrooms",
    "availability_30",
    "availability_60",
    "availability_90",
    "availability_365",
    "number_of_reviews_ltm",
    "number_of_reviews_l30d",
    "review_scores_value",
}

PRICE_PATTERN = re.compile(r"^[+-]?\$?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d{1,2})?$")
NUMBER_PATTERN = re.compile(r"^[+-]?\d+(?:\.\d+)?$")

LISTING_COLUMNS = [
    "listing_id", "snapshot_date", "source_file", "source_row_number", "source",
    "last_scraped", "last_scraped_status",
    "neighbourhood_raw", "neighbourhood", "neighbourhood_is_known",
    "room_type_raw", "room_type", "room_type_is_known",
    "bedrooms_raw", "bedrooms", "bedroom_status", "bedroom_is_zero", "bedroom_segment",
    "minimum_nights", "minimum_nights_status", "stay_type",
    "price_raw", "price_usd", "price_status", "has_valid_price",
    "availability_30", "availability_30_status",
    "availability_60", "availability_60_status",
    "availability_90", "availability_90_status",
    "availability_365", "availability_365_status",
    "number_of_reviews", "number_of_reviews_status",
    "number_of_reviews_ltm", "number_of_reviews_ltm_status",
    "number_of_reviews_l30d", "number_of_reviews_l30d_status",
    "last_review", "last_review_status",
    "reviews_per_month", "reviews_per_month_status",
    "review_scores_value", "review_scores_value_status", "review_scores_value_zero",
    "pricing_eligible", "segment_key",
]

SEGMENT_COLUMNS = [
    "snapshot_date", "neighbourhood", "room_type", "bedroom_segment",
    "listing_rows", "priced_rows", "price_coverage", "median_price_usd",
    "p25_price_usd", "p75_price_usd", "price_iqr_usd", "min_price_usd", "max_price_usd", "is_small_sample",
]


def sha256_file(path: Path) -> str:
    """Return an input fingerprint without modifying the source file."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _raw_text(series: pd.Series) -> pd.Series:
    """Return source tokens as nullable pandas strings without turning blanks into NA."""
    return series.astype("string")


def _blank_mask(series: pd.Series) -> pd.Series:
    return series.isna() | series.astype("string").str.strip().eq("")


def normalize_text(series: pd.Series, missing_label: str = "Unknown") -> pd.Series:
    """Trim and collapse whitespace, using a visible value for blank labels."""
    value = _raw_text(series).str.replace(r"\s+", " ", regex=True).str.strip()
    return value.mask(_blank_mask(value), missing_label).astype("string")


def parse_price(series: pd.Series) -> tuple[pd.Series, pd.Series]:
    """Parse only ordinary USD currency tokens; return value and audit status.

    Examples accepted: ``$67.22``, ``1,200``, and ``125``.  Scientific notation,
    embedded letters, negative values, and zero are not valid pricing inputs.
    """
    raw = _raw_text(series).str.strip()
    missing = _blank_mask(raw)
    format_ok = raw.str.fullmatch(PRICE_PATTERN, na=False)
    numeric_text = raw.where(format_ok).str.replace("$", "", regex=False).str.replace(",", "", regex=False)
    price = pd.to_numeric(numeric_text, errors="coerce").astype("Float64")

    status = pd.Series("malformed", index=series.index, dtype="string")
    status.loc[missing] = "missing"
    status.loc[format_ok & price.gt(0).fillna(False)] = "valid"
    status.loc[format_ok & price.le(0).fillna(False)] = "invalid_nonpositive"
    price = price.mask(status.ne("valid"))
    return price, status


def parse_integer(series: pd.Series, *, maximum: int | None = None) -> tuple[pd.Series, pd.Series]:
    """Parse a nonnegative whole-number measure, retaining an audit status."""
    raw = _raw_text(series).str.strip()
    missing = _blank_mask(raw)
    format_ok = raw.str.fullmatch(NUMBER_PATTERN, na=False)
    numeric = pd.to_numeric(raw.where(format_ok), errors="coerce")
    whole = numeric.notna() & numeric.eq(numeric.round())
    in_range = numeric.ge(0)
    if maximum is not None:
        in_range &= numeric.le(maximum)
    valid = format_ok & whole & in_range.fillna(False)

    status = pd.Series("malformed", index=series.index, dtype="string")
    status.loc[missing] = "missing"
    status.loc[format_ok & ~whole.fillna(False)] = "invalid_noninteger"
    status.loc[format_ok & whole.fillna(False) & ~in_range.fillna(False)] = "invalid_range"
    status.loc[valid] = "valid"
    value = pd.Series(numeric.where(valid), index=series.index, dtype="Float64").round().astype("Int64")
    return value, status


def parse_decimal(
    series: pd.Series, *, minimum: float | None = None, maximum: float | None = None
) -> tuple[pd.Series, pd.Series]:
    """Parse a decimal measure while making malformed and out-of-range values visible."""
    raw = _raw_text(series).str.strip()
    missing = _blank_mask(raw)
    format_ok = raw.str.fullmatch(NUMBER_PATTERN, na=False)
    numeric = pd.to_numeric(raw.where(format_ok), errors="coerce").astype("Float64")
    in_range = numeric.notna()
    if minimum is not None:
        in_range &= numeric.ge(minimum)
    if maximum is not None:
        in_range &= numeric.le(maximum)
    valid = format_ok & in_range.fillna(False)

    status = pd.Series("malformed", index=series.index, dtype="string")
    status.loc[missing] = "missing"
    status.loc[format_ok & ~in_range.fillna(False)] = "invalid_range"
    status.loc[valid] = "valid"
    return numeric.mask(~valid), status


def parse_date(series: pd.Series) -> tuple[pd.Series, pd.Series]:
    """Parse ISO calendar dates and preserve parse status for dashboard context."""
    raw = _raw_text(series).str.strip()
    missing = _blank_mask(raw)
    parsed = pd.to_datetime(raw.mask(missing), format="%Y-%m-%d", errors="coerce")
    status = pd.Series("malformed", index=series.index, dtype="string")
    status.loc[missing] = "missing"
    status.loc[parsed.notna()] = "valid"
    # ISO strings keep CSV output stable and avoid timezone conversion.
    return parsed.dt.strftime("%Y-%m-%d").astype("string"), status


def bedroom_segment(bedrooms: pd.Series, status: pd.Series) -> pd.Series:
    """Return explicit, stable bedroom categories for dashboard comparisons."""
    segment = pd.Series("Unknown", index=bedrooms.index, dtype="string")
    valid = status.eq("valid")
    segment.loc[valid & bedrooms.eq(0).fillna(False)] = "Studio"
    one_to_five = valid & bedrooms.between(1, 5).fillna(False)
    segment.loc[one_to_five] = bedrooms.loc[one_to_five].astype("string") + " bedroom"
    segment.loc[valid & bedrooms.ge(6).fillna(False)] = "6+ bedrooms"
    return segment


def _optional_column(frame: pd.DataFrame, name: str) -> pd.Series:
    return frame[name] if name in frame.columns else pd.Series(pd.NA, index=frame.index, dtype="string")


def clean_snapshot(input_path: Path, snapshot_date: str) -> tuple[pd.DataFrame, dict]:
    """Clean one source snapshot without modifying it."""
    if snapshot_date not in SNAPSHOT_DATES:
        raise ValueError(f"Unsupported snapshot_date {snapshot_date!r}; expected one of {SNAPSHOT_DATES}")
    if not input_path.is_file():
        raise FileNotFoundError(input_path)

    raw_hash = sha256_file(input_path)
    raw = pd.read_csv(input_path, dtype="string", keep_default_na=False, low_memory=False)
    missing_columns = sorted(REQUIRED_COLUMNS - set(raw.columns))
    if missing_columns:
        raise ValueError(f"{input_path.name} is missing required columns: {missing_columns}")

    listing_id = _raw_text(raw["id"]).str.strip()
    if _blank_mask(listing_id).any():
        raise ValueError(f"{input_path.name} contains missing listing IDs")
    duplicate_ids = listing_id.duplicated(keep=False)
    if duplicate_ids.any():
        examples = listing_id.loc[duplicate_ids].drop_duplicates().head(5).tolist()
        raise ValueError(f"{input_path.name} has duplicate listing IDs: {examples}")

    output = pd.DataFrame(index=raw.index)
    output["listing_id"] = listing_id
    output["snapshot_date"] = pd.Series(snapshot_date, index=raw.index, dtype="string")
    output["source_file"] = pd.Series(input_path.name, index=raw.index, dtype="string")
    output["source_row_number"] = pd.array(range(1, len(raw) + 1), dtype="Int64")
    output["source"] = normalize_text(_optional_column(raw, "source"))
    output["last_scraped"], output["last_scraped_status"] = parse_date(_optional_column(raw, "last_scraped"))

    output["neighbourhood_raw"] = _raw_text(raw["neighbourhood_cleansed"])
    output["neighbourhood"] = normalize_text(raw["neighbourhood_cleansed"])
    output["neighbourhood_is_known"] = output["neighbourhood"].ne("Unknown").astype("boolean")
    output["room_type_raw"] = _raw_text(raw["room_type"])
    room_text = normalize_text(raw["room_type"])
    output["room_type"] = room_text.str.casefold().map(ROOM_TYPES).fillna("Unknown").astype("string")
    output["room_type_is_known"] = output["room_type"].ne("Unknown").astype("boolean")

    output["bedrooms_raw"] = _raw_text(raw["bedrooms"])
    output["bedrooms"], output["bedroom_status"] = parse_integer(raw["bedrooms"])
    output["bedroom_is_zero"] = output["bedrooms"].eq(0).fillna(False).astype("boolean")
    output["bedroom_segment"] = bedroom_segment(output["bedrooms"], output["bedroom_status"])

    output["minimum_nights"], output["minimum_nights_status"] = parse_integer(_optional_column(raw, "minimum_nights"))
    output["stay_type"] = pd.Series("Unknown", index=raw.index, dtype="string")
    output.loc[output["minimum_nights"].between(1, 29).fillna(False), "stay_type"] = "Short stay (<30 nights)"
    output.loc[output["minimum_nights"].ge(30).fillna(False), "stay_type"] = "Long stay (30+ nights)"

    output["price_raw"] = _raw_text(raw["price"])
    output["price_usd"], output["price_status"] = parse_price(raw["price"])
    output["has_valid_price"] = output["price_status"].eq("valid").astype("boolean")

    for name, maximum in (("availability_30", 30), ("availability_60", 60), ("availability_90", 90), ("availability_365", 365)):
        output[name], output[f"{name}_status"] = parse_integer(raw[name], maximum=maximum)
    for name in ("number_of_reviews", "number_of_reviews_ltm", "number_of_reviews_l30d"):
        output[name], output[f"{name}_status"] = parse_integer(_optional_column(raw, name))
    output["last_review"], output["last_review_status"] = parse_date(_optional_column(raw, "last_review"))
    output["reviews_per_month"], output["reviews_per_month_status"] = parse_decimal(
        _optional_column(raw, "reviews_per_month"), minimum=0
    )
    output["review_scores_value"], output["review_scores_value_status"] = parse_decimal(
        raw["review_scores_value"], minimum=0, maximum=5
    )
    output["review_scores_value_zero"] = output["review_scores_value"].eq(0).fillna(False).astype("boolean")

    # Conservative default pending team approval: price benchmarks use valid
    # positive prices and known dimensions, but do not exclude source types,
    # long stays, or high prices.
    output["pricing_eligible"] = (
        output["has_valid_price"]
        & output["neighbourhood_is_known"]
        & output["room_type_is_known"]
        & output["bedroom_status"].eq("valid")
    ).astype("boolean")
    output["segment_key"] = (
        output["neighbourhood"] + " | " + output["room_type"] + " | " + output["bedroom_segment"]
    ).astype("string")
    output = output.reindex(columns=LISTING_COLUMNS)

    if sha256_file(input_path) != raw_hash:
        raise ValueError(f"Raw input changed during cleaning: {input_path}")
    report = {
        "snapshot_date": snapshot_date,
        "source_file": input_path.name,
        "source_sha256": raw_hash,
        "source_rows": int(len(raw)),
        "clean_rows": int(len(output)),
        "valid_price_rows": int(output["has_valid_price"].sum()),
        "missing_price_rows": int(output["price_status"].eq("missing").sum()),
        "malformed_or_invalid_price_rows": int((~output["price_status"].isin(["valid", "missing"])).sum()),
        "unknown_bedroom_rows": int(output["bedroom_segment"].eq("Unknown").sum()),
        "missing_bedroom_rows": int(output["bedroom_status"].eq("missing").sum()),
        "zero_bedroom_rows": int(output["bedroom_is_zero"].sum()),
        "price_status_counts": {str(k): int(v) for k,v in output["price_status"].value_counts().items()},
        "actual_scrape_dates": sorted(output["last_scraped"].dropna().unique().tolist()),
        "source_counts": {str(k): int(v) for k,v in output["source"].value_counts().items()},
        "raw_unchanged": True,
    }
    return output, report


def build_segment_summary(cleaned: pd.DataFrame) -> pd.DataFrame:
    """Compute transparent price benchmarks without filtering price outliers."""
    # Retain rows with a known segment even when their price is missing.  That
    # makes the listing denominator and price coverage informative; pandas
    # aggregation naturally omits null prices from the price statistics.
    segment_population = (
        cleaned["neighbourhood_is_known"].fillna(False)
        & cleaned["room_type_is_known"].fillna(False)
        & cleaned["bedroom_status"].eq("valid")
    )
    eligible = cleaned.loc[segment_population].copy()
    dimensions = ["snapshot_date", "neighbourhood", "room_type", "bedroom_segment"]
    if eligible.empty:
        return pd.DataFrame(columns=SEGMENT_COLUMNS)
    summary = eligible.groupby(dimensions, dropna=False)["price_usd"].agg(
        listing_rows="size",
        priced_rows="count",
        median_price_usd="median",
        p25_price_usd=lambda values: values.quantile(0.25),
        p75_price_usd=lambda values: values.quantile(0.75),
        min_price_usd="min",
        max_price_usd="max",
    ).reset_index()
    summary["price_coverage"] = summary["priced_rows"] / summary["listing_rows"]
    summary["price_iqr_usd"] = summary["p75_price_usd"] - summary["p25_price_usd"]
    summary["is_small_sample"] = summary["priced_rows"] < 20
    return summary.reindex(columns=SEGMENT_COLUMNS).sort_values(dimensions).reset_index(drop=True)


def run_pipeline(march_path: Path, june_path: Path, output_dir: Path) -> dict:
    """Clean the two approved snapshots and write analysis-ready artifacts."""
    march, march_report = clean_snapshot(Path(march_path), "2026-03-16")
    june, june_report = clean_snapshot(Path(june_path), "2026-06-15")
    cleaned = pd.concat([march, june], ignore_index=True)
    if cleaned.duplicated(["snapshot_date", "listing_id"]).any():
        raise AssertionError("Canonical compound key is not unique")
    segments = build_segment_summary(cleaned)

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    listings_path = output_dir / "canonical_listings_clean.csv"
    segments_path = output_dir / "canonical_price_segments.csv"
    report_path = output_dir / "canonical_cleaning_report.json"
    cleaned.to_csv(listings_path, index=False)
    segments.to_csv(segments_path, index=False)
    report = {
        "schema_version": "1.0",
        "pipeline": "canonical_clean.py",
        "output_fingerprints": {p.name: sha256_file(p) for p in (listings_path, segments_path)},
        "canonical_grain": "one listing per snapshot",
        "compound_key": ["snapshot_date", "listing_id"],
        "inputs": [march_report, june_report],
        "output_rows": int(len(cleaned)),
        "output_columns": LISTING_COLUMNS,
        "segment_columns": SEGMENT_COLUMNS,
        "outlier_policy": "No price outliers are removed or capped; the team must approve any outlier screen.",
        "pricing_eligibility": "valid positive price plus known neighbourhood, room type, and bedroom segment; source and stay type are retained but not excluded by default.",
        "outputs": [listings_path.name, segments_path.name],
    }
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


def main(argv: Iterable[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--march", required=True, type=Path, help="March 16, 2026 detailed listings CSV or CSV.GZ")
    parser.add_argument("--june", required=True, type=Path, help="June 15, 2026 detailed listings CSV or CSV.GZ")
    parser.add_argument("--output-dir", required=True, type=Path, help="Directory for newly generated artifacts")
    args = parser.parse_args(argv)
    report = run_pipeline(args.march, args.june, args.output_dir)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
