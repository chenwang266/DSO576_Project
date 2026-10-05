"""Clean the Inside Airbnb Los Angeles snapshots (March and June 2026).

Business question: which LA neighbourhood x property-segment combinations should a
Marketplace Strategy Manager prioritise for closer pricing review?

Run from the project root:  python src/clean.py
Reads  data/raw/*.csv.gz  (never modified)
Writes data/clean/listings_clean.csv.gz and supporting tables in outputs/.

Each approved rule is one function named rNN_*; every rule appends to outputs/cleaning_log.csv.
Rows are never deleted for quality reasons: problems become flag columns.
"""
import csv
import hashlib
import re
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data" / "raw"
CLEAN_DIR = ROOT / "data" / "clean"
OUT_DIR = ROOT / "outputs"
RAW_FILES = {"2026-03": "3_15.csv.gz", "2026-06": "6_15.csv.gz"}
CLEAN_FILE = CLEAN_DIR / "listings_clean.csv.gz"

# Part 2 parameters (approved)
MONTHLY_MIN_NIGHTS = 30   # R4a: min stay >= 30 nights is a monthly price quote
OUTLIER_K = 3.0           # R13: IQR multiplier on log(price)
MIN_GROUP_N = 20          # R17: priced listings needed before a segment is ranked
INT_SENTINEL = 2147483647  # R11: max 32-bit int used as "no limit"
OCCUPANCY_CAP = 255       # R12: Inside Airbnb caps estimated_occupancy_l365d at 255

KEY = ["snapshot", "id"]
LOG = []


def log(rule, column, rows_affected, df_before_n, df_after_n, note=""):
    LOG.append({"rule": rule, "column": column, "rows_affected": int(rows_affected),
                "rows_before": int(df_before_n), "rows_after": int(df_after_n), "note": note})


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def blank(s):
    return s.isna() | (s.astype("string").str.strip() == "")


# --------------------------------------------------------------------------- structure
def r01_stack_and_key(raw):
    """U1/U8: one row = one listing in one snapshot; key = (snapshot, id)."""
    frames = []
    for snap, df in raw.items():
        exact = df.duplicated().sum()
        dup_id = df["id"].duplicated().sum()
        log("R01", "*", exact, len(df), len(df), f"{snap}: exact duplicate rows={exact}, repeated id={dup_id}")
        frames.append(df.assign(snapshot=snap))
    out = pd.concat(frames, ignore_index=True)
    out = out[["snapshot"] + [c for c in out.columns if c != "snapshot"]]
    n_dup_key = out.duplicated(KEY).sum()
    assert n_dup_key == 0, f"{n_dup_key} duplicated (snapshot, id) keys"
    log("R01", "snapshot,id", 0, len(out), len(out),
        f"stacked {len(raw)} snapshots; duplicated(snapshot,id)={n_dup_key}")
    return out


def r02_provenance(raw):
    """U2: record source, dates, shape and hash of every raw file."""
    rows = []
    for snap, df in raw.items():
        path = RAW_DIR / RAW_FILES[snap]
        rows.append({"snapshot": snap, "file": f"data/raw/{RAW_FILES[snap]}",
                     "source": "Inside Airbnb, Los Angeles listings.csv.gz (https://insideairbnb.com/get-the-data/)",
                     "scrape_id": df["scrape_id"].iloc[0],
                     "last_scraped_min": df["last_scraped"].min(), "last_scraped_max": df["last_scraped"].max(),
                     "rows": len(df), "columns": df.shape[1], "sha256": sha256(path)})
    manifest = pd.DataFrame(rows)
    manifest.to_csv(OUT_DIR / "source_manifest.csv", index=False)
    for r in rows:
        log("R02", "*", 0, r["rows"], r["rows"], f"{r['file']} sha256={r['sha256'][:12]}...")
    return manifest


def r03_drop_uninformative_columns(df):
    """U3: drop only columns with no information (empty, constant, exact copies, fully derivable)."""
    n = len(df)
    evidence = {}
    for c in ["neighborhood_overview", "host_since", "host_response_time", "host_response_rate",
              "host_acceptance_rate", "host_thumbnail_url", "host_neighbourhood", "host_total_listings_count",
              "neighbourhood", "calendar_updated", "instant_bookable"]:
        assert blank(df[c]).all(), c
        evidence[c] = "100% empty in both snapshots"
    assert (df["host_verifications"] == "None").all()
    evidence["host_verifications"] = "constant string 'None' on every row"
    assert (df["minimum_minimum_nights"] == df["minimum_nights"]).all()
    evidence["minimum_minimum_nights"] = "identical to minimum_nights on every row"
    assert (df["maximum_maximum_nights"] == df["maximum_nights"]).all()
    evidence["maximum_maximum_nights"] = "identical to maximum_nights on every row"
    assert (df["listing_url"] == "https://www.airbnb.com/rooms/" + df["id"]).all()
    evidence["listing_url"] = "always 'https://www.airbnb.com/rooms/' + id"
    assert (df["host_url"] == "https://www.airbnb.com/users/show/" + df["host_id"]).all()
    evidence["host_url"] = "always 'https://www.airbnb.com/users/show/' + host_id"
    for c, why in evidence.items():
        log("R03", c, 0, n, n, f"column dropped: {why}")
    pd.DataFrame({"column": list(evidence), "evidence": list(evidence.values())}).to_csv(
        OUT_DIR / "dropped_columns.csv", index=False)
    return df.drop(columns=list(evidence))


