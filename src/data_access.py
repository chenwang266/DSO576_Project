"""Canonical schema, fingerprints, and typed loading/validation of the canonical artifacts.

No Streamlit imports. Loaded frames are returned fresh on every call; callers must not mutate cached copies.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

LISTINGS_FILE = "canonical_listings_clean.csv"
SEGMENTS_FILE = "canonical_price_segments.csv"
REPORT_FILE = "canonical_cleaning_report.json"
CANONICAL_FILES = (LISTINGS_FILE, SEGMENTS_FILE, REPORT_FILE)

UNKNOWN = "Unknown"
ROOM_TYPES = ("Entire home/apt", "Private room", "Shared room", "Hotel room")
BEDROOM_SEGMENTS = ("Studio", "1 bedroom", "2 bedrooms", "3 bedrooms", "4 bedrooms", "5 bedrooms", "6+ bedrooms")
BEDROOM_ORDER = {label: order for order, label in enumerate(BEDROOM_SEGMENTS)}
SHORT_STAY = "Short stay (<30 nights)"
LONG_STAY = "Long stay (30+ nights)"
STAY_CATEGORIES = (SHORT_STAY, LONG_STAY, UNKNOWN)

PRICE_STATUSES = ("valid", "missing", "malformed", "invalid_nonpositive")
FIELD_STATUSES = ("valid", "missing", "malformed", "out_of_range", "unavailable")
AVAILABILITY_HORIZONS = {"availability_30": 30, "availability_60": 60, "availability_90": 90, "availability_365": 365}
COUNT_FIELDS = ("number_of_reviews_ltm", "number_of_reviews_l30d")
CONTEXT_FIELDS = ("availability_90", "number_of_reviews_ltm", "review_scores_value", "minimum_nights")
SEGMENT_DIMENSIONS = ("neighbourhood", "room_type", "bedroom_segment")

# Canonical listing columns and their in-memory dtypes. Order is the on-disk order.
LISTING_SCHEMA: dict[str, str] = {
    "snapshot_date": "string",
    "snapshot_label": "string",
    "listing_id": "string",
    "source_file": "string",
    "source_row": "Int64",
    "input_sha256": "string",
    "last_scraped": "string",
    "source_raw": "string",
    "source_category": "string",
    "price_raw": "string",
    "price_usd": "float64",
    "price_status": "string",
    "neighbourhood_raw": "string",
    "neighbourhood": "string",
    "room_type_raw": "string",
    "room_type": "string",
    "bedrooms_raw": "string",
    "bedrooms": "Int64",
    "bedrooms_status": "string",
    "bedroom_segment": "string",
    "bedroom_order": "Int64",
    "minimum_nights_raw": "string",
    "minimum_nights": "Int64",
    "minimum_nights_status": "string",
    "stay_category": "string",
    **{field: "Int64" for field in AVAILABILITY_HORIZONS},
    **{f"{field}_status": "string" for field in AVAILABILITY_HORIZONS},
    "number_of_reviews_ltm": "Int64",
    "number_of_reviews_ltm_status": "string",
    "number_of_reviews_l30d": "Int64",
    "number_of_reviews_l30d_status": "string",
    "review_scores_value": "float64",
    "review_scores_value_status": "string",
    "value_score_is_zero": "boolean",
    "number_of_reviews": "Int64",
    "number_of_reviews_status": "string",
    "reviews_per_month": "float64",
    "reviews_per_month_status": "string",
    "first_review": "string",
    "last_review": "string",
    "has_valid_price": "boolean",
    "has_valid_dimensions": "boolean",
    "pricing_eligible": "boolean",
    "segment_key": "string",
}
LISTING_COLUMNS = tuple(LISTING_SCHEMA)

SEGMENT_SCHEMA: dict[str, str] = {
    "snapshot_date": "string",
    "segment_key": "string",
    "neighbourhood": "string",
    "room_type": "string",
    "bedroom_segment": "string",
    "bedroom_order": "Int64",
    "listing_rows": "Int64",
    "priced_rows": "Int64",
    "price_coverage": "float64",
    "median_price_usd": "float64",
    "p25_price_usd": "float64",
    "p75_price_usd": "float64",
    "price_iqr_usd": "float64",
    "min_price_usd": "float64",
    "max_price_usd": "float64",
    "is_small_sample": "boolean",
}
SEGMENT_COLUMNS = tuple(SEGMENT_SCHEMA)


class CanonicalDataError(ValueError):
    """Canonical files are missing, malformed, or inconsistent."""


@dataclass(frozen=True)
class CanonicalData:
    listings: pd.DataFrame
    segments: pd.DataFrame
    report: dict
    fingerprint: str  # combined SHA-256 of the three canonical files; use as a cache key
    directory: Path


def fingerprint(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def combined_fingerprint(directory: str | Path) -> str:
    directory = Path(directory)
    digest = hashlib.sha256()
    for name in CANONICAL_FILES:
        digest.update(f"{name}:{fingerprint(directory / name)}\n".encode())
    return digest.hexdigest()


def segment_key(neighbourhood: str, room_type: str, bedroom_segment: str) -> str:
    """Stable, delimiter-safe identifier for a neighbourhood × room type × bedroom segment."""
    return json.dumps([neighbourhood, room_type, bedroom_segment], ensure_ascii=False)


def _to_bool(series: pd.Series, name: str) -> pd.Series:
    mapping = {"True": True, "False": False, "true": True, "false": False}
    values = series.astype("string").str.strip()
    unknown = ~values.isin(list(mapping))
    if unknown.any():
        raise CanonicalDataError(f"Column {name} has non-Boolean values, e.g. {values[unknown].iloc[0]!r}.")
    return values.map(mapping).astype("boolean")


def coerce_types(frame: pd.DataFrame, schema: dict[str, str], label: str) -> pd.DataFrame:
    """Convert an all-string frame (as read from CSV) to the canonical dtypes, failing on missing columns."""
    missing = [col for col in schema if col not in frame.columns]
    if missing:
        raise CanonicalDataError(
            f"{label} is missing columns {missing}. Regenerate with: uv run python scripts/canonical_clean.py")
    out = pd.DataFrame(index=frame.index)
    for col, dtype in schema.items():
        raw = frame[col]
        if dtype == "string":
            out[col] = raw.astype("string")
        elif dtype == "boolean":
            out[col] = _to_bool(raw, col)
        else:
            text = raw.astype("string").str.strip().replace("", pd.NA)
            number = pd.to_numeric(text, errors="coerce")
            if (number.isna() & text.notna()).any():
                bad = text[number.isna() & text.notna()].iloc[0]
                raise CanonicalDataError(f"Column {col} in {label} has a non-numeric value {bad!r}.")
            if dtype == "Int64":
                if (number.dropna() % 1 != 0).any():
                    raise CanonicalDataError(f"Column {col} in {label} has non-integer values.")
                out[col] = number.astype("Int64")
            else:
                out[col] = number.astype("float64")
    return out


def _fail_if(mask, message: str) -> None:
    if bool(np.asarray(mask).any()):
        raise CanonicalDataError(message)


def validate_listings(data: pd.DataFrame, dates: tuple[str, ...] | None = None) -> pd.DataFrame:
    """Check keys, statuses, ranges, and derived flags. Returns the frame unchanged on success."""
    missing = [col for col in LISTING_COLUMNS if col not in data.columns]
    if missing:
        raise CanonicalDataError(f"Canonical listings missing columns {missing}.")
    ids = data.listing_id
    _fail_if(ids.isna() | ids.str.strip().eq("") | ids.ne(ids.str.strip()), "Missing or untrimmed listing IDs.")
    _fail_if(data.duplicated(["snapshot_date", "listing_id"]), "Duplicate (snapshot_date, listing_id) keys.")
    if dates is not None:
        _fail_if(~data.snapshot_date.isin(dates), f"Unexpected snapshot dates; expected only {list(dates)}.")

    _fail_if(~data.price_status.isin(PRICE_STATUSES), "Unknown price_status values.")
    valid_price = data.price_status.eq("valid")
    _fail_if(valid_price & ~(data.price_usd > 0).fillna(False), "Valid price rows need a positive price_usd.")
    _fail_if(~valid_price & data.price_usd.notna(), "Only valid price rows may carry price_usd.")
    _fail_if(data.has_valid_price.ne(valid_price), "has_valid_price disagrees with price_status.")

    _fail_if(~data.room_type.isin(ROOM_TYPES + (UNKNOWN,)), "Unexpected room_type labels.")
    _fail_if(data.neighbourhood.isna() | data.neighbourhood.eq(""), "Blank neighbourhood must be labelled Unknown.")
    _fail_if(~data.bedroom_segment.isin(BEDROOM_SEGMENTS + (UNKNOWN,)), "Unexpected bedroom_segment labels.")
    expected_order = data.bedroom_segment.map(BEDROOM_ORDER).astype("Int64")
    _fail_if(expected_order.fillna(-1).ne(data.bedroom_order.fillna(-1)), "bedroom_order disagrees with bedroom_segment.")
    beds = data.bedrooms
    expected_segment = pd.Series(UNKNOWN, index=data.index, dtype="string")
    known = beds.notna()
    expected_segment[known] = beds[known].clip(upper=6).map(lambda n: BEDROOM_SEGMENTS[int(n)])
    _fail_if(expected_segment.ne(data.bedroom_segment), "bedroom_segment disagrees with bedrooms.")
    _fail_if(known.ne(data.bedrooms_status.eq("valid")), "bedrooms_status disagrees with bedrooms.")

    _fail_if(~data.stay_category.isin(STAY_CATEGORIES), "Unexpected stay_category labels.")
    nights = data.minimum_nights
    expected_stay = pd.Series(UNKNOWN, index=data.index, dtype="string")
    expected_stay[nights.between(1, 29).fillna(False)] = SHORT_STAY
    expected_stay[nights.ge(30).fillna(False)] = LONG_STAY
    _fail_if(expected_stay.ne(data.stay_category), "stay_category disagrees with minimum_nights.")

    for field, horizon in AVAILABILITY_HORIZONS.items():
        _fail_if((data[field] < 0).fillna(False) | (data[field] > horizon).fillna(False), f"{field} out of range.")
    for field in (*AVAILABILITY_HORIZONS, *COUNT_FIELDS, "minimum_nights", "bedrooms", "number_of_reviews",
                  "review_scores_value", "reviews_per_month"):
        status = data[f"{field}_status"]
        _fail_if(~status.isin(FIELD_STATUSES), f"Unknown {field}_status values.")
        _fail_if(data[field].notna().ne(status.eq("valid")), f"{field} values disagree with {field}_status.")
    for field in (*COUNT_FIELDS, "minimum_nights", "number_of_reviews"):
        _fail_if((data[field] < 0).fillna(False), f"{field} must be nonnegative.")
    _fail_if(~data.review_scores_value.between(0, 5) & data.review_scores_value.notna(), "Value score outside 0-5.")
    _fail_if(data.value_score_is_zero.ne(data.review_scores_value.eq(0).fillna(False)), "value_score_is_zero mismatch.")

    dims = data.neighbourhood.ne(UNKNOWN) & data.room_type.ne(UNKNOWN) & data.bedroom_segment.ne(UNKNOWN)
    _fail_if(data.has_valid_dimensions.ne(dims), "has_valid_dimensions disagrees with dimensions.")
    _fail_if(data.pricing_eligible.ne(dims & valid_price), "pricing_eligible must equal valid price + dimensions.")
    _fail_if(dims & data.segment_key.isna(), "Comparable rows need a segment_key.")
    _fail_if(~dims & data.segment_key.notna() & data.segment_key.ne(""), "Non-comparable rows must not have a segment_key.")
    return data


def validate_segments(segments: pd.DataFrame, small_sample_threshold: int = 20) -> pd.DataFrame:
    missing = [col for col in SEGMENT_COLUMNS if col not in segments.columns]
    if missing:
        raise CanonicalDataError(f"Canonical segments missing columns {missing}.")
    _fail_if(segments.duplicated(["snapshot_date", "segment_key"]), "Duplicate (snapshot_date, segment_key) segments.")
    _fail_if(segments.priced_rows > segments.listing_rows, "priced_rows cannot exceed listing_rows.")
    _fail_if(segments.is_small_sample.ne(segments.priced_rows < small_sample_threshold), "is_small_sample mismatch.")
    return segments


def _read_strings(path: Path) -> pd.DataFrame:
    return pd.read_csv(path, dtype=str, keep_default_na=False, na_filter=False, encoding="utf-8")


def load_canonical(directory: str | Path, dates: tuple[str, ...] | None = None,
                   small_sample_threshold: int = 20) -> CanonicalData:
    """Load and validate the three canonical artifacts from ``directory``."""
    directory = Path(directory)
    absent = [name for name in CANONICAL_FILES if not (directory / name).exists()]
    if absent:
        raise CanonicalDataError(
            f"Canonical files {absent} not found in {directory}. Place the March/June raw listings under data/raw/ "
            "(see README) and run: uv run python scripts/canonical_clean.py")
    key = combined_fingerprint(directory)
    listings = coerce_types(_read_strings(directory / LISTINGS_FILE), LISTING_SCHEMA, LISTINGS_FILE)
    listings["segment_key"] = listings.segment_key.replace("", pd.NA)
    validate_listings(listings, dates)
    segments = coerce_types(_read_strings(directory / SEGMENTS_FILE), SEGMENT_SCHEMA, SEGMENTS_FILE)
    validate_segments(segments, small_sample_threshold)
    try:
        report = json.loads((directory / REPORT_FILE).read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise CanonicalDataError(f"{REPORT_FILE} is not valid JSON: {error}") from error
    if combined_fingerprint(directory) != key:
        raise CanonicalDataError("Canonical files changed while loading; retry.")
    return CanonicalData(listings, segments, report, key, directory)
