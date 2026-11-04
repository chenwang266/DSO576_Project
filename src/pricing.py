"""Price summaries, inclusive LA peer premiums, distributions and context. No UI imports, no hidden state.

`aggregate` is the single snapshot aggregation routine: segment tables, peer tables, the canonical segment file
and single-segment detail all call it, so their numbers cannot drift apart.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from src.data_access import BEDROOM_ORDER, CONTEXT_FIELDS, SEGMENT_DIMENSIONS, UNKNOWN, segment_key
from src.filters import (PEER_DEFINITION, OptionalFilters, SegmentSelection, apply_optional_filters,
                         local_population, neighbourhood_room_rows, peer_population)

SMALL_SAMPLE_THRESHOLD = 20
PRICE_COLUMNS = ("listing_rows", "priced_rows", "price_coverage", "median_price_usd", "p25_price_usd",
                 "p75_price_usd", "price_iqr_usd", "min_price_usd", "max_price_usd", "is_small_sample")
CONTEXT_COLUMNS = tuple(f"{field}_{stat}" for field in CONTEXT_FIELDS for stat in ("median", "n"))
SUMMARY_COLUMNS = PRICE_COLUMNS + CONTEXT_COLUMNS
SEGMENT_KEYS = ["snapshot_date", *SEGMENT_DIMENSIONS]
PEER_KEYS = ["snapshot_date", "room_type", "bedroom_segment"]

STUDIO_WARNING = ("Studio comparisons may be distorted by bedroom coding/completeness changes between snapshots "
                  "(zero-bedroom counts differ sharply); do not interpret them as supply changes.")

PREMIUM_AVAILABLE = "available"
PREMIUM_REASONS = {
    "no_local_prices": "no eligible local prices",
    "local_below_minimum": "local priced count {local} is below the minimum {minimum}",
    "peer_below_minimum": "LA peer priced count {peer} is below the minimum {minimum}",
    "peer_median_nonpositive": "LA peer median is not positive",
}


def aggregate(rows: pd.DataFrame, keys=(), small_sample_threshold: int = SMALL_SAMPLE_THRESHOLD) -> pd.DataFrame:
    """Summarize comparable listings per group of ``keys`` (one row for the whole frame when ``keys`` is empty).

    listing_rows counts valid-dimension listings including missing prices; price statistics use eligible prices
    only (linear-interpolated quantiles); each context median uses its own non-missing observations.
    """
    keys = list(keys)
    base = rows.loc[rows.has_valid_dimensions.fillna(False).astype(bool)]
    group = keys or ["_population"]
    if not keys:
        base = base.assign(_population=0)
    grouped = base.groupby(group, sort=True, observed=True)
    out = grouped.size().rename("listing_rows").to_frame()

    eligible = base.loc[base.pricing_eligible.fillna(False).astype(bool)]
    prices = eligible.groupby(group, sort=True, observed=True)["price_usd"]
    out = out.join(prices.agg(priced_rows="count", median_price_usd="median",
                              min_price_usd="min", max_price_usd="max"))
    out["p25_price_usd"] = prices.quantile(0.25)
    out["p75_price_usd"] = prices.quantile(0.75)
    out["priced_rows"] = out.priced_rows.fillna(0).astype("int64")
    out["price_coverage"] = (out.priced_rows / out.listing_rows).where(out.listing_rows > 0)
    out["price_iqr_usd"] = out.p75_price_usd - out.p25_price_usd
    out["is_small_sample"] = out.priced_rows < small_sample_threshold

    for field in CONTEXT_FIELDS:
        values = base[field].astype("float64")
        context = values.groupby([base[g] for g in group], sort=True, observed=True)
        out[f"{field}_median"] = context.median()
        out[f"{field}_n"] = context.count()
        out[f"{field}_n"] = out[f"{field}_n"].fillna(0).astype("int64")

    if not keys:
        if out.empty:
            out = pd.DataFrame([{**{col: np.nan for col in SUMMARY_COLUMNS}, "listing_rows": 0, "priced_rows": 0,
                                 "is_small_sample": 0 < small_sample_threshold,
                                 **{f"{f}_n": 0 for f in CONTEXT_FIELDS}}])
        return out.reset_index(drop=True)[list(SUMMARY_COLUMNS)]
    return out.reset_index()[keys + list(SUMMARY_COLUMNS)]


def premium(local_median, peer_median, local_priced, peer_priced, min_priced: int):
    """Vectorized ``100 × (local / peer − 1)`` with an explanation code for every suppressed value."""
    local_median, peer_median = np.asarray(local_median, float), np.asarray(peer_median, float)
    local_priced, peer_priced = np.asarray(local_priced, float), np.asarray(peer_priced, float)
    status = np.full(local_median.shape, PREMIUM_AVAILABLE, dtype=object)
    status[~(peer_median > 0)] = "peer_median_nonpositive"
    status[np.nan_to_num(peer_priced) < min_priced] = "peer_below_minimum"
    status[np.nan_to_num(local_priced) < min_priced] = "local_below_minimum"
    status[np.nan_to_num(local_priced) == 0] = "no_local_prices"
    ok = status == PREMIUM_AVAILABLE
    with np.errstate(divide="ignore", invalid="ignore"):
        value = np.where(ok, 100.0 * (local_median / peer_median - 1.0), np.nan)
    return value, status


def premium_reason(status: str, local_priced, peer_priced, min_priced: int) -> str | None:
    if status == PREMIUM_AVAILABLE:
        return None
    return PREMIUM_REASONS[status].format(local=int(local_priced or 0), peer=int(peer_priced or 0), minimum=min_priced)


def _unknown_bedroom_share(rows: pd.DataFrame, keys: list[str]) -> pd.DataFrame:
    """Share of known-neighbourhood/room listings in each group whose bedroom segment is Unknown."""
    known = rows.loc[rows.neighbourhood.ne(UNKNOWN) & rows.room_type.ne(UNKNOWN)]
    unknown = known.bedroom_segment.eq(UNKNOWN).astype(float)
    return unknown.groupby([known[k] for k in keys], sort=True).agg(["mean", "size"]).reset_index()


def segment_metrics(data: pd.DataFrame, filters: OptionalFilters = OptionalFilters(), *,
                    min_priced: int = 20, small_sample_threshold: int = SMALL_SAMPLE_THRESHOLD) -> pd.DataFrame:
    """Local and inclusive-peer summaries plus premium for every comparable segment in every snapshot.

    Stay/source refinements are recalculated from listings, never from precomputed medians.
    """
    if min_priced < 1:
        raise ValueError("min_priced must be a positive integer")
    base = apply_optional_filters(data, filters)
    local = aggregate(base, SEGMENT_KEYS, small_sample_threshold)
    peer = aggregate(base, PEER_KEYS, small_sample_threshold)
    peer = peer.rename(columns={c: f"peer_{c}" for c in SUMMARY_COLUMNS})
    result = local.merge(peer, on=PEER_KEYS, how="left", validate="many_to_one")

    result["premium_pct"], result["premium_status"] = premium(
        result.median_price_usd, result.peer_median_price_usd, result.priced_rows, result.peer_priced_rows, min_priced)
    result["sufficient_evidence"] = result.premium_status.eq(PREMIUM_AVAILABLE)

    local_share = _unknown_bedroom_share(base, ["snapshot_date", "neighbourhood", "room_type"]).rename(
        columns={"mean": "local_unknown_bedroom_share", "size": "local_room_listing_rows"})
    peer_share = _unknown_bedroom_share(base, ["snapshot_date", "room_type"]).rename(
        columns={"mean": "peer_unknown_bedroom_share", "size": "peer_room_listing_rows"})
    result = result.merge(local_share, on=["snapshot_date", "neighbourhood", "room_type"], how="left")
    result = result.merge(peer_share, on=["snapshot_date", "room_type"], how="left")

    sources = base.loc[base.has_valid_dimensions.fillna(False).astype(bool)]
    city = sources.source_category.eq("city scrape").astype(float)
    city_share = city.groupby([sources[k] for k in SEGMENT_KEYS], sort=True).mean().rename("local_city_scrape_share")
    result = result.merge(city_share.reset_index(), on=SEGMENT_KEYS, how="left")

    result.insert(1, "segment_key", [segment_key(*v) for v in result[list(SEGMENT_DIMENSIONS)].itertuples(index=False)])
    result.insert(5, "bedroom_order", result.bedroom_segment.map(BEDROOM_ORDER).astype("int64"))
    result["min_priced"] = min_priced
    return result.sort_values(["snapshot_date", "neighbourhood", "room_type", "bedroom_order"],
                              kind="mergesort").reset_index(drop=True)


def canonical_segments(data: pd.DataFrame, small_sample_threshold: int = SMALL_SAMPLE_THRESHOLD) -> pd.DataFrame:
    """Unfiltered date × segment price table written to canonical_price_segments.csv."""
    table = aggregate(data, SEGMENT_KEYS, small_sample_threshold)
    table.insert(1, "segment_key", [segment_key(*v) for v in table[list(SEGMENT_DIMENSIONS)].itertuples(index=False)])
    table.insert(5, "bedroom_order", table.bedroom_segment.map(BEDROOM_ORDER).astype("int64"))
    table = table.sort_values(["snapshot_date", "neighbourhood", "room_type", "bedroom_order"], kind="mergesort")
    return table[["snapshot_date", "segment_key", "neighbourhood", "room_type", "bedroom_segment", "bedroom_order",
                  *PRICE_COLUMNS]].reset_index(drop=True)


def histogram_bins(prices, bins: int = 20) -> pd.DataFrame:
    """Equal-width bins of eligible prices; a single bin for constant prices; empty frame when no prices."""
    values = pd.Series(prices, dtype="float64").dropna()
    if values.empty:
        return pd.DataFrame({"left": pd.Series(dtype=float), "right": pd.Series(dtype=float),
                             "count": pd.Series(dtype="int64")})
    if values.min() == values.max():
        return pd.DataFrame({"left": [values.min()], "right": [values.max()], "count": [len(values)]})
    counts, edges = np.histogram(values.to_numpy(), bins=bins)
    return pd.DataFrame({"left": edges[:-1], "right": edges[1:], "count": counts.astype("int64")})


def segment_detail(data: pd.DataFrame, selection: SegmentSelection, filters: OptionalFilters = OptionalFilters(), *,
                   min_priced: int = 20, coverage_warning: float = 0.8, histogram_bin_count: int = 20,
                   small_sample_threshold: int = SMALL_SAMPLE_THRESHOLD, unknown_bedroom_warning: float = 0.1) -> dict:
    """Everything the Segment Detail view needs for one snapshot/segment, with reasons for missing results."""
    if min_priced < 1:
        raise ValueError("min_priced must be a positive integer")
    local_rows = local_population(data, selection, filters)
    peer_rows = peer_population(data, selection.snapshot, selection.room_type, selection.bedroom_segment, filters)
    local = aggregate(local_rows, small_sample_threshold=small_sample_threshold).iloc[0].to_dict()
    peer = aggregate(peer_rows, small_sample_threshold=small_sample_threshold).iloc[0].to_dict()
    value, status = premium([local["median_price_usd"]], [peer["median_price_usd"]],
                            [local["priced_rows"]], [peer["priced_rows"]], min_priced)

    share_rows = neighbourhood_room_rows(data, selection.snapshot, selection.neighbourhood, selection.room_type, filters)
    peer_share_rows = neighbourhood_room_rows(data, selection.snapshot, None, selection.room_type, filters)
    local_unknown = share_rows.bedroom_segment.eq(UNKNOWN).mean() if len(share_rows) else np.nan
    peer_unknown = peer_share_rows.bedroom_segment.eq(UNKNOWN).mean() if len(peer_share_rows) else np.nan

    context = pd.DataFrame([
        {"field": field, "local_median": local[f"{field}_median"], "local_n": local[f"{field}_n"],
         "peer_median": peer[f"{field}_median"], "peer_n": peer[f"{field}_n"]} for field in CONTEXT_FIELDS])
    prices = local_rows.loc[local_rows.pricing_eligible.fillna(False).astype(bool), "price_usd"]

    reason = premium_reason(status[0], local["priced_rows"], peer["priced_rows"], min_priced)
    warnings = []
    if local["listing_rows"] == 0:
        warnings.append("No comparable listings for this selection and filters.")
    if reason:
        warnings.append(f"Premium unavailable: {reason}. Raw price metrics remain shown.")
    for name, summary in (("Local", local), ("LA peer", peer)):
        if summary["listing_rows"] and summary["priced_rows"] < small_sample_threshold:
            warnings.append(f"{name} small sample: {summary['priced_rows']} priced listings "
                            f"(fewer than {small_sample_threshold}).")
        if pd.notna(summary["price_coverage"]) and summary["price_coverage"] < coverage_warning:
            warnings.append(f"{name} price coverage {100 * summary['price_coverage']:.1f}% is below the "
                            f"{100 * coverage_warning:.1f}% warning threshold; listings are retained.")
    if selection.bedroom_segment == "Studio":
        warnings.append(STUDIO_WARNING)
    for name, share in (("Local neighbourhood/room", local_unknown), ("LA peer room", peer_unknown)):
        if pd.notna(share) and share >= unknown_bedroom_warning:
            warnings.append(f"{name} listings with unknown bedrooms: {100 * share:.1f}% are excluded from "
                            "comparable segments.")

    return {
        "selection": selection, "filters": filters, "min_priced": min_priced, "coverage_warning": coverage_warning,
        "local": local, "peer": peer, "premium_pct": float(value[0]), "premium_status": status[0],
        "premium_reason": reason, "sufficient_evidence": status[0] == PREMIUM_AVAILABLE,
        "local_unknown_bedroom_share": local_unknown, "peer_unknown_bedroom_share": peer_unknown,
        "context": context, "histogram": histogram_bins(prices, histogram_bin_count), "local_prices": prices,
        "peer_definition": PEER_DEFINITION, "warnings": warnings,
    }

