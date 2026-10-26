"""Independent raw-file oracle and real-data user interaction evidence.

Run after pytest. Writes aggregate evidence only; never exports listing IDs.
"""
import csv
import gzip
import hashlib
import json
import re
import sys
import time
from pathlib import Path
from statistics import median
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from streamlit.testing.v1 import AppTest
from src.data_access import ROOT, DATES, settings, load_data, fingerprint
from src.pricing import detail


def raw_oracle(path, neighborhood):
    # Separate csv reader, explicit loop, independent USD validation and median.
    prices, peer, count = [], [], 0
    with gzip.open(path, 'rt', encoding='utf-8', newline='') as handle:
        for row in csv.DictReader(handle):
            if row['room_type'] != 'Entire home/apt':
                continue
            try:
                bedroom = float(row['bedrooms'])
            except ValueError:
                continue
            if bedroom != 1:
                continue
            name = ' '.join(row['neighbourhood_cleansed'].split())
            if not name or name == 'Unknown':
                continue
            local = name == neighborhood
            if local:
                count += 1
            text = row['price'].strip()
            if not re.fullmatch(r'\$?(?:\d+|\d{1,3}(?:,\d{3})+)(?:\.\d{1,2})?', text):
                continue
            value = float(text.replace('$', '').replace(',', ''))
            if value <= 0:
                continue
            peer.append(value)
            if local:
                prices.append(value)
    return {'listings': count, 'priced': len(prices), 'median': median(prices),
        'coverage': len(prices) / count, 'peer_n': len(peer), 'peer_median': median(peer),
        'premium_pct': 100 * (median(prices) / median(peer) - 1)}


def source_digest():
    files = [ROOT / 'app.py'] + sorted((ROOT / 'src').glob('*.py')) + [ROOT / 'scripts/canonical_clean.py', ROOT / 'uv.lock']
    combined = hashlib.sha256()
    hashes = {}
    for path in files:
        key = path.relative_to(ROOT).as_posix()
        digest = fingerprint(path)
        hashes[key] = digest
        combined.update((key + ':' + digest + '\n').encode())
    return combined.hexdigest(), hashes


def main():
    config = settings()
    data, cleaning = load_data()
    independent = {}
    for neighborhood in ['Hollywood', 'Venice']:
        independent[neighborhood] = {}
        for date, key in zip(DATES, ['march', 'june']):
            expected = raw_oracle((ROOT / config[key]).resolve(), neighborhood)
            backend = detail(data, snapshot=date, neighbourhood=neighborhood,
                room_type='Entire home/apt', bedrooms=1)
            assert backend['local']['listing_rows'] == expected['listings']
            assert backend['local']['priced_rows'] == expected['priced']
            assert backend['local']['median_price_usd'] == expected['median']
            assert abs(backend['local']['price_coverage'] - expected['coverage']) < 1e-12
            assert backend['peer']['median_price_usd'] == expected['peer_median']
            assert abs(backend['premium_pct'] - expected['premium_pct']) < 1e-10
            independent[neighborhood][date] = expected
        baseline = independent[neighborhood][DATES[0]]['median']
        current = independent[neighborhood][DATES[1]]['median']
        independent[neighborhood]['expected_change_usd'] = current - baseline
        independent[neighborhood]['expected_change_pct'] = 100 * (current - baseline) / baseline

    start = time.perf_counter()
    app = AppTest.from_file(str(ROOT / 'app.py')).run(timeout=180)
    first_execution = time.perf_counter() - start
    assert not app.exception, str(app.exception)
    def displayed():
        return {item.label: item.value for item in app.metric}
    observations = []
    def record(step, neighborhood):
        values = displayed()
        expected = independent[neighborhood]
        assert values['March median'] == f"${expected[DATES[0]]['median']:,.2f}"
        assert values['June median'] == f"${expected[DATES[1]]['median']:,.2f}"
        assert values['Median change (USD)'] == f"${expected['expected_change_usd']:,.2f}"
        assert values['Median change (%)'] == f"{expected['expected_change_pct']:.1f}%"
        observations.append({'step': step, 'snapshot': app.selectbox(key='snapshot').value,
            'neighborhood': neighborhood, 'displayed_metrics': values})
    record('Initial June / Hollywood / Entire home/apt / 1 bedroom', 'Hollywood')
    app.selectbox(key='snapshot').set_value(DATES[0]).run(timeout=180)
    assert not app.exception
    assert displayed()['Local median'] == f"${independent['Hollywood'][DATES[0]]['median']:,.2f}"
    record('Switch detail snapshot to March; history must stay identical', 'Hollywood')
    app.selectbox(key='neighbourhood').set_value('Venice').run(timeout=180)
    assert not app.exception
    record('Switch neighborhood to Venice; both comparison dates update', 'Venice')
    app.button[0].click().run(timeout=180)
    assert not app.exception
    assert app.selectbox(key='snapshot').value == DATES[1]
    assert app.selectbox(key='neighbourhood').value == 'Hollywood'
    record('Reset restores June and Hollywood', 'Hollywood')
    digest, hashes = source_digest()
    result = {'status': 'PASS', 'source_bundle_sha256': digest, 'source_files': hashes,
        'rows': len(data), 'raw_unchanged': cleaning['raw_unchanged'],
        'input_sha256': cleaning['input_sha256'],
        'independent_raw_calculations': independent, 'app_interactions': observations,
        'first_apptest_execution_seconds': round(first_execution, 3),
        'limitations': ['AppTest exercises real Streamlit widgets and rendered element values, not browser pixel layout.',
            'No fresh-agent build test or production deployment performed.',
            'Timing is AppTest execution, not measured browser cold-load latency.']}
    destination = ROOT / 'audit_full_data_results.json'
    destination.write_text(json.dumps(result, indent=2, allow_nan=False), encoding='utf-8')
    print(json.dumps(result, indent=2, allow_nan=False))


if __name__ == '__main__':
    main()
