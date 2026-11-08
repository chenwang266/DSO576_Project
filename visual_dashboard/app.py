"""Los Angeles Airbnb pricing review — final submission interface."""
import json
import pandas as pd
import streamlit as st
from src.config import BEDROOM_ORDER, DATES, processed_dir, settings
from src.data_access import fingerprint, load_data
from src.filters import local_population
from src.history import comparison, shortlist
from src.pricing import CONTEXT
from src.charts import (distribution, price_band, price_comparison, premium_comparison,
                        context_comparison, evidence_coverage, bedroom_completeness,
                        priority_bars, persistence_map, pattern_counts, segment_label)

st.set_page_config(page_title="LA · Pricing Review", page_icon="◈", layout="wide")
st.markdown('''<style>
.block-container{padding-top:4.2rem;max-width:1450px;padding-bottom:3rem}
h1{font-size:2.5rem!important;letter-spacing:-.045em;font-weight:750!important}
h2,h3{letter-spacing:-.025em} [data-testid="stMetric"]{background:white;border:1px solid #dfe7ef;border-radius:14px;padding:16px 18px}
[data-testid="stMetricLabel"]{color:#586e83} [data-testid="stMetricValue"]{font-size:1.85rem}
[data-baseweb="tab-list"]{gap:18px;border-bottom:1px solid #dce5ee;margin-bottom:18px}
[data-testid="stSidebar"]{border-right:1px solid #dfe7ef}
.eyebrow{font-size:11px;font-weight:750;letter-spacing:.16em;color:#087f8c;margin:0 0 8px}.subtitle{color:#587087;font-size:16px;max-width:860px;margin-bottom:25px}
@media(max-width:700px){.block-container{padding:4rem 1rem} h1{font-size:1.9rem!important}}
</style>''', unsafe_allow_html=True)

@st.cache_data(show_spinner="Validating canonical data…")
def cached_load(directory, content_hash):
    return load_data(directory)

@st.cache_data(show_spinner="Calculating comparable segments…")
def cached_comparison(directory, content_hash, stay, source, minimum, coverage):
    frame, _ = cached_load(directory, content_hash)
    return comparison(frame, stay, source, minimum, coverage)

def money(value):
    return f"${value:,.2f}" if pd.notna(value) else "Unavailable"

def percent(value):
    return f"{value:+.1f}%" if pd.notna(value) else "Unavailable"

def coverage_text(value):
    return f"{value:.1%}" if pd.notna(value) else "Unavailable"

def count(value):
    return f"{value:,.0f}" if pd.notna(value) else "Unavailable"

def evidence_csv(frame):
    # Deliberately no display rounding; exports retain complete numeric precision.
    return frame.to_csv(index=False).encode("utf-8-sig")

try:
    config = settings()
    directory = str(processed_dir())
    content_hash = fingerprint(directory)
    data, report = cached_load(directory, content_hash)
except (ValueError, OSError, KeyError) as exc:
    st.title("LA Pricing Review")
    st.error(str(exc))
    st.code("uv run python scripts/canonical_clean.py --march data/raw/listings-2026-03-16.csv.gz --june data/raw/listings-2026-06-15.csv.gz --output-dir data/processed")
    st.stop()

def reset():
    for key, value in dict(snapshot=DATES[1], neighbourhood="Hollywood", room="Entire home/apt", bedroom="1 bedroom", stay="All stays", source="All sources", minimum=config["min_priced"], coverage=int(config["coverage_warning"]*100), direction="Both").items():
        st.session_state[key]=value
    st.session_state.pop("shortlist_selection", None)
    st.session_state["review_focus"]=None

if "snapshot" not in st.session_state:
    reset()

def selector(label, options, key):
    if st.session_state.get(key) not in options:
        st.warning(f"Requested {label.lower()} is unavailable in this dataset; choose an available value.")
        st.session_state[key] = options[0]
    return st.selectbox(label, options, key=key)

with st.sidebar:
    st.markdown("### Review controls")
    st.caption("One comparable segment · two snapshots")
    snapshot=selector("Detail snapshot", list(DATES), "snapshot")
    neighbourhood=selector("Neighborhood", sorted(data.loc[data.neighbourhood_is_known,"neighbourhood"].unique()), "neighbourhood")
    room=selector("Room type", sorted(data.loc[data.room_type_is_known,"room_type"].unique()), "room")
    bedroom=selector("Bedrooms", [b for b in BEDROOM_ORDER if b in set(data.bedroom_segment)], "bedroom")
    st.divider()
    stay=selector("Minimum stay cohort", ["All stays"] + sorted(data.stay_type.unique()), "stay")
    source=selector("Source category", ["All sources"] + sorted(data.source.unique()), "source")
    minimum=st.number_input("Minimum priced count", min_value=1, max_value=10000, step=1, key="minimum")
    coverage=st.slider("Coverage warning (%)", 0, 100, key="coverage")
    st.caption("Exploratory thresholds; the fixed small-sample flag is always <20 priced listings.")
    st.button("Reset to defaults", on_click=reset, use_container_width=True)
    st.divider()
    st.caption("Inside Airbnb · Los Angeles\n\n16 March & 15 June 2026")

