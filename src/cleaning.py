"""Raw Inside Airbnb detailed-listings snapshots → canonical listing rows, segment table and cleaning report.

Raw files are only read. Host details, names, descriptions and coordinates are not carried into canonical outputs.
"""
from __future__ import annotations

import json
import os
import re
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd

from src.config import Snapshot
from src.data_access import (AVAILABILITY_HORIZONS, BEDROOM_ORDER, BEDROOM_SEGMENTS, LISTING_COLUMNS,
                             LISTINGS_FILE, LONG_STAY, REPORT_FILE, ROOM_TYPES, SEGMENTS_FILE, SHORT_STAY, UNKNOWN,
                             fingerprint, segment_key, validate_listings, validate_segments)
from src.pricing import canonical_segments

REQUIRED_FIELDS = ("id", "price", "neighbourhood_cleansed", "room_type", "bedrooms", "availability_30",
                   "availability_60", "availability_90", "availability_365", "number_of_reviews_ltm",
                   "number_of_reviews_l30d", "review_scores_value")
OPTIONAL_FIELDS = ("minimum_nights", "source", "last_scraped", "first_review", "last_review", "number_of_reviews",
                   "reviews_per_month")
# Spec reference counts, compared (never substituted) in the report.
REFERENCE_COUNTS = {
    "2026-03-16": {"rows": 46088, "missing_price": 8910, "zero_bedrooms": 2570, "missing_bedrooms": 3196},
    "2026-06-15": {"rows": 43751, "missing_price": 5565, "zero_bedrooms": 9, "missing_bedrooms": 9572},
}
POLICIES = [
    "Grain: one row per (snapshot_date, listing_id); IDs are trimmed strings; missing or duplicate IDs fail.",
    "Prices: strict USD parsing; missing, malformed and nonpositive prices are retained but excluded from statistics.",
    "No price imputation, caps or trimming; extreme positive prices are kept.",
    "No exclusions by stay length or source category by default.",
    "Bedrooms: 0 = Studio, 1-5 separate, >=6 = 6+ bedrooms; missing/invalid = Unknown, never Studio.",
    "Minimum nights: 1-29 short stay, >=30 long stay; zero/missing/invalid = Unknown stay.",
    "Availability cannot exceed its horizon; out-of-range values are nulled and flagged.",
    "Value score must be within 0-5; zero scores are flagged, missing stays missing.",
    "Pricing eligibility = valid price + known neighbourhood + known room type + valid bedrooms.",
    "Unknown dimensions remain in listings but cannot form comparable segments.",
    "Missing optional fields stay unavailable; missing required fields fail.",
    "Host details, listing text and coordinates are excluded from canonical outputs.",
]

_USD = re.compile(r"^(?P<neg1>-)?\$?(?P<neg2>-)?(?P<num>\d{1,3}(?:,\d{3})+|\d+)(?:\.(?P<dec>\d{1,2}))?$")
_INTEGER = re.compile(r"^\d+(?:\.0+)?$")
_NEGATIVE_NUMBER = re.compile(r"^-\d+(?:\.\d+)?$")
_DECIMAL = re.compile(r"^\d+(?:\.\d+)?$")


class CleaningError(ValueError):
    """Raw input is missing, malformed, or violates a hard constraint."""


def parse_price(value) -> tuple[float | None, str]:
    """Strict USD parsing: ``$1,234.56`` / ``1234.5`` → valid; blank → missing; ``$0``/negative → invalid_nonpositive."""
    text = "" if value is None or (isinstance(value, float) and np.isnan(value)) else str(value).strip()
    if not text:
        return None, "missing"
    match = _USD.fullmatch(text)
    if not match or (match["neg1"] and match["neg2"]):
        return None, "malformed"
    number = float(match["num"].replace(",", "") + (f".{match['dec']}" if match["dec"] else ""))
    if match["neg1"] or match["neg2"] or number <= 0:
        return None, "invalid_nonpositive"
    return number, "valid"


def parse_integers(raw: pd.Series, maximum: int | None = None) -> tuple[pd.Series, pd.Series]:
    """Nullable nonnegative integers with statuses valid/missing/malformed/out_of_range."""
    text = raw.astype("string").str.strip().fillna("")
    status = pd.Series("malformed", index=raw.index, dtype="object")
    status[text.eq("")] = "missing"
    integer = text.str.fullmatch(_INTEGER.pattern)
    values = pd.to_numeric(text.where(integer), errors="coerce")
    status[integer] = "valid"
    status[text.str.fullmatch(_NEGATIVE_NUMBER.pattern)] = "out_of_range"
    if maximum is not None:
        status[integer & (values > maximum)] = "out_of_range"
    return values.where(status.eq("valid")).astype("Int64"), status