# --------------------------------------------------------------------------- types / text
ID_COLS = ["id", "host_id", "host_profile_id", "scrape_id"]
BOOL_COLS = ["host_is_superhost", "host_has_profile_pic", "host_identity_verified", "has_availability"]
DATE_COLS = ["last_scraped", "calendar_last_scraped", "first_review", "last_review",
             "price_quote_checkin_date", "price_quote_checkout_date"]
NUM_COLS = ["hosts_time_as_user_years", "hosts_time_as_user_months", "hosts_time_as_host_years",
            "hosts_time_as_host_months", "host_listings_count", "latitude", "longitude", "accommodates",
            "bathrooms", "bedrooms", "beds", "price_quote_total_price", "price_quote_price_per_night",
            "minimum_nights", "maximum_nights", "maximum_minimum_nights", "minimum_maximum_nights",
            "minimum_nights_avg_ntm", "maximum_nights_avg_ntm", "availability_30", "availability_60",
            "availability_90", "availability_365", "availability_eoy", "number_of_reviews",
            "number_of_reviews_ltm", "number_of_reviews_l30d", "number_of_reviews_ly",
            "estimated_occupancy_l365d", "estimated_revenue_l365d", "review_scores_rating",
            "review_scores_accuracy", "review_scores_cleanliness", "review_scores_checkin",
            "review_scores_communication", "review_scores_location", "review_scores_value",
            "calculated_host_listings_count", "calculated_host_listings_count_entire_homes",
            "calculated_host_listings_count_private_rooms", "calculated_host_listings_count_shared_rooms",
            "reviews_per_month"]


def r04_convert_types(df):
    """U4/U5: blanks -> NA; IDs stay text; price/numbers/booleans/dates converted with failures counted."""
    n = len(df)
    df = df.copy()
    examples = []

    for c in df.columns:
        if c == "snapshot":
            continue
        b = df[c] == ""
        df[c] = df[c].astype("string").mask(b)
        if b.any():
            log("R04", c, b.sum(), n, n, "blank string -> NA (missing kept as missing)")

    for c in ID_COLS:
        assert df[c].dropna().str.fullmatch(r"\d+").all(), c
        log("R04", c, 0, n, n, "kept as string (ids > 2^53 would lose precision as float)")

    raw_price = df["price"]
    df["price_usd"] = pd.to_numeric(raw_price.str.replace(r"[$,]", "", regex=True), errors="coerce")
    failed = df["price_usd"].isna() & raw_price.notna()
    log("R04", "price_usd", raw_price.notna().sum(), n, n,
        f"'$1,234.00' -> float; conversion failures={failed.sum()}; nulls kept={raw_price.isna().sum()}")
    examples += [{"column": "price", "before": b, "after": a}
                 for b, a in zip(raw_price.dropna().head(5), df["price_usd"].dropna().head(5))]

    for c in NUM_COLS:
        before = df[c]
        conv = pd.to_numeric(before, errors="coerce")
        failed = conv.isna() & before.notna()
        if conv.dropna().eq(conv.dropna().round()).all():
            conv = conv.astype("Int64")
        df[c] = conv
        log("R04", c, before.notna().sum(), n, n, f"text -> {conv.dtype}; conversion failures={failed.sum()}")

    for c in BOOL_COLS:
        before = df[c]
        bad = before.notna() & ~before.isin(["t", "f"])
        df[c] = before.map({"t": True, "f": False}).astype("boolean")
        log("R04", c, before.notna().sum(), n, n, f"'t'/'f' -> boolean, NA kept; unexpected values={bad.sum()}")
        examples += [{"column": c, "before": b, "after": a} for b, a in zip(before.head(3), df[c].head(3))]

    for c in DATE_COLS:
        before = df[c]
        df[c] = pd.to_datetime(before, format="%Y-%m-%d", errors="coerce")
        failed = df[c].isna() & before.notna()
        log("R04", c, before.notna().sum(), n, n, f"ISO text -> datetime; parse failures={failed.sum()}")

    pd.DataFrame(examples).to_csv(OUT_DIR / "r04_type_examples.csv", index=False)
    return df


def r04a_property_segment(df):
    """[Q] property_segment = room_type x stay_type (price is a monthly per-night quote when min stay >= 30)."""
    n = len(df)
    df = df.copy()
    mn = df["minimum_nights"]
    short = (mn < MONTHLY_MIN_NIGHTS).fillna(False).to_numpy(bool)
    df["stay_type"] = np.select([mn.isna().to_numpy(), short], ["Unknown", "Short-stay (<30n)"],
                                default="Monthly (30+n)")
    df["property_segment"] = df["room_type"] + " | " + df["stay_type"]
    df["segment"] = df["neighbourhood_cleansed"] + " || " + df["property_segment"]
    for v, cnt in df["stay_type"].value_counts().items():
        log("R04a", "stay_type", cnt, n, n, f"stay_type={v}")
    log("R04a", "property_segment", n, n, n,
        f"{df['property_segment'].nunique()} property segments; {df.groupby('snapshot')['segment'].nunique().to_dict()} "
        "neighbourhood x property segments per snapshot")
    return df


