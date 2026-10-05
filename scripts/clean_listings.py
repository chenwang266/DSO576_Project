"""Reproducible LA listing-snapshot cleaning; never writes into data/raw.

Run from any directory: python scripts/clean_listings.py
Verify regeneration: python scripts/clean_listings.py --verify-reproducibility
Requires pandas >= 2.2. All policy predicates are documented in data_dictionary.md.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import tempfile
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SNAPSHOTS = ("2026-03-16", "2026-06-15")
ARTIFACTS = ("listings_clean.csv", "listings_sample.csv", "validation_report.json", "data_dictionary.md")
OMIT_EMPTY = "neighborhood_overview host_since host_response_time host_response_rate host_acceptance_rate host_thumbnail_url host_neighbourhood host_total_listings_count host_verifications neighbourhood calendar_updated instant_bookable".split()
OMIT_CONTEXT = "name description picture_url host_url host_profile_id host_profile_url host_name hosts_time_as_user_years hosts_time_as_user_months hosts_time_as_host_years hosts_time_as_host_months host_location host_about host_picture_url amenities".split()
DATES = "last_scraped calendar_last_scraped first_review last_review price_quote_checkin_date price_quote_checkout_date".split()
BOOLS = "host_is_superhost host_has_profile_pic host_identity_verified has_availability".split()
TEXT = "id listing_url scrape_id host_id source neighbourhood_cleansed neighbourhood_group_cleansed room_type property_type bathrooms_text price_quote_raw license".split()
FLOATS = "latitude longitude bathrooms minimum_nights_avg_ntm maximum_nights_avg_ntm price_quote_total_price price_quote_price_per_night reviews_per_month estimated_revenue_l365d review_scores_rating review_scores_accuracy review_scores_cleanliness review_scores_checkin review_scores_communication review_scores_location review_scores_value".split()
ROOMS = {"Entire home/apt", "Private room", "Shared room", "Hotel room"}
GROUPS = {"City of Los Angeles", "Other Cities", "Unincorporated Areas"}
SOURCES = {"city scrape", "previous scrape"}
LICENSE_PATTERN = re.compile(r"(?:HSR\d{2}-\d{6}|(?:PRP|NRP)\d{2}-\d{5}|STR\d{2}-\d{4,5}|SRH-?\d{4}-\d{5}|HS-\d{6}-\d{4}|\d+)", re.I)


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def counts(frame: pd.DataFrame, column: str) -> dict:
    return {str(k): int(v) for k, v in frame[column].value_counts(dropna=False).sort_index().items()}


def missing(frame: pd.DataFrame) -> dict:
    return {c: int(n) for c, n in frame.isna().sum().items()}


def records(frame: pd.DataFrame) -> list:
    # pandas JSON writer safely serializes nullable scalars as JSON null.
    return json.loads(frame.to_json(orient="records"))


def checkpoint(report: dict, name: str, before: pd.DataFrame | None,
               after: pd.DataFrame, rules: dict | None = None) -> None:
    """Account for all representation/value changes; don't sum overlapping rows."""
    changed = pd.Series(False, index=after.index)
    columns = {}
    if before is not None:
        require(before.index.equals(after.index), f"{name}: row/order changes require explicit accounting")
        for c in before.columns.intersection(after.columns):
            left, right = before[c].astype("string"), after[c].astype("string")
            mask = ~(left.eq(right).fillna(False) | (left.isna() & right.isna()))
            if mask.any():
                changed |= mask
                examples = []
                for i in mask[mask].index[:3]:
                    examples.append({"id": str(after.at[i, "id"]),
                                     "snapshot_date": str(after.at[i, "snapshot_date"]),
                                     "before": None if pd.isna(left.at[i]) else str(left.at[i]),
                                     "after": None if pd.isna(right.at[i]) else str(right.at[i])})
                columns[c] = {"changed_rows": int(mask.sum()), "examples": examples}
    flags = {c: {"true": int(after[c].sum()), "unknown": int(after[c].isna().sum())}
             for c in after if c.startswith("flag_") or c in ["no_reviews", "primary_pricing_eligible", "demand_eligible"]}
    entry = {"step": name, "input_rows": len(before) if before is not None else len(after),
             "output_rows": len(after), "dropped_rows": 0, "drop_reason": "No row exclusions are applied",
             "distinct_existing_rows_changed": int(changed.sum()), "changed_columns": columns,
             "added_columns": list(after.columns.difference(before.columns, sort=False)) if before is not None else ["snapshot_date", "source_file", "source_row_number"],
             "removed_columns": list(before.columns.difference(after.columns, sort=False)) if before is not None else [],
             "missing_counts": missing(after), "flag_counts": flags,
             "rules": rules or {}, "duplicate_keys": int(after.duplicated(["id", "snapshot_date"]).sum())}
    if before is not None:
        entry["missing_counts_before"] = missing(before)
    entry["added_fields_populated_rows"] = {c: int(after[c].notna().sum()) for c in entry["added_columns"]}
    report["steps"].append(entry)
    print(f"\n{name}: {entry['input_rows']:,} -> {len(after):,} rows; dropped=0; existing rows changed={int(changed.sum()):,}")
    print("Missing counts:", json.dumps(entry["missing_counts"], sort_keys=True))
    print("Flag counts:", json.dumps(flags, sort_keys=True))
    print("Changed columns:", json.dumps({c: v["changed_rows"] for c, v in columns.items()}, sort_keys=True))


