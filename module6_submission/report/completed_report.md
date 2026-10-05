# Module 6 - Project Data Cleaning Checklist

Project: Short-Term Rental Marketplace Health | Student: chenwang266 | Branch: chenwang
Individual report, October 5, 2026. Team reconciliation and stakeholder confirmation remain pending.

## 1. State the vision along with a specific analysis question
Status: Done
Working individual vision: a marketplace analyst prioritizes Los Angeles neighborhoods for pricing/host-support follow-up. Compare March and June listing counts and advertised median price by neighborhood and room type, with calendar availability and review ratings as context. Stakeholder confirmation and team agreement remain limitations; this is descriptive, not a causal recommendation.

## 2. Define one row
Status: Done
One listing observed in one snapshot. Key (snapshot_date, id) is unique for all 89,839 cleaned rows. IDs are strings. A repeated ID between snapshots is valid.

## 3. Preserve the source
Status: Done
Inside Airbnb Los Angeles detailed listings, March 16 and June 15, 2026. Original 90-column CSV files remain outside the package, unchanged. Full-data audit records exact SHA-256 hashes. Actual retrieval date is unknown; inspected October 5, 2026. README gives source access and reload instructions.

## 4. Inspect columns and types
Status: Done
Read all originals as strings; select 28 analytical original fields. Parse 16 numeric fields, 4 date fields, and 3 t/f boolean fields; leave identifiers/labels as strings. 0 nonmissing conversion failures across selected fields. Failures would become missing and be counted. column_audit.csv lists every selected field, type, and missing count; excluded fields were not cleaned or validated.

## 5. Standardize text
Status: Done
Trim surrounding whitespace only, blank to missing, and preserve case/distinct neighborhood labels and ID leading zeros. 0 selected values required whitespace trimming. Example label 'Hollywood' stays 'Hollywood'; t/f becomes True/False; '$67.22' becomes 67.22. No case-collapsing or fabricated whitespace examples. text_examples.csv is header-only when no changes occur.

## 6. Investigate duplicates
Status: Done
March: 0 exact duplicates and 0 repeated IDs. June: 0 and 0. None removed. 38,102 IDs repeat validly across snapshots. Conflicting within-snapshot IDs stop the pipeline.

## 7. Handle missing data
Status: Done
No imputation or row deletion for missing fields. Price missing: March 8,910 before/after; June 5,565 before/after. Rating missing: March 12,519 before/after; June 11,257 before/after. instant_bookable is entirely missing in both snapshots. Missing price cannot mean free lodging; missing rating cannot mean poor quality. Every affected field appears in the missing-data table below and column_audit.csv.

## 8. Check suspicious values
Status: Done
No failed date parses or impossible selected numerical values; no stay-order, availability-order, review-order, future-review, or unknown-room-type flags. Retained prices over $2,000: March 646, June 774. Minimum stays over 365 nights: March 23, June 24. Review thresholds flag observations for sensitivity analysis, not automatic deletion. Actual March scraping spans March 16-18; June spans June 15-17 and June 22-23.

## 9. Verify merges
Status: Done
Outer one-to-one join by ID: 46,088 March rows and 43,751 June rows produce 51,737 IDs. Matched 38,102; March-only 7,986; June-only 5,649. Outer union and intersection verified independently, with no unexpected multiplication. listing_comparison.csv and full_data_checks.json contain evidence.

## 10. Reconcile changes
Status: Done
46,088 + 43,751 = 89,839 original and final listing-snapshot rows. Zero deleted. Combined 90 source columns become 28 selected columns plus 27 provenance/quality columns (55 total). Parsed price sum unchanged: March $12,987,240.50; June $14,640,324.20. These sums are audit statistics, not revenue. Count difference June versus March is -2,337 and reflects snapshot composition, not row cleaning.

## 11. Check calculations
Status: Done
Listing counts include all rows. Price has 37,178 March / 38,186 June usable observations; ratings have 33,569 / 32,494. Availability_365 has 46,088 / 43,751. Missing values are excluded from numerical totals/means/medians, and nonmissing counts accompany each group metric. Missing neighborhood/room keys become [Unknown] for grouping; none in these sources. Group totals independently reconcile. 31,893 matched listings support paired prices; median June-minus-March change is $0.10. No inference about realized revenue or occupancy.

## 12. Verify individual records
Status: Done
Five original-to-cleaned checks below: missing price, currency price, missing rating, boolean label, and unusually high price. All expected results match. Original filename/version, string ID, and source record position locate each check. record_checks.json holds machine-readable evidence; all five records are in the inspection sample.

## 13. Test reproducibility
Status: Done
Fresh Python process reran clean_data.py from both untouched originals into a separate temporary directory. 8 deterministic output files matched submitted SHA-256 hashes. Independent validation checked 89,839 rows and passed. Notebook execution: PASS, 4 code cells. Commands and restart/run-all procedure are in README; evidence is reproducibility.json and notebook_execution.json.

