# Los Angeles listings: inspection and cleaning plan

Prepared for Christos on 2026-10-04. Decision: which **neighbourhood × room-type** segments a Marketplace Strategy Manager should prioritize for pricing guidance.

## Scope and safeguards

The inspection findings below describe the original raw files. The **Decisions made** section records Christos's subsequent instructions and supersedes conflicting proposals elsewhere in this document. The implemented pipeline never modifies either raw file.

## Decisions made

Christos approved the following on 2026-10-04:

1. Keep every listing-snapshot row. Add `stay_type`: `short` for minimum_nights <30, `long` for >=30, and `unknown` if missing. Primary pricing segments use short stays; report the long cohort separately.
2. Keep and flag missing prices. Exclude them from price statistics and report segment priced coverage. No price imputation.
3. Never fill price from quote price.
4. Keep and flag `previous scrape` rows; exclude them from primary pricing eligibility. Report price missingness by source before applying eligibility.
5. Flag price <10 and >5000. Preserve values without capping or deletion; summarize prices with medians.
6. Flag possible inactivity when number_of_reviews_ltm ==0 and availability_365 >=300. Exclude these rows from demand metrics, but retain them in cleaned output.
7. Keep all three neighbourhood groups.
8. Derive snapshot_date from filename; retain last_scraped separately.
9. Preserve raw license tokens. Add license_status (`hsr_registered`, `exempt`, `other_identifier`, `missing`); N/A counts as missing. Uppercase recognized identifier patterns only in a separate column. A pattern match does not verify registration.
10. Segment by neighbourhood_cleansed x room_type. No pooling or category-label changes.
11. Preserve null reviews_per_month and add no_reviews based on zero lifetime reviews.
12. Keep estimated occupancy/revenue under their original explicitly estimated names and units.
13. Preserve capacity fields with no imputation.
14. Create only four data/clean artifacts: listings_clean.csv, listings_sample.csv (<=50 with a reason column), validation_report.json, data_dictionary.md. Do not create Parquet, per-cell change logs, or dropped_rows files.

Implementation details: primary_pricing_eligible means short stay, nonmissing price, and city scrape. Extreme-price and possible-inactivity flags do not remove rows from price statistics. demand_eligible means short stay, city scrape, and not possibly inactive; it does not require a price. Long stays receive separate summaries. Priced coverage is reported both for all segment rows and within each stay cohort, including a city-scrape denominator for primary pricing. Missing comparison inputs yield unknown flags rather than a false classification. Current inputs contain no unexpected source/room labels or impossible stay limits; future schema, key, or parse failures stop with explicit diagnostics rather than choosing repairs or duplicate survivors.

Recognized license identifiers: case-insensitive HSR##-######, PRP/NRP##-#####, STR##-#### or ##### , SRH[-]####-#####, HS-######-####, and digits-only tokens. The separate normalized field uppercases these matches only; unrecognized tokens remain verbatim in license and are flagged. Exemption text is classified separately, not uppercased. Exact pattern checks do not assert legal compliance.

The original goal's validation evidence in cleaning.ipynb remains part of implementation. Regeneration compares all four data artifacts from two independent runs; the notebook invokes that same validation workflow.

Implementation inspection clarified that `host_verifications` uses literal `None` tokens, recognized as missing by the initial pandas inspection. The pipeline explicitly records `None` -> missing for this omitted field. Other retained fields use blank-only missing conversion, and raw license retains both blanks and literal N/A. This accounts for the difference between raw token preservation and the original default-NA dtype inventory.

### Implementation results

The cleaning pipeline implements the decisions above, retains **89,839** rows, and drops **zero**. Each stage prints rows, missing counts, flag counts, and existing-field change counts; the validation report records added fields, omitted columns, rules, and before/after examples. The source hashes match the inspection fingerprints.

| Measure | March | June |
|---|---:|---:|
| Retained rows | 46,088 | 43,751 |
| Short stays | 23,495 | 23,259 |
| Long stays | 22,586 | 20,481 |
| Unknown stay type | 7 | 11 |
| Missing price | 8,910 | 5,565 |
| Primary pricing eligible | 19,096 | 20,550 |
| Primary demand-proxy eligible | 17,687 | 18,527 |
| Possible inactivity flagged | 8,323 | 8,913 |
| Price <10 flagged | 25 | 20 |
| Price >5000 flagged | 124 | 143 |
| Recognized license identifiers whose case is normalized | 138 | 147 |

Before eligibility, price missingness is 1,182/35,809 (**3.30%**) in March city-scrape rows versus 7,728/10,279 (**75.18%**) in previous-scrape rows. June has 757/37,691 (**2.01%**) versus 4,808/6,060 (**79.34%**). Every nonempty source price parses; no prices are filled or capped, and no source category labels are changed. The sample contains 50 unique listing-snapshot rows with reasons and covers every observed difficult-case type. Zero-price and impossible-value cases are unavailable rather than fabricated.

The four approved data artifacts are produced by scripts/clean_listings.py. cleaning.ipynb independently validates preserved source values, policy predicates, segment coverage and medians, sample membership, unchanged raw hashes, and byte-identical regeneration of all four artifacts in a fresh output directory. No per-cell log, dropped_rows file, or Parquet output is produced.

- Never write to `data/raw/`. Record input SHA-256 hashes and verify them after future runs.
- Read `id` and `host_id` as strings from ingestion through output and reloading. Never pass them through floats. There are 19-digit listing IDs. If additional identifiers are retained, also read those as strings.
- Preserve source labels and units. Document every parsing, label mapping, unit conversion, missing-token interpretation, exclusion, and derived field.
- Flag suspicious values first; preserve their original values pending a decision.
- Never fill `price` from `price_quote_price_per_night` without Christos's approval.
- After each major transformation report input/output rows, distinct rows affected, changed cells by column, missing counts before/after, flag counts, drops with reasons, and key uniqueness. Overlapping flags must not be summed as distinct affected rows.

## 1. Shapes and schema