stay_filter=None if stay=="All stays" else stay
source_filter=None if source=="All sources" else source
compared=cached_comparison(directory, content_hash, stay_filter, source_filter, minimum, coverage/100)
# Every exported evidence row identifies the precise canonical build.
compared["canonical_fingerprint"] = content_hash
selected=compared.loc[compared.neighbourhood.eq(neighbourhood) & compared.room_type.eq(room) & compared.bedroom_segment.eq(bedroom)]
row=selected.iloc[0] if len(selected) else None
label="march" if snapshot==DATES[0] else "june"

st.markdown('<p class="eyebrow">DSO 576 · MARKETPLACE STRATEGY</p>',unsafe_allow_html=True)
st.title("Los Angeles Pricing Review")
st.markdown('<p class="subtitle">Find persistent advertised price patterns. Check comparable listings, evidence coverage, and source context before prioritizing a human review.</p>',unsafe_allow_html=True)
a,b,c=st.columns([3,2,2])
a.markdown(f"**{neighbourhood}** · {room} · {bedroom}")
b.caption(f"Stay: {stay} · Source: {source}")
c.caption(f"Evidence minimum: {minimum} · Coverage warning: {coverage}%")
st.caption("Advertised price patterns for human review · LA peers include this neighborhood · Explore definitions and limits under Data Quality & Methodology.")

def methodology(key):
    with st.expander("Data Quality & Methodology"):
        st.markdown("**Source:** [Inside Airbnb](https://insideairbnb.com/get-the-data/) Los Angeles detailed listings, supplied March 16 and June 15, 2026 extracts. Nominal snapshot dates are preserved separately from actual scrape dates.")
        quality=[]
        for item in report["inputs"]:
            quality.append({"Snapshot":item["snapshot_date"], "Listing rows":item["clean_rows"], "Missing prices":item["missing_price_rows"], "Invalid/malformed prices":item["malformed_or_invalid_price_rows"],"Unknown bedrooms (excluded from comparable segments)":item["unknown_bedroom_rows"],"Recorded Studio zeros":item["zero_bedroom_rows"],"Actual scrape dates":", ".join(item["actual_scrape_dates"])})
        st.dataframe(pd.DataFrame(quality),hide_index=True,use_container_width=True)
        st.markdown("**Peer benchmark:** pooled listing-level prices from all LA neighborhoods with the same room type and bedroom group, including the selected neighborhood, with identical stay/source filters. Context uses each measure’s valid observations, including listings with missing prices.")
        st.markdown("**Policies:** retain missing-price rows and every positive price, including extremes; no imputation or cap. Unknown dimensions are retained in canonical data but excluded from comparable segments. Zero bedrooms = Studio; missing bedrooms = Unknown; ≥6 = 6+. Quartiles use linear interpolation. Missing results remain unavailable.")
        st.markdown("**Evidence:** fixed small sample = fewer than 20 valid prices. Adjustable minimum controls premiums and persistence only. Coverage warnings do not remove rows. Persistent means the same nonzero premium/discount direction in both dates; score is the smaller absolute premium. Thresholds are exploratory, not statistical significance.")
        st.markdown("**Limitations:** repeated cross-sections, not matched listings. Bedroom coding/completeness changes can distort Studio and private-room comparisons. Bedroom warnings use ≥25% unknown or a ≥10 percentage-point deterioration (proposed defaults). Previous-scrape categories and actual dates may affect comparisons. Context is explanatory and never scored. No team approval is implied; see DECISIONS.md.")
        st.caption(f"Canonical content fingerprint: {content_hash}")
        st.download_button("Download cleaning and provenance report", json.dumps(report,indent=2), "canonical_cleaning_report.json", "application/json", key=f"report_{key}")

# Distinct explicit keys avoid cross-tab identity collisions.
def quality_panel(key):
    with st.container(key=key):
        methodology(key)

