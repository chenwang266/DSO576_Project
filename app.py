"""LA Airbnb Pricing Review dashboard (Streamlit). Run with: uv run streamlit run app.py

The app only selects, caches and displays backend outputs; all calculations live in src/pricing.py and
src/history.py. Cached results are keyed by the canonical file fingerprint plus every filter and setting.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st

from src import charts
from src.config import ConfigError, Settings, load_settings
from src.data_access import CANONICAL_FILES, CONTEXT_FIELDS, CanonicalDataError, combined_fingerprint, load_canonical
from src.filters import PEER_DEFINITION, OptionalFilters, SegmentSelection, available_options
from src.history import DIRECTIONS, compare_snapshots, rank_shortlist
from src.pricing import premium_reason, segment_detail, segment_metrics
from src import presentation as fmt

TABS = ("Segment Detail", "March–June Comparison", "Review Shortlist")
ALL_STAYS, ALL_SOURCES = "All stays", "All sources"
PLOT_CONFIG = {"displayModeBar": False}
DIRECTION_OPTIONS = {"Both": "both", "Premium": "premium", "Discount": "discount"}

st.set_page_config(page_title="LA Airbnb Pricing Review", page_icon="🏠", layout="wide")


# ---------- data loading and cached computations ----------

def _file_stats(directory: Path) -> tuple:
    absent = [name for name in CANONICAL_FILES if not (directory / name).exists()]
    if absent:
        raise CanonicalDataError(
            f"Canonical files {absent} not found in {directory}. Place the March/June raw listings under data/raw/ "
            "(see README) and run: uv run python scripts/canonical_clean.py")
    return tuple((name, (directory / name).stat().st_mtime_ns, (directory / name).stat().st_size)
                 for name in CANONICAL_FILES)


@st.cache_data(show_spinner=False, max_entries=4)
def _fingerprint(directory: str, stats: tuple) -> str:
    # `stats` (mtime, size) is part of the key so edited files are re-hashed; the hash itself is the data key.
    return combined_fingerprint(directory)


@st.cache_resource(show_spinner="Loading and validating canonical data…", max_entries=1)
def _load(directory: str, fingerprint: str, dates: tuple, small_sample_threshold: int):
    data = load_canonical(directory, dates, small_sample_threshold)
    if data.fingerprint != fingerprint:
        raise CanonicalDataError("Canonical files changed while loading; reload the page.")
    return data


@st.cache_data(show_spinner=False, max_entries=4)
def _options(directory: str, fingerprint: str, dates: tuple, small: int) -> dict:
    return available_options(_load(directory, fingerprint, dates, small).listings)


@st.cache_data(show_spinner="Comparing snapshots…", max_entries=32)
def _comparison(directory: str, fingerprint: str, dates: tuple, labels: tuple, stay, source, min_priced: int,
                coverage_warning: float, small: int, unknown_warning: float) -> pd.DataFrame:
    data = _load(directory, fingerprint, dates, small)
    filters = OptionalFilters(stay, source)
    metrics = segment_metrics(data.listings, filters, min_priced=min_priced, small_sample_threshold=small)
    return compare_snapshots(metrics, dates, labels, coverage_warning=coverage_warning, small_sample_threshold=small,
                             unknown_bedroom_warning=unknown_warning, source_filtered=source is not None)


@st.cache_data(show_spinner="Summarising segment…", max_entries=64)
def _detail(directory: str, fingerprint: str, dates: tuple, snapshot: str, neighbourhood: str, room_type: str,
            bedroom_segment: str, stay, source, min_priced: int, coverage_warning: float, bins: int, small: int,
            unknown_warning: float) -> dict:
    data = _load(directory, fingerprint, dates, small)
    return segment_detail(data.listings, SegmentSelection(snapshot, neighbourhood, room_type, bedroom_segment),
                          OptionalFilters(stay, source), min_priced=min_priced, coverage_warning=coverage_warning,
                          histogram_bin_count=bins, small_sample_threshold=small,
                          unknown_bedroom_warning=unknown_warning)


def _setup_error(error: Exception) -> None:
    st.title("LA Airbnb Pricing Review")
    st.error(f"**Setup needed.** {error}")
    st.markdown(
        "1. `uv sync --locked`\n"
        "2. Put `listings-2026-03-16.csv.gz` and `listings-2026-06-15.csv.gz` (Inside Airbnb, Los Angeles, detailed "
        "listings) in `data/raw/`, or point `config/project.json` at them.\n"
        "3. `uv run python scripts/canonical_clean.py`\n"
        "4. `uv run streamlit run app.py`\n\nNo data is downloaded automatically.")
    st.stop()


try:
    SETTINGS: Settings = load_settings()
    DIRECTORY = str(SETTINGS.processed_dir)
    FINGERPRINT = _fingerprint(DIRECTORY, _file_stats(SETTINGS.processed_dir))
    DATES = SETTINGS.dates
    LABELS = tuple(SETTINGS.labels[d] for d in DATES)
    SMALL = SETTINGS.small_sample_threshold
    DATA = _load(DIRECTORY, FINGERPRINT, DATES, SMALL)
    OPTIONS = _options(DIRECTORY, FINGERPRINT, DATES, SMALL)
except (ConfigError, CanonicalDataError) as error:
    _setup_error(error)

SUFFIXES = tuple(label.lower() for label in LABELS)
DEFAULTS = {
    "snapshot": SETTINGS.default_selection.get("snapshot", DATES[-1]),
    "neighbourhood": SETTINGS.default_selection.get("neighbourhood", "Hollywood"),
    "room_type": SETTINGS.default_selection.get("room_type", "Entire home/apt"),
    "bedroom_segment": SETTINGS.default_selection.get("bedroom_segment", "1 bedroom"),
    "stay": SETTINGS.default_selection.get("stay") or ALL_STAYS,
    "source": SETTINGS.default_selection.get("source") or ALL_SOURCES,
    "min_priced": SETTINGS.min_priced_count,
    "coverage_pct": round(100 * SETTINGS.coverage_warning),
    "direction": "Both",
}


# ---------- sidebar ----------

def _reset() -> None:
    for key, value in DEFAULTS.items():
        st.session_state[key] = value


def _open_shortlist_row() -> None:
    """Shortlist row selection: load that segment into the sidebar and open Segment Detail; filters unchanged."""
    rows = st.session_state["shortlist_table"].selection.rows
    keys = st.session_state.get("_shortlist_keys", [])
    if rows and rows[0] < len(keys):
        st.session_state["neighbourhood"], st.session_state["room_type"], st.session_state["bedroom_segment"] = (
            keys[rows[0]])
        st.session_state["view"] = TABS[0]


for key, value in DEFAULTS.items():
    st.session_state.setdefault(key, value)

unavailable = []
choices = {
    "snapshot": OPTIONS["snapshots"], "neighbourhood": OPTIONS["neighbourhoods"], "room_type": OPTIONS["room_types"],
    "bedroom_segment": OPTIONS["bedroom_segments"], "stay": [ALL_STAYS, *OPTIONS["stays"]],
    "source": [ALL_SOURCES, *OPTIONS["sources"]],
}
for key, options in choices.items():
    if st.session_state[key] not in options:
        unavailable.append(f"{st.session_state[key]!r} is not available for {key.replace('_', ' ')} in the "
                           f"validated data; showing {options[0]!r} instead.")
        st.session_state[key] = options[0]

with st.sidebar:
    st.header("Selection")
    for message in unavailable:
        st.warning(message, icon="⚠️")
    st.selectbox("Snapshot (Segment Detail only)", choices["snapshot"], key="snapshot",
                 format_func=lambda d: f"{SETTINGS.labels[d]} ({d})")
    st.selectbox("Neighbourhood", choices["neighbourhood"], key="neighbourhood")
    st.selectbox("Room type", choices["room_type"], key="room_type")
    st.selectbox("Bedrooms", choices["bedroom_segment"], key="bedroom_segment",
                 help="Studio = 0 bedrooms. Listings with unknown bedrooms are excluded, never merged with Studio.")
    st.subheader("Optional filters")
    st.selectbox("Minimum-night stay", choices["stay"], key="stay")
    st.selectbox("Listing source", choices["source"], key="source",
                 help="Inside Airbnb `source`: 'city scrape' or 'previous scrape'.")
    st.subheader("Evidence thresholds")
    st.number_input("Minimum priced listings", min_value=1, max_value=1000, step=1, key="min_priced",
                    help="Applied to local and LA peer separately. Exploratory, not statistical significance.")
    st.slider("Coverage warning below (%)", min_value=0, max_value=100, step=5, key="coverage_pct",
              help="Segments below this price coverage get a warning; nothing is excluded.")
    st.button("Reset to defaults", on_click=_reset, width="stretch")

SNAPSHOT = st.session_state["snapshot"]
SEGMENT = (st.session_state["neighbourhood"], st.session_state["room_type"], st.session_state["bedroom_segment"])
STAY = None if st.session_state["stay"] == ALL_STAYS else st.session_state["stay"]
SOURCE = None if st.session_state["source"] == ALL_SOURCES else st.session_state["source"]
MIN_PRICED = int(st.session_state["min_priced"])
COVERAGE = st.session_state["coverage_pct"] / 100
VIEW = fmt.ViewSettings(DATES, LABELS, OptionalFilters(STAY, SOURCE), MIN_PRICED, COVERAGE, SMALL,
                        SETTINGS.unknown_bedroom_warning, FINGERPRINT)

comparison = _comparison(DIRECTORY, FINGERPRINT, DATES, LABELS, STAY, SOURCE, MIN_PRICED, COVERAGE, SMALL,
                         SETTINGS.unknown_bedroom_warning)
match = comparison.loc[(comparison.neighbourhood == SEGMENT[0]) & (comparison.room_type == SEGMENT[1])
                       & (comparison.bedroom_segment == SEGMENT[2])]
SEGMENT_ROW = match.iloc[0].to_dict() if len(match) else None


# ---------- shared pieces ----------

def methodology() -> None:
    with st.expander("Data Quality & Methodology"):
        st.markdown(fmt.methodology_markdown(DATA.report, VIEW))


def show_warnings(warnings: list[str]) -> None:
    if not warnings:
        st.success("No warnings for this view.", icon="✅")
    for warning in warnings:
        st.warning(warning, icon="⚠️")


def evidence_download(key: str, detail: dict | None = None) -> None:
    frame = fmt.evidence_export(SEGMENT_ROW, VIEW, SEGMENT, detail["warnings"] if detail else None,
                                SETTINGS.labels[SNAPSHOT] if detail else None)
    st.download_button("Download segment evidence (CSV)", fmt.to_csv_bytes(frame), key=key, icon="⬇️",
                       file_name=f"evidence_{'_'.join(SEGMENT).replace('/', '-').replace(' ', '-')}.csv",
                       mime="text/csv")


def filter_caption() -> str:
    names = VIEW.filters.describe()
    return (f"{names['stay_filter']} · {names['source_filter']} · minimum {MIN_PRICED} priced listings · "
            f"coverage warning below {fmt.fmt_share(COVERAGE)}")


# ---------- page ----------

st.title("LA Airbnb Pricing Review")
st.caption("Screens Los Angeles neighbourhood × room type × bedroom segments for **human pricing review** using "
           "advertised prices from two Inside Airbnb snapshots. It does not estimate optimal prices, revenue, "
           "occupancy, demand or causal effects.")

detail_tab, compare_tab, shortlist_tab = st.tabs(TABS, key="view", on_change="rerun")

with detail_tab:
    if detail_tab.open:
        detail = _detail(DIRECTORY, FINGERPRINT, DATES, SNAPSHOT, *SEGMENT, STAY, SOURCE, MIN_PRICED, COVERAGE,
                         SETTINGS.histogram_bins, SMALL, SETTINGS.unknown_bedroom_warning)
        local, peer = detail["local"], detail["peer"]
        st.subheader(f"{fmt.segment_label(*SEGMENT)} — {SETTINGS.labels[SNAPSHOT]} ({SNAPSHOT})")
        st.caption(filter_caption())
        if local["listing_rows"] == 0:
            st.info("No comparable listings for this neighbourhood, room type and bedroom segment in this snapshot "
                    "under the current filters. Try the other snapshot or clear the optional filters.", icon="ℹ️")
        cols = st.columns(3)
        cols[0].metric("Listings (valid dimensions)", fmt.fmt_count(local["listing_rows"]))
        cols[1].metric("Priced listings", fmt.fmt_count(local["priced_rows"]))
        cols[2].metric("Price coverage", fmt.fmt_share(local["price_coverage"]),
                       help="Priced / valid-dimension listings; unavailable when there are no listings.")
        cols = st.columns(3)
        cols[0].metric("Median price", fmt.fmt_usd(local["median_price_usd"]))
        cols[1].metric("IQR (P75 − P25)", fmt.fmt_usd(local["price_iqr_usd"]),
                       help=f"P25 {fmt.fmt_usd(local['p25_price_usd'])} · P75 {fmt.fmt_usd(local['p75_price_usd'])}")
        cols[2].metric("Premium vs LA peer", fmt.fmt_pct(detail["premium_pct"], signed=True),
                       help=detail["premium_reason"] and f"Unavailable: {detail['premium_reason']}.")
        if detail["premium_reason"]:
            st.caption(f"Premium unavailable: {detail['premium_reason']}.")

        st.markdown("**Warnings**")
        show_warnings(detail["warnings"])

        figure = charts.price_histogram(detail["histogram"], local["median_price_usd"],
                                        f"Local price distribution ({SETTINGS.histogram_bins} equal-width bins)")
        if figure is None:
            st.info("No eligible local prices to plot for this selection.", icon="ℹ️")
        else:
            st.plotly_chart(figure, width="stretch", config=PLOT_CONFIG)

        left, right = st.columns(2)
        with left:
            st.markdown("**Local vs LA peer prices**")
            st.caption(PEER_DEFINITION)
            table = pd.DataFrame({
                "Measure": ["Listings (valid dimensions)", "Priced listings", "Price coverage", "Median", "P25", "P75",
                            "IQR", "Minimum", "Maximum"],
                **{name: [fmt.fmt_count(s["listing_rows"]), fmt.fmt_count(s["priced_rows"]),
                          fmt.fmt_share(s["price_coverage"]), fmt.fmt_usd(s["median_price_usd"]),
                          fmt.fmt_usd(s["p25_price_usd"]), fmt.fmt_usd(s["p75_price_usd"]),
                          fmt.fmt_usd(s["price_iqr_usd"]), fmt.fmt_usd(s["min_price_usd"]),
                          fmt.fmt_usd(s["max_price_usd"])]
                   for name, s in (("Local", local), ("LA peer (incl. selected)", peer))}})
            st.dataframe(table, hide_index=True, width="stretch")
        with right:
            st.markdown("**Context (explanatory, not scored)**")
            st.caption("Medians over each field's own valid observations, including listings without a valid price.")
            context = detail["context"]
            st.dataframe(pd.DataFrame({
                "Field": [fmt.CONTEXT_LABELS[f] for f in context.field],
                "Local median": [fmt.fmt_number(v) for v in context.local_median],
                "Local n": [fmt.fmt_count(v) for v in context.local_n],
                "LA peer median": [fmt.fmt_number(v) for v in context.peer_median],
                "LA peer n": [fmt.fmt_count(v) for v in context.peer_n]}), hide_index=True, width="stretch")
            st.caption(f"Unknown-bedroom share excluded from segments: local neighbourhood/room "
                       f"{fmt.fmt_share(detail['local_unknown_bedroom_share'])}, LA room type "
                       f"{fmt.fmt_share(detail['peer_unknown_bedroom_share'])}.")
        evidence_download("detail_evidence", detail)
        methodology()

with compare_tab:
    if compare_tab.open:
        st.subheader(f"{fmt.segment_label(*SEGMENT)} — {LABELS[0]} vs {LABELS[1]}")
        st.caption(f"{filter_caption()}. Snapshot selection does not affect this tab. Repeated cross-sections, not "
                   "matched listings; changes are descriptive, not causal.")
        if SEGMENT_ROW is None:
            st.info("This segment has no comparable listings in either snapshot under the current filters.",
                    icon="ℹ️")
        else:
            row, (a, b) = SEGMENT_ROW, SUFFIXES
            st.markdown(f"### {fmt.PERSISTENCE_LABELS.get(row['persistence'], row['persistence'])}")
            if pd.notna(row["review_score"]):
                st.caption(f"Review score (smaller absolute premium): {fmt.fmt_pct(row['review_score'])}")
            cols = st.columns(4)
            cols[0].metric(f"{LABELS[0]} median", fmt.fmt_usd(row[f"median_price_usd_{a}"]))
            cols[1].metric(f"{LABELS[1]} median", fmt.fmt_usd(row[f"median_price_usd_{b}"]))
            cols[2].metric("Change (USD)", fmt.fmt_usd_change(row["change_usd"]))
            cols[3].metric("Change (%)", fmt.fmt_pct(row["change_pct"], signed=True),
                           help="Unavailable when either median is missing or the March baseline is not positive.")
            left, right = st.columns(2)
            left.plotly_chart(charts.comparison_prices(row, LABELS, SUFFIXES), width="stretch",
                              config=PLOT_CONFIG)
            right.plotly_chart(charts.comparison_premiums(row, LABELS, SUFFIXES), width="stretch",
                               config=PLOT_CONFIG)

            def value(column: str, kind: str, suffix: str):
                v = row.get(f"{column}_{suffix}")
                if kind == "count":
                    return "No listings" if pd.isna(row.get(f"listing_rows_{suffix}")) else fmt.fmt_count(v)
                return {"usd": fmt.fmt_usd, "share": fmt.fmt_share, "num": fmt.fmt_number,
                        "pct": lambda x: fmt.fmt_pct(x, signed=True)}[kind](v)

            def premium_cell(suffix: str) -> str:
                if pd.isna(row.get(f"listing_rows_{suffix}")):
                    return "Unavailable: no listings"
                if row[f"premium_status_{suffix}"] == "available":
                    return fmt.fmt_pct(row[f"premium_pct_{suffix}"], signed=True)
                return "Unavailable: " + premium_reason(row[f"premium_status_{suffix}"], row[f"priced_rows_{suffix}"],
                                                        row[f"peer_priced_rows_{suffix}"], MIN_PRICED)

            measures = [("Listings (valid dimensions)", "listing_rows", "count"),
                        ("Priced listings", "priced_rows", "count"), ("Price coverage", "price_coverage", "share"),
                        ("Median", "median_price_usd", "usd"), ("P25", "p25_price_usd", "usd"),
                        ("P75", "p75_price_usd", "usd"), ("IQR", "price_iqr_usd", "usd"),
                        ("LA peer priced listings", "peer_priced_rows", "count"),
                        ("LA peer coverage", "peer_price_coverage", "share"),
                        ("LA peer median", "peer_median_price_usd", "usd"),
                        *[(f"Local {fmt.CONTEXT_LABELS[f].lower()} (median)", f"{f}_median", "num")
                          for f in CONTEXT_FIELDS],
                        ("Unknown-bedroom share, local neighbourhood/room", "local_unknown_bedroom_share", "share"),
                        ("Unknown-bedroom share, LA room type", "peer_unknown_bedroom_share", "share"),
                        ("City-scrape share (local)", "local_city_scrape_share", "share")]
            table = pd.DataFrame({
                "Measure": ["Premium vs LA peer"] + [m[0] for m in measures],
                LABELS[0]: [premium_cell(a)] + [value(c, k, a) for _, c, k in measures],
                LABELS[1]: [premium_cell(b)] + [value(c, k, b) for _, c, k in measures]})
            st.dataframe(table, hide_index=True, width="stretch")
            st.markdown("**Warnings**")
            show_warnings([w for w in (row["warnings"] or "").split("; ") if w])
        evidence_download("compare_evidence")
        methodology()

with shortlist_tab:
    if shortlist_tab.open:
        st.subheader("Review shortlist: persistent premiums and discounts")
        st.caption(f"{filter_caption()}. Ranks every known-bedroom segment under these filters, independently of the "
                   "sidebar segment. Score = smaller absolute premium of the two snapshots; context is not scored.")
        st.segmented_control("Direction", list(DIRECTION_OPTIONS), key="direction", required=True)
        direction = DIRECTION_OPTIONS[st.session_state["direction"] or "Both"]
        shortlist = rank_shortlist(comparison, direction)
        counts = comparison.persistence.value_counts()
        st.caption(" · ".join(f"{fmt.PERSISTENCE_LABELS[name]}: {int(counts.get(name, 0)):,}"
                              for name in fmt.PERSISTENCE_LABELS) + f" (of {len(comparison):,} segments)")
        if shortlist.empty:
            st.info("No segments meet the persistence and evidence rules for this direction and these filters. "
                    "An empty shortlist is a valid result; try lowering the minimum priced count or clearing "
                    "filters.", icon="ℹ️")
        else:
            st.session_state["_shortlist_keys"] = list(
                shortlist[["neighbourhood", "room_type", "bedroom_segment"]].itertuples(index=False, name=None))
            st.caption("Select a row to open it in Segment Detail. Stay, source and threshold settings are kept.")
            st.dataframe(fmt.shortlist_display(shortlist, LABELS), key="shortlist_table", hide_index=True,
                         on_select=_open_shortlist_row, selection_mode="single-row", width="stretch",
                         column_config={"Rank": st.column_config.NumberColumn(width="small"),
                                        "Segment": st.column_config.TextColumn(width="large"),
                                        "Warnings": st.column_config.TextColumn(width="large")})
        cols = st.columns(2)
        with cols[0]:
            st.download_button("Download visible shortlist (CSV)",
                               fmt.to_csv_bytes(fmt.shortlist_export(shortlist, VIEW, direction)),
                               file_name=f"review_shortlist_{direction}.csv", mime="text/csv", icon="⬇️")
        with cols[1]:
            st.caption(f"Selected segment: {fmt.segment_label(*SEGMENT)}")
            evidence_download("shortlist_evidence")
        methodology()

st.caption(fmt.ATTRIBUTION)
