"""Outer-joined repeated cross-sections and transparent review ranking."""
import numpy as np
import pandas as pd
from .config import DATES, BEDROOM_ORDER, validate_thresholds
from .filters import optional_filters
from .pricing import KEYS, snapshot_summary

STATUS = ["Persistent premium", "Persistent discount", "Reversed", "Neutral"]

def persistence(march, june):
    if pd.isna(march) or pd.isna(june):
        return "Insufficient evidence"
    if march > 0 and june > 0:
        return STATUS[0]
    if march < 0 and june < 0:
        return STATUS[1]
    if march * june < 0:
        return STATUS[2]
    return STATUS[3]

def row_warnings(row, coverage_warning=.8):
    warnings = []
    for period, label in [("march", "March"), ("june", "June")]:
        if pd.isna(row.get(f"listing_rows_{period}")):
            warnings.append(f"{label}: segment absent; evidence unavailable.")
            continue
        for prefix, population in [("", "local"), ("peer_", "peer")]:
            coverage = row.get(f"{prefix}price_coverage_{period}")
            if pd.notna(coverage) and coverage < coverage_warning:
                warnings.append(f"{label} {population} price coverage {coverage:.1%} is below the {coverage_warning:.0%} warning threshold.")
            if row.get(f"{prefix}is_small_sample_{period}") == True:
                warnings.append(f"{label} {population}: small sample (<20 priced listings).")
        if row.get(f"sufficient_data_{period}") != True:
            warnings.append(f"{label}: premium fails current minimum evidence requirement.")
        for population in ["local", "peer"]:
            share = row.get(f"{population}_unknown_bedroom_share_{period}")
            if pd.notna(share) and share >= .25:
                warnings.append(f"{label} {population}: bedroom completeness warning; {share:.1%} unknown bedrooms excluded.")
        previous = row.get(f"previous_scrape_share_{period}")
        peer_previous = row.get(f"peer_previous_scrape_share_{period}")
        if (pd.notna(previous) and previous > 0) or (pd.notna(peer_previous) and peer_previous > 0):
            warnings.append(f"{label} source caution: previous-scrape share local {previous:.1%}, peer {peer_previous:.1%}; nominal dates may differ from scrape dates.")
        if row.get(f"unknown_source_share_{period}", 0) > 0 or row.get(f"peer_unknown_source_share_{period}", 0) > 0:
            warnings.append(f"{label}: source category is unavailable for some listings.")
    for population in ["local", "peer"]:
        m, j = (row.get(f"{population}_unknown_bedroom_share_{d}") for d in ["march", "june"])
        if pd.notna(m) and pd.notna(j) and j - m >= .10:
            warnings.append(f"{population.title()} bedroom completeness deteriorated by {(j-m)*100:.1f} percentage points; composition may distort comparison.")
    if row.get("bedroom_segment") == "Studio":
        warnings.append("Studio coding warning: recorded zeros and missing bedrooms change sharply between snapshots; do not interpret this as supply change.")
    return " | ".join(warnings) or "No row-specific quality warning at current settings."

def comparison(frame, stay=None, source=None, min_priced=20, coverage_warning=.8):
    validate_thresholds(min_priced, coverage_warning)
    stats = snapshot_summary(optional_filters(frame, stay, source), min_priced)
    tables = [stats.loc[stats.snapshot_date.eq(date)].drop(columns="snapshot_date").rename(columns=lambda c: c if c in KEYS else f"{c}_{label}") for date, label in zip(DATES, ["march", "june"])]
    result = tables[0].merge(tables[1], on=KEYS, how="outer", validate="one_to_one")
    result["change_usd"] = result.median_price_usd_june - result.median_price_usd_march
    result["change_pct"] = (100 * result.change_usd / result.median_price_usd_march).where(result.median_price_usd_march.gt(0))
    result["persistence_status"] = [persistence(m, j) for m,j in zip(result.premium_pct_march, result.premium_pct_june)]
    persistent = result.persistence_status.isin(STATUS[:2])
    result["direction"] = result.persistence_status.map({STATUS[0]: "Premium", STATUS[1]: "Discount"}).fillna("Unavailable")
    result["review_score"] = np.minimum(result.premium_pct_march.abs(), result.premium_pct_june.abs()).where(persistent)
    result["snapshot_march"] = DATES[0]
    result["snapshot_june"] = DATES[1]
    result["minimum_priced"] = min_priced
    result["coverage_warning_threshold"] = coverage_warning
    result["stay_filter"] = stay or "All stays"
    result["source_filter"] = source or "All sources"
    result["peer_definition"] = "Pooled LA listings with same room/bedrooms/stay/source; includes selected neighborhood"
    result["warnings"] = result.apply(lambda row: row_warnings(row, coverage_warning), axis=1)
    return result

def shortlist(compared, direction="Both"):
    if direction not in ["Both", "Premium", "Discount"]:
        raise ValueError("Direction must be Both, Premium, or Discount")
    result = compared.loc[compared.persistence_status.isin(STATUS[:2])].copy()
    if direction != "Both":
        result = result.loc[result.direction.eq(direction)]
    result["_bedroom_order"] = result.bedroom_segment.map({b: i for i,b in enumerate(BEDROOM_ORDER)})
    result = result.sort_values(["review_score", "neighbourhood", "room_type", "_bedroom_order"], ascending=[False, True, True, True], kind="stable").drop(columns="_bedroom_order").reset_index(drop=True)
    result.insert(0, "rank", range(1, len(result)+1))
    return result
