# DSO576_Project
Short-Term Rental Marketplace Health

Business Question: A Marketplace Strategy Manager at Airbnb must decide which Los Angeles neighborhood-property segments should be prioritized for closer pricing review.

Vision: The manager selects a neighborhood, room type, and bedroom count; compares the segment's observed price distribution with comparable listings; reviews availability, recent review activity, value ratings, and minimum-stay rules; and checks whether the price pattern persists across snapshots. The output is a shortlist of segments for human review.

Main metric: median nightly price per segment, with IQR as price spread and estimated occupancy, 30-day availability and reviews in the last 12 months as demand signals.

Will Samuels:

Branch name: wsamuels /
Branch URL: https://github.com/chenwang266/DSO576_Project/tree/wsamuels / 
Commit ID:

## Data cleaning

**Unit of analysis:** segment = `neighbourhood_cleansed` x `property_segment` (`room_type` x stay type). **Row grain:** one listing per snapshot, key = (`snapshot`, `id`).

### Source (U2)
| snapshot | raw file | scrape_id | scrape dates | rows x cols | sha256 |
|---|---|---|---|---|---|
| 2026-03 | `data/raw/3_15.csv.gz` | 20260316030553 | 2026-03-16 to 03-18 | 46,088 x 90 | `ffdef08afe58b62e57cffb9da0f1daa97bf76e223fe98ce9e2022dd330976fc6` |
| 2026-06 | `data/raw/6_15.csv.gz` | 20260615054117 | 2026-06-15 to 06-23 | 43,751 x 90 | `ebc99e8a5ff2f60cbd91323571c2bdf1f8c2c74fe3ac9669d7c9a24d2294dec5` |