def context_table(r, period):
    values=[]
    labels={"availability_90":"Availability · next 90 days", "reviews_ltm":"Reviews · last 12 months", "value_score":"Review value · 0–5", "minimum_nights":"Minimum nights"}
    for metric in CONTEXT:
        local=r.get(f"{metric}_median_{period}")
        peer=r.get(f"peer_{metric}_median_{period}")
        values.append({"Measure":labels[metric],"Local median":f"{local:,.2f}" if pd.notna(local) else "Unavailable","Local valid n":count(r.get(f"{metric}_valid_n_{period}")),"LA peer median":f"{peer:,.2f}" if pd.notna(peer) else "Unavailable","Peer valid n":count(r.get(f"peer_{metric}_valid_n_{period}"))})
    return pd.DataFrame(values)

def show_warnings(r, period=None):
    parts=r['warnings'].split(" | ")
    if period:
        other="June" if period=="march" else "March"
        parts=[p for p in parts if not p.startswith(other) and 'deteriorated' not in p]
    issues=[p for p in parts if not p.startswith("No row-specific")]
    threshold_issues=[p for p in issues if "minimum evidence" in p or "segment absent" in p]
    coverage_issues=[p for p in issues if "price coverage" in p]
    bedroom_issues=[p for p in issues if 'bedroom' in p.lower() or 'Studio coding' in p]
    if threshold_issues:
        st.warning("Evidence limit: " + " ".join(threshold_issues))
    if coverage_issues:
        st.warning("Coverage needs attention: " + " ".join(coverage_issues))
    if bedroom_issues:
        st.warning("Bedroom composition needs attention. Unknown-bedroom exclusions or Studio coding changes can distort this comparison; inspect the composition chart and quality notes.")
    if issues:
        with st.expander(f"Quality notes · {len(issues)} checks to consider"):
            for issue in issues:st.markdown(f"- {issue}")
    else:
        st.caption("No row-specific quality warning at the current settings.")


def plot(fig, key):
    st.plotly_chart(fig, use_container_width=True, key=key, config={"displaylogo":False})


def detail_tables(r, period):
    records=[]
    for prefix,name in [("","This segment"),("peer_","LA peer · includes local")]:
        records.append({"Population":name,"Listings":count(r[f'{prefix}listing_rows_{period}']),"Priced":count(r[f'{prefix}priced_rows_{period}']),"Coverage":coverage_text(r[f'{prefix}price_coverage_{period}']),"Median":money(r[f'{prefix}median_price_usd_{period}']),"P25":money(r[f'{prefix}p25_price_usd_{period}']),"P75":money(r[f'{prefix}p75_price_usd_{period}'])})
    st.dataframe(pd.DataFrame(records),hide_index=True,use_container_width=True)
    st.dataframe(context_table(r,period),hide_index=True,use_container_width=True)


segment_tab,compare_tab,review_tab=st.tabs(["01  Segment Detail", "02  March–June Comparison", "03  Review Shortlist"])
with segment_tab:
    st.subheader(f"Observed pricing · {snapshot}")
    if row is None or pd.isna(row.get(f"listing_rows_{label}")):
        st.warning("No known-dimension listings match this segment and these filters in the selected snapshot. Choose another segment or broaden stay/source filters.")
    else:
        cols=st.columns(5)
        cols[0].metric("Listings / priced",f"{count(row[f'listing_rows_{label}'])} / {count(row[f'priced_rows_{label}'])}")
        cols[1].metric("Price coverage",coverage_text(row[f'price_coverage_{label}']))
        cols[2].metric("Median price (USD)",money(row[f'median_price_usd_{label}']))
        cols[3].metric("Price IQR (USD)",money(row[f'price_iqr_usd_{label}']))
        cols[4].metric("Relative to LA peer",percent(row[f'premium_pct_{label}']))
        premium=row[f'premium_pct_{label}']
        if pd.notna(premium):
            position="above" if premium>0 else "below" if premium<0 else "equal to"
            message=f"**What stands out:** the local median is {abs(premium):.1f}% {position} the LA peer median." if premium else "**What stands out:** the local and LA peer medians are equal."
            st.markdown(message+f" Valid prices are available for {count(row[f'priced_rows_{label}'])} of {count(row[f'listing_rows_{label}'])} comparable listings.")
        else:st.caption(f"Premium unavailable: {row[f'premium_unavailable_reason_{label}']}")
        left,right=st.columns(2)
        with left:
            st.markdown("#### Where do prices sit?")
            population=local_population(data,snapshot,neighbourhood,room,bedroom,stay_filter,source_filter)
            plot(distribution(population.price_usd.dropna(),row[f'median_price_usd_{label}']),"detail_distribution")
            st.caption("20 bins across the full positive price range. Dashed line = median; extremes remain included.")
        with right:
            st.markdown("#### How does this segment compare?")
            plot(price_band(row,label),"detail_price_band")
            st.caption("Diamond = median; band = middle 50% (P25–P75), not a confidence interval. The peer pools LA listings with the same room and bedroom group.")
        st.markdown("#### What is the surrounding context?")
        plot(context_comparison(row,label),"detail_context")
        st.caption("Each panel has its own units and starts at zero. Hover for valid observation counts. Availability is not occupancy; context does not affect the review score.")
        st.markdown("#### How much price evidence is available?")
        plot(evidence_coverage(row,label,coverage/100),"detail_coverage")
        show_warnings(row,label)
        with st.expander("Supporting numbers · benchmark and context"):
            detail_tables(row,label)
        st.download_button("Export segment evidence",evidence_csv(selected),"selected_segment_evidence.csv","text/csv",key="detail_export")
    quality_panel("detail_quality")