# zero-width joiners (u200c/u200d) are kept: they bind emoji sequences together
CTRL = re.compile(r"[\x00-\x1f\x7f\u200b\u200e\u200f\u2028\u2029\ufeff]")


def r05_standardize_text(df):
    """U6: clean whitespace/control chars in listing name; label columns verified already clean."""
    n = len(df)
    df = df.copy()
    for c in ["neighbourhood_cleansed", "neighbourhood_group_cleansed", "room_type", "property_type"]:
        s = df[c]
        issues = ((s != s.str.strip()) | s.str.contains("  ", regex=False) | s.str.contains(CTRL)).sum()
        case_variants = s.nunique() - s.str.lower().str.strip().nunique()
        log("R05", c, 0, n, n, f"check passed: whitespace/control issues={issues}, case-variant labels={case_variants}")
    before = df["name"]
    after = (before.str.replace(CTRL, " ", regex=True).str.replace(r"\s+", " ", regex=True).str.strip())
    changed = before.notna() & (before != after)
    df["name"] = after
    log("R05", "name", changed.sum(), n, n, "removed control chars, collapsed repeated spaces, stripped ends")
    ex = pd.DataFrame({"id": df.loc[changed, "id"], "before": before[changed].map(repr),
                       "after": after[changed].map(repr)})
    # show one example of each kind of fix
    kinds = [before[changed].str.contains(CTRL), before[changed] != before[changed].str.strip(),
             before[changed].str.contains("  ", regex=False)]
    picks = pd.concat([ex[k].head(2) for k in kinds]).drop_duplicates().head(5)
    picks.to_csv(OUT_DIR / "r05_text_examples.csv", index=False)
    return df


def r06_units_and_formats(df):
    """U7: one currency, one date format; document snapshot-dependent coding of size fields."""
    n = len(df)
    cur = df["price_quote_raw"].str.extract(r'"currency": "?([A-Z]{3}|null)"?')[0]
    non_usd = cur.notna() & ~cur.isin(["USD", "null"])
    log("R06", "price_quote_raw.currency", non_usd.sum(), n, n,
        f"currency values: {cur.value_counts(dropna=False).to_dict()}; non-USD={non_usd.sum()}")
    has_price = df["price_usd"].notna()
    nights = (df["price_quote_checkout_date"] - df["price_quote_checkin_date"]).dt.days
    per_night_ok = ((df["price_quote_total_price"] / nights - df["price_usd"]).abs() <= 0.02)[has_price & nights.gt(0)]
    log("R06", "price_usd", (~per_night_ok).sum(), n, n,
        f"price = quote total / quote nights on {per_night_ok.mean():.4%} of priced rows (unit = USD per night)")
    for c in ["bedrooms", "beds", "bathrooms"]:
        z = df[c].eq(0).groupby(df["snapshot"]).sum().to_dict()
        na = df[c].isna().groupby(df["snapshot"]).sum().to_dict()
        log("R06", c, 0, n, n, f"zeros by snapshot={z}, nulls by snapshot={na}: 0-vs-null coding changed "
            "between snapshots; not recoded, excluded from segment keys")
    return df


# --------------------------------------------------------------------------- duplicates / missing
NEAR_DUP_COLS = ["host_id", "name", "neighbourhood_cleansed", "property_type", "accommodates", "bedrooms",
                 "price_usd", "latitude", "longitude"]


def r07_duplicates(df):
    """U8: remove exact duplicates (none expected), flag near duplicates within a snapshot."""
    n = len(df)
    exact = df.duplicated()
    df = df[~exact].copy()
    log("R07", "*", exact.sum(), n, len(df), "exact duplicate rows removed (keep first)")
    rep = df.duplicated(KEY).sum()
    log("R07", "snapshot,id", rep, len(df), len(df), f"repeated keys with differing values={rep}")
    df["near_dup_flag"] = df.duplicated(["snapshot"] + NEAR_DUP_COLS, keep=False)
    log("R07", "near_dup_flag", df["near_dup_flag"].sum(), len(df), len(df),
        "same host/name/neighbourhood/type/size/price/coords, different id: flagged, kept")
    return df


