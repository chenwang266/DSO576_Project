"""One aggregation routine for canonical summaries, detail, and history."""
import numpy as np
import pandas as pd
from .filters import valid_dimensions

KEYS = ["neighbourhood", "room_type", "bedroom_segment"]
CONTEXT = {"availability_90": "availability_90", "reviews_ltm": "number_of_reviews_ltm", "value_score": "review_scores_value", "minimum_nights": "minimum_nights"}

def aggregate(frame, keys):
    grouped = frame.groupby(keys, dropna=False, sort=True)
    output = grouped.price_usd.agg(listing_rows="size", priced_rows="count", median_price_usd="median", min_price_usd="min", max_price_usd="max")
    output["p25_price_usd"] = grouped.price_usd.quantile(.25, interpolation="linear")
    output["p75_price_usd"] = grouped.price_usd.quantile(.75, interpolation="linear")
    output["price_iqr_usd"] = output.p75_price_usd - output.p25_price_usd
    output["price_coverage"] = output.priced_rows / output.listing_rows
    output["is_small_sample"] = output.priced_rows < 20
    for label, column in CONTEXT.items():
        output[f"{label}_median"] = grouped[column].median()
        output[f"{label}_valid_n"] = grouped[column].count()
    source_data = frame.assign(_previous=frame.source.eq("previous scrape"), _unknown_source=frame.source.eq("Unknown"))
    sg = source_data.groupby(keys, dropna=False, sort=True)
    output["previous_scrape_share"] = sg._previous.mean()
    output["unknown_source_share"] = sg._unknown_source.mean()
    return output.reset_index()

def snapshot_summary(frame, min_priced=20):
    """Pool peer listings across LA, explicitly including each local neighborhood."""
    if min_priced < 1:
        raise ValueError("Minimum priced count must be positive")
    data = valid_dimensions(frame)
    local_keys = ["snapshot_date"] + KEYS
    peer_keys = ["snapshot_date", "room_type", "bedroom_segment"]
    local = aggregate(data, local_keys)
    peer = aggregate(data, peer_keys)
    peer = peer.rename(columns={c: f"peer_{c}" for c in peer if c not in peer_keys})
    out = local.merge(peer, on=peer_keys, how="left", validate="many_to_one")
    # Completeness uses the pre-bedroom population; otherwise exclusions vanish.
    before_bedrooms = frame.loc[frame.neighbourhood_is_known & frame.room_type_is_known].copy()
    before_bedrooms["_unknown"] = before_bedrooms.bedroom_status.ne("valid")
    for prefix, keys in [("local", ["snapshot_date", "neighbourhood", "room_type"]), ("peer", ["snapshot_date", "room_type"])]:
        completeness = before_bedrooms.groupby(keys)._unknown.agg(**{f"{prefix}_bedroom_base_rows": "size", f"{prefix}_unknown_bedroom_rows": "sum", f"{prefix}_unknown_bedroom_share": "mean"}).reset_index()
        out = out.merge(completeness, on=keys, how="left", validate="many_to_one")
    out["sufficient_data"] = (out.priced_rows >= min_priced) & (out.peer_priced_rows >= min_priced) & out.peer_median_price_usd.gt(0)
    out["premium_pct"] = (100 * (out.median_price_usd / out.peer_median_price_usd - 1)).where(out.sufficient_data)
    out["premium_unavailable_reason"] = np.where(out.sufficient_data, "", f"Local and peer each need at least {min_priced} valid prices and a positive peer median.")
    return out

def histogram(values):
    values = pd.Series(values, dtype="float64").dropna()
    values = values.loc[np.isfinite(values) & values.gt(0)]
    if values.empty:
        return pd.DataFrame(columns=["left", "right", "count"])
    bins = 1 if values.min() == values.max() else 20
    counts, edges = np.histogram(values, bins=bins)
    return pd.DataFrame({"left": edges[:-1], "right": edges[1:], "count": counts})