| Snapshot (filename date) | Rows | Columns |
|---|---:|---:|
| 2026-03-16 | 46,088 | 90 |
| 2026-06-15 | 43,751 | 90 |
| Stacked, before adding metadata | 89,839 | 90 |

**Both files have identical column names, identical column order, and identical pandas dtypes under the same inspection settings. There are zero dtype mismatches.** CSV files themselves do not encode dtypes: this confirmation uses pandas 3.0.5, `read_csv(dtype={'id': 'string', 'host_id': 'string'}, low_memory=False)`, with default missing-token recognition. A full per-column dtype and missing-count inventory is provided in the appendix.

The inspection used numerical and date parsing only in temporary analysis views. `price` is read as text; date and t/f fields are text when populated. Entirely empty columns infer `float64`, which is an inference artifact, not their intended meaning. `host_profile_id` also infers `float64`; do not reuse that inferred representation if keeping it.

Expected clean grain: one listing per snapshot, unique key `(id, snapshot_date)`. Set `snapshot_date` from the filename, keep actual scrape dates separately, and keep both records when an ID appears in both files. This is a two-snapshot panel, not 89,839 distinct listings.

## 2. Missingness and confirmations

Counts below use pandas default missing-token recognition. For the four fields Christos named, the CSV tokens were also inspected directly: all are empty strings, not merely unparseable values. **Confirmed: `host_response_rate`, `host_acceptance_rate`, `instant_bookable`, and `host_since` are each missing in all 89,839 rows; `price` is missing in 14,475; `minimum_nights` is missing in 18.**

| Important column | March missing | June missing | Stacked missing |
|---|---:|---:|---:|
| id / host_id (each) | 0 | 0 | 0 |
| price | 8,910 | 5,565 | 14,475 |
| price_quote_price_per_night | 8,913 | 5,569 | 14,482 |
| price_quote_total_price | 8,913 | 5,569 | 14,482 |
| room_type / property_type (each) | 0 | 0 | 0 |
| neighbourhood_cleansed / neighbourhood_group_cleansed (each) | 0 | 0 | 0 |
| minimum_nights / maximum_nights (each) | 7 | 11 | 18 |
| estimated_occupancy_l365d | 0 | 0 | 0 |
| availability_30 / 60 / 90 / 365 (each) | 0 | 0 | 0 |
| number_of_reviews / number_of_reviews_ltm / number_of_reviews_l30d (each) | 0 | 0 | 0 |
| reviews_per_month | 12,519 | 11,257 | 23,776 |
| first_review / last_review (each) | 12,519 | 11,257 | 23,776 |
| last_scraped / calendar_last_scraped (each) | 0 | 0 | 0 |
| price_quote_checkin_date / price_quote_checkout_date (each) | 8,088 | 4,792 | 12,880 |
| source | 0 | 0 | 0 |
| license (default NA interpretation) | 32,992 | 30,559 | 63,551 |
| host_is_superhost / host_has_profile_pic / host_identity_verified (each) | 356 | 203 | 559 |
| has_availability | 3,574 | 472 | 4,046 |
| host_response_rate / host_acceptance_rate / instant_bookable / host_since (each) | 46,088 | 43,751 | 89,839 |
| calendar_updated | 46,088 | 43,751 | 89,839 |
| bathrooms | 10,288 | 7,761 | 18,049 |
| bathrooms_text | 102 | 168 | 270 |
| bedrooms | 3,196 | 9,572 | 12,768 |
| beds | 10,439 | 6,631 | 17,070 |
| review_scores_rating | 12,519 | 11,257 | 23,776 |
| estimated_revenue_l365d | 8,910 | 5,565 | 14,475 |

### Price and quote missing on the same rows

| Joint state | March | June | Stacked |
|---|---:|---:|---:|
| Both missing | 8,910 | 5,565 | 14,475 |
| Price missing, quote present | 0 | 0 | 0 |
| Price present, quote missing | 3 | 4 | 7 |
| Both present | 37,175 | 38,182 | 75,357 |

Every missing-price row also lacks the nightly quote. Quote-based filling would recover **zero** prices in these files, even if approved. When both fields are populated, parsed values agree within 0.005 currency units on all 75,357 rows. Equality here does not establish interchangeable price semantics in other files.

Missing `reviews_per_month`, `first_review`, and `last_review` coincide with zero lifetime reviews in both snapshots; none of the missing-rate rows has a nonzero lifetime review count. Preserve missingness unless an explicit analytical policy says otherwise.

## 3. Duplicates and snapshot membership

Exact duplicates compare all 90 parsed source columns within each file; the comparison precedes metadata and standardization. Repeated IDs are measured separately from exact rows.

| Check | March | June |
|---|---:|---:|
| Exact duplicate rows beyond first occurrence | 0 | 0 |
| IDs repeated within snapshot (distinct repeated IDs) | 0 | 0 |
| Rows belonging to repeated IDs | 0 | 0 |
| Extra rows beyond first occurrence of an ID | 0 | 0 |
| Missing / nondigit IDs | 0 / 0 | 0 / 0 |

Both `id` and `host_id` contain only digit strings, with no missing values. Hosts may own multiple listings; repeated `host_id` is not a duplicate criterion.

| Cross-snapshot distinct listing IDs | Count |
|---|---:|
| Present in both | 38,102 |
| Only March | 7,986 |
| Only June | 5,649 |
| Union | 51,737 |

Reconciliation: `38,102 + 7,986 = 46,088`; `38,102 + 5,649 = 43,751`; `2 × 38,102 + 7,986 + 5,649 = 89,839`. Reappearance across snapshots is expected, and absence in one scrape does not prove market entry or exit. Proposed current row drops: **zero**. If future duplicate checks fail, stop and report conflicting records before choosing a survivor.

## 4. Important-column rules

M/J means March/June. Proposed rules are not approved transformations. Numeric bounds distinguish impossible values from unusual but plausible values.