def r08_price_missing(df):
    """[Q] U9/U11: missing price is not random; keep null, flag, report coverage and compare groups."""
    n = len(df)
    df = df.copy()
    df["price_missing"] = df["price_usd"].isna()
    for snap, g in df.groupby("snapshot"):
        log("R08", "price_missing", g["price_missing"].sum(), n, n,
            f"{snap}: {g['price_missing'].mean():.1%} missing; by source="
            f"{g.groupby('source')['price_missing'].mean().round(3).to_dict()}")
    cov = (df.groupby(["snapshot", "neighbourhood_cleansed", "property_segment"])
             .agg(listings=("id", "size"), priced=("price_missing", lambda s: (~s).sum()))
             .reset_index())
    cov["price_coverage_pct"] = (cov["priced"] / cov["listings"] * 100).round(1)
    cov.to_csv(OUT_DIR / "price_coverage_by_segment.csv", index=False)
    cmp_cols = ["availability_30", "estimated_occupancy_l365d", "number_of_reviews_ltm", "number_of_reviews"]
    comp = (df.groupby(["snapshot", "price_missing"])
              .agg(rows=("id", "size"), share_previous_scrape=("source", lambda s: (s == "previous scrape").mean()),
                   **{f"median_{c}": (c, "median") for c in cmp_cols},
                   share_has_availability_true=("has_availability", lambda s: s.eq(True).mean()))
              .reset_index())
    comp.to_csv(OUT_DIR / "price_missing_comparison.csv", index=False)
    return df


REVIEW_FIELDS = ["review_scores_rating", "first_review", "last_review", "reviews_per_month"]


def r09_structural_missing(df):
    """U9 structural: no reviews -> no scores/dates; no price -> no revenue estimate. Keep null, flag."""
    n = len(df)
    df = df.copy()
    df["no_reviews"] = df["number_of_reviews"].eq(0)
    for c in REVIEW_FIELDS:
        mismatch = (df[c].isna() != df["no_reviews"]).sum()
        assert mismatch == 0, (c, mismatch)
    log("R09", "no_reviews", df["no_reviews"].sum(), n, n,
        f"{', '.join(REVIEW_FIELDS)} null iff number_of_reviews==0 (0 exceptions); kept null")
    sub = [c for c in df.columns if c.startswith("review_scores_") and c != "review_scores_rating"]
    extra = (df[sub].isna().any(axis=1) & ~df["no_reviews"]).sum()
    log("R09", "review_scores_* subscores", extra, n, n, "subscore missing although reviews exist: kept null")
    mismatch = (df["estimated_revenue_l365d"].isna() != df["price_missing"]).sum()
    assert mismatch == 0
    log("R09", "estimated_revenue_l365d", df["estimated_revenue_l365d"].isna().sum(), n, n,
        "null iff price null (revenue = occupancy x price); kept null")
    return df


def r10_other_missing(df):
    """U9/U10: host profile gaps, has_availability gaps, unknown stay type: keep NA, flag, count."""
    n = len(df)
    df = df.copy()
    df["host_profile_missing"] = df["hosts_time_as_user_years"].isna()
    log("R10", "host_profile_missing", df["host_profile_missing"].sum(), n, n,
        "host profile fields empty; kept null")
    log("R10", "has_availability", df["has_availability"].isna().sum(), n, n, "blank kept as NA (not False)")
    log("R10", "minimum_nights", df["minimum_nights"].isna().sum(), n, n,
        "null min stay -> stay_type 'Unknown' (separate group, not ranked)")
    for c in ["neighbourhood_cleansed", "room_type"]:
        log("R10", c, df[c].isna().sum(), n, n, "missing group key count")
    return df


# --------------------------------------------------------------------------- suspicious values
def r11_sentinels(df):
    """U13: placeholder values -> NA + flag; placeholder licence text flagged only."""
    n = len(df)
    df = df.copy()
    nights_cols = ["maximum_nights", "minimum_maximum_nights", "maximum_nights_avg_ntm"]
    df["max_nights_sentinel"] = df[nights_cols].eq(INT_SENTINEL).any(axis=1)
    for c in nights_cols:
        hit = df[c].eq(INT_SENTINEL)
        df[c] = df[c].mask(hit)
        log("R11", c, hit.sum(), n, n, f"{INT_SENTINEL} -> NA")
    score_cols = [c for c in df.columns if c.startswith("review_scores_")]
    df["review_score_zero"] = df[score_cols].eq(0).any(axis=1)
    for c in score_cols:
        hit = df[c].eq(0)
        df[c] = df[c].mask(hit)
        if hit.any():
            log("R11", c, hit.sum(), n, n, "0.0 is impossible on a 1-5 scale -> NA")
    hit = df["host_listings_count"].eq(0)
    df["host_listings_count_zero"] = hit
    df["host_listings_count"] = df["host_listings_count"].mask(hit)
    log("R11", "host_listings_count", hit.sum(), n, n, "0 impossible for a host with a live listing -> NA")
    lic = df["license"].str.strip().str.upper()
    df["license_placeholder"] = lic.str.fullmatch(r"(HSR\d{2}-)?(0{6}|123456)|N/?A").fillna(False).astype(bool)
    log("R11", "license_placeholder", df["license_placeholder"].sum(), n, n, "placeholder licence text flagged; raw kept")
    return df