## 14. Document remaining limitations
Status: Done
Working vision requires team/stakeholder confirmation. Missing price is substantial and potentially systematic. Snapshot windows, seasonality, composition changes, and stale scraped data limit comparisons. Los Angeles region includes distinct municipalities. Calendar availability is not occupancy; advertised price is not transaction revenue; ratings omit unreviewed listings. Excluded fields and unprovided calendar/review transaction tables were not validated. Follow-up needs calendar/booking evidence, consistent price quote dates, missingness investigation, and team reconciliation.

## Five record checks

- missing price: 2026-03-16 / ID 1452068118494812958 / source record 2; price: '' -> expected None, actual None; matches=True. retain missing; never invent a zero
- currency price: 2026-03-16 / ID 1452093968341982976 / source record 3; price: '$315.00' -> expected 315.0, actual 315.0; matches=True. remove dollar sign and thousands separator
- missing rating: 2026-03-16 / ID 1453392869063399506 / source record 8; review_scores_rating: '' -> expected None, actual None; matches=True. retain missing; absence of rating is not a zero score
- boolean label: 2026-03-16 / ID 1452149405821816967 / source record 4; host_is_superhost: 'f' -> expected False, actual False; matches=True. f means False
- high advertised price: 2026-03-16 / ID 98284 / source record 167; price: '$2,081.00' -> expected 2081.0, actual 2081.0; matches=True. retain extreme positive price and flag it for sensitivity analysis

## Codex verification response
Codex verification response: I checked the submitted cleaning implementation and full-data evidence against the assignment. Independent validation passed on 89,839 rows, including source-price parsing, key/row reconciliation, outer-join membership, group denominators, bounds, and sample membership. Five documented record checks passed. Fresh-process hashes matched all 8 pipeline outputs; the notebook ran all code cells successfully. This supports the working descriptive question using the selected fields. It does not establish correctness of excluded source columns, random sample representativeness, stakeholder approval, or group consensus. The student remains responsible for reviewing the rules and interpretation.

## Cleaning decision log
# Proposed cleaning rules - written before running the pipeline

Author: chenwang266. Branch: chenwang. Date: October 5, 2026.

Working vision: a short-term rental marketplace analyst decides which Los Angeles neighborhoods warrant follow-up pricing or host-support research. Question: how do listing counts, advertised median prices, calendar availability, and review ratings differ between the March and June 2026 snapshots, by neighborhood and room type? This is an individual working vision, awaiting team agreement.

One row is one listing observed in one snapshot. The expected key is (snapshot_date, id); repeated IDs between snapshots are valid observations.

1. Preserve both source CSVs byte-for-byte; hash them in the audit. Load every original column as text first, preserving identifier precision and leading zeros. Use the filename date as snapshot_date while retaining actual last_scraped dates.
2. Select 28 original fields needed for this analysis (see KEEP in clean_data.py). Exclude personal host/profile details, exact coordinates, images, free text, URLs, licenses, and model-derived occupancy/revenue. Retain public listing IDs for comparison and audit. Add provenance and quality flags. This is a purpose-specific cleaned table, not a cleaned copy of every original field.
3. Strip only leading/trailing whitespace in selected fields. Convert empty/whitespace-only strings to missing. Preserve capitalization and neighborhood/property labels; do not collapse distinct labels or impute unknown groups.
4. Parse dollar prices and commas as numbers; parse other numeric fields without guessing units. Parse dates strictly as YYYY-MM-DD and booleans t/f to True/False. Record conversion failures and set failed conversions to missing.
5. Remove only exact duplicates across all original columns. Stop if an ID repeats within a snapshot after that removal; manual adjudication would be needed. Do not drop unmatched listings when comparing snapshots.
6. Keep missing values. Zero reviews/beds/bathrooms remain valid zero values; missing prices and ratings are never filled with zero. Groups retain rows for counts; each numerical metric reports its own nonmissing denominator.
7. Negative numeric values are impossible in these selected fields. Zero price, capacity, minimum/maximum nights are invalid. Calendar availability must be within its named horizon, ratings within 0-5, and counts/capacity/night limits/availability must be integers. Set invalid analytical values to missing and add a field-specific flag; retain the original source record.
8. Retain positive prices over $2,000 and minimum stays over 365 nights, but flag them. These thresholds are review triggers, not proof of error. Flag reversed stay bounds, inconsistent availability horizons, reversed review dates, reviews after scraping, and unknown room types. Do not repair these contradictions by inventing values.
9. Outer-join March and June by string listing ID with validate='one_to_one'; report matched/unmatched counts. Paired price changes require valid prices in both snapshots. Disappearance is not proof of delisting, nor is new appearance proof of a newly created listing.
10. Produce a deterministic sample of at most 50 rows including five difficult record checks and populated flags; retain all columns of the cleaned analytic table. The sample is not a statistical estimate of marketplace conditions.

Rule revisions: none at proposal time. Any later changes must be recorded here.

Limitations: advertised prices are not realized revenue; availability includes blocked days and is not occupancy; snapshots have different scrape windows and seasonal/composition effects; missing prices may be systematic; public records can be stale; Los Angeles-region neighborhoods include separate municipalities. No causal conclusions or regulatory status are inferred.

Execution revision: instant_bookable is entirely missing in both inputs. Retained as missing and switched the boolean record-check example to host_is_superhost; no cleaning rule changed.

