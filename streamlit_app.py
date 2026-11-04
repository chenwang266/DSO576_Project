"""Streamlit Community Cloud entry point for the DSO 576 project."""
from pathlib import Path
import os
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from pricing_backend import (DATES, KEYS, BEDROOMS, CONTEXT, CAUTION, load_data,
                             filter_data, metrics, history, shortlist, warnings)

st.set_page_config(page_title='LA Airbnb · Pricing Review', page_icon='🏘️', layout='wide')
ROOT = Path(__file__).resolve().parent
DATA = Path(os.environ.get('AIRBNB_RAW_DIR', ROOT / 'data/raw'))

@st.cache_data(show_spinner='Validating the two LA snapshots…')
def cached_data(folder, fingerprints):
    return load_data(folder)

@st.cache_data(show_spinner=False)
def analyze(d, stay, source, minimum):
    filtered = filter_data(d, stay, source)
    m = metrics(filtered, minimum)
    return m, history(m)

st.title('Los Angeles Airbnb Pricing Review')
st.caption('DSO 576 · Inside Airbnb · March–June 2026')
st.write('Identify neighborhood–room–bedroom segments for human pricing review using advertised prices and repeated-snapshot evidence.')
try:
    paths = [DATA / f'listings-{date}.csv.gz' for date in DATES]
    fingerprints = tuple((str(p), p.stat().st_size, p.stat().st_mtime_ns) for p in paths)
    data, report = cached_data(str(DATA), fingerprints)
except (OSError, ValueError) as exc:
    st.error(f'Data setup required: {exc}')
    st.info('Keep both supplied listings-2026-03-16.csv.gz and listings-2026-06-15.csv.gz in data/raw/, or set AIRBNB_RAW_DIR to their folder.')
    st.stop()

def reset():
    for key in ['snapshot', 'neighbourhood', 'room', 'bedroom', 'stay', 'source', 'minimum', 'coverage', 'direction', 'selection']:
        st.session_state.pop(key, None)

def choose(label, options, preferred, key):
    return st.sidebar.selectbox(label, options, index=options.index(preferred) if preferred in options else 0, key=key)

st.sidebar.header('Review settings')
st.sidebar.button('Reset', on_click=reset)
snapshot = choose('Detail snapshot', list(DATES), DATES[1], 'snapshot')
known = data[data.eligible_dimensions]
if known.empty:
    st.warning('No listings have valid neighborhood, room type and bedroom dimensions.')
    st.stop()
hood = choose('Neighborhood', sorted(known.neighbourhood.unique()), 'Hollywood', 'neighbourhood')
room = choose('Room type', sorted(known.room_type.unique()), 'Entire home/apt', 'room')
bed = choose('Bedrooms', [x for x in BEDROOMS if x in set(known.bedroom_segment)], '1 bedroom', 'bedroom')
stay = choose('Minimum-night category', ['All'] + sorted(data.stay.unique()), 'All', 'stay')
source = choose('Source category', ['All'] + sorted(data.source.unique()), 'All', 'source')
minimum = st.sidebar.number_input('Minimum priced listings', min_value=1, max_value=10000, value=20, key='minimum')
coverage = st.sidebar.slider('Coverage warning (%)', 0, 100, 80, key='coverage') / 100
st.sidebar.caption('Thresholds are exploratory. The canonical small-sample flag always uses fewer than 20 priced listings.')
m, h = analyze(data, stay, source, minimum)
selection = dict(zip(KEYS, [hood, room, bed]))

def select(frame, seg):
    mask = pd.Series(True, index=frame.index)
    for key, value in seg.items():
        mask &= frame[key].eq(value)
    return frame.loc[mask]

def methodology():
    with st.expander('Data Quality & Methodology'):
        st.write('Source: Inside Airbnb, Los Angeles detailed listings. Peer benchmarks pool listings across all LA neighborhoods, including the selected neighborhood, with identical room, bedroom, stay and source filters.')
        st.write('Positive valid USD prices only; no caps or imputation. Coverage includes listings with valid dimensions and missing prices. Context uses its own valid observations, including rows without prices. Unknown dimensions are excluded from comparable segments.')
        st.write('Premium = 100 × (local median / inclusive LA peer median − 1). Both populations must meet the selected minimum. Persistence requires the same nonzero sign in both snapshots; score is the smaller absolute premium. Missing results remain unavailable.')
        st.warning(CAUTION)
        st.write('Repeated cross-sections: price changes are not matched-listing or causal effects. These results do not estimate optimal prices, occupancy, demand or revenue. Defaults follow BUILD_SPEC; team approval is not established.')
        st.json(report)