Source: Inside Airbnb, Los Angeles `listings.csv.gz` (https://insideairbnb.com/get-the-data/). Raw files are read-only and are never modified.

### How to run (U20)
```
pip install -r requirements.txt      # Python 3.9
python src/profile_raw.py > outputs/profile_raw.txt     # optional: read-only profile
python src/profile_checks.py > outputs/profile_checks.txt
python src/clean.py                  # rebuilds every file below from data/raw
```
The output is deterministic. `outputs/output_hashes.csv` should read
`data/clean/listings_clean.csv.gz  f4b92b16c4d7dc60422253a01595e442f9ec9efc5cb8120ed6eb7d6611e609f6`.
Read the clean file with ID columns as text: `pd.read_csv(..., dtype={"id": str, "host_id": str, "host_profile_id": str, "scrape_id": str})`.

### Expected files
| file | contents |
|---|---|
| `data/clean/listings_clean.csv.gz` | 89,839 rows x 95 columns, no rows removed; flag columns added |
| `outputs/cleaning_log.csv` | one line per rule and column: rule, column, rows_affected, rows_before, rows_after, note |
| `outputs/reconciliation.csv`, `reconciliation_by_rule.csv` | funnel from raw rows to the analysis sample; rows removed by rule (all 0) |
| `outputs/record_checks.csv` | U19 check of hard cases, with expected results written before the run |
| `outputs/missing_summary.csv` | nulls per column before and after (count and %) |
| `outputs/price_coverage_by_segment.csv`, `price_missing_comparison.csv` | price coverage by segment; listings with vs without a price |
| `outputs/segment_sizes.csv`, `small_segments.csv` | n per segment; segments below n=20 reported separately |
| `outputs/outlier_sensitivity.csv`, `r13_outlier_examples.csv` | segment median and IQR with vs without outliers; flagged rows |
| `outputs/logic_checks.csv`, `dropped_columns.csv`, `source_manifest.csv`, `clean_schema.csv`, `r04_type_examples.csv`, `r05_text_examples.csv` | evidence for R14, R03, R02, the column dtypes, R04 and R05 |

### Rules (implemented as `rNN_*` functions in `src/clean.py`)
R01 stack the snapshots and set the key · R02 provenance · R03 drop 16 columns with no information (11 empty, 1 constant, 2 exact copies, 2 URLs rebuildable from IDs) · R04 types (IDs stay strings; `price` becomes `price_usd`; booleans; dates; 0 conversion failures) · **R04a** `stay_type` / `property_segment` / `segment` · R05 clean whitespace and invisible characters in `name` · R06 check units (all USD; price = quote total / nights) · R07 duplicates (0 exact; near duplicates flagged) · **R08** `price_missing` flag · R09 structural missing (`no_reviews`) · R10 other missing · R11 sentinels set to NA plus flags · R12 range checks (`occupancy_at_cap`, `bedrooms_gt_accommodates`) · **R13** `price_outlier` · R14 logic checks · R15 date checks · R16 merge (not applicable) · **R17** `segment_rankable`.

### Judgment calls tied to the business question (U22)
- **Stay type is part of the segment (R04a).** `price` is the per-night amount of a quote for a stay as long as the listing's minimum stay, after discounts. For listings with a minimum of 30+ nights it is a discounted monthly rate (median about $134 vs $274 for short stays). Pooling the two would make a neighbourhood look "cheap" just because it has more monthly rentals, which is the wrong reason to send it to pricing review.
- **Bedrooms are not part of the segment (R06).** The two snapshots code size differently (2,240 studios with 0 bedrooms in March are blank in June), so a size split would differ between snapshots for reasons that have nothing to do with pricing.
- **Missing prices are excluded from the price metric, not imputed (R08).** 86–87% of listings without a price are "previous scrape" rows with 0 availability and 0 recent reviews, i.e. listings that couldn't be quoted. Imputing a price would create supply that a pricing manager can't act on.
- **Outliers: log-price IQR with k = 3, computed per snapshot x property segment across all of LA, and flagged rather than removed (R13).** Computing it within each neighbourhood would hide the unusual segments the manager is looking for. k = 3 catches data errors ($3–10/night monthly rooms, a $11,412 one-guest tiny home) without labelling the luxury tail as wrong. Medians change by more than 5% in only 14 of 716 rankable segments, mostly luxury monthly segments in Bel-Air and Malibu.
- **Minimum of 20 priced listings to rank a segment (R17).** A median and IQR from fewer than 20 listings are too noisy to justify a review. 358 segments per snapshot qualify (about 89% of priced listings); the rest are listed in `small_segments.csv`.

### Reconciliation (U18)
| step | 2026-03 | 2026-06 |
|---|---|---|
| all raw rows | 46,088 | 43,751 |
| after cleaning (0 removed) | 46,088 | 43,751 |
| with a price (lost: missing price) | 37,178 (−8,910) | 38,186 (−5,565) |
| known stay type (lost: null minimum nights) | 37,171 (−7) | 38,177 (−9) |
| in a rankable segment, n ≥ 20 (lost: small segments) | 33,123 (−4,048) | 34,038 (−4,139) |
| of which flagged as price outliers (kept) | 183 | 141 |

### Five-record check (U19)
5 of 6 matched. **No match:** listing `1127572` ($8.47/night, 300-night minimum) was expected *not* to be flagged, because I estimated the Private room | Monthly low fence at about $5. The actual fence is $10.24, so it is flagged as a low outlier. The prediction was wrong; the rule worked as specified, and the expected value was left unchanged.

### Limitations (U21)
- **Price is a single quote**, for one set of dates at the minimum stay length. It is not the average nightly rate, and it excludes cleaning fees and taxes (those fields are empty). Segment medians reflect quoted asking prices, not prices paid.
- **Demand signals are modelled and censored.** `estimated_occupancy_l365d` is derived from reviews (no listing has occupancy > 0 without recent reviews) and is capped at 255 nights (6,346 rows at the cap). Listings with few reviews, and segments with many hosts who rarely get reviewed, will look low-demand.
- **Missing price is not random.** It is concentrated in inactive "previous scrape" listings, so segment medians describe active supply only. Segments with low price coverage (`price_coverage_by_segment.csv`) should be read with caution.
- **Two snapshots only (March and June).** Seasonal effects can't be separated from trend, and availability values describe each scrape moment only.
- **Empty fields that would help:** `instant_bookable`, host response and acceptance rates, and `host_since` are 100% empty in this release.
- **Size fields** (bedrooms, beds, bathrooms) are coded inconsistently between snapshots, so price per bedroom or per guest across snapshots is unreliable.
- **What would help:** calendar-level prices (`calendar.csv.gz`) to get a typical nightly rate, and booking data instead of review-based occupancy estimates.