def r12_range_checks(df):
    """U12: check every key numeric column against its possible range; flag censored/odd values."""
    n = len(df)
    df = df.copy()
    checks = {
        "latitude in LA County box [33.3, 34.9]": df["latitude"].between(33.3, 34.9),
        "longitude in LA County box [-119.0, -117.6]": df["longitude"].between(-119.0, -117.6),
        "accommodates >= 1": df["accommodates"].ge(1),
        "price_usd > 0 (where present)": df["price_usd"].gt(0) | df["price_usd"].isna(),
        "availability_30 in [0,30]": df["availability_30"].between(0, 30),
        "availability_365 in [0,365]": df["availability_365"].between(0, 365),
        "estimated_occupancy_l365d in [0,365]": df["estimated_occupancy_l365d"].between(0, 365),
        "number_of_reviews >= 0": df["number_of_reviews"].ge(0),
        "minimum_nights >= 1 (where present)": df["minimum_nights"].ge(1).fillna(True),
        "review_scores_rating in [1,5] (where present)": df["review_scores_rating"].between(1, 5).fillna(True),
    }
    for name, ok in checks.items():
        log("R12", name.split(" ")[0], (~ok.astype(bool)).sum(), n, n, f"range check: {name}; failures shown")
    df["occupancy_at_cap"] = df["estimated_occupancy_l365d"].eq(OCCUPANCY_CAP)
    log("R12", "occupancy_at_cap", df["occupancy_at_cap"].sum(), n, n,
        f"estimated_occupancy_l365d == {OCCUPANCY_CAP} (model cap: censored, true value may be higher)")
    df["bedrooms_gt_accommodates"] = (df["bedrooms"] > df["accommodates"]).fillna(False).astype(bool)
    log("R12", "bedrooms_gt_accommodates", df["bedrooms_gt_accommodates"].sum(), n, n, "possible but odd: flagged")
    return df


def r13_price_outliers(df):
    """[Q] U14: flag log-price outliers (IQR, k=3) within property_segment x snapshot; keep rows."""
    n = len(df)
    df = df.copy()
    lp = np.log(df["price_usd"].astype(float))
    grp = [df["snapshot"], df["property_segment"]]
    q1 = lp.groupby(grp).transform(lambda s: s.quantile(0.25))
    q3 = lp.groupby(grp).transform(lambda s: s.quantile(0.75))
    iqr = q3 - q1
    low, high = lp < q1 - OUTLIER_K * iqr, lp > q3 + OUTLIER_K * iqr
    df["price_outlier"] = (low | high).fillna(False).astype(bool)
    df["price_outlier_side"] = np.select([low, high], ["low", "high"], default="")
    df["price_outlier_side"] = df["price_outlier_side"].replace("", pd.NA)
    df["price_fence_low_usd"] = np.exp(q1 - OUTLIER_K * iqr).round(2)
    df["price_fence_high_usd"] = np.exp(q3 + OUTLIER_K * iqr).round(2)
    log("R13", "price_outlier", df["price_outlier"].sum(), n, n,
        f"log-price IQR k={OUTLIER_K} within snapshot x property_segment; low={low.sum()}, high={high.sum()}")
    df[df["price_outlier"]].sort_values("price_usd")[
        ["snapshot", "id", "property_type", "property_segment", "accommodates", "minimum_nights", "price_usd",
         "price_fence_low_usd", "price_fence_high_usd", "number_of_reviews_ltm"]
    ].to_csv(OUT_DIR / "r13_outlier_examples.csv", index=False)
    return df


def r14_logic_checks(df):
    """U15: cross-column logic; passes are reported as evidence."""
    n = len(df)
    nights = (df["price_quote_checkout_date"] - df["price_quote_checkin_date"]).dt.days
    parts = (df["calculated_host_listings_count_entire_homes"] + df["calculated_host_listings_count_private_rooms"]
             + df["calculated_host_listings_count_shared_rooms"])
    checks = {
        "number_of_reviews_ltm <= number_of_reviews": df["number_of_reviews_ltm"] <= df["number_of_reviews"],
        "number_of_reviews_l30d <= number_of_reviews_ltm": df["number_of_reviews_l30d"] <= df["number_of_reviews_ltm"],
        "number_of_reviews_ly <= number_of_reviews": df["number_of_reviews_ly"] <= df["number_of_reviews"],
        "first_review <= last_review": (df["first_review"] <= df["last_review"]) | df["first_review"].isna(),
        "last_review <= last_scraped": (df["last_review"] <= df["last_scraped"]) | df["last_review"].isna(),
        "availability_30 <= 60 <= 90 <= 365": (df["availability_30"] <= df["availability_60"])
            & (df["availability_60"] <= df["availability_90"]) & (df["availability_90"] <= df["availability_365"]),
        "minimum_nights <= maximum_nights": (df["minimum_nights"] <= df["maximum_nights"]).fillna(True),
        "price_usd == price_quote_price_per_night": ((df["price_usd"] - df["price_quote_price_per_night"]).abs() <= 0.01)
            .fillna(df["price_usd"].isna() | df["price_quote_price_per_night"].isna()),
        "quote nights >= minimum_nights": (nights >= df["minimum_nights"]).fillna(True),
        "estimated_revenue == occupancy x price (+-$1)":
            ((df["estimated_revenue_l365d"] - df["estimated_occupancy_l365d"] * df["price_usd"]).abs() <= 1).fillna(True),
        "occupancy > 0 implies reviews_ltm > 0": ~(df["estimated_occupancy_l365d"].gt(0) & df["number_of_reviews_ltm"].eq(0)),
        "calculated_host_listings_count == entire+private+shared": df["calculated_host_listings_count"] == parts,
    }
    rows = []
    for name, ok in checks.items():
        ok = ok.astype(bool)
        fail = (~ok).sum()
        note = ""
        if name.startswith("calculated_host") and fail:
            rt = df.loc[~ok, "room_type"].value_counts().to_dict()
            note = f"explained: hosts with hotel rooms (no hotel bucket); failing rows by room_type={rt}"
        rows.append({"check": name, "rows_checked": n, "passes": int(ok.sum()), "failures": int(fail), "note": note})
        log("R14", name.split(" ")[0], fail, n, n, f"logic: {name}; failures={fail}. {note}")
    pd.DataFrame(rows).to_csv(OUT_DIR / "logic_checks.csv", index=False)
    return df