| Column | Problem found | Proposed rule | Reason | How to check it |
|---|---|---|---|---|
| id, host_id | IDs can exceed float precision; no missing/nondigit IDs | Keep strings; id + snapshot_date key; also string-type any retained scrape/profile identifier | Prevent irreversible key corruption | Compare exact raw tokens and lengths after reload; assert compound key uniqueness |
| price | M/J missing 8,910/5,565; `$` and comma formatting; range 3.31–20,583.33 / 3.77–20,583.33; no zero/negative or parse failures | Preserve raw text; parse numeric value without changing units; flag missing, zero, negative, low, high; no imputation or capping | Pricing analysis needs numeric values and transparent coverage | All 75,364 nonmissing prices parse; reconcile missingness and token-to-number changes; inspect flagged IDs |
| price_quote_price_per_night | Missing 8,913/5,569; zero additional coverage; all overlapping values agree | Keep separate numeric field; retain quote dates and provenance; no fill into price | A quote is attached to a stay/date context | Joint missingness table, agreement check, currency and duration checks |
| price_quote_total_price / price_quote_raw | Total and nightly amount have different units; raw JSON includes currency and failed quote context | Keep total amount separate; retain raw JSON for audit; extract currency only if approved | Avoid treating stay totals as nightly amounts | Quote JSON inspection found only USD or null currency; validate JSON and check total/duration relationships without overwriting |
| room_type | Four labels, no missing or case/whitespace variants | Preserve `Entire home/apt`, `Private room`, `Shared room`, `Hotel room` exactly | Defines requested segmentation | Assert accepted label set and unchanged counts; no title-casing |
| property_type | 96/90 distinct labels; no whitespace/case variants; small categories possible | Retain original labels as context; no collapsing without a mapping approved by Christos | Property and room type are different dimensions | Compare raw/clean unique labels and frequencies; publish any mapping |
| neighbourhood_cleansed | 266/265 labels, union 266; no missing or case/whitespace variants | Use as segment geography, preserve labels; validate joins if a reference becomes available | Better coverage than entirely empty `neighbourhood` | Compare distinct labels and exact join coverage; report unmatched labels |
| neighbourhood_group_cleansed | Three labels; includes areas outside City of Los Angeles | Preserve all three labels; add scope flags if approved | City-only filtering materially changes population | Report City/Other/Unincorporated counts before/after any filter |
| minimum_nights | Missing 7/11; ≥30 on 22,586/20,481; range 1–1,124; no fractional/zero/negative | Nullable integer nights; flag missing and ≥30; preserve unusual positive values | Long-stay offers may require separate pricing guidance | Assert positive integer when present; compare with maximum_nights; count flags |
| maximum_nights and other night-limit fields | Maximum reaches 2,147,483,647; six rows per snapshot >1,125 | Keep nights; flag extreme/sentinel-like limits; do not silently cap | Very large values can mean unconstrained stays rather than literal durations | Count >1,125; check integer bounds and min/max consistency; distinguish averages from integer counts |
| estimated_occupancy_l365d | Integer 0–255; 3,179/3,167 equal 255; 22,172/19,649 zeros | Preserve as source estimate in days; flag concentration at 255; no conversion to observed occupancy | Estimate and apparent ceiling must not be presented as bookings | Check [0,365], histogram/ceiling count; document semantics before deriving a rate |
| availability_30 / availability_365 | No missing; valid integer ranges 0–30 / 0–365; zeros and near-full calendars common | Preserve available-day counts; flag high availability with no recent reviews; retain 60/90-day counts for checks | Unavailable days may be booked or host-blocked | Bounds, integrality, 30 ≤ 60 ≤ 90 ≤ 365 for each listing; never label 365 − availability as observed bookings |
| reviews_per_month | Missing 12,519/11,257, all tied to zero lifetime reviews; maxima 52.89/47.35 | Preserve nullable rate, flag negative/invalid and unusually high rates; do not auto-fill zero | Undefined rate differs from measured zero | Reconcile missingness against lifetime reviews; range/quantile checks |
| last_review | Missing 12,519/11,257; 5/97 after filename date, but none after own last_scraped | Parse ISO date; retain missing; compare against actual row scrape date | Collection spans multiple days; filename date is not a hard event cutoff | Strict date parse; first_review ≤ last_review ≤ last_scraped when present |
| source | `previous scrape`: 10,279/6,060; `city scrape`: 35,809/37,691 | Preserve label; add previous-scrape flag; retain rows pending eligibility decision | Potential stale/reused records affect comparability | Exact value counts; compare price missingness and segment coverage by source before filtering |
| license | Blank, explicit N/A, mixed-case identifiers, multiple prefix systems, digits and exemption text | Preserve raw strings; flag format; optionally create separate normalized value/status after approval | Format is not legal validity or permission to operate | Separate blank/N/A/exemption/identifier types; review every mapping and affected count |
| accommodates / bathrooms / bathrooms_text / bedrooms / beds | Uneven missingness; zero bedrooms/beds/baths in March; bathrooms include half units | Keep nullable source measures and bathroom text; flag zeros/extremes; no inference from room type or text without approval | Zero may describe studio/shared arrangements; missing differs from zero | Nonnegative numeric bounds; fractional bathrooms allowed; counts and comparison by snapshot |
| number_of_reviews / number_of_reviews_ltm / number_of_reviews_l30d | Recent-year zeros 22,172/19,649; not proof of inactivity | Keep integer counts; use only as activity proxies | Reviews measure observed review activity | Nonnegative integers; l30d ≤ ltm ≤ lifetime; all inspected rows pass |
| review_scores_* | Ratings on 0–5 scale; main rating has one zero per snapshot; missing on unreviewed listings | Preserve existing scale; flag zero for review; no rescaling or filling | A missing or zero score requires context | Range [0,5], missing counts and no-review relationship; all seven score fields pass bounds |
| estimated_revenue_l365d | Missing exactly as often as price; modeled rather than realized revenue | Retain explicitly named estimate if desired; no use as observed earnings | Avoid circular conclusions about price and modeled revenue | Preserve units; inspect definition and dependence before selecting decision metrics |
| host_response_rate / host_acceptance_rate | Entirely blank in both snapshots | Leave out analytical output, document 100% missing; no default zero | No information available | Confirm 89,839 empty tokens per column |

