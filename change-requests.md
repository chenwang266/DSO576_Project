# Team change requests

Copy this template into the top folder of your team's app repository if `change-requests.md` is missing. If it already exists, add to it; do not replace your teammates' work. Keep your individual evidence and conclusions in `my-audit.md`.

## Claims

Add your name and what you will audit. Choose a different scope from your teammates, or explain the new evidence you will contribute.

| Author | Feature | Number | Distinct scope or new evidence |
| --- | --- | --- | --- |
| | | | |
| Will Samuels | §1 Prioritize use case: ranked review shortlist | Segment premium (%) and review score | Independent recomputation from raw snapshots (not the team cleaner); bedroom-completeness effect on June private-room segments; 6+ bedroom grouping |
| Christos Georgaklis | §2 Data and cleaning: price-status handling and coverage warning, as shown in Data Quality & Methodology panel and Segment Detail | Price status counts and price coverage (priced ÷ valid-dimension listings) per snapshot | Independent csv-module recount from raw snapshots (no pandas/team code) plus 10 synthetic price strings run through the team's price() parser; distinct from Will's bedroom scope and Riley's §3 scope |
| Riley Lyu | §3 Analysis definitions: March–June same-segment comparison, snapshot independence and missing-date behavior | Change in median advertised price (USD and percent of March median) | New BUILD_SPEC-generated candidate `audit-riley-chapter3@4bdd0a3`; independent raw-file Hollywood/Venice medians plus synthetic boundary checks and Streamlit widget interactions. Evidence: [tests](https://github.com/chenwang266/DSO576_Project/tree/4bdd0a3c37a631e33c3e2d625ed8f44b12ada29c/generated_dashboard/tests), [aggregate results](https://github.com/chenwang266/DSO576_Project/blob/4bdd0a3c37a631e33c3e2d625ed8f44b12ada29c/generated_dashboard/audit_full_data_results.json). No actionable defect established in this tested scope; personal conclusions remain in my-audit.md. Team adoption of the candidate is not assumed; existing requests against older implementations remain open. |
| Vincent Liang | §4 Review Shortlist row warnings | Fixed `is_small_sample` flag under adjusted minimum | Reproduced on the newer `audit-riley-chapter3@4bdd0a3` Streamlit candidate with exact full raw snapshots and UI output; separate from prior requests against older branches. |

## Requests

Copy this block for each actionable finding and choose a unique ID. Reference that ID in your individual audit. A check that finds no defect belongs in your audit; do not invent a bug to fill a request.

### AUDIT-XX Short description

- Author:
- Status: open
- App version or commit checked:
- Feature or number and its intended behavior or definition:
- Inputs and steps to reproduce:
- Expected result:
- Actual result:
- Evidence (including file, function, and relevant lines if code was checked):
- Likely cause, if established, and remaining uncertainty:
- Requested change:
- Verification check and expected result:
- Implementation commit and verification result, if resolved:

Record findings without undoing a teammate's work. Mark a request resolved only after verifying the change.

### AUDIT-WS-01 Shortlist shows no bedroom-completeness warning for June private-room segments

- Author: Will Samuels
- Status: open
- App version or commit checked: spec `main@be155ab`; implementation `origin/chenwang@e021c6a` (`phase2/analysis.py`, `phase2/outputs/ranked_review_list.csv`)
- Feature or number and its intended behavior or definition: Review shortlist / premium (%). BUILD_SPEC §2 and §4 require warnings that bedroom coding or completeness changes can distort comparisons, shown on comparison and shortlist rows.
- Inputs and steps to reproduce: Raw `origin/wsamuels:data/raw/3_15.csv.gz` and `6_15.csv.gz`. Count blank `bedrooms` where `room_type == "Private room"`. Then look up Venice and Santa Monica Private room 1BR in `ranked_review_list.csv`.
- Expected result: Rows whose segment or peer population is materially reduced by unknown bedrooms carry a visible bedroom-completeness warning.
- Actual result: June private-room bedrooms are blank for 6,640/10,590 listings (63%) versus 2,267/11,754 (19%) in March. The private 1BR peer pool falls from 8,562 to 3,293. Venice private 1BR goes from 121 to 38 listings (premium 145%→201%), and Santa Monica from 196 to 96 (139%→321%). The median June/March listing ratio across the 37 ranked private-room rows is 0.40. No warning column exists.
- Evidence (including file, function, and relevant lines if code was checked): `analysis.py` `_aggregate`: `data = data.dropna(subset=keys)` silently drops unknown-bedroom rows. Output columns contain no warn/flag fields. Reproduced with `origin/wsamuels:audit_checks/wsamuels_premium_check.py`.
- Likely cause, if established, and remaining uncertainty: Dropping unknown bedrooms is correct per spec, but the warning is missing. It is not established whether blank-bedroom private rooms are priced differently from known-bedroom ones.
- Requested change: Add per-row, per-snapshot unknown-bedroom share (local and peer) and a warning when completeness drops sharply between snapshots. Show it in the comparison and shortlist and include it in exports.
- Verification check and expected result: Venice / Private room / 1BR shortlist row shows a bedroom-completeness warning for June. Hollywood / Entire home / 1BR (June missingness is low) does not.
- Implementation commit and verification result, if resolved:

### AUDIT-WS-02 Bedrooms not collapsed to "6+" segment

- Author: Will Samuels
- Status: open
- App version or commit checked: `origin/chenwang@e021c6a`
- Feature or number and its intended behavior or definition: Segment definition behind premium and review score. BUILD_SPEC §2: bedrooms `0 → Studio, 1–5 separate, ≥6 → 6+ bedrooms`.
- Inputs and steps to reproduce: `segment_comparison.csv` contains bedroom values 6 through 24 as separate segments (271 segment-rows ≥6). Compare rank 50 with the spec definition using `python3 audit_checks/wsamuels_premium_check.py` on the raw files (6+ segment of Hollywood Hills West / Entire home/apt).
- Expected result: Hollywood Hills West / Entire / 6+: priced 47 (Mar) / 46 (Jun), peer median $1,362.44 / $1,520.26, premium +81.05% / +93.87%, score 81.05 (about rank 30).
- Actual result: Hollywood Hills West / Entire / 6BR only: priced 26 / 23, peer median $1,196.38 / $1,239.50, premium +50.19% / +54.18%, score 50.19, rank 50.
- Evidence (including file, function, and relevant lines if code was checked): `analysis.py` `KEYS = ['snapshot_date', 'neighbourhood_cleansed', 'room_type', 'bedrooms']` groups on the raw numeric bedroom count. There is no bucketing step.
- Likely cause, if established, and remaining uncertainty: Cleaner and analysis were written before the spec's 6+ rule. A full rerun may also let new 7+ segments pass the 20-listing threshold, so the exact new ranks are unverified.
- Requested change: Add a canonical bedroom segment field (`Studio`, `1`–`5`, `6+`, `Unknown`) and use it as the segment and peer key.
- Verification check and expected result: Rerun. No bedroom values above 6 appear, and HHW / Entire / 6+ shows score 81.050175.
- Implementation commit and verification result, if resolved:

### AUDIT-WS-03 Shortlist lacks direction, persistence status, small-sample/coverage warnings, and spec filters

- Author: Will Samuels
- Status: open
- App version or commit checked: `origin/chenwang@e021c6a`
- Feature or number and its intended behavior or definition: Prioritize use case (§1). §3 requires statuses Persistent premium/discount, Reversed, Neutral, and Insufficient evidence, a premium/discount/both option, and stay/source filters. §4 requires the shortlist to show direction, counts, coverage, and warnings.
- Inputs and steps to reproduce: Inspect the columns of `ranked_review_list.csv` and `segment_comparison.csv`, and the signature of `segment_metrics`.
- Expected result: Each row has `direction`, `persistence_status`, `is_small_sample`, coverage, and coverage warning (<80%). The ranking function accepts a direction option, and `minimum_nights`/`source` filters are available.
- Actual result: Only a Boolean `persistent_pattern`, so 34 reversed and 2,006 insufficient-evidence segment-rows are indistinguishable. No direction or warning columns. 77 ranked rows have March coverage below 80% and 28 have June coverage below 80%, all unflagged. Filters offered are `property_type`, `accommodates`, and `exclude_high_prices` instead of stay/source.
- Evidence (including file, function, and relevant lines if code was checked): `analysis.py` `snapshot_comparison` (`persistent_pattern` Boolean), `ranked_review_list` (no direction argument), `segment_metrics` signature.
- Likely cause, if established, and remaining uncertainty: Backend predates the final spec. The premium and score math itself is correct (verified independently).
- Requested change: Add the status label, direction, small-sample and coverage flags, a direction argument for ranking, and stay/source filters recalculated from listings.
- Verification check and expected result: Segments with opposite-sign premiums show `Reversed`. Filtering direction=discount returns only negative-premium rows (185 under current defaults). Rows with coverage below 80% carry a warning.
- Implementation commit and verification result, if resolved:

### AUDIT-VL-01 Shortlist omits row-specific low-coverage warnings
- Author: Vincent Liang
- Status: resolved locally; awaiting team merge
- App version or commit checked: `audit-riley-chapter3@4bdd0a3`
- Feature or number and intended behavior: `BUILD_SPEC.md` §4 Review Shortlist must show and export warnings for each row; default price-coverage warning is below 80%.
- Inputs and steps to reproduce: Use the March/June raw files with SHA-256 `ffdef08a…` / `ebc99e8a…`; run the candidate cleaner and app at defaults. Inspect rank 5, Malibu / Entire home/apt / 3 bedrooms, in Review Shortlist and its CSV export.
- Expected result: This row states that March local price coverage is below 80%; counts and denominator remain visible.
- Actual result: March is 68 priced / 86 listings = 79.069767%, June is 73 / 86 = 84.883721%. The row's `warnings` value contains only generic bedroom and source cautions. Across the 319 ranked rows, 80 have at least one date below 80% local coverage and none receives a row-specific coverage warning.
- Evidence: Streamlit AppTest on full data showed the rank-5 `warnings` value. `generated_dashboard/app.py` lines 95–96, 164–169 assign the same warnings to all rows; lines 141–145 implement coverage warnings only in Comparison. Individual audit: `my-audit.md` Feature Audit.
- Likely cause and uncertainty: Shortlist export reuses global warning text instead of calculating warnings from each row's March/June coverage. This finding is for the candidate branch only.
- Requested change: Derive warnings from each shortlist row's local and peer coverage and current warning threshold. Include the affected date/population in the on-screen row and CSV; preserve existing bedroom/source cautions.
- Verification check and expected result: At default 80%, Malibu rank 5 says March local coverage below 80% in the displayed row and export. Set warning threshold to 75%: that specific coverage warning disappears while counts remain 68/86. A row above threshold remains unflagged.
- Implementation commit and verification result, if resolved: local branch `audit-vl-01-shortlist-warnings@216ee92a8d6f7523902bab6c17032aa9e4f18174`. Added `add_shortlist_warnings()` and a regression test. Candidate suite: 18 passed. With the full canonical data, Malibu / Entire home/apt / 3 bedrooms remains rank 5 and now shows `March local price coverage 79.1% is below the 80% warning threshold.` both in the Streamlit shortlist and its export frame. No application exceptions in Streamlit AppTest.

### AUDIT-VL-02 Adjustable minimum incorrectly changes canonical small-sample number flag

- Author: Vincent Liang
- Status: open
- App version or commit checked: `audit-riley-chapter3@4bdd0a3`
- Feature or number and intended behavior: `BUILD_SPEC.md` §3 fixes `is_small_sample = priced_rows < 20`; the adjustable minimum only determines premium qualification.
- Inputs and steps to reproduce: Use the full canonical data and select June / Altadena / Entire home/apt / 3 bedrooms. Set minimum priced count to 20, then 30. Inspect `is_small_sample_june` and `sufficient_data_june` in March–June Comparison or call `segment_metrics` with each setting.
- Expected result: With 23 listings and exactly 20 valid prices, `is_small_sample_june=False` at both settings. At minimum 30, `sufficient_data_june=False` and premium is suppressed.
- Actual result: At minimum 20, `is_small_sample_june=False`; at minimum 30, `is_small_sample_june=True`. AppTest rendered 20 priced, `is_small_sample_june=True`, `sufficient_data_june=False` at 30.
- Evidence: `generated_dashboard/src/pricing.py` line 32 uses `values['priced_rows'] < min_priced`; `segment_metrics` passes the adjustable value at lines 51–53; `generated_dashboard/app.py` lines 87 and 92 provide the UI setting. Individual audit: `my-audit.md` Number Audit.
- Likely cause and uncertainty: The canonical quality flag and exploratory qualification threshold share one variable. The premium suppression itself was correct.
- Requested change: Set `is_small_sample` from `priced_rows < 20` regardless of user threshold. Keep a separate `sufficient_data` or qualification field for the adjustable minimum.
- Verification check and expected result: On the Altadena example, minimum 20 and 30 both show `is_small_sample=False`; at 30, `sufficient_data=False` and premium unavailable. Add a boundary check for 19/20 priced listings with minimum 30.
- Implementation commit and verification result, if resolved:

## Completed checks

### AUDIT-RL-01 March–June comparison and price change

- Author: Riley Lyu
- Status: checked; no defect found in these cases
- App version or commit checked: `audit-riley-chapter3@4bdd0a3`
- Feature or number and its intended behavior or definition: BUILD_SPEC §3. Compare the same segment in March and June. Dollar change is June median minus March median; percentage change uses March as the denominator.
- Inputs and steps to reproduce: Select Hollywood / Entire home/apt / 1 bedroom, all stays and sources, minimum 20. Open March–June Comparison. Switch the detail snapshot to March, change the neighborhood to Venice, then click Reset. Also test March prices [100, 200, missing] and June prices [150, 250, missing].
- Expected result: Hollywood shows a $2.04 decrease, about 1.3%. Switching the detail snapshot leaves the comparison unchanged. Changing neighborhoods updates both dates. Reset restores June and Hollywood. The small case gives a $50 increase and 33.3%.
- Actual result: All of these matched. Hollywood medians were $162.91 and $160.87. Venice showed a 2.1% increase. A June-only test segment showed March and the change as unavailable.
- Evidence (including file, function, and relevant lines if code was checked): `generated_dashboard/src/history.py`, `snapshot_comparison`, lines 10 and 18–20. [Test code](https://github.com/chenwang266/DSO576_Project/blob/4bdd0a3c37a631e33c3e2d625ed8f44b12ada29c/generated_dashboard/tests/test_chapter3.py) and [full-data results](https://github.com/chenwang266/DSO576_Project/blob/4bdd0a3c37a631e33c3e2d625ed8f44b12ada29c/generated_dashboard/audit_full_data_results.json). Codex ran the checks using Streamlit AppTest and separate raw-file calculations.
- Likely cause, if established, and remaining uncertainty: No cause to investigate in this scope. Browser layout, every segment and all export interactions were not checked. This does not clear issues found by other team members.
- Requested change: None for the tested comparison and price-change calculation. Keep the checks for future updates.
- Verification check and expected result: Run `uv run pytest -q` and `uv run python tests/audit_full_data.py` from `generated_dashboard` with the supplied data. Hollywood should remain -$2.04 and about -1.3%; a missing or nonpositive March baseline should give an unavailable percentage.
- Implementation commit and verification result, if resolved: Not applicable; no fix was made. At `4bdd0a3`, 17 test cases and the separate full-data checks passed. This is a completed check, not a resolved bug request.