def r15_date_checks(df):
    """U16: all dates parse and fall inside the expected window; record snapshot dates."""
    n = len(df)
    for c in DATE_COLS:
        s = df[c]
        late = (s > df["last_scraped"] + pd.Timedelta(days=400)) if c.startswith("price_quote") else (s > df["last_scraped"])
        early = s < pd.Timestamp("2008-08-01")  # Airbnb founded Aug 2008
        log("R15", c, (late | early).sum(), n, n,
            f"range {s.min().date() if s.notna().any() else None} to {s.max().date() if s.notna().any() else None}; "
            f"out-of-window={int((late | early).sum())}")
    for snap, g in df.groupby("snapshot"):
        log("R15", "last_scraped", 0, n, n,
            f"{snap} snapshot dates {g['last_scraped'].min().date()} to {g['last_scraped'].max().date()}: "
            "availability/occupancy describe this moment only")
    return df


def r16_merge_check(df):
    """U17: no join performed (snapshots stacked). Report the would-be 1:1 id match for reference."""
    n = len(df)
    ids = {s: set(g["id"]) for s, g in df.groupby("snapshot")}
    a, b = ids["2026-03"], ids["2026-06"]
    log("R16", "id", 0, n, n,
        f"Not applicable: no merge, snapshots are stacked. id overlap: both={len(a & b)}, "
        f"Mar only={len(a - b)}, Jun only={len(b - a)}; id unique within each snapshot")
    return df


def r17_small_groups(df):
    """[Q] U23: rank only segments with >= MIN_GROUP_N priced listings; report the rest separately."""
    n = len(df)
    df = df.copy()
    priced = df[~df["price_missing"]]
    seg_n = priced.groupby(["snapshot", "segment"]).size().rename("segment_n_priced")
    df = df.merge(seg_n, left_on=["snapshot", "segment"], right_index=True, how="left", validate="m:1")
    df["segment_n_priced"] = df["segment_n_priced"].fillna(0).astype(int)
    df["segment_rankable"] = (df["segment_n_priced"] >= MIN_GROUP_N) & (df["stay_type"] != "Unknown")
    assert len(df) == n
    sizes = (df.groupby(["snapshot", "neighbourhood_cleansed", "property_segment"])
               .agg(listings=("id", "size"), priced=("price_missing", lambda s: (~s).sum()),
                    segment_rankable=("segment_rankable", "first"))
               .reset_index())
    sizes.to_csv(OUT_DIR / "segment_sizes.csv", index=False)
    sizes[~sizes["segment_rankable"]].to_csv(OUT_DIR / "small_segments.csv", index=False)
    for snap, g in sizes.groupby("snapshot"):
        r = g[g["segment_rankable"]]
        log("R17", "segment_rankable", df.loc[df["snapshot"].eq(snap) & df["segment_rankable"]].shape[0], n, n,
            f"{snap}: {len(r)} of {len(g)} segments have >= {MIN_GROUP_N} priced listings "
            f"({r['priced'].sum()} of {g['priced'].sum()} priced listings); smaller ones in small_segments.csv")
    return df


# --------------------------------------------------------------------------- verification
def outlier_sensitivity(df):
    """U14: segment medians with vs without flagged outliers (rankable segments)."""
    p = df[~df["price_missing"] & df["segment_rankable"]]
    keys = ["snapshot", "neighbourhood_cleansed", "property_segment"]
    allm = p.groupby(keys)["price_usd"].agg(n_all="size", median_all="median",
                                           iqr_all=lambda s: s.quantile(.75) - s.quantile(.25))
    trim = p[~p["price_outlier"]].groupby(keys)["price_usd"].agg(
        n_excl="size", median_excl="median", iqr_excl=lambda s: s.quantile(.75) - s.quantile(.25))
    out = allm.join(trim, how="left").reset_index()
    out["median_change_pct"] = ((out["median_excl"] / out["median_all"] - 1) * 100).round(2)
    out["iqr_change_pct"] = ((out["iqr_excl"] / out["iqr_all"] - 1) * 100).round(2)
    out.to_csv(OUT_DIR / "outlier_sensitivity.csv", index=False)
    return out