### All date fields

Dates remain calendar dates, not timezone-shifted timestamps. Strict ISO parsing must retain missing values and report any failed populated token. `calendar_updated` is entirely blank; `scrape_id` is an identifier with date-like content, not a date column. Proposed `snapshot_date` is new filename-derived metadata.

| Column | Problem found | Proposed rule | Reason | How to check it |
|---|---|---|---|---|
| last_scraped | March 2026-03-16–18; June 2026-06-15–23; 33,160/34,996 after filename date | Preserve actual ISO scrape date alongside snapshot_date | Avoid false future-date flags | Zero invalid dates; compare row events to last_scraped |
| calendar_last_scraped | Same ranges as last_scraped; differs from it on 5/7 rows | Preserve separately; flag discrepancy, do not force equal | Calendar and listing collection may differ | Zero parse failures; count mismatched dates |
| host_since | 100% empty | Record missingness; leave out unless schema placeholders requested | No host-tenure evidence here | Raw empty-token count 46,088/43,751 |
| first_review | Missing 12,519/11,257; earliest 2009-05-26; latest 2026-03-16 / 2026-06-16 | Nullable ISO date; preserve | New/unreviewed listings lack a date | Zero invalid dates; zero first_review > last_review; compare to row scrape date |
| last_review | Latest 2026-03-17 / 2026-06-22; missing as above | Nullable ISO date, no imputation | Activity evidence must respect collection window | Zero last_review > last_scraped; count filename-date overruns separately |
| price_quote_checkin_date | Missing 8,088/4,792; ranges 2026-03-16–2027-03-13 / 2026-06-15–2027-06-20 | Keep quote date; future dates expected | Quote timing affects price comparison | Zero invalid dates; pair with checkout and quote presence |
| price_quote_checkout_date | Missing 8,088/4,792; ranges 2026-03-17–2027-03-18 / 2026-06-16–2027-06-23 | Keep quote date; future dates expected | Stay duration and future season differ | Zero invalid dates; zero checkout ≤ checkin |
| calendar_updated | Entirely blank | Record missingness; leave out of analytical output | No update-date information | Confirm empty tokens and avoid assuming snapshot_date |
| snapshot_date (new) | Filename and row collection dates differ | ISO filename date identifying snapshot, pending confirmation | Stable reproducible panel key | Exactly two snapshot labels; id + snapshot_date unique |

### All t/f fields

Only `t`, `f`, and missing were observed. Proposed representation is nullable Boolean (`t` → true, `f` → false, missing stays missing), with this exact mapping documented. Preserve source tokens in audit evidence. This is a representation change, not a category regrouping.

| Column | Problem found | Proposed rule | Reason | How to check it |
|---|---|---|---|---|
| host_is_superhost | M: t 16,567, f 29,165, missing 356; J: t 16,952, f 26,596, missing 203 | Nullable Boolean; no missing-to-false fill | Unknown host status differs from false | Reconcile t/f/missing counts after mapping |
| host_has_profile_pic | M: t 44,335, f 1,397, missing 356; J: t 42,172, f 1,376, missing 203 | Same mapping | Preserve three states | Reject unexpected tokens and reconcile counts |
| host_identity_verified | M: t 44,363, f 1,369, missing 356; J: t 42,839, f 709, missing 203 | Same mapping | Unknown is not unverified | Reject unexpected tokens and reconcile counts |
| has_availability | M: t 42,184, f 330, missing 3,574; J: t 43,065, f 214, missing 472 | Same mapping; do not infer from availability counts | Source status may differ from numeric calendar fields | Reconcile counts; inspect contradictions rather than overwriting |
| instant_bookable | Missing 46,088/43,751; no populated t/f values | Leave out or retain all-null nullable Boolean, per decision | No evidence of booking mode | Confirm 100% missing and never default to false |

## 5. Text standardization and license formats

Category checks compared original values with stripped text, collapsed whitespace, and case-folded text, within each snapshot and across the stack. For `room_type`, `property_type`, `neighbourhood_cleansed`, `neighbourhood_group_cleansed`, and `source`, there are **zero surrounding-whitespace rows, zero whitespace-collapse changes, and zero case/whitespace collision groups**. No label standardization is needed for these observed categories. Preserve spelling, case, slash notation, and the British `neighbourhood` column names. Property types have union 96, neighbourhoods union 266.

| Room type | March | June |
|---|---:|---:|
| Entire home/apt | 33,676 | 32,454 |
| Private room | 11,754 | 10,590 |
| Shared room | 391 | 292 |
| Hotel room | 267 | 415 |

| Geographic group | March | June |
|---|---:|---:|
| City of Los Angeles | 23,212 | 21,710 |
| Other Cities | 18,642 | 17,960 |
| Unincorporated Areas | 4,234 | 4,081 |

Although shown in IDE context, `data/raw/neighbourhoods.csv` was not present on disk during inspection. Do not claim a geographic-reference join has been validated. Scope filtering or neighbourhood merging requires a decision and, for boundary checks, a suitable reference.

License formats were inspected from the original CSV strings, independently of pandas NA handling. Categories below are descriptive, mutually exclusive, and do not assert legal validity.

| Raw license format | March | June |
|---|---:|---:|
| Empty string | 32,988 | 30,555 |
| Exact uppercase HSR + two digits + hyphen + six digits | 7,030 | 6,979 |
| Same HSR pattern with case variants | 79 | 82 |
| Contains exemption text | 3,670 | 3,867 |
| Digits only | 507 | 427 |
| Other populated strings, including explicit N/A | 1,814 | 1,841 |

There are four literal `N/A` licenses in **each** file. Default pandas parsing counts those as missing, producing 32,992/30,559 rather than the blank-only 32,988/30,555. Preserve the raw token and decide separately whether a derived status treats N/A as unknown.