def segment_summaries(d: pd.DataFrame) -> dict:
    keys = ["snapshot_date", "neighbourhood_cleansed", "room_type"]
    summaries = d.groupby(keys, observed=True, sort=True).agg(
        listing_rows=("id", "size"), priced_rows=("price", "count"), median_price=("price", "median"))
    summaries["priced_coverage"] = summaries.priced_rows / summaries.listing_rows
    cohort = d.groupby(keys + ["stay_type"], observed=True, sort=True).agg(
        listing_rows=("id", "size"), priced_rows=("price", "count"), median_price=("price", "median"))
    cohort["priced_coverage"] = cohort.priced_rows / cohort.listing_rows
    # Primary denominator includes unpriced short-stay city-scrape rows.
    base = d.loc[d.stay_type.eq("short") & ~d.flag_previous_scrape]
    primary = base.groupby(keys, observed=True, sort=True).agg(
        eligible_supply_rows=("id", "size"), priced_rows=("price", "count"), median_price=("price", "median"))
    primary["priced_coverage"] = primary.priced_rows / primary.eligible_supply_rows
    demand = d.loc[d.demand_eligible].groupby(keys, observed=True, sort=True).agg(
        eligible_rows=("id", "size"), reviews_ltm=("number_of_reviews_ltm", "sum"),
        median_available_days_365=("availability_365", "median"),
        median_estimated_occupancy_days=("estimated_occupancy_l365d", "median"))
    return {"all_segments": records(summaries.reset_index()),
            "stay_cohorts": records(cohort.reset_index()),
            "primary_pricing_segments": records(primary.reset_index()),
            "demand_proxy_segments": records(demand.reset_index()),
            "notes": "Every summary is per snapshot. Price extremes are retained. Demand measures are proxies/estimates, not observed bookings. Segments with no primary supply have no primary median; see all_segments for full coverage."}


