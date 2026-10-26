"""LA pricing review dashboard generated from the team's BUILD_SPEC.md."""
import json
import os
from pathlib import Path
import pandas as pd
import streamlit as st
from src.data_access import load_data, processed_dir, fingerprint, DATES, CONTEXT
from src.filters import filter_listings
from src.pricing import detail, segment_metrics
from src.history import snapshot_comparison, ranked_review_list
from src.charts import price_histogram

st.set_page_config(page_title='LA | Pricing Review', page_icon='↗', layout='wide')
st.markdown('''<style>
.stApp {background:#f6f8f7} h1,h2,h3 {color:#183a35}
[data-testid="stMetric"] {background:white;padding:16px;border-radius:10px;border:1px solid #dce5e1}
[data-testid="stSidebar"] {background:#eef3f0}
</style>''', unsafe_allow_html=True)


@st.cache_data(show_spinner=False)
def cached_data(directory, file_hash, report_hash):
    return load_data(directory)


@st.cache_data(show_spinner=False)
def cached_metrics(data, file_hash, minimum, stay, source):
    return segment_metrics(data, min_priced=minimum, stay=stay, source=source)


def money(value):
    return f'${value:,.2f}' if pd.notna(value) else 'Unavailable'


def percent(value):
    return f'{value:.1f}%' if pd.notna(value) else 'Unavailable'


def methodology(report):
    with st.expander('Data Quality & Methodology'):
        st.write('Source: Inside Airbnb Los Angeles detailed listings. Nominal snapshots: March 16 and June 15, 2026.')
        st.write('LA peer includes the selected neighborhood. Listings are pooled; neighborhood medians are not averaged.')
        st.write('Unknown dimensions are excluded from comparable segments. Missing prices are retained for coverage and valid context. No price caps or imputation.')
        st.write('These are repeated cross-sections, not matched-listing changes or causal effects. Availability is not occupancy. This tool does not estimate optimal prices, revenue or demand.')
        st.write('Bedroom coding/completeness changes can distort Studio comparisons; they are not evidence of supply changes.')
        st.write('Minimum counts and coverage warnings are exploratory team defaults; approval remains unconfirmed.')
        st.json(report['by_snapshot'])


def reset():
    for key in ['snapshot', 'neighbourhood', 'room', 'bedrooms', 'stay', 'source', 'minimum', 'coverage', 'direction']:
        st.session_state.pop(key, None)


directory = Path(os.environ.get('LA_DASHBOARD_DATA', str(processed_dir())))
try:
    file_hash = fingerprint(directory / 'canonical_listings_clean.csv')
    report_hash = fingerprint(directory / 'canonical_cleaning_report.json')
    data, report = cached_data(str(directory), file_hash, report_hash)
except (FileNotFoundError, ValueError, KeyError) as error:
    st.error(f'{error}. Setup: run uv run python scripts/canonical_clean.py from generated_dashboard.')
    st.stop()

st.caption('LOS ANGELES  /  MARKETPLACE STRATEGY')
st.title('Pricing review workspace')
st.write('Compare advertised prices. Follow the evidence. Prioritize human review.')
st.caption(f'{len(data):,} listing-snapshot rows · input fingerprint {file_hash[:12]}')

with st.sidebar:
    st.header('Review scope')
    st.button('Reset', on_click=reset)
    snapshot = st.selectbox('Snapshot', DATES, index=1, key='snapshot')
    neighborhoods = sorted(data.loc[data.valid_dimensions, 'neighbourhood'].unique().tolist())
    rooms = sorted(data.loc[data.valid_dimensions, 'room_type'].unique().tolist())
    bedrooms_values = sorted(int(x) for x in data.loc[data.valid_dimensions, 'bedrooms'].unique())
    if not neighborhoods or not rooms or not bedrooms_values:
        st.error('No validated comparable segments. Check source data and cleaning report.')
        st.stop()
    neighborhood = st.selectbox('Neighborhood', neighborhoods,
        index=neighborhoods.index('Hollywood') if 'Hollywood' in neighborhoods else 0, key='neighbourhood')
    room = st.selectbox('Room type', rooms, index=rooms.index('Entire home/apt') if 'Entire home/apt' in rooms else 0, key='room')
    bedrooms = st.selectbox('Bedrooms', bedrooms_values,
        index=bedrooms_values.index(1) if 1 in bedrooms_values else 0,
        format_func=lambda x: 'Studio' if x == 0 else '6+ bedrooms' if x == 6 else f'{x} bedroom' + ('s' if x != 1 else ''), key='bedrooms')
    stay_value = st.selectbox('Stay category', ['All'] + sorted(data.stay.unique().tolist()), key='stay')
    source_value = st.selectbox('Source category', ['All'] + sorted(data.source.unique().tolist()), key='source')
    minimum = int(st.number_input('Minimum priced count', min_value=1, value=20, step=1, key='minimum'))
    coverage_warning = st.slider('Coverage warning (%)', 0, 100, 80, key='coverage') / 100

stay, source = (None if stay_value == 'All' else stay_value), (None if source_value == 'All' else source_value)
scope = dict(neighbourhood=neighborhood, room_type=room, bedrooms=bedrooms, stay=stay, source=source)
metrics = cached_metrics(data, file_hash, minimum, stay, source)
comparison = snapshot_comparison(metrics)
selected = comparison.loc[comparison.neighbourhood.eq(neighborhood) & comparison.room_type.eq(room) & comparison.bedrooms.eq(bedrooms)]
warnings = ['Bedroom coding/completeness differs across snapshots; use care with Studio comparisons.',
            'Source composition can change across snapshots; optional filters apply equally to local and peer.']