def parse_decimal(raw: pd.Series, low: float, high: float | None) -> tuple[pd.Series, pd.Series]:
    text = raw.astype("string").str.strip().fillna("")
    status = pd.Series("malformed", index=raw.index, dtype="object")
    status[text.eq("")] = "missing"
    numeric = text.str.fullmatch(_DECIMAL.pattern) | text.str.fullmatch(_NEGATIVE_NUMBER.pattern)
    values = pd.to_numeric(text.where(numeric), errors="coerce")
    in_range = (values >= low) & ((values <= high) if high is not None else True)
    status[numeric] = "out_of_range"
    status[numeric & in_range.fillna(False)] = "valid"
    return values.where(status.eq("valid")).astype("float64"), status


def bedroom_segments(bedrooms: pd.Series) -> pd.Series:
    labels = pd.Series(UNKNOWN, index=bedrooms.index, dtype="object")
    known = bedrooms.notna()
    labels[known] = [BEDROOM_SEGMENTS[min(int(n), 6)] for n in bedrooms[known]]
    return labels


def read_raw(path: Path) -> pd.DataFrame:
    """Read every raw field as a string (no NA coercion), failing visibly on unreadable or incomplete files."""
    try:
        raw = pd.read_csv(path, dtype=str, keep_default_na=False, na_filter=False, encoding="utf-8")
    except Exception as error:  # noqa: BLE001 - surface any reader failure with the file name
        raise CleaningError(f"Could not read {path}: {error}") from error
    missing = [field for field in REQUIRED_FIELDS if field not in raw.columns]
    if missing:
        raise CleaningError(f"{path.name} is missing required fields {missing}. Supply the Inside Airbnb "
                            "detailed listings file (listings.csv.gz), not the summary listings.csv.")
    return raw


def clean_snapshot(raw: pd.DataFrame, snapshot: Snapshot, input_sha256: str) -> pd.DataFrame:
    ids = raw["id"].str.strip()
    if ids.eq("").any():
        raise CleaningError(f"{snapshot.path.name}: {int(ids.eq('').sum())} rows have a missing listing id.")
    duplicated = ids[ids.duplicated()]
    if not duplicated.empty:
        raise CleaningError(f"{snapshot.path.name}: duplicate listing ids within snapshot, e.g. {duplicated.iloc[0]!r}.")

    def optional(field: str) -> pd.Series:
        return raw[field] if field in raw.columns else pd.Series(pd.NA, index=raw.index, dtype="string")

    out = pd.DataFrame(index=raw.index)
    out["snapshot_date"] = snapshot.date
    out["snapshot_label"] = snapshot.label
    out["listing_id"] = ids
    out["source_file"] = snapshot.path.name
    out["source_row"] = np.arange(1, len(raw) + 1)  # 1-based data record number (header excluded)
    out["input_sha256"] = input_sha256
    out["last_scraped"] = optional("last_scraped").str.strip().replace("", pd.NA)
    out["source_raw"] = optional("source")
    out["source_category"] = out.source_raw.str.strip().replace("", pd.NA).fillna(UNKNOWN)

    out["price_raw"] = raw["price"]
    parsed = [parse_price(value) for value in raw["price"]]
    out["price_usd"] = pd.Series([p[0] for p in parsed], index=raw.index, dtype="float64")
    out["price_status"] = [p[1] for p in parsed]

    out["neighbourhood_raw"] = raw["neighbourhood_cleansed"]
    out["neighbourhood"] = raw["neighbourhood_cleansed"].str.split().str.join(" ").replace("", UNKNOWN)
    out["room_type_raw"] = raw["room_type"]
    room = raw["room_type"].str.strip()
    out["room_type"] = room.where(room.isin(ROOM_TYPES), UNKNOWN)

    out["bedrooms_raw"] = raw["bedrooms"]
    out["bedrooms"], out["bedrooms_status"] = parse_integers(raw["bedrooms"])
    out["bedroom_segment"] = bedroom_segments(out.bedrooms)
    out["bedroom_order"] = out.bedroom_segment.map(BEDROOM_ORDER).astype("Int64")

    out["minimum_nights_raw"] = optional("minimum_nights")
    if "minimum_nights" in raw.columns:
        out["minimum_nights"], out["minimum_nights_status"] = parse_integers(raw["minimum_nights"])
    else:
        out["minimum_nights"], out["minimum_nights_status"] = pd.Series(pd.NA, index=raw.index, dtype="Int64"), "unavailable"
    nights = out.minimum_nights
    out["stay_category"] = np.select([nights.between(1, 29).fillna(False), nights.ge(30).fillna(False)],
                                     [SHORT_STAY, LONG_STAY], UNKNOWN)

    for field, horizon in AVAILABILITY_HORIZONS.items():
        out[field], out[f"{field}_status"] = parse_integers(raw[field], horizon)
    for field in ("number_of_reviews_ltm", "number_of_reviews_l30d"):
        out[field], out[f"{field}_status"] = parse_integers(raw[field])
    out["review_scores_value"], out["review_scores_value_status"] = parse_decimal(raw["review_scores_value"], 0, 5)
    out["value_score_is_zero"] = out.review_scores_value.eq(0).fillna(False)

    for field, parser in (("number_of_reviews", lambda s: parse_integers(s)),
                          ("reviews_per_month", lambda s: parse_decimal(s, 0, None))):
        if field in raw.columns:
            out[field], out[f"{field}_status"] = parser(raw[field])
        else:
            out[field] = (pd.Series(pd.NA, index=raw.index, dtype="Int64") if field == "number_of_reviews"
                          else pd.Series(np.nan, index=raw.index, dtype="float64"))
            out[f"{field}_status"] = "unavailable"
    out["first_review"] = optional("first_review").str.strip().replace("", pd.NA)
    out["last_review"] = optional("last_review").str.strip().replace("", pd.NA)

    out["has_valid_price"] = out.price_status.eq("valid")
    out["has_valid_dimensions"] = (out.neighbourhood.ne(UNKNOWN) & out.room_type.ne(UNKNOWN)
                                   & out.bedroom_segment.ne(UNKNOWN))
    out["pricing_eligible"] = out.has_valid_price & out.has_valid_dimensions
    out["segment_key"] = [segment_key(n, r, b) if ok else pd.NA for n, r, b, ok in
                          out[["neighbourhood", "room_type", "bedroom_segment", "has_valid_dimensions"]]
                          .itertuples(index=False)]
    out = out[list(LISTING_COLUMNS)]
    for col in ("value_score_is_zero", "has_valid_price", "has_valid_dimensions", "pricing_eligible"):
        out[col] = out[col].astype("boolean")
    for col in out.columns:
        if out[col].dtype == object:
            out[col] = out[col].astype("string")
    return out