License has no surrounding whitespace, but collapsing internal whitespace would affect two rows per snapshot. There are 21/25 within-snapshot case/whitespace collision groups, including `HSR19-123456` versus `Hsr19-123456`, `HSR19-003826` versus `hsr19-003826`, and variants of PRP/NRP/STR prefixes. Uppercasing all populated licenses would change 3,828/4,035 rows, largely including exemption prose, so blanket uppercasing is not proposed. A separate identifier-only normalized field could uppercase recognized prefixes and normalize spaces after approval while preserving `license` verbatim. Do not remove hyphens, discard numeric-only values, pad identifiers, infer expiration from digits, or classify exemptions as invalid.

Other observed identifiers include `PRP22-00864`, `NRP25-02140`, `STR24-0100`, `SRH-2018-00018`, `SRH2019-00230`, and `HS-004636-2025`; digits-only examples include `228269` and `241180`. Preserve them as text. Values such as `HSR19-000000` and `HSR19-123456` look placeholder-like but must only be flagged for review. No registry verification was performed.

## 6. Suspicious values: flagged, not fixed

Thresholds in this section are inspection screens, not approved exclusion rules. Counts are listing-snapshot rows; overlapping screens can identify the same row.

| Flag / screen | March | June | Interpretation |
|---|---:|---:|---|
| price = 0 | 0 | 0 | No free-price tokens found |
| price < 0 | 0 | 0 | No negative prices found |
| 0 < price < 10 | 25 | 20 | Low-price screen; units unchanged |
| price > 1,000 | 2,019 | 2,494 | Broad high-price sensitivity screen |
| price > 5,000 | 124 | 143 | Proposed extreme-price review screen |
| price > 10,000 | 18 | 21 | Narrow extreme-price screen |
| minimum_nights ≥ 30 | 22,586 | 20,481 | Long-stay context, not an error |
| source = previous scrape | 10,279 | 6,060 | Possible freshness concern, not automatic invalidity |
| No reviews in 12 months AND availability_365 ≥ 300 | 8,323 | 8,913 | Candidate inactivity flag, not confirmed inactivity |
| Same review condition AND availability_365 ≥ 330 | 7,519 | 7,548 | Alternative high-availability threshold |
| estimated_occupancy_l365d = 255 | 3,179 | 3,167 | Apparent concentration/ceiling; source algorithm not verified |
| maximum_nights > 1,125 | 6 | 6 | Sentinel-like extreme; maximum 2,147,483,647 |
| review_scores_rating = 0 | 1 | 1 | Needs review despite being inside numeric bounds |
| calendar_last_scraped differs from last_scraped | 5 | 7 | Provenance discrepancy |

Price quantiles among nonmissing prices: median **205.41 / 223.67**, p95 **1,053.825 / 1,160.8325**, p99 **2,663.55 / 2,917.2395**. Keep fractional currency units; do not round to integers. The maximum-priced listing is ID `25870842`, an `Entire villa`, at `$20,583.33` in both files. High prices may represent real luxury inventory. Do not winsorize, cap, or delete them based on magnitude alone.

The candidate inactivity screen uses `number_of_reviews_ltm == 0`, not `reviews_per_month == 0` or a filled-in date. High availability and no recent reviews can describe new, seasonal, blocked, or low-demand inventory. Neither this flag nor `365 - availability_365` establishes actual bookings or occupancy.

### Impossible-value checks completed

- Zero out-of-range or fractional counts in availability_30/60/90/365; zero violations of cumulative availability ordering.
- Zero estimated_occupancy_l365d outside [0,365] or fractional values; observed range is [0,255]. Its exact modeling semantics and ceiling remain unverified.
- Zero negative or fractional minimum_nights; zero minimum_nights > maximum_nights on populated pairs.
- Zero invalid populated tokens in the seven populated ISO date columns; host_since and calendar_updated are entirely empty. Zero reversed quote stays, first_review > last_review, or last_review > row last_scraped.
- Zero invalid t/f tokens; zero missing/nondigit id or host_id tokens.
- Zero numeric parse failures for the inspected price, quote nightly amount, stay limits, occupancy, availability, reviews, capacity, coordinates, and main rating fields.
- Zero negative populated values in inferred numeric columns except longitude (negative longitude is expected here). Zero global coordinate-bound violations (latitude ±90, longitude ±180). Geographic boundary membership was not tested.
- Zero violations of review-count ordering l30d ≤ ltm ≤ lifetime; zero values outside [0,5] in any of the seven review-score columns.

Only these tests justify the zero counts above; they do not establish that every unusual value is correct. Future cleaning should report additional checks for any retained field rather than silently coerce failures to null.

## 7. Proposed cleaned schema and output artifacts

Retain all 89,839 rows in the base listing-snapshot output unless Christos explicitly chooses exclusions. Build pricing eligibility separately so unpriced, long-stay, older-source, and suspected-inactive listings remain available for coverage and sensitivity analysis.

Proposed retained source columns (exact source labels):

- **Identity/provenance:** `id`, `host_id`, `listing_url`, `scrape_id`, `last_scraped`, `calendar_last_scraped`, `source`.
- **Segmentation/location:** `neighbourhood_cleansed`, `neighbourhood_group_cleansed`, `room_type`, `property_type`, `latitude`, `longitude`.
- **Price/quote:** `price` (numeric after documented parsing), `price_quote_price_per_night`, `price_quote_total_price`, `price_quote_checkin_date`, `price_quote_checkout_date`, `price_quote_raw` (audit context).
- **Stay/capacity:** `minimum_nights`, `maximum_nights`, `minimum_minimum_nights`, `maximum_minimum_nights`, `minimum_maximum_nights`, `maximum_maximum_nights`, `minimum_nights_avg_ntm`, `maximum_nights_avg_ntm`, `accommodates`, `bathrooms`, `bathrooms_text`, `bedrooms`, `beds`.
- **Availability/activity:** `has_availability`, `availability_30`, `availability_60`, `availability_90`, `availability_365`, `availability_eoy`, `number_of_reviews`, `number_of_reviews_ltm`, `number_of_reviews_l30d`, `number_of_reviews_ly`, `reviews_per_month`, `first_review`, `last_review`, `estimated_occupancy_l365d`, `estimated_revenue_l365d` (explicit estimates).
- **Quality/host context:** all seven `review_scores_*` fields, `host_is_superhost`, `host_has_profile_pic`, `host_identity_verified`, `host_listings_count`, and all four `calculated_host_listings_count*` fields.
- **License:** `license` preserving raw tokens; any separate status/normalized value only after approval.

