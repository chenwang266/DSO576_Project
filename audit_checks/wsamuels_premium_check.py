"""Independent check of the segment premium and review score (Will Samuels audit).

Written from BUILD_SPEC.md sections 2-3 directly from the raw Inside Airbnb files.
It does not import or copy phase2/analysis.py, so agreement is real corroboration.

Usage:
    python audit_checks/wsamuels_premium_check.py MARCH.csv.gz JUNE.csv.gz
    python audit_checks/wsamuels_premium_check.py --toy      # spec's hand-calculable case only
"""
import re
import sys

import numpy as np
import pandas as pd

ROOMS = {'Entire home/apt', 'Private room', 'Shared room', 'Hotel room'}
PRICE = re.compile(r'^\$?\d{1,3}(,\d{3})*(\.\d+)?$|^\$?\d+(\.\d+)?$')
MIN_PRICED = 20


def parse_price(s):
    s = s.strip()
    if not s:
        return np.nan
    if not PRICE.match(s):
        return np.nan
    v = float(s.replace('$', '').replace(',', ''))
    return v if v > 0 else np.nan


def bedroom_segment(s):
    s = s.strip()
    if not re.fullmatch(r'\d+(\.0+)?', s):
        return 'Unknown'
    n = int(float(s))
    return 'Studio' if n == 0 else ('6+' if n >= 6 else str(n))


def load(path):
    d = pd.read_csv(path, dtype=str, keep_default_na=False)
    out = pd.DataFrame({
        'id': d['id'].str.strip(),
        'hood': d['neighbourhood_cleansed'].str.split().str.join(' ').replace('', 'Unknown'),
        'room': d['room_type'].str.strip().where(d['room_type'].str.strip().isin(ROOMS), 'Unknown'),
        'beds': d['bedrooms'].map(bedroom_segment),
        'price': d['price'].map(parse_price),
    })
    assert out.id.ne('').all() and not out.id.duplicated().any()
    return out


def summarize(prices):
    p = pd.Series(prices).dropna()
    if p.empty:
        return dict(n=0, median=np.nan, p25=np.nan, p75=np.nan)
    return dict(n=len(p), median=np.median(p),
                p25=np.percentile(p, 25), p75=np.percentile(p, 75))  # numpy default = linear


def premium(local_prices, peer_prices, min_priced=MIN_PRICED):
    loc, peer = summarize(local_prices), summarize(peer_prices)
    if loc['n'] < min_priced or peer['n'] < min_priced or not peer['median'] > 0:
        return loc, peer, np.nan
    return loc, peer, 100 * (loc['median'] / peer['median'] - 1)


def segment(df, hood, room, beds):
    valid = df[(df.hood != 'Unknown') & (df.room != 'Unknown') & (df.beds != 'Unknown')]
    local = valid[(valid.hood == hood) & (valid.room == room) & (valid.beds == beds)]
    peer = valid[(valid.room == room) & (valid.beds == beds)]  # includes selected hood
    loc, pr, prem = premium(local.price, peer.price)
    loc['listings'] = len(local)
    loc['coverage'] = loc['n'] / len(local) if len(local) else np.nan
    return loc, pr, prem, len(peer)


def persistence(m, j):
    if np.isnan(m) or np.isnan(j):
        return 'Insufficient evidence', np.nan
    if m > 0 and j > 0:
        return 'Persistent premium', min(abs(m), abs(j))
    if m < 0 and j < 0:
        return 'Persistent discount', min(abs(m), abs(j))
    if m == 0 or j == 0:
        return 'Neutral', np.nan
    return 'Reversed', np.nan


def pct(x):
    return 'unavailable' if np.isnan(x) else f'{x:+.6f}%'


def toy():
    # BUILD_SPEC section 6 numeric check: local [100,200,missing], others [300,400]
    local = [100, 200, np.nan]
    peer = local + [300, 400]
    loc, pr, prem = premium(local, peer, min_priced=2)
    prem20 = premium(local, peer)[2]
    print('STEP 1: hand-calculated example from BUILD_SPEC section 6')
    print('  Local prices [100, 200, missing]; other neighborhoods [300, 400]')
    print(f'  {"":24}{"expected":>12}{"script":>14}')
    for label, want, got in [('Local median', '150', f'{loc["median"]:g}'),
                             ('Local P25', '125', f'{loc["p25"]:g}'),
                             ('Local P75', '175', f'{loc["p75"]:g}'),
                             ('Coverage', '2/3', f'{loc["n"]}/{len(local)}'),
                             ('Peer median (inclusive)', '250', f'{pr["median"]:g}'),
                             ('Premium, threshold 2', '-40%', f'{prem:g}%'),
                             ('Premium, threshold 20', 'unavailable', pct(prem20))]:
        print(f'  {label:24}{want:>12}{got:>14}')
    assert (loc['median'], loc['p25'], loc['p75'], pr['median']) == (150, 125, 175, 250)
    assert abs(prem - -40) < 1e-12 and np.isnan(prem20)
    print('  PASS: all values match the spec\n')


if __name__ == '__main__':
    toy()
    if len(sys.argv) != 3:
        print('Pass the March and June raw files to also run STEP 2 on real data.')
        sys.exit()
    snaps = {'March': load(sys.argv[1]), 'June': load(sys.argv[2])}
    print('STEP 2: raw file counts (spec reference: rows 46,088/43,751, missing prices '
          '8,910/5,565, missing bedrooms 3,196/9,572)')
    for name, df in snaps.items():
        print(f'  {name:6} rows {len(df):,}   missing/invalid price {df.price.isna().sum():,}   '
              f'unknown bedrooms {(df.beds == "Unknown").sum():,}')
    print('\nSTEP 3: premium = 100 x (local median / LA peer median - 1); '
          'compare "premium" with the team CSV')
    for seg in [('Hollywood', 'Entire home/apt', '1'), ('Avalon', 'Entire home/apt', '1'),
                ('Venice', 'Private room', '1'), ('Santa Monica', 'Private room', '1')]:
        print(f'\n  {seg[0]} / {seg[1]} / {seg[2]} bedroom')
        print(f'    {"":7}{"listings":>9}{"priced":>8}{"coverage":>10}{"median $":>10}'
              f'{"peer priced":>13}{"peer median $":>15}{"premium":>14}')
        prems = {}
        for name, df in snaps.items():
            loc, pr, prem, peer_rows = segment(df, *seg)
            prems[name] = prem
            print(f'    {name:7}{loc["listings"]:>9,}{loc["n"]:>8,}{loc["coverage"]:>10.1%}'
                  f'{loc["median"]:>10.2f}{pr["n"]:>13,}{pr["median"]:>15.2f}{pct(prem):>14}')
        status, score = persistence(prems['March'], prems['June'])
        score = 'n/a' if np.isnan(score) else f'{score:.6f}'
        print(f'    Result: {status}; review score (smaller of the two |premiums|) = {score}')
