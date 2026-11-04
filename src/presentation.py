"""Display formatting, export tables and methodology text built from backend outputs.

No Streamlit imports and no analysis formulas: every number shown or exported comes from `pricing` / `history`.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timezone

import pandas as pd

from src.filters import PEER_DEFINITION, OptionalFilters
from src.history import PERSISTENT_DISCOUNT, PERSISTENT_PREMIUM

UNAVAILABLE = "Unavailable"
CONTEXT_LABELS = {
    "availability_90": "Availability, next 90 days (nights)",
    "number_of_reviews_ltm": "Reviews, last 12 months",
    "review_scores_value": "Value score (0–5)",
    "minimum_nights": "Minimum nights",
}
CONTEXT_SHORT = {"availability_90": "Avail 90d", "number_of_reviews_ltm": "Reviews 12m",
                 "review_scores_value": "Value", "minimum_nights": "Min nights"}
DIRECTION_LABELS = {PERSISTENT_PREMIUM: "▲ Premium", PERSISTENT_DISCOUNT: "▼ Discount"}
PERSISTENCE_LABELS = {PERSISTENT_PREMIUM: "▲ Persistent premium", PERSISTENT_DISCOUNT: "▼ Persistent discount",
                      "Reversed": "⇅ Reversed", "Neutral": "• Neutral", "Insufficient evidence": "? Insufficient evidence"}
ATTRIBUTION = ("Data: [Inside Airbnb](https://insideairbnb.com/get-the-data/), Los Angeles detailed listings, "
               "licensed under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). Advertised prices only.")
LIMITS = (
    "Advertised nightly prices, not booked prices, revenue, occupancy or demand. No optimal price is estimated.",
    "March and June are repeated cross-sections, not matched listings; changes are not causal effects.",
    "Thresholds (minimum priced count, coverage warning, small sample < 20) are exploratory screening rules, "
    "not statistical significance tests.",
    "Shortlisted segments are candidates for human pricing review, not recommendations to change prices.",
    "Context fields explain a segment; they are not part of the ranking score.",
)


def _missing(value) -> bool:
    return value is None or (isinstance(value, float) and math.isnan(value)) or value is pd.NA or pd.isna(value)


def fmt_usd(value) -> str:
    return UNAVAILABLE if _missing(value) else f"${value:,.2f}"


def fmt_pct(value, *, signed: bool = False) -> str:
    """Percentage points already scaled to 0–100."""
    if _missing(value):
        return UNAVAILABLE
    return f"{value:+.1f}%" if signed else f"{value:.1f}%"


def fmt_share(fraction) -> str:
    """A 0–1 fraction shown as a percentage."""
    return UNAVAILABLE if _missing(fraction) else f"{100 * fraction:.1f}%"


def fmt_usd_change(value) -> str:
    return UNAVAILABLE if _missing(value) else f"{'+' if value >= 0 else '-'}${abs(value):,.2f}"


def fmt_count(value) -> str:
    return "0" if _missing(value) else f"{int(value):,}"


def fmt_number(value) -> str:
    if _missing(value):
        return UNAVAILABLE
    text = f"{value:,.2f}".rstrip("0").rstrip(".")
    return text or "0"


def segment_label(neighbourhood: str, room_type: str, bedroom_segment: str) -> str:
    return f"{neighbourhood} · {room_type} · {bedroom_segment}"


@dataclass(frozen=True)
class ViewSettings:
    """Everything that determines a computed view; exported alongside every CSV."""
    dates: tuple[str, str]
    labels: tuple[str, str]
    filters: OptionalFilters
    min_priced: int
    coverage_warning: float
    small_sample_threshold: int
    unknown_bedroom_warning: float
    fingerprint: str

    def record(self, **extra) -> dict:
        return {
            "generated_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "canonical_fingerprint": self.fingerprint,
            f"{self.labels[0].lower()}_nominal_date": self.dates[0],
            f"{self.labels[1].lower()}_nominal_date": self.dates[1],
            **self.filters.describe(),
            "min_priced_count": self.min_priced,
            "coverage_warning_threshold": self.coverage_warning,
            "small_sample_threshold": self.small_sample_threshold,
            "unknown_bedroom_warning_threshold": self.unknown_bedroom_warning,
            **extra,
            "peer_definition": PEER_DEFINITION,
        }


def _context_summary(row: dict, suffix: str) -> str:
    parts = []
    for field, short in CONTEXT_SHORT.items():
        n = row.get(f"{field}_n_{suffix}")
        value = row.get(f"{field}_median_{suffix}")
        parts.append(f"{short} {fmt_number(value) if not _missing(n) and n > 0 else 'n/a'}")
    return " · ".join(parts)


def _priced_of(row: dict, suffix: str) -> str:
    listings = row.get(f"listing_rows_{suffix}")
    if _missing(listings):
        return "No listings"
    return f"{fmt_count(row[f'priced_rows_{suffix}'])} / {fmt_count(listings)}"


def shortlist_display(shortlist: pd.DataFrame, labels: tuple[str, str]) -> pd.DataFrame:
    """Formatted shortlist for on-screen display (one row per ranked segment, same order)."""
    a, b = (label.lower() for label in labels)
    rows = []
    for row in shortlist.to_dict("records"):
        rows.append({
            "Rank": int(row["rank"]),
            "Segment": segment_label(row["neighbourhood"], row["room_type"], row["bedroom_segment"]),
            "Direction": DIRECTION_LABELS.get(row["persistence"], row["persistence"]),
            "Score (min |premium|)": fmt_pct(row["review_score"]),
            f"{labels[0]} premium": fmt_pct(row[f"premium_pct_{a}"], signed=True),
            f"{labels[1]} premium": fmt_pct(row[f"premium_pct_{b}"], signed=True),
            f"{labels[0]} priced / listings": _priced_of(row, a),
            f"{labels[1]} priced / listings": _priced_of(row, b),
            f"{labels[0]} coverage": fmt_share(row[f"price_coverage_{a}"]),
            f"{labels[1]} coverage": fmt_share(row[f"price_coverage_{b}"]),
            f"{labels[0]} context (local medians)": _context_summary(row, a),
            f"{labels[1]} context (local medians)": _context_summary(row, b),
            "Warnings": row["warnings"] or "None",
        })
    columns = ["Rank", "Segment", "Direction", "Score (min |premium|)", f"{labels[0]} premium",
               f"{labels[1]} premium", f"{labels[0]} priced / listings", f"{labels[1]} priced / listings",
               f"{labels[0]} coverage", f"{labels[1]} coverage", f"{labels[0]} context (local medians)",
               f"{labels[1]} context (local medians)", "Warnings"]
    return pd.DataFrame(rows, columns=columns)


def _with_settings(frame: pd.DataFrame, settings: ViewSettings, **extra) -> pd.DataFrame:
    record = settings.record(**extra)
    out = frame.copy()
    for position, (name, value) in enumerate(record.items()):
        out.insert(position, name, value)
    return out


def shortlist_export(shortlist: pd.DataFrame, settings: ViewSettings, direction: str) -> pd.DataFrame:
    """Visible shortlist with every backend column at full precision, prefixed by the settings that produced it."""
    return _with_settings(shortlist, settings, shortlist_direction=direction)


def evidence_export(row: dict | None, settings: ViewSettings, segment: tuple[str, str, str],
                    detail_warnings: list[str] | None = None, detail_snapshot: str | None = None) -> pd.DataFrame:
    """Long (section, field, value) evidence record for one segment: settings, both dates' metrics, warnings."""
    records = [("settings", key, value) for key, value in settings.record().items()]
    records += [("segment", "neighbourhood", segment[0]), ("segment", "room_type", segment[1]),
                ("segment", "bedroom_segment", segment[2])]
    if row is None:
        records.append(("comparison", "status",
                        "No comparable listings for this segment in either snapshot under these filters."))
    else:
        for key, value in row.items():
            if key in ("neighbourhood", "room_type", "bedroom_segment"):
                continue
            records.append(("comparison", key, None if _missing(value) else value))
    for warning in detail_warnings or []:
        records.append((f"detail warnings ({detail_snapshot})", "warning", warning))
    return pd.DataFrame(records, columns=["section", "field", "value"])