Proposed new columns: `snapshot_date`, `source_file`, `source_row_number` (1-based CSV data-record ordinal, not physical line number), `price_raw`, and documented flags for missing price/minimum_nights, nonpositive/extreme price, long stay, previous scrape, suspected inactivity, zero rating, occupancy ceiling, extreme maximum_nights, and date/provenance inconsistencies. Flag names and exact predicates go in the data dictionary. Add other derived values only after a decision below. Define missing-input flags explicitly rather than treating unknown comparisons as false.

Leave out all fully missing source fields from the analytical output: `neighborhood_overview`, `host_since`, `host_response_time`, `host_response_rate`, `host_acceptance_rate`, `host_thumbnail_url`, `host_neighbourhood`, `host_total_listings_count`, `host_verifications`, `neighbourhood`, `calendar_updated`, `instant_bookable`.

Also propose leaving out unneeded free text, images, and profile metadata: `name`, `description`, `picture_url`, `host_url`, `host_profile_id`, `host_profile_url`, `host_name`, `hosts_time_as_user_years`, `hosts_time_as_user_months`, `hosts_time_as_host_years`, `hosts_time_as_host_months`, `host_location`, `host_about`, `host_picture_url`, `amenities`. Dropping columns is separate from dropping rows; list omissions and reasons in the dictionary, and keep all original files unchanged. If host_profile_id is later retained, re-read it as a string from raw, never recover it from the float inspection view.

After decisions, proposed artifacts (not created now):

| Artifact | Purpose |
|---|---|
| `scripts/clean_listings.py` | Reproducible pipeline using explicit dtypes, selected approved rules, and deterministic ordering |
| `data/clean/listings_clean.csv` | Combined output with unique id + snapshot_date, including flags |
| `data/clean/listings_sample.csv` | At most 50 unique listing-snapshot rows with difficult cases and selection reasons |
| `data/clean/validation_report.json` | Shapes, schemas, missingness, overlaps, flags, key checks, stage counts, source hashes |
| `data/clean/change_log.csv` | Per-row/per-column changed values with rule ID and before/after values; metadata additions separately recorded |
| `data/clean/dropped_rows.csv` | Original key/provenance and explicit reason for every drop; header-only if zero |
| `data/clean/data_dictionary.md` | Kept/omitted fields, units, label/Boolean maps, flags, approved policy and limitations |
| `cleaning.ipynb` | Executed evidence: raw profile, each transformation's changes, assertions, and regeneration verification |

CSV consumers must explicitly load string identifiers; CSV cannot enforce types. Include loader instructions and schema in the dictionary, or choose an additional typed format below. Output inventory should be explicit; avoid adding redundant per-snapshot exports unless needed.

Sample proposal: deterministic case selection across both snapshots, deduplicated by compound key, followed by seeded coverage of ordinary rows. Cover missing price/quote, price-without-quote, low and extreme price, 19-digit IDs, missing minimum_nights, long stays, previous scrape, possible inactivity, missing reviews, occupancy at 255, extreme maximum_nights, zero rating, license case/space variants and N/A/exempt/numeric/other formats, and differing scrape dates. Use overlapping cases where helpful to stay within 50; state any case type with zero available examples (such as price = 0), and never invent a difficult row.

## 8. Implementation and validation sequence after decisions

1. Freeze approved choices as explicit configuration. Record input hashes, versions, file shapes, per-column dtypes, missing-token policy, and row ordinals. Assert the same column schema and read identifiers safely.
2. Add filename snapshot date and provenance; stack without row loss. Report 46,088 + 43,751 = 89,839 rows and 51,737 distinct IDs. Report keys, duplicates, and overlap before any edits.
3. Parse numeric/date/Boolean fields with documented representation maps and no unit changes. Retain raw price/license evidence and log before/after values. Report each stage's distinct affected rows and cell counts, parse failures, null changes, and all drops (expected zero).
4. Apply only approved text standardization, with a published mapping and exact changed-row counts. Current segment categories need zero changes; license treatment is pending. Report category counts before/after.
5. Add flags before considering remedial actions. Report counts per snapshot and overlapping flag combinations; preserve values. Apply only approved eligibility/exclusion policies and report each reason's count and distinct excluded total.
6. Write selected outputs in deterministic order, plus the sample, audit tables, dictionary, and validation report. Assert conservation (`input rows = kept + dropped`), unique compound keys, safe identifier reload, missingness, ranges, allowed labels, dates, and mapping counts.
7. Execute notebook cells showing findings and change reports. Independently reload outputs and reconcile every changed or dropped row to a rule. Run the script again from unchanged raw files into a fresh output directory and compare every generated artifact byte-for-byte (or an explicitly documented canonical comparison if a format requires it). Avoid volatile timestamps in reproducible artifacts. Recheck raw hashes.

## Decisions for Christos

**No choice below has been implemented.** These are the judgment calls in this plan; evidence favors conservative retention for cleaning, with separate dashboard filters, but Christos chooses the analytical policy.