def reconciliation(df, start_rows):
    rows = []
    for snap in ["2026-03", "2026-06", "all"]:
        g = df if snap == "all" else df[df["snapshot"] == snap]
        steps = [("1 all listings (raw)", start_rows[snap], ""),
                 ("2 after cleaning (no rows removed)", len(g), "R07 exact duplicates (0)"),
                 ("3 with a price", (~g["price_missing"]).sum(), "R08 price missing"),
                 ("4 known stay type", (~g["price_missing"] & g["stay_type"].ne("Unknown")).sum(), "R04a min stay unknown"),
                 ("5 in rankable segment (n>=20)", (~g["price_missing"] & g["segment_rankable"]).sum(),
                  f"R17 segment < {MIN_GROUP_N} priced listings"),
                 ("(info) of which price_outlier", (~g["price_missing"] & g["segment_rankable"] & g["price_outlier"]).sum(),
                  "R13 kept in main run; sensitivity in outlier_sensitivity.csv")]
        prev = None
        for step, cnt, reason in steps:
            lost = "" if prev is None or step.startswith("(info)") else prev - int(cnt)
            rows.append({"snapshot": snap, "step": step, "rows": int(cnt), "rows_lost": lost, "reason": reason})
            if not step.startswith("(info)"):
                prev = int(cnt)
    rec = pd.DataFrame(rows)
    rec.to_csv(OUT_DIR / "reconciliation.csv", index=False)
    by_rule = (pd.DataFrame(LOG).assign(diff=lambda d: d["rows_before"] - d["rows_after"])
               .groupby("rule", sort=False)["diff"].sum().rename("rows_removed").reset_index())
    by_rule.to_csv(OUT_DIR / "reconciliation_by_rule.csv", index=False)
    return rec, by_rule


# Expected results written BEFORE looking at the cleaned output (U19).
RECORD_CHECKS = [
    {"case": "impossible zero rating", "snapshot": "2026-03", "id": "6764023",
     "expected": "review_scores_rating NA, review_score_zero True, no_reviews False",
     "reason": "1 review with a 0.0 rating is impossible on a 1-5 scale -> sentinel"},
    {"case": "max-nights sentinel", "snapshot": "2026-06", "id": "44503357",
     "expected": "maximum_nights NA, max_nights_sentinel True",
     "reason": "2147483647 is the int32 max used as 'no limit'"},
    {"case": "high price outlier", "snapshot": "2026-03", "id": "53064422",
     "expected": "price_usd 11412.0, price_outlier True (high)",
     "reason": "$11,412/night for a 1-guest tiny home is far above the Entire|Short-stay fence"},
    {"case": "very low monthly price", "snapshot": "2026-03", "id": "1127572",
     "expected": "stay_type Monthly, price_usd 8.47, price_outlier False",
     "reason": "300-night min stay: monthly-rate segment has a wide log-IQR, k=3 low fence is ~$5"},
    {"case": "long id type conversion", "snapshot": "2026-03", "id": "1452068118494812958",
     "expected": "id string '1452068118494812958' unchanged",
     "reason": "19-digit id > 2^53 would be corrupted as float; kept as text"},
    {"case": "missing price (previous scrape)", "snapshot": "2026-03", "id": None,
     "expected": "price_usd NA, price_missing True, estimated_revenue NA, price_outlier False",
     "reason": "first previous-scrape row without a price: missing kept as missing, not filled"},
]


def five_record_check(df, raw):
    rows = []
    for chk in RECORD_CHECKS:
        snap, rid = chk["snapshot"], chk["id"]
        r0 = raw[snap]
        if rid is None:
            used = {c["id"] for c in RECORD_CHECKS}
            pool = r0.loc[(r0["source"] == "previous scrape") & (r0["price"] == "") & ~r0["id"].isin(used), "id"]
            rid = pool.iloc[0]
        orig = r0.loc[r0["id"] == rid].iloc[0]
        new = df.loc[(df["snapshot"] == snap) & (df["id"] == rid)].iloc[0]
        case = chk["case"]
        if case == "impossible zero rating":
            ok = pd.isna(new["review_scores_rating"]) and new["review_score_zero"] and not new["no_reviews"]
            o, a = f"rating={orig['review_scores_rating']}", f"rating={new['review_scores_rating']}, flag={new['review_score_zero']}"
        elif case == "max-nights sentinel":
            ok = pd.isna(new["maximum_nights"]) and new["max_nights_sentinel"]
            o, a = f"maximum_nights={orig['maximum_nights']}", f"maximum_nights={new['maximum_nights']}, flag={new['max_nights_sentinel']}"
        elif case == "high price outlier":
            ok = new["price_usd"] == 11412.0 and new["price_outlier"] and new["price_outlier_side"] == "high"
            o, a = f"price={orig['price']}", f"price_usd={new['price_usd']}, outlier={new['price_outlier']} ({new['price_outlier_side']}), high fence={new['price_fence_high_usd']}"
        elif case == "very low monthly price":
            ok = new["stay_type"] == "Monthly (30+n)" and new["price_usd"] == 8.47 and not new["price_outlier"]
            o, a = f"price={orig['price']}, min_nights={orig['minimum_nights']}", f"stay={new['stay_type']}, price_usd={new['price_usd']}, outlier={new['price_outlier']}, low fence={new['price_fence_low_usd']}"
        elif case == "long id type conversion":
            ok = new["id"] == rid and str(new["id"]) == orig["id"]
            o, a = f"id text={orig['id']} (as float: {float(orig['id']):.0f})", f"id={new['id']} dtype={df['id'].dtype}"
        else:
            ok = pd.isna(new["price_usd"]) and new["price_missing"] and pd.isna(new["estimated_revenue_l365d"]) and not new["price_outlier"]
            o, a = f"id={rid} price='{orig['price']}' revenue='{orig['estimated_revenue_l365d']}'", f"price_usd={new['price_usd']}, price_missing={new['price_missing']}, revenue={new['estimated_revenue_l365d']}"
        rows.append({**chk, "id": rid, "original": o, "actual": a, "match": "match" if ok else "NO MATCH"})
    out = pd.DataFrame(rows)
    out.to_csv(OUT_DIR / "record_checks.csv", index=False)
    return out


