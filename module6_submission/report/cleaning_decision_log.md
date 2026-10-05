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