def to_csv_bytes(frame: pd.DataFrame) -> bytes:
    """UTF-8 CSV; floats are written with full repr precision (no rounding)."""
    return frame.to_csv(index=False).encode("utf-8")


def _snapshot_lines(report: dict) -> list[str]:
    lines = []
    for snap in report.get("snapshots", []):
        scraped = snap.get("actual_scrape_dates", {})
        span = f"{min(scraped)} to {max(scraped)}" if scraped else "not available"
        prices = snap.get("price_status", {})
        beds = snap.get("bedrooms", {})
        segments = beds.get("segments", {})
        lines.append(
            f"- **{snap['label']}** (nominal {snap['nominal_date']}; actual scrape dates {span}): "
            f"{fmt_count(snap['rows'])} listings; {fmt_count(prices.get('missing', 0))} missing prices, "
            f"{fmt_count(prices.get('malformed', 0))} malformed, "
            f"{fmt_count(prices.get('invalid_nonpositive', 0))} nonpositive; "
            f"{fmt_count(segments.get('Unknown', 0))} unknown-bedroom listings excluded from comparable segments "
            f"({fmt_share(1 - beds.get('known_share', 1))}); {fmt_count(beds.get('zero_bedrooms', 0))} Studio "
            f"(zero-bedroom) listings; {fmt_count(snap.get('pricing_eligible', 0))} pricing-eligible.")
    return lines