def _snapshot_report(frame: pd.DataFrame, raw_columns: list[str], snapshot: Snapshot) -> dict:
    counts = lambda s: {str(k): int(v) for k, v in s.value_counts(dropna=False).sort_index().items()}  # noqa: E731
    recalculated = {
        "rows": len(frame),
        "missing_price": int(frame.price_status.eq("missing").sum()),
        "zero_bedrooms": int(frame.bedrooms.eq(0).sum()),
        "missing_bedrooms": int(frame.bedrooms_status.eq("missing").sum()),
    }
    reference = REFERENCE_COUNTS.get(snapshot.date)
    return {
        "label": snapshot.label,
        "nominal_date": snapshot.date,
        "actual_scrape_dates": counts(frame.last_scraped.fillna("missing")),
        "rows": len(frame),
        "price_status": counts(frame.price_status),
        "has_valid_price": int(frame.has_valid_price.sum()),
        "has_valid_dimensions": int(frame.has_valid_dimensions.sum()),
        "pricing_eligible": int(frame.pricing_eligible.sum()),
        "bedrooms": {
            "status": counts(frame.bedrooms_status),
            "segments": {k: int(v) for k, v in frame.bedroom_segment.value_counts().items()},
            "zero_bedrooms": recalculated["zero_bedrooms"],
            "known_share": float(frame.bedrooms_status.eq("valid").mean()) if len(frame) else None,
        },
        "unknown_neighbourhood": int(frame.neighbourhood.eq(UNKNOWN).sum()),
        "unknown_room_type": int(frame.room_type.eq(UNKNOWN).sum()),
        "room_type": counts(frame.room_type),
        "stay_category": counts(frame.stay_category),
        "source_category": counts(frame.source_category),
        "field_status": {field: counts(frame[f"{field}_status"]) for field in
                         (*AVAILABILITY_HORIZONS, "number_of_reviews_ltm", "number_of_reviews_l30d",
                          "review_scores_value", "minimum_nights", "number_of_reviews", "reviews_per_month")},
        "value_score_zero": int(frame.value_score_is_zero.sum()),
        "optional_fields_unavailable": [f for f in OPTIONAL_FIELDS if f not in raw_columns],
        "reference_check": None if reference is None else {
            "reference": reference, "recalculated": recalculated,
            "matches": {k: recalculated[k] == v for k, v in reference.items()},
        },
    }