detail_tab, comparison_tab, shortlist_tab = st.tabs(['Segment Detail', 'March–June Comparison', 'Review Shortlist'])

with detail_tab:
    st.subheader(f'{neighborhood} · {room} · ' + ('Studio' if bedrooms == 0 else f'{bedrooms} bedroom(s)'))
    info = detail(data, snapshot=snapshot, min_priced=minimum, **scope)
    local, peer = info['local'], info['peer']
    if not local['listing_rows']:
        st.warning('This selection has no comparable listings. Choose another segment or filter.')
    if not info['sufficient_data']:
        st.warning(f'Insufficient priced evidence: both local and peer require at least {minimum}. Raw summaries remain available; premium is suppressed.')
    if pd.notna(local['price_coverage']) and local['price_coverage'] < coverage_warning:
        st.warning('Price coverage below warning threshold. Listings are retained.')
    cols = st.columns(4)
    cols[0].metric('Local median', money(local['median_price_usd']))
    cols[1].metric('Local coverage', percent(local['price_coverage'] * 100))
    cols[2].metric('Price premium', percent(info['premium_pct']))
    cols[3].metric('Priced / listings', f"{local['priced_rows']} / {local['listing_rows']}")
    st.caption('LA peer includes the selected neighborhood; same room, bedroom, stay and source filters.')
    st.dataframe(pd.DataFrame({'Local': local, 'LA peer (inclusive)': peer}), width='stretch')
    prices = info['local_rows'].loc[info['local_rows'].pricing_eligible, 'price_usd']
    if prices.empty:
        st.info('No eligible prices for a histogram.')
    else:
        st.plotly_chart(price_histogram(prices, local['median_price_usd']), width='stretch')
    methodology(report)

with comparison_tab:
    st.subheader('Same segment, two snapshots')
    st.caption('The Snapshot selector affects Segment Detail only. Stay/source filters are identical across March and June.')
    for warning in warnings:
        st.warning(warning)
    if selected.empty:
        st.info('No segment evidence in either snapshot under these filters.')
    else:
        row = selected.iloc[0]
        columns = st.columns(4)
        columns[0].metric('March median', money(row.median_price_usd_march))
        columns[1].metric('June median', money(row.median_price_usd_june))
        columns[2].metric('Median change (USD)', money(row.change_usd))
        columns[3].metric('Median change (%)', percent(row.change_pct))
        st.write('Evidence status: ' + row.persistence)
        st.caption('Unavailable changes mean the baseline or opposite-date evidence is missing. Percent changes require a positive March median.')
        compare_columns = [c for c in selected.columns if c.endswith('_march') or c.endswith('_june')]
        st.dataframe(selected[compare_columns].T.rename(columns={selected.index[0]: 'Value'}), width='stretch')
        for suffix, label in [('march', 'March'), ('june', 'June')]:
            if pd.notna(row.get('priced_rows_' + suffix)) and row['priced_rows_' + suffix] < minimum:
                st.warning(f'{label}: insufficient priced evidence; premium, persistence and ranking suppressed.')
            if pd.notna(row.get('price_coverage_' + suffix)) and row['price_coverage_' + suffix] < coverage_warning:
                st.warning(f'{label}: price coverage below warning threshold.')
        evidence = selected.copy()
        evidence['march_date'], evidence['june_date'] = DATES
        evidence['minimum_priced'], evidence['coverage_warning'] = minimum, coverage_warning
        evidence['stay_filter'], evidence['source_filter'] = stay_value, source_value
        evidence['warnings'] = ' | '.join(warnings)
        evidence['canonical_sha256'] = file_hash
        st.download_button('Export selected evidence', evidence.to_csv(index=False).encode(),
            'selected_evidence.csv', 'text/csv')
    methodology(report)

with shortlist_tab:
    st.subheader('Persistent patterns for human review')
    st.caption('All known-bedroom segments are ranked independently of the detail selection. Context is explanatory, not scored.')
    direction = st.selectbox('Direction', ['Both', 'Premium', 'Discount'], key='direction')
    ranked = ranked_review_list(comparison, direction)
    if ranked.empty:
        st.info('No persistent segments meet these evidence settings. An empty shortlist is valid.')
    else:
        export = ranked.copy()
        export['march_date'], export['june_date'] = DATES
        export['minimum_priced'], export['coverage_warning'] = minimum, coverage_warning
        export['stay_filter'], export['source_filter'] = stay_value, source_value
        export['warnings'], export['canonical_sha256'] = ' | '.join(warnings), file_hash
        shown = st.dataframe(export, width='stretch', on_select='rerun', selection_mode='single-row', key='shortlist')
        if shown.selection.rows:
            selected_rank = ranked.iloc[shown.selection.rows[0]]
            st.write('Selected segment evidence (stay/source filters preserved)')
            st.dataframe(export.iloc[shown.selection.rows].T)
            def open_detail():
                st.session_state['neighbourhood'] = selected_rank.neighbourhood
                st.session_state['room'] = selected_rank.room_type
                st.session_state['bedrooms'] = int(selected_rank.bedrooms)
            st.button('Open selected segment in Detail', on_click=open_detail)
        st.download_button('Export visible shortlist', export.to_csv(index=False).encode(), 'review_shortlist.csv', 'text/csv')
    methodology(report)