def methodology_markdown(report: dict, settings: ViewSettings) -> str:
    lines = [
        ATTRIBUTION,
        "",
        "**Snapshots and data quality**",
        *_snapshot_lines(report),
        "",
        "**Definitions**",
        f"- Segment = neighbourhood × room type × bedroom segment (Studio, 1–5, 6+). Unknown bedrooms are never "
        "merged with Studio and cannot form a comparable segment.",
        f"- {PEER_DEFINITION}",
        "- Pricing eligible = valid positive price + known neighbourhood, room type and bedrooms. Price coverage = "
        "priced listings / valid-dimension listings (missing-price listings stay in the denominator).",
        "- Median, P25 and P75 use linear interpolation; IQR = P75 − P25. Premium = 100 × (local median / "
        "LA peer median − 1).",
        "- Context medians (availability, reviews, value score, minimum nights) use each field's own valid "
        "observations, including listings without a valid price.",
        "- Persistence: both qualifying premiums positive → persistent premium; both negative → persistent "
        "discount; opposite signs → reversed; either zero → neutral; otherwise insufficient evidence. Score = "
        "smaller absolute premium of the two snapshots.",
        "",
        "**Current settings and policies**",
        f"- Stay filter: {settings.filters.describe()['stay_filter']}; source filter: "
        f"{settings.filters.describe()['source_filter']}.",
        f"- Minimum priced listings for a premium: {settings.min_priced} (local and LA peer separately). Below "
        "it, raw metrics stay visible but premium, persistence and ranking are suppressed.",
        f"- Coverage warning below {fmt_share(settings.coverage_warning)}; no listings are excluded for low "
        f"coverage. Small sample = fewer than {settings.small_sample_threshold} priced listings.",
        f"- Bedroom-completeness and source-mix warnings at a {fmt_share(settings.unknown_bedroom_warning)} "
        "shift (team approval pending).",
        "- No price imputation, caps or outlier removal; extreme prices are kept. Host details and coordinates "
        "are not used or shown.",
        "",
        "**Limits**",
        *[f"- {limit}" for limit in LIMITS],
    ]
    return "\n".join(lines)