with compare_tab:
    st.subheader("What changed between March and June?")
    st.caption("Both dates use the same segment and stay/source filters. The detail snapshot selector does not change this comparison.")
    if row is None:
        st.warning("No comparable segment exists under these filters in either date.")
    else:
        cols=st.columns(3)
        cols[0].metric("Median change · June − March",money(row.change_usd))
        cols[1].metric("Change / March median",percent(row.change_pct))
        cols[2].metric("Persistence",row.persistence_status)
        if pd.notna(row.change_usd):
            movement="rose" if row.change_usd>0 else "fell" if row.change_usd<0 else "was unchanged"
            st.markdown(f"**Read the change:** the local median {movement} from **{money(row.median_price_usd_march)}** to **{money(row.median_price_usd_june)}**. The price pattern is **{row.persistence_status.lower()}**.")
        left,right=st.columns(2)
        with left:
            st.markdown("#### Price levels and spread")
            plot(price_comparison(row),"comparison_price")
            st.caption("Points = medians; whiskers = middle 50% of prices, not uncertainty. Two repeated snapshots, not a monthly time series.")
        with right:
            st.markdown("#### Premium or discount in each snapshot")
            plot(premium_comparison(row),"comparison_premium")
            st.caption("Right of zero = above the same-date peer; left = below. Failed evidence thresholds remain unavailable.")
        left,right=st.columns(2)
        with left:
            st.markdown("#### Is the price evidence comparable?")
            plot(evidence_coverage(row,threshold=coverage/100),"comparison_coverage")
            st.caption("Hover to see priced/listing counts. The dashed threshold warns without removing records.")
        with right:
            st.markdown("#### Did bedroom completeness change?")
            plot(bedroom_completeness(row),"comparison_bedrooms")
            st.caption("Unknown bedrooms are excluded from comparable segments. These shares use the population before bedroom exclusions, not just this bedroom group.")
        with st.expander("Explore how context changed"):
            plot(context_comparison(row),"comparison_context")
            st.caption("Local and peer medians under identical filters; hover for each measure’s valid observation count.")
        show_warnings(row)
        st.download_button("Export selected segment evidence",evidence_csv(selected),"selected_segment_evidence.csv","text/csv",key="selected_evidence")
        with st.expander("Supporting numbers · March and June"):
            for period in ["march","june"]:
                st.markdown(f"**{period.title()}**")
                detail_tables(row,period)
        with st.expander("Complete comparison evidence · full precision"):
            st.dataframe(selected.T.rename(columns={selected.index[0]:"Value"}).astype(str),use_container_width=True)
    quality_panel("comparison_quality")