def _atomic_write(path: Path, write) -> None:
    handle, temp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    os.close(handle)
    try:
        write(Path(temp))
        os.chmod(temp, 0o644)
        os.replace(temp, path)
    finally:
        if os.path.exists(temp):
            os.remove(temp)


def run_cleaning(snapshots: tuple[Snapshot, ...], output_dir: Path, small_sample_threshold: int = 20) -> dict:
    """Clean both snapshots and write the three canonical artifacts. Returns the cleaning report."""
    missing = [s for s in snapshots if not s.path.is_file()]
    if missing:
        lines = "\n".join(f"  - {s.label} ({s.date}): expected at {s.path}" for s in missing)
        raise CleaningError(
            "Raw snapshot file(s) not found:\n" + lines + "\nObtain the Inside Airbnb Los Angeles detailed listings "
            "(listings.csv.gz) for these exact dates through the team's private repository (data/raw/) or the "
            "course-authorized workflow, then pass --march/--june or update config/project.json. "
            "No substitute data is downloaded.")
    output_dir = Path(output_dir).resolve()
    inputs = {s.path.resolve() for s in snapshots}
    targets = {output_dir / name for name in (LISTINGS_FILE, SEGMENTS_FILE, REPORT_FILE)}
    if inputs & targets:
        raise CleaningError("Output paths would overwrite a raw input; choose another --output-dir.")

    before = {s.date: fingerprint(s.path) for s in snapshots}
    frames, reports = [], []
    for snapshot in snapshots:
        raw = read_raw(snapshot.path)
        frame = clean_snapshot(raw, snapshot, before[snapshot.date])
        if len(frame) != len(raw):
            raise CleaningError(f"Row conservation failed for {snapshot.path.name}.")
        frames.append(frame)
        reports.append(_snapshot_report(frame, list(raw.columns), snapshot))
    listings = pd.concat(frames, ignore_index=True)
    validate_listings(listings, tuple(s.date for s in snapshots))
    segments = canonical_segments(listings, small_sample_threshold)
    validate_segments(segments, small_sample_threshold)
    comparable = listings.loc[listings.has_valid_dimensions.astype(bool)].groupby("snapshot_date").size()
    if not segments.groupby("snapshot_date").listing_rows.sum().equals(comparable):
        raise CleaningError("Segment listing_rows do not reconcile with comparable listing rows.")

    output_dir.mkdir(parents=True, exist_ok=True)
    _atomic_write(output_dir / LISTINGS_FILE, lambda p: listings.to_csv(p, index=False, encoding="utf-8"))
    _atomic_write(output_dir / SEGMENTS_FILE, lambda p: segments.to_csv(p, index=False, encoding="utf-8"))
    after = {s.date: fingerprint(s.path) for s in snapshots}
    if after != before:
        raise CleaningError("Raw input SHA-256 changed during cleaning; raw files must not be modified.")

    report = {
        "source": "Inside Airbnb, Los Angeles detailed listings (source extract geography)",
        "inputs": [{"label": s.label, "nominal_date": s.date, "file": s.path.name, "bytes": s.path.stat().st_size,
                    "sha256_before": before[s.date], "sha256_after": after[s.date],
                    "unchanged": before[s.date] == after[s.date]} for s in snapshots],
        "outputs": {name: {"sha256": fingerprint(output_dir / name), "rows": rows}
                    for name, rows in ((LISTINGS_FILE, len(listings)), (SEGMENTS_FILE, len(segments)))},
        "row_counts": {"total": len(listings), **{s.date: len(f) for s, f in zip(snapshots, frames)}},
        "segment_rows": {k: int(v) for k, v in segments.groupby("snapshot_date").size().items()},
        "snapshots": reports,
        "schema": {"listings": {c: str(listings[c].dtype) for c in listings.columns},
                   "segments": {c: str(segments[c].dtype) for c in segments.columns}},
        "required_fields": list(REQUIRED_FIELDS),
        "optional_fields": list(OPTIONAL_FIELDS),
        "small_sample_threshold": small_sample_threshold,
        "policies": POLICIES,
    }
    _atomic_write(output_dir / REPORT_FILE,
                  lambda p: p.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"))
    return report
