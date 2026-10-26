# Team change requests

Copy this template into the top folder of your team's app repository if `change-requests.md` is missing. If it already exists, add to it; do not replace your teammates' work. Keep your individual evidence and conclusions in `my-audit.md`.

## Claims

Add your name and what you will audit. Choose a different scope from your teammates, or explain the new evidence you will contribute.

| Author | Feature | Number | Distinct scope or new evidence |
| --- | --- | --- | --- |
| | | | |
| Christos Georgaklis | §2 Data and cleaning: price-status handling and coverage warning, as shown in Data Quality & Methodology panel and Segment Detail | Price status counts and price coverage (priced ÷ valid-dimension listings) per snapshot | Independent csv-module recount from raw snapshots (no pandas/team code) plus 10 synthetic price strings run through the team's price() parser; distinct from Will's bedroom scope and Riley's §3 scope |
| Will Samuels | §1 Prioritize use case: ranked review shortlist | Segment premium (%) and review score | Independent recomputation from raw snapshots (not the team cleaner); bedroom-completeness effect on June private-room segments; 6+ bedroom grouping |
| Riley Lyu | §3 Analysis definitions: March–June same-segment comparison, snapshot independence and missing-date behavior | Change in median advertised price (USD and percent of March median) | New BUILD_SPEC-generated candidate `audit-riley-chapter3@4bdd0a3`; independent raw-file Hollywood/Venice medians plus synthetic boundary checks and Streamlit widget interactions. Evidence: [tests](https://github.com/chenwang266/DSO576_Project/tree/4bdd0a3c37a631e33c3e2d625ed8f44b12ada29c/generated_dashboard/tests), [aggregate results](https://github.com/chenwang266/DSO576_Project/blob/4bdd0a3c37a631e33c3e2d625ed8f44b12ada29c/generated_dashboard/audit_full_data_results.json). No actionable defect established in this tested scope; personal conclusions remain in my-audit.md. Team adoption of the candidate is not assumed; existing requests against older implementations remain open. |

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
