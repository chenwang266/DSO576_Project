# Data dictionary

Source: Inside Airbnb, Los Angeles detailed listings (the source extract's geography), nominal snapshots 2026-03-16 and 2026-06-15. All files are UTF-8 CSV. Booleans are written as `True`/`False`, and a missing value is an empty cell.

## `canonical_listings_clean.csv`

One row per listing per snapshot. `(snapshot_date, listing_id)` is unique. All rows are kept, including rows with missing prices or unknown dimensions. Host details, listing text and coordinates are not included.

| Column | Type | Meaning |
| --- | --- | --- |
| `snapshot_date` | string | Nominal snapshot date from config (`2026-03-16` / `2026-06-15`). Not taken from the scrape date. |
| `snapshot_label` | string | `March` / `June` |
| `listing_id` | string | Raw `id` with surrounding whitespace trimmed. Kept as text so it stays exact, including leading zeros. |
| `source_file`, `source_row` | string, int | Raw file name and 1-based data record number (header excluded) |
| `input_sha256` | string | SHA-256 of the raw input file |
| `last_scraped` | string | Actual scrape date from the source. Optional field. |
| `source_raw`, `source_category` | string | Raw `source` value. The category is that value trimmed, with blank → `Unknown`. Values: `city scrape`, `previous scrape`. |
| `price_raw`, `price_usd`, `price_status` | string, float, string | Original price text, the parsed positive USD amount, and `valid` / `missing` / `malformed` / `invalid_nonpositive`. `price_usd` is filled only when the status is `valid`. |
| `neighbourhood_raw`, `neighbourhood` | string | Raw `neighbourhood_cleansed`. The clean value collapses whitespace, with blank → `Unknown`. |
| `room_type_raw`, `room_type` | string | One of `Entire home/apt`, `Private room`, `Shared room`, `Hotel room`, otherwise `Unknown` |
| `bedrooms_raw`, `bedrooms`, `bedrooms_status` | string, int, string | Raw text, the valid nonnegative integer count, and `valid` / `missing` / `malformed` / `out_of_range` |
| `bedroom_segment`, `bedroom_order` | string, int | `Studio` (0), `1 bedroom` … `5 bedrooms`, `6+ bedrooms` (≥6), or `Unknown` when missing or invalid. Missing is never treated as Studio. The order field is 0–6, or empty for Unknown. |
| `minimum_nights_raw`, `minimum_nights`, `minimum_nights_status` | string, int, string | Optional field. The status is `unavailable` if the column is absent. |
| `stay_category` | string | `Short stay (<30 nights)` for 1–29 nights, `Long stay (30+ nights)` for ≥30, and `Unknown` for zero, missing or invalid |
| `availability_{30,60,90,365}` + `_status` | int, string | Nonnegative and no larger than the horizon. Values outside that range are blanked and marked `out_of_range`. |
| `number_of_reviews_ltm`, `number_of_reviews_l30d` + `_status` | int, string | Nullable nonnegative integers |
| `review_scores_value`, `review_scores_value_status`, `value_score_is_zero` | float, string, bool | Score from 0 to 5. Missing stays missing. Zero is flagged. |
| `number_of_reviews`, `reviews_per_month` + `_status` | int/float, string | Optional fields. The status is `unavailable` if the column is absent. |
| `first_review`, `last_review` | string | Optional raw dates |
| `has_valid_price` | bool | `price_status == valid` |
| `has_valid_dimensions` | bool | Neighbourhood, room type and bedroom segment are all known |
| `pricing_eligible` | bool | `has_valid_price` and `has_valid_dimensions` |
| `segment_key` | string | JSON `["<neighbourhood>", "<room_type>", "<bedroom_segment>"]`. Empty when the dimensions are not valid. |

## `canonical_price_segments.csv`

One row per `snapshot_date` × segment, over all stays and sources. Only segments with at least one valid-dimension listing appear.

| Column | Meaning |
| --- | --- |
| `snapshot_date`, `segment_key`, `neighbourhood`, `room_type`, `bedroom_segment`, `bedroom_order` | Segment identity |
| `listing_rows` | Listings with valid dimensions, including those with missing or invalid prices |
| `priced_rows` | Pricing-eligible listings |
| `price_coverage` | `priced_rows / listing_rows` |
| `median_price_usd`, `p25_price_usd`, `p75_price_usd` | Computed from eligible prices with linear interpolation |
| `price_iqr_usd` | `p75 − p25` |
| `min_price_usd`, `max_price_usd` | Range of eligible prices. Not capped. |
| `is_small_sample` | `priced_rows < 20`. Fixed, and not tied to the adjustable minimum. |

## `canonical_cleaning_report.json`

Contents:

- inputs: nominal date, file name, size, and SHA-256 before and after cleaning
- output SHA-256 hashes and row counts
- for each snapshot: actual scrape dates, price statuses, bedroom status and segment counts, unknown dimensions, stay and source counts, field validation statuses, and a check against the spec's reference counts
- schema and dtypes
- policies

## Backend outputs (not persisted)

- **`pricing.segment_metrics`**: one row per date × segment under the given stay/source filters. It carries the local columns above plus context (`<field>_median` and `<field>_n` for `availability_90`, `number_of_reviews_ltm`, `review_scores_value` and `minimum_nights`) and the same set again prefixed `peer_` for the inclusive LA peer. It also includes:
  - `premium_pct`, calculated as `100 × (local median / peer median − 1)`
  - `premium_status`: `available` / `no_local_prices` / `local_below_minimum` / `peer_below_minimum` / `peer_median_nonpositive`
  - `sufficient_evidence`
  - `local_unknown_bedroom_share` (same neighbourhood and room) and `peer_unknown_bedroom_share` (same room across LA)
  - `local_city_scrape_share`
  - `min_priced`
- **`history.compare_snapshots`**: an outer join on the segment, with `_march` / `_june` suffixes and nothing forward-filled. It adds:
  - `change_usd` (June − March)
  - `change_pct` (100 × change / March, blank unless March > 0)
  - `persistence`: `Persistent premium` / `Persistent discount` / `Reversed` / `Neutral` / `Insufficient evidence`
  - `direction`
  - `review_score`: the smaller absolute premium of March and June, persistent segments only
  - `warnings` (`; `-separated) and `warning_count`
- **`history.rank_shortlist`**: persistent rows with a `rank` column, sorted by `review_score` descending, then by neighbourhood, room type and bedroom order.

## Dashboard exports (CSV)

- **`review_shortlist_<direction>.csv`**: one row per visible shortlist segment. The first columns record the settings that produced it: `generated_utc`, `canonical_fingerprint`, `march_nominal_date`, `june_nominal_date`, `stay_filter`, `source_filter`, `min_priced_count`, `coverage_warning_threshold`, `small_sample_threshold`, `unknown_bedroom_warning_threshold`, `shortlist_direction`, `peer_definition`. Then every `history.rank_shortlist` column (`rank`, segment identity, both dates' local and peer metrics and context, premiums and statuses, changes, persistence, score, warnings) at full precision. An empty shortlist exports the header only.
- **`evidence_<segment>.csv`**: long format with `section`, `field`, `value`. Sections are `settings` (as above, without direction), `segment`, `comparison` (every `history.compare_snapshots` field for that segment, or a status line if it has no listings in either snapshot) and, when exported from Segment Detail, `detail warnings (<snapshot>)`.

