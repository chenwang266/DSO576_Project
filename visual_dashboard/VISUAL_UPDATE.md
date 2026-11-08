# Visual analytics revision — November 4, 2026

The instructor requested more analysis charts and a more approachable customer experience. This revision changes the presentation of existing evidence; the canonical inputs, pricing definitions and audit fixes remain intact.

## Questions answered visually

| Customer question | Visualization | Evidence / interpretation |
| --- | --- | --- |
| Where do prices sit? | Full-range histogram | 20 equal-width bins, one for constant prices; no positive-price clipping |
| How does the local segment compare? | Median diamond + P25–P75 band | Actual price distribution spread, explicitly not a confidence interval |
| What is the surrounding context? | Four comparisons on separate scales | Availability, recent reviews, review value and minimum nights; valid counts on hover |
| What changed across snapshots? | Median comparison with P25–P75 whiskers | Two repeated cross-sections; no invented monthly observations |
| Did the relative price gap repeat? | Signed March/June horizontal bars | Same-date inclusive LA peer is zero; failed evidence is unavailable |
| Is price evidence comparable? | Stacked valid/unavailable price coverage | Exact priced/listing counts on hover; adjustable warning line |
| Did bedroom completeness change? | Local/peer unknown-bedroom share bars | Pre-bedroom population denominator; Studio remains distinct from Unknown |
| Which segments should be reviewed first? | Ranked March/June grouped bars | Top 5/10/15/20; same transparent backend score; original signs retained |
| How consistent are price patterns? | March premium × June premium scatter | One segment per point; unavailable premiums omitted, never replaced with zero |
| How much of the market qualifies? | Five-status count chart | Segment counts, including insufficient evidence; independent of direction selection |

## Customer flow

Start with a plain-language question, key metrics and a computed takeaway. Use charts to compare levels, changes and evidence. Hover for supporting denominators and exact values. Wide tables and raw field names are behind expandable evidence panels. Exports retain full precision and complete warnings. Critical coverage/evidence/composition cautions remain visible; repeated source details are grouped in quality notes.

Both the Python Streamlit app and a buildless public Sites companion implement this approach. The Site lets customers click a priority bar or scatter point, choose a segment from a selector, or select a compact table row; shared stay/source filters remain intact. CSV download works without a Python server.

## Data and numerical consistency

The Site contains **aggregate segment data only**. It does not host raw listing archives, listing IDs, host details or coordinates. Twelve stay/source bundles are generated using `scripts/export_site_data.py` from the same canonical Python backend, including full-range histogram counts. The browser applies adjustable evidence gates to backend metrics and preserves fixed small-sample flags and null opposite-date evidence. Pooled medians, quartiles, premiums and scores originate from the Python backend.

`reports/site_parity.json` records 36 filter/threshold cases and 42,303 segment-level comparisons between browser adapters and Python results. It checks prices, coverage, premiums, statuses, fixed flags, complete rank order and selected CSV/warning cases. Python tests include additional chart-data checks. The raw data fingerprint remains unchanged.

## Verification

- `uv run pytest -q`: 55 tests pass, including new percentile-band, coverage/threshold, context-denominator, signed ranking, missing-evidence and status-count checks.
- `reports/site_parity.json`: all 36 combinations pass, 42,303 segment checks.
- Browser checks cover default prices, cross-period views, clicking a ranked bar, shared filter changes, segment selection and an actual CSV download read back from disk.
- A 390px viewport has no horizontal page overflow; charts stack vertically and the full evidence table scrolls within its container.
- `reports/ui_performance.json` is remeasured for this revision: approximately 2.06 seconds cold Streamlit AppTest execution and 0.36–0.37 seconds for cached detail changes. Browser rendering is outside that measurement.

See `reports/SITES_BROWSER_CHECKS.md`, the screenshots and the current fresh-extraction report for the final verification scope. Prior-version records, where retained, are historical and not new verification results.