with review_tab:
    st.subheader("Which segments need a closer look?")
    st.caption("Review all LA neighborhood × room × bedroom groups under the shared stay/source filters. Your detail segment does not restrict this list.")
    with st.expander("Market pattern overview · all shared filters"):
        plot(pattern_counts(compared),"review_patterns")
        st.caption("Counts are segments, not listings. Includes groups present in only one date. This overview is independent of the direction selection below.")
    direction=st.radio("Pattern direction",["Both","Premium","Discount"],horizontal=True,key="direction")
    ranked=shortlist(compared,direction)
    cols=st.columns(3)
    cols[0].metric("Segments to review",f"{len(ranked):,}")
    cols[1].metric("Persistent premiums",f"{int(ranked.direction.eq('Premium').sum()):,}")
    cols[2].metric("Persistent discounts",f"{int(ranked.direction.eq('Discount').sum()):,}")
    st.caption(f"{len(ranked):,} qualifying segments · score = min(|March premium|, |June premium|), in percentage points. Larger scores mean a larger repeated price gap, not a recommended price change.")
    if ranked.empty:
        st.info("No persistent segments meet the selected evidence criteria. An empty shortlist is a valid result; broaden filters or lower the exploratory minimum if appropriate.")
    else:
        st.markdown("#### Start with the largest repeated price gaps")
        top_n=st.select_slider("Segments shown in priority chart",options=[5,10,15,20],value=10,key="priority_limit")
        plot(priority_bars(ranked,top_n),"review_priority")
        st.caption(f"Showing the first {min(top_n,len(ranked))} of {len(ranked)} ranked segments, in score order. Bars retain their signs: premium to the right, discount to the left. Hover for counts and score.")
    st.markdown("#### Did the pattern repeat in both snapshots?")
    plot(persistence_map(compared,direction),"review_persistence")
    eligible=compared.dropna(subset=['premium_pct_march','premium_pct_june'])
    st.caption(f"Each point is a segment with qualifying premiums in both dates ({len(eligible):,} before the direction filter). Upper right = persistent premium; lower left = persistent discount; opposite quadrants = reversed. Unavailable premiums are omitted, never placed at zero. Hover or zoom to explore.")
    st.session_state['_ranked_keys']=ranked[["neighbourhood","room_type","bedroom_segment"]].to_dict("records")
    def select_shortlist_row():
        event=st.session_state.get("shortlist_selection",{})
        selection=event.get("selection",{}).get("rows",[])
        if selection and selection[0]<len(st.session_state['_ranked_keys']):
            keys=st.session_state['_ranked_keys'][selection[0]]
            st.session_state.neighbourhood=keys['neighbourhood']
            st.session_state.room=keys['room_type']
            st.session_state.bedroom=keys['bedroom_segment']
    def inspect_choice():
        i=st.session_state.get('review_focus')
        if i is not None and i<len(st.session_state['_ranked_keys']):
            keys=st.session_state['_ranked_keys'][i]
            st.session_state.neighbourhood=keys['neighbourhood']
            st.session_state.room=keys['room_type']
            st.session_state.bedroom=keys['bedroom_segment']
    if not ranked.empty:
        scope=(stay,source,minimum,coverage,direction)
        if st.session_state.get('_review_scope')!=scope:
            st.session_state['review_focus']=None
            st.session_state['_review_scope']=scope
        labels=segment_label(ranked).tolist()
        st.selectbox("Inspect a shortlisted segment",options=list(range(len(ranked))),index=None,placeholder="Choose a segment to open its detail",format_func=lambda i:f"#{i+1} · {labels[i]}",key="review_focus",on_change=inspect_choice)
        compact=ranked[['rank','direction','review_score','price_coverage_march','price_coverage_june']].copy()
        compact.insert(1,'Segment',labels)
        compact['warnings']=ranked.warnings
        with st.expander(f"Browse the shortlist · {len(ranked):,} segments"):
            st.caption("Select a row using its checkbox to update Segment Detail. Warnings, context and all denominators are available in the selected evidence and export.")
            st.dataframe(compact,hide_index=True,use_container_width=True,height=390,on_select=select_shortlist_row,selection_mode='single-row',key='shortlist_selection',column_config={'rank':'Rank','direction':'Pattern','warnings':st.column_config.TextColumn('Row quality notes',width='large'),'review_score':st.column_config.NumberColumn('Score (pp)',format='%.1f'),'price_coverage_march':st.column_config.ProgressColumn('March price coverage',format='percent',min_value=0,max_value=1),'price_coverage_june':st.column_config.ProgressColumn('June price coverage',format='percent',min_value=0,max_value=1)})
    if row is not None:
        st.markdown(f"#### Selected evidence · {neighbourhood} · {bedroom}")
        st.caption(f"{room} · {row.persistence_status} · March {percent(row.premium_pct_march)} / June {percent(row.premium_pct_june)}")
        show_warnings(row)
        st.download_button("Export selected review evidence",evidence_csv(selected),"selected_review_evidence.csv","text/csv",key="review_evidence")
        with st.expander("Selected segment · complete evidence"):
            st.dataframe(selected,hide_index=True,use_container_width=True)
    st.download_button("Export visible shortlist · all evidence columns",evidence_csv(ranked),"la_review_shortlist.csv","text/csv",key="shortlist_export")
    with st.expander("Full shortlist context & evidence"):
        st.dataframe(ranked,hide_index=True,use_container_width=True)
    quality_panel("shortlist_quality")
st.divider()
st.caption("DSO 576 · Inside Airbnb Los Angeles · March–June 2026 · Human review support. Advertised prices do not establish optimal pricing, occupancy, demand, revenue or causal effects.")