def missing_summary(raw_stacked, df):
    n = len(df)
    rows = []
    for c in df.columns:
        before = int(blank(raw_stacked[c]).sum()) if c in raw_stacked else None
        after = int(df[c].isna().sum())
        rows.append({"column": c, "null_before": before,
                     "null_before_pct": None if before is None else round(before / n * 100, 2),
                     "null_after": after, "null_after_pct": round(after / n * 100, 2)})
    pd.DataFrame(rows).to_csv(OUT_DIR / "missing_summary.csv", index=False)


# --------------------------------------------------------------------------- main
def main():
    CLEAN_DIR.mkdir(parents=True, exist_ok=True)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    raw = {s: pd.read_csv(RAW_DIR / f, dtype=str, keep_default_na=False) for s, f in RAW_FILES.items()}
    start_rows = {s: len(d) for s, d in raw.items()}
    start_rows["all"] = sum(start_rows.values())

    r02_provenance(raw)
    df = r01_stack_and_key(raw)
    raw_stacked = df.copy()
    df = r03_drop_uninformative_columns(df)
    df = r04_convert_types(df)
    df = r04a_property_segment(df)
    df = r05_standardize_text(df)
    df = r06_units_and_formats(df)
    df = r07_duplicates(df)
    df = r08_price_missing(df)
    df = r09_structural_missing(df)
    df = r10_other_missing(df)
    df = r11_sentinels(df)
    df = r12_range_checks(df)
    df = r13_price_outliers(df)
    df = r14_logic_checks(df)
    df = r15_date_checks(df)
    df = r16_merge_check(df)
    df = r17_small_groups(df)

    df = df.sort_values(KEY, kind="stable").reset_index(drop=True)
    assert df.duplicated(KEY).sum() == 0
    # QUOTE_ALL: some host_about values contain a bare '\r', which QUOTE_MINIMAL leaves unquoted
    df.to_csv(CLEAN_FILE, index=False, quoting=csv.QUOTE_ALL, compression={"method": "gzip", "mtime": 0})
    back = pd.read_csv(CLEAN_FILE, dtype=str, keep_default_na=False)
    assert back.shape == df.shape and back["snapshot"].isin(RAW_FILES).all(), f"round-trip failed: {back.shape}"
    assert back["id"].tolist() == df["id"].tolist(), "ids changed on round-trip"
    pd.DataFrame({"column": df.columns, "dtype": df.dtypes.astype(str)}).to_csv(OUT_DIR / "clean_schema.csv", index=False)

    missing_summary(raw_stacked, df)
    sens = outlier_sensitivity(df)
    rec, by_rule = reconciliation(df, start_rows)
    checks = five_record_check(df, raw)
    pd.DataFrame(LOG).to_csv(OUT_DIR / "cleaning_log.csv", index=False)

    hashes = {p.relative_to(ROOT).as_posix(): sha256(p) for p in [CLEAN_FILE]}
    pd.Series(hashes).rename_axis("file").rename("sha256").to_csv(OUT_DIR / "output_hashes.csv")

    print(f"clean file: {CLEAN_FILE.relative_to(ROOT)}  shape={df.shape}  sha256={hashes[CLEAN_FILE.relative_to(ROOT).as_posix()]}")
    print("\nReconciliation funnel:\n", rec.to_string(index=False))
    print("\nRows removed by rule:\n", by_rule.to_string(index=False))
    print("\nOutlier sensitivity (rankable segments): median change >5% in",
          int((sens["median_change_pct"].abs() > 5).sum()), "of", len(sens), "segments; max |change|",
          sens["median_change_pct"].abs().max(), "%")
    print("\nFive-record check:\n", checks[["case", "id", "match"]].to_string(index=False))


if __name__ == "__main__":
    main()
