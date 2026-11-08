# Verified issue resolution — final local build

The original `change-requests.md` is preserved verbatim. “Resolved” below means implemented and verified **in this submitted local package**, not merged into another team's branch. No implementation commit is invented: see `reports/source_manifest.json` for this export's source hashes. The source archive commit identifiers are recorded in DECISIONS.md.

| Request | Final behavior | Verification |
| --- | --- | --- |
| AUDIT-WS-01 | Pre-bedroom local/peer base counts, unknown counts and shares are retained per date. Visible comparison and shortlist/export warn at ≥25% unknown or ≥10 pp deterioration. | `test_ws01_bedroom_warning`: Venice Private room 1BR receives the warning; Hollywood Entire home 1BR does not receive a high-missingness bedroom warning. Independent raw recount confirms private-room missing bedrooms: 2,267/11,754 in March and 6,640/10,590 in June. Studio's coding warning is separate. |
| AUDIT-WS-02 | All analysis, peer keys and ranking use the canonical 6+ bucket; raw valid numeric bedrooms remain preserved for provenance. | `test_ws02_6plus`: Hollywood Hills West / Entire / 6+ has 47/46 priced rows; review score 81.050175 percentage points (within 1e-6). |
| AUDIT-WS-03 | Five explicit persistence statuses; Premium/Discount/Both direction; stay/source refinements from listing rows; fixed sample flag and row-specific local/peer coverage warnings. Context never affects rank. | `test_ws03_status_direction_filters`, synthetic status/tie tests; default shortlist 319 segments = 134 premium + 185 discount. Optional-filter medians reconcile to listing populations. |
| AUDIT-VL-01 | Warnings calculated from each row/date/population with current coverage setting and retained alongside bedroom/source cautions, on screen and in exports. | `test_vl01_row_coverage_and_export`: Malibu Entire 3BR March 68/86 = 79.069767…%; warning at 80%, absent at 75%; full-precision denominators unchanged. |
| AUDIT-VL-02 | `is_small_sample` always uses `<20`; adjustable `sufficient_data` controls premium availability separately. | `test_vl02_altadena_fixed_flag`: Altadena Entire 3BR June priced=20; flag False at minimum 20 and 30, sufficient_data False and premium unavailable at 30. Synthetic 19/20 checks cover both boundaries. |

AUDIT-RL-01 was a completed check, not a defect. It is preserved and regressed: Hollywood medians remain $162.91 / $160.87; change −$2.04 (−1.252225…%). Missing opposite-date synthetic cases retain null March/change. UI tests confirm snapshot independence and Reset behavior.

## Additional prototype gaps corrected

- Removed active use of December data, optional property/capacity controls, the arbitrary context-weighted/mean-premium rank, and percentile-clamped histogram from the original prototype. The original HTML remains a reference only.
- Separated all listing counts from valid priced counts; missing-price rows contribute context and coverage denominators.
- Added three specified tabs, downloadable full evidence, clear unavailable states and source attribution.
- Upgraded canonical reproducibility and SHA-256 integrity checks; removed premature rounding in segment CSVs.
- Added standalone reusable backends, pinned dependencies, executable tests, clean-extraction validation, setup instructions, data dictionary, and decision/approval disclosure.

## Evidence-based qualification to AUDIT-WS-01

The original request expected no Hollywood Entire 1BR bedroom warning, describing June missingness as low. The supplied full data show that its **pre-bedroom local Entire-home population** has unknown-bedroom share 5.8697% in March versus 20.0163% in June, a 14.1466 percentage-point deterioration. Its pooled Entire-home peer share is lower (2.2093% → 8.7293%). Accordingly Hollywood receives **no ≥25% high-missingness alert**, but does retain a distinct ≥10 pp local-composition deterioration caution. Hiding this warning just to reproduce the old expectation would suppress real evidence. Venice receives the required high-missingness warnings. This diagnostic policy and its proposed status are documented explicitly.

## Executable evidence

Run `uv run pytest -q` and `uv run python scripts/verify_submission.py`. Inspect `reports/issue_case_evidence.csv`, `reports/default_review_shortlist.csv`, `reports/default_segment_comparison.csv`, `reports/validation_results.json`, UI/browser records and `reports/pytest_final.txt`. The five targeted cases are exported at full precision; their warnings include the relevant dates and populations.
