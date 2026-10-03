#!/usr/bin/env python3
"""Create analysis-ready Inside Airbnb listing snapshots without touching sources.

The script expects the Los Angeles *detailed listings* CSV/CSV.GZ files.  It
writes all derived artifacts to --output-dir and never opens either input in a
writable mode.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import pandas as pd


SNAPSHOTS = {
    "march_2026": "2026-03-16",
    "june_2026": "2026-06-15",
}

# These are the dimensions and measures needed by the dashboard.  The source
# may include many more columns; retaining this small, documented set avoids
# accidental dependence on fields that change across Inside Airbnb releases.
KEEP_COLUMNS = [
    "id", "name", "host_id", "host_is_superhost", "neighbourhood_cleansed",
    "latitude", "longitude", "property_type", "room_type", "accommodates",
    "bathrooms_text", "bedrooms", "beds", "price", "minimum_nights",
    "maximum_nights", "availability_30", "availability_60", "availability_90",
    "availability_365", "number_of_reviews", "number_of_reviews_ltm",
    "review_scores_rating", "instant_bookable", "license", "last_scraped",
]
REQUIRED_COLUMNS = {"id", "neighbourhood_cleansed", "room_type", "bedrooms", "price"}


def clean_text(series: pd.Series, missing: str = "Unknown") -> pd.Series:
    """Trim and collapse whitespace, assigning a visible label to blanks."""
    value = series.astype("string").str.replace(r"\s+", " ", regex=True).str.strip()
    return value.mask(value.isna() | value.eq(""), missing)


def parse_price(series: pd.Series) -> pd.Series:
    """Parse values such as '$1,234.50'; non-positive or malformed values are NA."""
    value = series.astype("string").str.replace(r"[^0-9.\-]", "", regex=True)
    value = pd.to_numeric(value, errors="coerce")
    return value.mask(value <= 0).round(2)


def sha256_file(path: Path) -> str:
    """Return a content fingerprint without modifying the raw source file."""
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def bedroom_segment(series: pd.Series) -> pd.Series:
    """Use stable, dashboard-friendly bins while retaining the original number."""
    bedrooms = pd.to_numeric(series, errors="coerce")
    valid_integer = bedrooms.notna() & bedrooms.ge(0) & bedrooms.eq(bedrooms.round())
    bedrooms = bedrooms.where(valid_integer).astype("Int64")
    labels = pd.Series("Unknown", index=series.index, dtype="string")
    is_studio = bedrooms.eq(0).fillna(False)
    is_one_to_five = bedrooms.between(1, 5).fillna(False)
    is_six_plus = bedrooms.ge(6).fillna(False)
    labels.loc[is_studio] = "Studio"
    labels.loc[is_one_to_five] = bedrooms.loc[is_one_to_five].astype("string") + " bedroom"
    labels.loc[is_six_plus] = "6+ bedrooms"
    return bedrooms, labels


def clean_snapshot(input_path: Path, snapshot_name: str, snapshot_date: str) -> tuple[pd.DataFrame, dict]:
    source = pd.read_csv(input_path, low_memory=False)
    missing = REQUIRED_COLUMNS - set(source.columns)
    if missing:
        raise ValueError(f"{input_path.name} is missing required columns: {sorted(missing)}")

    duplicate_ids = int(source["id"].duplicated(keep=False).sum())
    if duplicate_ids:
        raise ValueError(
            f"{input_path.name} has {duplicate_ids:,} rows with non-unique listing IDs. "
            "Resolve the source extract before matching listings."
        )

    output = source.reindex(columns=[column for column in KEEP_COLUMNS if column in source.columns]).copy()
    output["listing_id"] = pd.to_numeric(output.pop("id"), errors="coerce").astype("Int64")
    if output["listing_id"].isna().any():
        raise ValueError(f"{input_path.name} contains missing or non-numeric listing IDs.")

    output["snapshot_name"] = snapshot_name
    output["snapshot_date"] = pd.Timestamp(snapshot_date)
    output["neighbourhood"] = clean_text(output.pop("neighbourhood_cleansed"))
    output["room_type"] = clean_text(output["room_type"])
    output["property_type"] = clean_text(output["property_type"]) if "property_type" in output else "Unknown"
    output["bedrooms"], output["bedroom_segment"] = bedroom_segment(output["bedrooms"])
    output["price_usd"] = parse_price(output.pop("price"))
    output["has_valid_price"] = output["price_usd"].notna()
    output["segment_key"] = (
        output["neighbourhood"] + " | " + output["room_type"] + " | " + output["bedroom_segment"]
    )

    # Invalid prices stay in the cleaned listing-level file for coverage checks,
    # but are excluded from price statistics below. No price outlier is silently
    # removed: dashboard users can apply a stated cap/filter if desired.
    summary = {
        "snapshot_name": snapshot_name,
        "snapshot_date": snapshot_date,
        "input_file": input_path.name,
        "input_bytes": input_path.stat().st_size,
        "input_sha256": sha256_file(input_path),
        "source_rows": int(len(source)),
        "clean_rows": int(len(output)),
        "valid_price_rows": int(output["has_valid_price"].sum()),
        "invalid_price_rows": int((~output["has_valid_price"]).sum()),
        "unknown_neighbourhood_rows": int(output["neighbourhood"].eq("Unknown").sum()),
        "unknown_room_type_rows": int(output["room_type"].eq("Unknown").sum()),
        "unknown_bedroom_rows": int(output["bedroom_segment"].eq("Unknown").sum()),
    }
    return output, summary


def price_segments(cleaned: pd.DataFrame) -> pd.DataFrame:
    valid = cleaned.loc[cleaned["has_valid_price"]].copy()
    group_columns = ["snapshot_name", "snapshot_date", "neighbourhood", "room_type", "bedroom_segment"]
    metrics = valid.groupby(group_columns, dropna=False)["price_usd"].agg(
        listings="size", mean_price_usd="mean", median_price_usd="median",
        p25_price_usd=lambda x: x.quantile(0.25), p75_price_usd=lambda x: x.quantile(0.75),
        min_price_usd="min", max_price_usd="max",
    ).reset_index()
    return metrics.round(2).sort_values(group_columns).reset_index(drop=True)


def snapshot_segment_changes(segments: pd.DataFrame) -> pd.DataFrame:
    """Compare March and June segment summaries, including segments in only one snapshot."""
    dimensions = ["neighbourhood", "room_type", "bedroom_segment"]
    metrics = ["listings", "mean_price_usd", "median_price_usd", "p25_price_usd", "p75_price_usd"]

    def select_snapshot(name: str, suffix: str) -> pd.DataFrame:
        selected = segments.loc[segments["snapshot_name"].eq(name), dimensions + metrics].copy()
        return selected.rename(columns={metric: f"{metric}_{suffix}" for metric in metrics})

    march = select_snapshot("march_2026", "march")
    june = select_snapshot("june_2026", "june")
    changes = march.merge(june, on=dimensions, how="outer", indicator=True)
    changes["segment_coverage"] = changes.pop("_merge").map({
        "both": "both_snapshots", "left_only": "march_only", "right_only": "june_only",
    })
    changes["listing_count_change"] = changes["listings_june"] - changes["listings_march"]
    for metric in ("mean_price_usd", "median_price_usd", "p25_price_usd", "p75_price_usd"):
        changes[f"{metric}_change_usd"] = changes[f"{metric}_june"] - changes[f"{metric}_march"]
    changes["median_price_change_pct"] = (
        100 * changes["median_price_usd_change_usd"] / changes["median_price_usd_march"]
    ).round(2)
    return changes.round(2).sort_values(dimensions).reset_index(drop=True)


def match_listings(march: pd.DataFrame, june: pd.DataFrame) -> pd.DataFrame:
    march_columns = ["listing_id", "price_usd", "has_valid_price", "neighbourhood", "room_type", "bedroom_segment"]
    june_columns = march_columns
    matched = march[march_columns].merge(june[june_columns], on="listing_id", how="inner", suffixes=("_march", "_june"))
    matched["has_valid_price_both"] = matched["has_valid_price_march"] & matched["has_valid_price_june"]
    matched["price_change_usd"] = (matched["price_usd_june"] - matched["price_usd_march"]).round(2)
    matched["price_change_pct"] = (
        100 * matched["price_change_usd"] / matched["price_usd_march"]
    ).where(matched["has_valid_price_both"]).round(2)
    matched["segment_changed"] = (
        (matched["neighbourhood_march"] != matched["neighbourhood_june"])
        | (matched["room_type_march"] != matched["room_type_june"])
        | (matched["bedroom_segment_march"] != matched["bedroom_segment_june"])
    )
    return matched.sort_values("listing_id").reset_index(drop=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--march", type=Path, required=True, help="Raw 2026-03-16 listings CSV or CSV.GZ")
    parser.add_argument("--june", type=Path, required=True, help="Raw 2026-06-15 listings CSV or CSV.GZ")
    parser.add_argument("--output-dir", type=Path, default=Path("data/processed"))
    args = parser.parse_args()

    for path in (args.march, args.june):
        if not path.is_file():
            raise FileNotFoundError(f"Input file not found: {path}")
    args.output_dir.mkdir(parents=True, exist_ok=True)

    march, march_summary = clean_snapshot(args.march, "march_2026", SNAPSHOTS["march_2026"])
    june, june_summary = clean_snapshot(args.june, "june_2026", SNAPSHOTS["june_2026"])
    combined = pd.concat([march, june], ignore_index=True)
    segments = price_segments(combined)
    segment_changes = snapshot_segment_changes(segments)
    matched = match_listings(march, june)

    combined.to_csv(args.output_dir / "la_listings_cleaned.csv", index=False)
    segments.to_csv(args.output_dir / "la_price_segments.csv", index=False)
    segment_changes.to_csv(args.output_dir / "la_price_segment_changes.csv", index=False)
    matched.to_csv(args.output_dir / "la_matched_listing_price_trends.csv", index=False)
    report = {
        "snapshots": [march_summary, june_summary],
        "matched_listings": int(len(matched)),
        "matched_listings_with_valid_price_both": int(matched["has_valid_price_both"].sum()),
        "matched_listings_with_segment_change": int(matched["segment_changed"].sum()),
        "segment_comparison": {
            "segments_in_both_snapshots": int(segment_changes["segment_coverage"].eq("both_snapshots").sum()),
            "march_only_segments": int(segment_changes["segment_coverage"].eq("march_only").sum()),
            "june_only_segments": int(segment_changes["segment_coverage"].eq("june_only").sum()),
        },
        "outputs": [
            "la_listings_cleaned.csv", "la_price_segments.csv", "la_price_segment_changes.csv",
            "la_matched_listing_price_trends.csv",
        ],
    }
    (args.output_dir / "cleaning_report.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
