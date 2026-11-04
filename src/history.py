"""March–June segment comparison, persistence labels, row warnings and the review shortlist.

These are repeated cross-sections of advertised prices, not matched-listing or causal changes. No UI imports.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from src.pricing import PREMIUM_AVAILABLE, STUDIO_WARNING, premium_reason

KEY_COLUMNS = ["segment_key", "neighbourhood", "room_type", "bedroom_segment", "bedroom_order"]
PERSISTENT_PREMIUM = "Persistent premium"
PERSISTENT_DISCOUNT = "Persistent discount"
REVERSED = "Reversed"
NEUTRAL = "Neutral"
INSUFFICIENT = "Insufficient evidence"
DIRECTIONS = {"premium": [PERSISTENT_PREMIUM], "discount": [PERSISTENT_DISCOUNT],
              "both": [PERSISTENT_PREMIUM, PERSISTENT_DISCOUNT]}


def persistence_status(first: pd.Series, second: pd.Series) -> pd.Series:
    """Classify qualifying premiums. Missing values (absent or below threshold) mean Insufficient evidence."""
    both = first.notna() & second.notna()
    status = pd.Series(INSUFFICIENT, index=first.index, dtype="object")
    status[both & (first > 0) & (second > 0)] = PERSISTENT_PREMIUM
    status[both & (first < 0) & (second < 0)] = PERSISTENT_DISCOUNT
    status[both & (((first > 0) & (second < 0)) | ((first < 0) & (second > 0)))] = REVERSED
    status[both & ((first == 0) | (second == 0))] = NEUTRAL
    return status


def compare_snapshots(metrics: pd.DataFrame, dates: tuple[str, str], labels: tuple[str, str] = ("March", "June"), *,
                      coverage_warning: float = 0.8, small_sample_threshold: int = 20,
                      unknown_bedroom_warning: float = 0.1, source_filtered: bool = False) -> pd.DataFrame:
    """Outer-join per-date segment metrics (from `pricing.segment_metrics` with one set of filters).

    Columns from each date get a ``_<label>`` suffix (``_march``/``_june``). Opposite-date metrics stay null when a
    segment is absent; nothing is forward-filled.
    """
    first_date, second_date = dates
    a, b = (label.lower() for label in labels)
    unexpected = set(metrics.snapshot_date.unique()) - set(dates)
    if unexpected:
        raise ValueError(f"metrics contain dates outside {dates}: {sorted(unexpected)}")
    min_values = metrics["min_priced"].unique() if "min_priced" in metrics else []
    if len(min_values) > 1:
        raise ValueError("metrics mix different minimum priced counts")
    min_priced = int(min_values[0]) if len(min_values) else None

    value_cols = [c for c in metrics.columns if c not in KEY_COLUMNS + ["snapshot_date", "min_priced"]]
    sides = []
    for date, label in ((first_date, a), (second_date, b)):
        side = metrics.loc[metrics.snapshot_date.eq(date), KEY_COLUMNS + value_cols]
        sides.append(side.rename(columns={c: f"{c}_{label}" for c in value_cols}))
    result = sides[0].merge(sides[1], on=KEY_COLUMNS, how="outer", validate="one_to_one", sort=False)

    first_med, second_med = result[f"median_price_usd_{a}"], result[f"median_price_usd_{b}"]
    result["change_usd"] = second_med - first_med
    result["change_pct"] = (100 * result.change_usd / first_med).where(first_med > 0)
    first_prem, second_prem = result[f"premium_pct_{a}"], result[f"premium_pct_{b}"]
    result["persistence"] = persistence_status(first_prem, second_prem)
    persistent = result.persistence.isin([PERSISTENT_PREMIUM, PERSISTENT_DISCOUNT])
    result["direction"] = np.select([result.persistence.eq(PERSISTENT_PREMIUM),
                                     result.persistence.eq(PERSISTENT_DISCOUNT)], ["Premium", "Discount"], None)
    result["review_score"] = np.fmin(first_prem.abs(), second_prem.abs()).where(persistent)
    result["warnings"] = [
        "; ".join(_row_warnings(row, (a, b), labels, min_priced, coverage_warning, small_sample_threshold,
                                unknown_bedroom_warning, source_filtered))
        for row in result.to_dict("records")]
    result["warning_count"] = [len(w.split("; ")) if w else 0 for w in result.warnings]
    return result.sort_values(["neighbourhood", "room_type", "bedroom_order"], kind="mergesort").reset_index(drop=True)


def _row_warnings(row: dict, suffixes, labels, min_priced, coverage_warning, small_sample_threshold,
                  unknown_bedroom_warning, source_filtered) -> list[str]:
    warnings = []
    for suffix, label in zip(suffixes, labels):
        listings = row.get(f"listing_rows_{suffix}")
        if pd.isna(listings):
            warnings.append(f"{label}: no comparable listings under these filters (metrics left blank).")
            continue
        status = row[f"premium_status_{suffix}"]
        if status != PREMIUM_AVAILABLE and min_priced is not None:
            reason = premium_reason(status, row[f"priced_rows_{suffix}"], row[f"peer_priced_rows_{suffix}"], min_priced)
            warnings.append(f"{label}: premium unavailable, {reason}.")
        priced = row[f"priced_rows_{suffix}"]
        if priced < small_sample_threshold:
            warnings.append(f"{label}: small sample, {int(priced)} priced listings (fewer than {small_sample_threshold}).")
        for who, column in (("local", "price_coverage"), ("LA peer", "peer_price_coverage")):
            coverage = row[f"{column}_{suffix}"]
            if pd.notna(coverage) and coverage < coverage_warning:
                warnings.append(f"{label} {who} price coverage {100 * coverage:.1f}% is below the "
                                f"{100 * coverage_warning:.1f}% warning threshold.")
    if row["bedroom_segment"] == "Studio":
        warnings.append(STUDIO_WARNING)
    a, b = suffixes
    for who, column in (("local neighbourhood/room", "local_unknown_bedroom_share"),
                        ("LA peer room", "peer_unknown_bedroom_share")):
        first, second = row.get(f"{column}_{a}"), row.get(f"{column}_{b}")
        if pd.notna(first) and pd.notna(second) and abs(second - first) >= unknown_bedroom_warning:
            warnings.append(f"Bedroom completeness shift ({who}): unknown-bedroom share {100 * first:.1f}% in "
                            f"{labels[0]} vs {100 * second:.1f}% in {labels[1]}; segment counts are not comparable "
                            "as supply changes.")
    first, second = row.get(f"local_city_scrape_share_{a}"), row.get(f"local_city_scrape_share_{b}")
    if not source_filtered and pd.notna(first) and pd.notna(second) and abs(second - first) >= unknown_bedroom_warning:
        warnings.append(f"Source mix shift: city-scrape share {100 * first:.1f}% in {labels[0]} vs "
                        f"{100 * second:.1f}% in {labels[1]}.")
    return warnings


def rank_shortlist(comparison: pd.DataFrame, direction: str = "both") -> pd.DataFrame:
    """Persistent segments ranked by the minimum absolute premium; ties by neighbourhood, room, bedroom order.

    An empty frame (with all columns plus ``rank``) is a valid result.
    """
    direction = direction.lower()
    if direction not in DIRECTIONS:
        raise ValueError(f"direction must be one of {sorted(DIRECTIONS)}")
    ranked = comparison.loc[comparison.persistence.isin(DIRECTIONS[direction])]
    ranked = ranked.sort_values(["review_score", "neighbourhood", "room_type", "bedroom_order"],
                                ascending=[False, True, True, True], kind="mergesort").reset_index(drop=True)
    ranked.insert(0, "rank", np.arange(1, len(ranked) + 1, dtype="int64"))
    return ranked
