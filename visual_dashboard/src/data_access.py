"""Typed loading, content fingerprints, and actionable integrity failures."""
import hashlib
import json
from pathlib import Path
import numpy as np
import pandas as pd
from scripts.canonical_clean import LISTING_COLUMNS, SEGMENT_COLUMNS
from .config import DATES

FILES = ["canonical_listings_clean.csv", "canonical_price_segments.csv", "canonical_cleaning_report.json"]
BOOLS = ["neighbourhood_is_known", "room_type_is_known", "bedroom_is_zero", "has_valid_price", "review_scores_value_zero", "pricing_eligible"]
NUMERIC = ["source_row_number", "bedrooms", "minimum_nights", "price_usd", "availability_30", "availability_60", "availability_90", "availability_365", "number_of_reviews", "number_of_reviews_ltm", "number_of_reviews_l30d", "reviews_per_month", "review_scores_value"]

def fingerprint(directory):
    digest = hashlib.sha256()
    for name in FILES:
        path = Path(directory) / name
        if not path.is_file():
            raise ValueError(f"Missing {path}. Run the canonical cleaning command in README.md with both supplied raw snapshots.")
        digest.update(name.encode())
        with path.open("rb") as handle:
            for block in iter(lambda: handle.read(1024*1024), b""):
                digest.update(block)
    return digest.hexdigest()

def file_hash(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def load_data(directory):
    directory = Path(directory)
    fingerprint(directory)
    report = json.loads((directory / FILES[2]).read_text())
    for name in FILES[:2]:
        if report.get("output_fingerprints", {}).get(name) != file_hash(directory/name):
            raise ValueError(f"Integrity mismatch for {name}. Regenerate canonical files; do not edit them manually.")
    data = pd.read_csv(directory/FILES[0], dtype="string", keep_default_na=False)
    missing = set(LISTING_COLUMNS) - set(data)
    if missing:
        raise ValueError(f"Canonical schema missing {sorted(missing)}. Regenerate data.")
    if data.listing_id.str.strip().eq("").any() or data.duplicated(["snapshot_date", "listing_id"]).any():
        raise ValueError("Canonical listing IDs must be present and unique within each snapshot.")
    if set(data.snapshot_date.unique()) != set(DATES):
        raise ValueError("Canonical data must contain exactly the required March and June dates.")
    for column in BOOLS:
        if not data[column].isin(["True", "False"]).all():
            raise ValueError(f"Invalid explicit Boolean in {column}")
        data[column] = data[column].map({"True": True, "False": False}).astype(bool)
    for column in NUMERIC:
        raw = data[column]
        values = pd.to_numeric(raw.replace("", pd.NA), errors="coerce").astype("float64")
        if ((raw.ne("")) & (values.isna() | ~np.isfinite(values))).any():
            raise ValueError(f"Invalid numeric canonical field: {column}")
        data[column] = values
    data["last_scraped"] = data.last_scraped.replace("", pd.NA)
    if not data.has_valid_price.eq(data.price_status.eq("valid")).all() or not data.has_valid_price.eq(data.price_usd.gt(0)).all():
        raise ValueError("Canonical price statuses do not reconcile.")
    expected = data.has_valid_price & data.neighbourhood_is_known & data.room_type_is_known & data.bedroom_status.eq("valid")
    if not data.pricing_eligible.eq(expected).all():
        raise ValueError("Pricing eligibility does not reconcile.")
    for column, maximum in [("availability_30",30),("availability_60",60),("availability_90",90),("availability_365",365),("review_scores_value",5)]:
        values = data[column].dropna()
        if not values.between(0, maximum).all():
            raise ValueError(f"Out-of-range {column}")
    if len(data) != report["output_rows"]:
        raise ValueError("Canonical row count does not match report")
    segments = pd.read_csv(directory / FILES[1])
    if set(SEGMENT_COLUMNS)-set(segments) or segments.duplicated(["snapshot_date", "neighbourhood", "room_type", "bedroom_segment"]).any():
        raise ValueError("Canonical segment schema or key is invalid")
    return data, report