def sample_rows(d: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    cases = {
        "missing_price_and_quote": d.flag_missing_price & d.price_quote_price_per_night.isna(),
        "priced_without_quote": d.price.notna() & d.price_quote_price_per_night.isna(),
        "price_below_10": d.flag_price_low, "price_above_5000": d.flag_price_high,
        "19_digit_listing_id": d.id.str.len().eq(19), "missing_minimum_nights": d.flag_missing_minimum_nights,
        "long_stay": d.stay_type.eq("long"), "previous_scrape": d.flag_previous_scrape,
        "possible_inactivity": d.flag_possible_inactivity, "no_lifetime_reviews": d.no_reviews,
        "occupancy_at_255": d.flag_occupancy_at_255, "extreme_maximum_nights": d.flag_extreme_maximum_nights,
        "zero_rating": d.flag_zero_rating, "license_case_normalized": d.flag_license_normalized,
        "license_whitespace_variant": d.flag_license_whitespace,
        "license_literal_NA": d.license.str.casefold().eq("n/a"),
        "license_exempt": d.license_status.eq("exempt"),
        "license_numeric": d.license.str.fullmatch(r"\d+"),
        "license_unrecognized": d.flag_license_unrecognized,
        "scrape_date_discrepancy": d.flag_scrape_date_discrepancy,
        "zero_price": d.flag_price_zero, "impossible_value": d.flag_impossible_value,
    }
    chosen = set()
    for date in SNAPSHOTS:
        for mask in cases.values():
            idx = d.index[mask.fillna(False) & d.snapshot_date.eq(date)]
            if len(idx):
                chosen.add(int(idx[0]))
    require(len(chosen) <= 50, "Difficult-case sample exceeds 50 rows")
    for i in d.loc[~d.index.isin(chosen)].sample(n=min(50-len(chosen), len(d)-len(chosen)), random_state=576).index:
        chosen.add(int(i))
    result = d.loc[sorted(chosen)].copy()
    result["reason"] = ["; ".join(name for name, mask in cases.items() if pd.notna(mask.at[i]) and bool(mask.at[i]))
                        or "seeded ordinary coverage" for i in result.index]
    return result, {name: {"available": int(mask.sum()), "sampled": int(mask.loc[result.index].sum())}
                    for name, mask in cases.items()}


def dictionary(d: pd.DataFrame) -> str:
    text = """# Clean Los Angeles listing-snapshot data

Grain: one row per listing per snapshot. Key: id + snapshot_date. All raw rows are retained; no prices or capacity values are imputed, capped, or deleted. Category labels and neighbourhood groups are unchanged. Both source CSVs are read-only.

## Loading and representations

Use pandas.read_csv(..., dtype={'id':'string', 'host_id':'string', 'scrape_id':'string', 'license':'string'}, keep_default_na=False) followed by explicit blank-only missing conversion according to this schema. License remains an exact raw string, including blank and N/A. Empty CSV numeric/date/Boolean cells mean missing. CSV cannot encode types; IDs must never pass through Excel numeric inference or floats. Script ingestion reads every raw token as a string, then maps blank tokens to missing in every source field except license. The omitted host_verifications field additionally maps literal None to missing, explaining its entirely missing status in the original inspection. Thus the eight literal N/A licenses remain preserved while license_status marks them missing.

price_raw preserves source currency text. price removes $ and thousands commas only; amount and fractional units are unchanged. No quote-to-price fallback exists. Source price is interpreted as a currency amount per listed night; quote currency evidence is USD when specified, but quote dates/fee semantics vary, so no currency conversion or fee normalization is performed. price_quote_total_price is a stay-total amount, not a nightly rate. price_quote_price_per_night is separate. Latitude/longitude remain decimal degrees. Night limits and availability are nights/days, reviews_per_month is reviews/month, review_scores_* remain 0–5. estimated_occupancy_l365d remains estimated days in the past 365 days and estimated_revenue_l365d remains a modeled currency estimate, not realized earnings. Do not derive observed bookings from unavailable days.

All six retained dates and snapshot_date serialize as YYYY-MM-DD. Dates are not timezone-converted. snapshot_date is filename-derived and actual scrape dates remain separate. t -> True, f -> False, blank -> missing for the four retained t/f fields; no missing-to-false fill. Integral count fields use nullable Int64; fractional measures use nullable Float64. No capacity imputation or bathroom-text extraction is performed. Source row number is a 1-based CSV data-record ordinal, not a physical line number.

## Policy and derived fields

- stay_type: short if minimum_nights <30, long if >=30, unknown if missing. No pooling of neighbourhood_cleansed x room_type segments.
- primary_pricing_eligible: short AND price present AND source == city scrape. Missing prices do not enter medians. Low/high prices and possible inactivity remain eligible for price statistics.
- demand_eligible: short AND city scrape AND NOT flag_possible_inactivity; price is not required. Long stays are separately summarized as a cohort and their flagged counts reported; no inactive row contributes to primary demand proxies.
- Priced coverage: nonmissing prices / all rows for each segment and cohort. Primary coverage denominator is all short city-scrape rows, including missing prices. Medians retain outliers. Do not combine cohorts or snapshots without explaining the changed population.
- no_reviews: number_of_reviews ==0. reviews_per_month and review dates stay null; a zero review count does not establish zero demand.
- flag_missing_price / flag_missing_minimum_nights: missing parsed source values.
- flag_price_low / flag_price_high: price <10 / price >5000, respectively. Missing prices yield unknown in comparison flags. Boundaries 10 and 5000 are not flagged. flag_price_zero is price ==0; flag_price_nonpositive is price <=0.
- flag_previous_scrape: source == previous scrape.
- flag_possible_inactivity: number_of_reviews_ltm ==0 AND availability_365 >=300. This is a suspicion, not proven inactivity.
- flag_occupancy_at_255: estimated_occupancy_l365d ==255, noting an apparent ceiling; no correction.
- flag_extreme_maximum_nights: maximum_nights >1125; preserves possible sentinel values.
- flag_zero_rating: review_scores_rating ==0. Missing ratings yield unknown.
- flag_scrape_date_discrepancy: last_scraped differs from calendar_last_scraped. flag_scraped_after_snapshot records multi-day collection rather than an error. flag_review_after_scrape uses the row's actual last_scraped.
- flag_impossible_value: union of nonpositive/fractional stay minima/maxima, min > max, negative/fractional review and capacity count fields, negative bathrooms/rates/revenue/occupancy, occupancy >365, bad cumulative calendar bounds/order, review-count order, coordinate bounds, scores outside [0,5], reversed review/quote dates, or review dates after actual scrape. These are screens, not repair instructions. Unknown comparisons are ignored in this union, and missingness is separately reported.
- license_status: missing for blank or case-insensitive N/A; exempt for text containing exempt; hsr_registered for case-insensitive HSR##-######; other_identifier for other populated tokens. hsr_registered denotes format only, not registry verification; other_identifier can include unrecognized prose.
- license_normalized: uppercase ONLY full matches of HSR##-######, PRP/NRP##-#####, STR##-#### or #####, SRH[-]####-#####, HS-######-####, or digits-only identifiers. Other tokens are missing here and remain intact in license. No whitespace or separator rewrites. flag_license_normalized records changed case; flag_license_whitespace compares raw with stripped/collapsed whitespace; flag_license_unrecognized means populated nonexempt license outside these patterns. Placeholder-like HSR suffixes 000000 and 123456 are flagged by flag_license_placeholder, never invalidated.

## Audit and reproducibility

validation_report.json includes exact source hashes, row/duplicate accounting, raw and output missingness, price/quote overlap, source-specific price coverage BEFORE eligibility, changed-cell counts and examples per transformation, overlapping-row totals, flag counts by snapshot, summary tables and sample coverage. Existing-cell change counts compare serialized string representations; dtype-only changes with identical text are separately visible in dtype inventories. Added columns report populated row counts. Dropped source columns are listed below; dropped rows are zero. No per-cell log or dropped_rows artifact is emitted, per Christos's instructions. Original source tokens can always be traced by source_file + source_row_number.

Run `python scripts/clean_listings.py --verify-reproducibility` to regenerate twice, compare SHA-256 of all four artifacts, and reload string keys. No run timestamps or temporary output paths enter artifact contents. Versions are recorded, so byte-identical verification assumes the same environment.

Sample: at most 50 rows, first available row of each difficult case per snapshot, deduplicated, then a seeded (576) supplement. reason records all matching case predicates. Report unavailable case types rather than manufacturing examples.

## Omitted columns

Entirely blank fields, omitted for lack of information: """
    text += ", ".join(OMIT_EMPTY) + ". The omitted host_verifications field uses literal None rather than blanks.\n\n"
    text += "Unused descriptive/profile/image/amenity fields, omitted for analysis scope: " + ", ".join(OMIT_CONTEXT) + ".\n\n"
    text += "## Output field schema\n\n| Column | pandas dtype | Meaning / origin |\n|---|---|---|\n"
    for c in d:
        origin = "Derived; predicate described above or provenance metadata" if c in NEW_COLUMNS or c.startswith("flag_") else "Source field; original meaning/units preserved"
        text += f"| {c} | {d[c].dtype} | {origin} |\n"
    return text


NEW_COLUMNS = "snapshot_date source_file source_row_number price_raw stay_type license_status license_normalized no_reviews primary_pricing_eligible demand_eligible".split()


def clean(raw_dir: Path, output_dir: Path) -> dict:
    raw_dir, output_dir = raw_dir.resolve(), output_dir.resolve()
    protected = (ROOT / "data/raw").resolve()
    require(not output_dir.is_relative_to(raw_dir) and not output_dir.is_relative_to(protected), "Output directory must not be inside data/raw")
    require(not raw_dir.is_relative_to(output_dir), "Output directory must not contain the raw directory")
    report = {"policy_version": 1, "pandas_version": pd.__version__, "steps": [], "inputs": {},
              "dropped_rows": 0, "drop_reason": "Keep every raw row; eligibility is a separate flag"}
    frames, schema = [], None
    for date in SNAPSHOTS:
        path = raw_dir / f"listings_{date}.csv"
        hash_before = digest(path)
        d = pd.read_csv(path, dtype="string", keep_default_na=False, low_memory=False)
        require(schema is None or list(d.columns) == schema, "Raw column names/order differ")
        schema = list(d.columns)
        require(len(schema) == 90, f"Expected inspected 90-column schema, got {len(schema)}")
        for c in ["id", "host_id"]:
            require(bool(d[c].str.fullmatch(r"\d+").all()), f"Missing/nondigit {c}: inspect before repairing")
        require(not d.id.duplicated().any(), f"Repeated IDs in {path.name}; no survivor rule approved")
        report["inputs"][date] = {"source_file": path.name, "sha256": hash_before, "shape": list(d.shape),
            "dtypes": {c: str(t) for c, t in d.dtypes.items()}, "exact_duplicate_rows": int(d.duplicated().sum()),
            "repeated_id_extra_rows": int(d.id.duplicated().sum()),
            "blank_tokens": {c: int(d[c].eq("").sum()) for c in d},
            "literal_NA_license": int(d.license.eq("N/A").sum())}
        d["snapshot_date"] = date
        d["source_file"] = path.name
        d["source_row_number"] = pd.array(range(1, len(d)+1), dtype="Int64")
        frames.append(d)
    d = pd.concat(frames, ignore_index=True)
    a, b = set(frames[0].id), set(frames[1].id)
    report["membership"] = {"both": len(a & b), "only_march": len(a-b), "only_june": len(b-a), "union": len(a | b)}
    checkpoint(report, "1. Raw string ingestion and filename provenance", None, d,
               {"metadata": "Added snapshot_date, source_file and row ordinal to all rows; no source values altered"})
    before = d.copy()
    for c in schema:
        if c != "license":
            d[c] = d[c].mask(d[c].eq(""), pd.NA)
    d["host_verifications"] = d.host_verifications.mask(d.host_verifications.eq("None"), pd.NA)
    checkpoint(report, "2. Blank-only missing-token interpretation", before, d,
               {"mapping": "empty source token -> missing except license; omitted host_verifications literal None -> missing; literal N/A licenses preserved"})
    for c in OMIT_EMPTY:
        require(d[c].isna().all(), f"Previously empty {c} now has values: review omission")
    before = d.copy()
    d = d.drop(columns=OMIT_EMPTY + OMIT_CONTEXT)
    checkpoint(report, "3. Select approved analytical schema", before, d,
               {"omission_reason": {**{c: "100% blank" for c in OMIT_EMPTY}, **{c: "Unused narrative/profile/context" for c in OMIT_CONTEXT}}})
    before = d.copy()
    d["price_raw"] = d.price.copy()
    numeric_columns = [c for c in d if c not in TEXT + DATES + BOOLS + ["snapshot_date", "source_file", "source_row_number", "price_raw"]]
    for c in numeric_columns:
        s = d[c]
        if c == "price":
            s = s.str.replace("$", "", regex=False).str.replace(",", "", regex=False)
        n = pd.to_numeric(s, errors="coerce")
        bad = s.notna() & n.isna()
        require(not bad.any(), f"{c}: {int(bad.sum())} invalid numeric tokens; flagged IDs {d.loc[bad, 'id'].head().tolist()}; no repair approved")
        dtype = "Float64" if c in FLOATS + ["price"] else "Int64"
        if dtype == "Int64":
            require(not (n.notna() & n.mod(1).ne(0)).any(), f"{c}: fractional count; flag and review before casting")
        d[c] = n.astype(dtype)
    for c in DATES:
        p = pd.to_datetime(d[c], format="%Y-%m-%d", errors="coerce")
        bad = d[c].notna() & p.isna()
        require(not bad.any(), f"{c}: {int(bad.sum())} invalid dates; no repair approved")
        d[c] = p.dt.strftime("%Y-%m-%d").astype("string")
    for c in BOOLS:
        bad = d[c].notna() & ~d[c].isin(["t", "f"])
        require(not bad.any(), f"{c}: invalid Boolean tokens: {d.loc[bad,c].unique().tolist()}")
        d[c] = d[c].map({"t": True, "f": False}).astype("boolean")
    checkpoint(report, "4. Parse amounts, counts, ISO dates and nullable Booleans", before, d,
               {"price": "strip $ and commas only; no unit change or filling", "Boolean": "t->True; f->False; missing unchanged", "counts": "nullable integers; fractional units preserved in Float64 fields"})
    report["price_missingness_by_source_before_eligibility"] = records(d.assign(price_missing=d.price.isna()).groupby(["snapshot_date", "source"], sort=True).agg(
        rows=("id", "size"), missing_price=("price_missing", "sum"), priced_rows=("price", "count")).assign(
        missing_price_fraction=lambda x: x.missing_price/x.rows).reset_index())
    print("\nPrice missingness by source BEFORE eligibility:")
    print(json.dumps(report["price_missingness_by_source_before_eligibility"], indent=2))
    report["price_quote_overlap"] = {}
    for date in SNAPSHOTS:
        x = d.loc[d.snapshot_date.eq(date)]
        p, q = x.price.notna(), x.price_quote_price_per_night.notna()
        report["price_quote_overlap"][date] = {"both_missing": int((~p & ~q).sum()), "price_missing_quote_present": int((~p & q).sum()),
            "price_present_quote_missing": int((p & ~q).sum()), "both_present": int((p & q).sum()),
            "different_over_0_005": int((p & q & (x.price-x.price_quote_price_per_night).abs().gt(.005)).sum())}
    before = d.copy()
    d["stay_type"] = pd.Series("unknown", index=d.index, dtype="string")
    d.loc[d.minimum_nights.lt(30).fillna(False), "stay_type"] = "short"
    d.loc[d.minimum_nights.ge(30).fillna(False), "stay_type"] = "long"
    d["flag_missing_price"] = d.price.isna().astype("boolean")
    d["flag_missing_minimum_nights"] = d.minimum_nights.isna().astype("boolean")
    for name, condition in {"price_low": d.price.lt(10), "price_high": d.price.gt(5000), "price_zero": d.price.eq(0),
        "price_nonpositive": d.price.le(0), "previous_scrape": d.source.eq("previous scrape"),
        "possible_inactivity": d.number_of_reviews_ltm.eq(0) & d.availability_365.ge(300),
        "occupancy_at_255": d.estimated_occupancy_l365d.eq(255), "extreme_maximum_nights": d.maximum_nights.gt(1125),
        "zero_rating": d.review_scores_rating.eq(0), "scrape_date_discrepancy": d.last_scraped.ne(d.calendar_last_scraped),
        "scraped_after_snapshot": d.last_scraped.gt(d.snapshot_date), "review_after_scrape": d.last_review.gt(d.last_scraped)}.items():
        d["flag_"+name] = condition.astype("boolean")
    d["no_reviews"] = d.number_of_reviews.eq(0).astype("boolean")
    checks = {}
    for c, limit in [("availability_30", 30), ("availability_60", 60), ("availability_90", 90), ("availability_365", 365), ("estimated_occupancy_l365d", 365)]:
        checks[c+"_bounds"] = d[c].lt(0) | d[c].gt(limit) | d[c].mod(1).ne(0)
    checks["availability_order"] = d.availability_30.gt(d.availability_60) | d.availability_60.gt(d.availability_90) | d.availability_90.gt(d.availability_365)
    for c in ["minimum_nights", "maximum_nights"]:
        checks[c+"_nonpositive"] = d[c].le(0)
    checks["stay_limit_order"] = d.minimum_nights.gt(d.maximum_nights)
    for c in ["number_of_reviews", "number_of_reviews_ltm", "number_of_reviews_l30d", "number_of_reviews_ly", "accommodates", "bedrooms", "beds", "bathrooms", "reviews_per_month", "estimated_revenue_l365d"]:
        checks[c+"_negative"] = d[c].lt(0)
    checks["capacity_accommodates_nonpositive"] = d.accommodates.le(0)
    checks["review_count_order"] = d.number_of_reviews_l30d.gt(d.number_of_reviews_ltm) | d.number_of_reviews_ltm.gt(d.number_of_reviews)
    checks["coordinates"] = d.latitude.abs().gt(90) | d.longitude.abs().gt(180)
    for c in d:
        if c.startswith("review_scores_"):
            checks[c+"_bounds"] = d[c].lt(0) | d[c].gt(5)
    checks["review_date_order"] = d.first_review.gt(d.last_review)
    checks["review_after_scrape"] = d.last_review.gt(d.last_scraped) | d.first_review.gt(d.last_scraped)
    checks["quote_date_order"] = d.price_quote_checkout_date.le(d.price_quote_checkin_date)
    checks["price_nonpositive"] = d.price.le(0)
    d["flag_impossible_value"] = pd.DataFrame(checks).fillna(False).any(axis=1).astype("boolean")
    report["impossible_checks"] = {date: {c: int(mask.loc[d.snapshot_date.eq(date)].sum()) for c, mask in checks.items()} for date in SNAPSHOTS}
    checkpoint(report, "5. Flag suspicious values and classify stay cohorts", before, d,
               {"suspicious_values": "Preserved unchanged; no flags delete or cap rows", "no_reviews": "zero lifetime reviews; no rate imputation"})
    print("Stay counts:", json.dumps(counts(d, "stay_type")))
    before = d.copy()
    s = d.license
    empty = s.str.strip().eq("") | s.str.strip().str.casefold().eq("n/a")
    exempt = ~empty & s.str.contains("exempt", case=False, regex=False)
    recognized = s.str.fullmatch(LICENSE_PATTERN)
    hsr = s.str.fullmatch(r"HSR\d{2}-\d{6}", case=False)
    d["license_status"] = pd.Series("other_identifier", index=d.index, dtype="string")
    d.loc[empty, "license_status"] = "missing"
    d.loc[exempt, "license_status"] = "exempt"
    d.loc[hsr, "license_status"] = "hsr_registered"
    d["license_normalized"] = s.str.upper().where(recognized, pd.NA)
    d["flag_license_normalized"] = (recognized & s.ne(s.str.upper())).astype("boolean")
    d["flag_license_whitespace"] = s.ne(s.str.strip().str.replace(r"\s+", " ", regex=True)).astype("boolean")
    d["flag_license_unrecognized"] = (~empty & ~exempt & ~recognized).astype("boolean")
    d["flag_license_placeholder"] = s.str.fullmatch(r"HSR\d{2}-(?:000000|123456)", case=False).astype("boolean")
    checkpoint(report, "6. License status and identifier-only normalization", before, d,
               {"raw_license": "Unchanged, including blank and N/A", "normalization": "Uppercase recognized full-match identifiers only; all others null in separate normalized field", "status": "Format classification does not establish registry validity"})
    print("License status counts:", json.dumps(counts(d, "license_status")))
    before = d.copy()
    for c, values in [("room_type", ROOMS), ("source", SOURCES), ("neighbourhood_group_cleansed", GROUPS)]:
        require(d[c].notna().all() and set(d[c]) <= values, f"Unexpected/missing {c}; review categories before eligibility")
    require(d.neighbourhood_cleansed.notna().all(), "Missing segment neighbourhood")
    d["primary_pricing_eligible"] = (d.stay_type.eq("short") & d.price.notna() & d.source.eq("city scrape")).astype("boolean")
    d["demand_eligible"] = (d.stay_type.eq("short") & d.source.eq("city scrape") & ~d.flag_possible_inactivity).astype("boolean")
    checkpoint(report, "7. Separate pricing and demand eligibility; retain all rows", before, d,
               {"pricing": "short & priced & city scrape; medians include extremes", "demand": "short & city scrape & not possibly inactive; price not required"})
    report["by_snapshot"] = {}
    for date in SNAPSHOTS:
        x = d.loc[d.snapshot_date.eq(date)]
        flag_columns = [c for c in x if c.startswith("flag_")]
        flag_matrix = x[flag_columns].fillna(False)
        report["by_snapshot"][date] = {"rows": len(x), "missing_counts": missing(x), "stay_type": counts(x, "stay_type"),
            "license_status": counts(x, "license_status"), "flag_counts": {c: {"true": int(x[c].sum()), "unknown": int(x[c].isna().sum())}
                for c in x if c.startswith("flag_") or c in ["no_reviews", "primary_pricing_eligible", "demand_eligible"]},
            "distinct_rows_with_any_flag": int(flag_matrix.any(axis=1).sum()),
            "distinct_rows_with_multiple_flags": int(flag_matrix.sum(axis=1).gt(1).sum())}
    for c in ["room_type", "property_type", "neighbourhood_cleansed", "neighbourhood_group_cleansed", "source", "license"]:
        original = pd.concat([x[c] for x in frames], ignore_index=True)
        require(d[c].equals(original), f"Source label/token modified: {c}")
    require(len(d) == sum(report["inputs"][date]["shape"][0] for date in SNAPSHOTS), "Row conservation failed")
    require(not d.duplicated(["id", "snapshot_date"]).any(), "Duplicate clean keys")
    for date in SNAPSHOTS:
        require(digest(raw_dir / report["inputs"][date]["source_file"]) == report["inputs"][date]["sha256"], "Raw file hash changed")
    report["validation"] = {"row_conservation": True, "unique_compound_key": True, "raw_hashes_unchanged": True,
        "price_imputed_rows": 0, "price_capped_rows": 0, "raw_license_changes": 0, "category_label_changes": 0,
        "dropped_rows": 0, "source_columns_omitted": OMIT_EMPTY+OMIT_CONTEXT,
        "output_dtypes": {c: str(t) for c,t in d.dtypes.items()}}
    report["segment_summaries"] = segment_summaries(d)
    sample, coverage = sample_rows(d)
    report["sample"] = {"rows": len(sample), "case_coverage": coverage, "seed": 576}
    output_dir.mkdir(parents=True, exist_ok=True)
    d.to_csv(output_dir / ARTIFACTS[0], index=False, lineterminator="\n")
    sample.to_csv(output_dir / ARTIFACTS[1], index=False, lineterminator="\n")
    # Independent output reload checks string keys against original records.
    reload = pd.read_csv(output_dir / ARTIFACTS[0], dtype="string", keep_default_na=False)
    for c in ["id", "host_id", "scrape_id", "license"]:
        require(reload[c].tolist() == d[c].astype("string").fillna("").tolist(), f"CSV round-trip changed {c}")
    require(len(reload) == len(d) and not reload.duplicated(["id", "snapshot_date"]).any(), "Reload row/key validation failed")
    require(len(sample)<=50 and not sample.duplicated(["id", "snapshot_date"]).any(), "Invalid sample")
    report["validation"]["csv_key_and_license_round_trip"] = True
    (output_dir / ARTIFACTS[2]).write_text(json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False)+"\n", encoding="utf-8")
    (output_dir / ARTIFACTS[3]).write_text(dictionary(d), encoding="utf-8")
    print(f"\nWrote {len(d):,} cleaned rows and {len(sample)} sampled rows to {output_dir}")
    print("Stay cohorts and eligibility:", json.dumps({date: {"stay_type": r["stay_type"], "primary_pricing": r["flag_counts"]["primary_pricing_eligible"], "demand": r["flag_counts"]["demand_eligible"]} for date,r in report["by_snapshot"].items()}))
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw-dir", type=Path, default=ROOT / "data/raw")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "data/clean")
    parser.add_argument("--verify-reproducibility", action="store_true")
    args = parser.parse_args()
    clean(args.raw_dir, args.output_dir)
    if args.verify_reproducibility:
        with tempfile.TemporaryDirectory(prefix="la_listing_regeneration_") as temp:
            clean(args.raw_dir, Path(temp))
            for filename in ARTIFACTS:
                require(digest(args.output_dir / filename) == digest(Path(temp) / filename), f"Regeneration mismatch: {filename}")
            print("\nPASS: all four outputs regenerate byte-for-byte from unchanged raw files.")


if __name__ == "__main__":
    main()