| Decision | Options | Evidence / consequence |
|---|---|---|
| Geographic scope | All supplied LA-area listings; City of Los Angeles only; selected groups | City counts 23,212/21,710; city-only analysis would exclude 22,876/22,041 rows from eligibility, or from output only if explicitly chosen |
| Snapshot date meaning | Filename date plus actual row scrape dates; row scrape date as analytical date alongside filename snapshot key | March collects through March 18, June through June 23; stable filename keys avoid fragmenting a snapshot |
| Missing-price policy | Keep missing and exclude from price statistics with coverage reporting; impute using a separately justified method | 14,475 missing; row deletion could bias segment coverage. No imputation method is justified by this inspection |
| Quote-to-price fill | Do not fill; approve a documented fallback rule | Approval is required for filling; these files have zero missing-price rows with a populated quote, so no recovery here |
| Price meaning/currency | Preserve numeric source amount with quote context; label as USD nightly only with agreed interpretation; review quote semantics further | `$` formatting; populated quote currency is USD on 33,006/38,207 raw quote objects, null on 4,994/752. Quotes vary by future stay dates; equal fields do not prove fee comparability |
| Extreme/low prices | Flag only; exclude from pricing eligibility; robust summaries; winsorize in a separate analytical field | <10: 25/20; >5,000: 124/143; >10,000: 18/21; p99 differs by snapshot. Choose fixed/percentile/segment threshold and document boundary inclusivity |
| Long stays | Include all; separate ≥30-night cohort; restrict guidance to <30 nights | 22,586/20,481 ≥30; 7/11 unknown minima need an explicit eligibility state |
| Previous-scrape rows | Retain with flags; exclude from guidance; compare both populations | 10,279/6,060 flagged; inspect segment and price-missingness composition before approving a filter |
| Candidate inactivity | Flag only; filter from guidance; use threshold 300/330 or another agreed value | With no reviews_ltm, ≥300 flags 8,323/8,913, ≥330 flags 7,519/7,548; inactivity is not verified |
| License missing-token policy | Preserve blank and literal N/A separately; treat both as unknown in derived status | Four literal N/A per snapshot; default pandas missing counts include them. No inference of legality from unknown |
| License normalization/grouping | Raw only plus flags; separate identifier normalization; separate exemption/status classes | Mixed jurisdictions, 79/82 HSR case variants, two whitespace changes per snapshot; preserve prose and separators. Specify treatment of suspicious placeholders; no registry validation here |
| Category pooling | Preserve categories; approved property-type or small-neighbourhood mapping | No whitespace/case variants; 96 property types and 266 neighbourhoods across stack. Pooling changes requested segment meaning and needs an explicit mapping |
| Missing review activity | Preserve null reviews_per_month and review dates; derive a distinct no-lifetime-reviews flag; fill rate zero only if explicitly justified | 23,776 missing rates match zero lifetime reviews. Filling changes rate meaning |
| Estimated occupancy/revenue use | Context only; use as labeled modeled signals; omit from dashboard rankings | Occupancy ends at 255 with 3,179/3,167 at that value; estimates are not observed bookings or earnings. Definition verification is still needed |
| Capacity gaps and unusual values | Preserve and flag; approve separate bathroom-text extraction; impute only with a justified method | Bathrooms/beds/bedrooms missingness differs by snapshot; half baths and studios make blanket rules inappropriate |
| Other anomalies/failures | Retain and flag; quarantine only from affected metrics; approve nulling/drops after case review | Extreme maximum_nights, zero ratings, scrape-date mismatches are present; tested impossible values currently zero. No arbitrary repair or duplicate survivor rule is approved |
| Representation/schema | Numeric price with raw copy, ISO dates, nullable Booleans; retain source t/f fields instead; retain all-null placeholders if a downstream schema needs them | Mappings must preserve missingness and units. Proposed omissions and derived fields require agreement; add a typed format if desired |
| Artifact formats and sample | Combined CSV and audit artifacts as proposed; add Parquet or per-snapshot CSVs; approve deterministic case sample strategy | CSV has no dtype metadata; sample ≤50 must show difficult cases. Final inventory determines the regeneration test |
| Dashboard eligibility and small segments | Keep filters independent from cleaning; set minimum priced listings/coverage before ranking; choose thresholds after segment profiling | Segment-level coverage and sample-size distributions have not yet been profiled. Use medians/quantiles versus means by decision; choose all listings or matched 38,102-ID cohort for change comparisons |

No dashboard prioritization score is selected yet. Approved cleaning should retain enough context to compare price dispersion, coverage, long-stay mix, freshness, and activity proxies without presenting availability as observed demand.

## Appendix: complete schema and missingness inventory

The following inventory is generated from the read-only inspection, with the same dtype in both files. It makes all 90 source columns and their missing counts reviewable.