def download(frame, name):
    export = frame.copy()
    for k, v in {'stay_filter': stay, 'source_filter': source, 'minimum_priced': minimum,
                 'coverage_warning': coverage, 'march_snapshot': DATES[0], 'june_snapshot': DATES[1],
                 'peer_definition': 'All LA neighborhoods including selected neighborhood'}.items():
        export[k] = v
    st.download_button('Download ' + name.replace('_', ' '), export.to_csv(index=False).encode(), name + '.csv', 'text/csv', key=name)

def money(v):
    return 'Unavailable' if pd.isna(v) else f'${v:,.2f}'

def detail(seg, key):
    rows = select(m[m.snapshot_date.eq(snapshot)], seg)
    st.subheader(' · '.join(seg.values()))
    if rows.empty:
        st.info('No valid-dimension listings match this segment and these filters in the selected snapshot.')
        return
    r = rows.iloc[0]
    cols = st.columns(4)
    cols[0].metric('Median advertised price', money(r.median_price_usd))
    cols[1].metric('Price IQR', money(r.price_iqr_usd))
    cols[2].metric('Price coverage', f'{r.price_coverage:.1%}', help=f'{r.priced_rows} priced / {r.listing_rows} valid-dimension listings')
    cols[3].metric('Premium vs inclusive LA peer', 'Unavailable' if pd.isna(r.premium_pct) else f'{r.premium_pct:+.1f}%')
    if not r.sufficient_data:
        st.warning(f'Premium unavailable: both local and peer populations need at least {minimum} priced listings. Raw summary statistics remain visible.')
    st.warning(warnings(r, coverage))
    local = select(filter_data(data, stay, source), seg)
    prices = local.loc[local.snapshot_date.eq(snapshot), 'price_usd'].dropna()
    if len(prices):
        counts, bins = __import__('numpy').histogram(prices, bins=1 if prices.nunique() == 1 else 20)
        fig = go.Figure(go.Bar(x=(bins[:-1]+bins[1:])/2, y=counts, width=bins[1:]-bins[:-1]))
        fig.add_vline(x=float(prices.median()), line_dash='dash', annotation_text='Local median')
        fig.update_layout(xaxis_title='Advertised nightly price (USD)', yaxis_title='Priced listings', bargap=.04)
        st.plotly_chart(fig, width='stretch', key=key)
    else:
        st.info('No valid positive prices for a histogram.')
    comparison = []
    for metric in ['listing_rows', 'priced_rows', 'price_coverage', 'median_price_usd', 'p25_price_usd', 'p75_price_usd', 'is_small_sample'] + [c+s for c in CONTEXT for s in ['_median', '_valid_count']]:
        comparison.append({'metric': metric, 'Local': r[metric], 'Inclusive LA peer': r[metric+'_peer']})
    st.dataframe(pd.DataFrame(comparison).astype(str), hide_index=True, width='stretch')
    evidence = rows.copy()
    evidence['warnings'] = warnings(r, coverage)
    download(evidence, key + '_evidence')

first, second, third = st.tabs(['Segment Detail', 'March–June Comparison', 'Review Shortlist'])
with first:
    detail(selection, 'segment')
    methodology()
with second:
    st.subheader('Same segment across both snapshots')
    rows = select(h, selection)
    if rows.empty:
        st.info('This segment has no comparable listings in either snapshot with the current filters.')
    else:
        r = rows.iloc[0]
        a, b, c = st.columns(3)
        a.metric('March median', money(r.median_price_usd_march))
        b.metric('June median', money(r.median_price_usd_june))
        c.metric('June − March', money(r.change_usd), None if pd.isna(r.change_pct) else f'{r.change_pct:+.1f}%')
        st.write('Evidence classification: **' + r.persistence + '**')
        st.warning(warnings(r, coverage))
        st.dataframe(rows.T.astype(str), width='stretch')
        evidence = rows.copy()
        evidence['warnings'] = warnings(r, coverage)
        download(evidence, 'comparison_evidence')
    methodology()
with third:
    direction = st.selectbox('Review direction', ['Both', 'Premium', 'Discount'], key='direction')
    ranked = shortlist(h, coverage, direction)
    st.caption('All known-bedroom segments under the shared stay/source filters. Detail snapshot and detail segment do not restrict this ranking.')
    if ranked.empty:
        st.info('No segments have persistent qualifying premiums or discounts under these settings.')
    else:
        visible = ['rank', *KEYS, 'persistence', 'score'] + [x+s for s in ['_march', '_june'] for x in ['premium_pct', 'priced_rows', 'listing_rows', 'price_coverage']] + ['warnings']
        st.dataframe(ranked[visible], hide_index=True, width='stretch')
        download(ranked, 'review_shortlist')
        labels = [' · '.join(str(r[k]) for k in ['rank', *KEYS]) for _, r in ranked.iterrows()]
        label = st.selectbox('Open shortlist segment detail', labels)
        selected = ranked.iloc[labels.index(label)]
        detail({k:selected[k] for k in KEYS}, 'shortlist_segment')
    methodology()