| Source column | March dtype | June dtype | March missing | June missing | Stacked missing |
|---|---|---|---:|---:|---:|
| id | string | string | 0 | 0 | 0 |
| listing_url | str | str | 0 | 0 | 0 |
| scrape_id | int64 | int64 | 0 | 0 | 0 |
| last_scraped | str | str | 0 | 0 | 0 |
| source | str | str | 0 | 0 | 0 |
| name | str | str | 1 | 0 | 1 |
| description | str | str | 1,312 | 924 | 2,236 |
| neighborhood_overview | float64 | float64 | 46,088 | 43,751 | 89,839 |
| picture_url | str | str | 0 | 0 | 0 |
| host_id | string | string | 0 | 0 | 0 |
| host_url | str | str | 0 | 0 | 0 |
| host_profile_id | float64 | float64 | 356 | 203 | 559 |
| host_profile_url | str | str | 357 | 214 | 571 |
| host_name | str | str | 355 | 203 | 558 |
| host_since | float64 | float64 | 46,088 | 43,751 | 89,839 |
| hosts_time_as_user_years | float64 | float64 | 356 | 203 | 559 |
| hosts_time_as_user_months | float64 | float64 | 356 | 203 | 559 |
| hosts_time_as_host_years | float64 | float64 | 356 | 203 | 559 |
| hosts_time_as_host_months | float64 | float64 | 356 | 203 | 559 |
| host_location | str | str | 11,075 | 10,662 | 21,737 |
| host_about | str | str | 20,488 | 19,044 | 39,532 |
| host_response_time | float64 | float64 | 46,088 | 43,751 | 89,839 |
| host_response_rate | float64 | float64 | 46,088 | 43,751 | 89,839 |
| host_acceptance_rate | float64 | float64 | 46,088 | 43,751 | 89,839 |
| host_is_superhost | str | str | 356 | 203 | 559 |
| host_thumbnail_url | float64 | float64 | 46,088 | 43,751 | 89,839 |
| host_picture_url | str | str | 356 | 203 | 559 |
| host_neighbourhood | float64 | float64 | 46,088 | 43,751 | 89,839 |
| host_listings_count | float64 | float64 | 356 | 203 | 559 |
| host_total_listings_count | float64 | float64 | 46,088 | 43,751 | 89,839 |
| host_verifications | float64 | float64 | 46,088 | 43,751 | 89,839 |
| host_has_profile_pic | str | str | 356 | 203 | 559 |
| host_identity_verified | str | str | 356 | 203 | 559 |
| neighbourhood | float64 | float64 | 46,088 | 43,751 | 89,839 |
| neighbourhood_cleansed | str | str | 0 | 0 | 0 |
| neighbourhood_group_cleansed | str | str | 0 | 0 | 0 |
| latitude | float64 | float64 | 0 | 0 | 0 |
| longitude | float64 | float64 | 0 | 0 | 0 |
| property_type | str | str | 0 | 0 | 0 |
| room_type | str | str | 0 | 0 | 0 |
| accommodates | int64 | int64 | 0 | 0 | 0 |
| bathrooms | float64 | float64 | 10,288 | 7,761 | 18,049 |
| bathrooms_text | str | str | 102 | 168 | 270 |
| bedrooms | float64 | float64 | 3,196 | 9,572 | 12,768 |
| beds | float64 | float64 | 10,439 | 6,631 | 17,070 |
| amenities | str | str | 0 | 0 | 0 |
| price | str | str | 8,910 | 5,565 | 14,475 |
| price_quote_checkin_date | str | str | 8,088 | 4,792 | 12,880 |
| price_quote_checkout_date | str | str | 8,088 | 4,792 | 12,880 |
| price_quote_total_price | float64 | float64 | 8,913 | 5,569 | 14,482 |
| price_quote_price_per_night | float64 | float64 | 8,913 | 5,569 | 14,482 |
| price_quote_raw | str | str | 8,088 | 4,792 | 12,880 |
| minimum_nights | float64 | float64 | 7 | 11 | 18 |
| maximum_nights | float64 | float64 | 7 | 11 | 18 |
| minimum_minimum_nights | float64 | float64 | 7 | 11 | 18 |
| maximum_minimum_nights | float64 | float64 | 7 | 11 | 18 |
| minimum_maximum_nights | float64 | float64 | 7 | 11 | 18 |
| maximum_maximum_nights | float64 | float64 | 7 | 11 | 18 |
| minimum_nights_avg_ntm | float64 | float64 | 0 | 0 | 0 |
| maximum_nights_avg_ntm | float64 | float64 | 0 | 0 | 0 |
| calendar_updated | float64 | float64 | 46,088 | 43,751 | 89,839 |
| has_availability | str | str | 3,574 | 472 | 4,046 |
| availability_30 | int64 | int64 | 0 | 0 | 0 |
| availability_60 | int64 | int64 | 0 | 0 | 0 |
| availability_90 | int64 | int64 | 0 | 0 | 0 |
| availability_365 | int64 | int64 | 0 | 0 | 0 |
| calendar_last_scraped | str | str | 0 | 0 | 0 |
| number_of_reviews | int64 | int64 | 0 | 0 | 0 |
| number_of_reviews_ltm | int64 | int64 | 0 | 0 | 0 |
| number_of_reviews_l30d | int64 | int64 | 0 | 0 | 0 |
| availability_eoy | int64 | int64 | 0 | 0 | 0 |
| number_of_reviews_ly | int64 | int64 | 0 | 0 | 0 |
| estimated_occupancy_l365d | int64 | int64 | 0 | 0 | 0 |
| estimated_revenue_l365d | float64 | float64 | 8,910 | 5,565 | 14,475 |
| first_review | str | str | 12,519 | 11,257 | 23,776 |
| last_review | str | str | 12,519 | 11,257 | 23,776 |
| review_scores_rating | float64 | float64 | 12,519 | 11,257 | 23,776 |
| review_scores_accuracy | float64 | float64 | 12,524 | 11,262 | 23,786 |
| review_scores_cleanliness | float64 | float64 | 12,524 | 11,262 | 23,786 |
| review_scores_checkin | float64 | float64 | 12,530 | 11,264 | 23,794 |
| review_scores_communication | float64 | float64 | 12,525 | 11,261 | 23,786 |
| review_scores_location | float64 | float64 | 12,531 | 11,265 | 23,796 |
| review_scores_value | float64 | float64 | 12,532 | 11,266 | 23,798 |
| license | str | str | 32,992 | 30,559 | 63,551 |
| instant_bookable | float64 | float64 | 46,088 | 43,751 | 89,839 |
| calculated_host_listings_count | int64 | int64 | 0 | 0 | 0 |
| calculated_host_listings_count_entire_homes | int64 | int64 | 0 | 0 | 0 |
| calculated_host_listings_count_private_rooms | int64 | int64 | 0 | 0 | 0 |
| calculated_host_listings_count_shared_rooms | int64 | int64 | 0 | 0 | 0 |
| reviews_per_month | float64 | float64 | 12,519 | 11,257 | 23,776 |

### Source fingerprints

These SHA-256 fingerprints identify the exact inspected files. Repeated inspection produced the same hashes.

- `listings_2026-03-16.csv`: `b112bcd60c4202dce8c6b798230dff0081a928a02902d7de02f962365c2d10a4`
- `listings_2026-06-15.csv`: `551de961e6d3c470a09fe79dea5fc3270b2b19ccd2c4c937d1f2ab7ab6e7b90a`
