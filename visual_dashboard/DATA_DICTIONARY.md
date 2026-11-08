# Data dictionary

## Canonical listing grain and types

`canonical_listings_clean.csv`: one row per `(snapshot_date, listing_id)`, 89,839 rows on the supplied inputs. Empty numeric/date CSV cells mean unavailable, never zero. IDs and categories are strings. Runtime numeric measures are nullable/NaN numeric values; explicit `True`/`False` columns load as booleans. No personal host details or coordinates are in the canonical artifacts/UI.

| Field(s) | Definition |
| --- | --- |
| `listing_id` | Trimmed source `id`, preserved as text (including leading zeros/long IDs) |
| `snapshot_date` | Nominal extract date: 2026-03-16 or 2026-06-15 |
| `source_file`, `source_row_number` | Input basename and 1-based source **record** number, excluding header (not physical text line for multiline CSV records) |
| `source` | Trimmed/collapsed source category; missing → Unknown |
| `last_scraped`, `last_review` | Valid ISO source dates or unavailable; separate from nominal date |
| `last_scraped_status`, `last_review_status` | valid / missing / malformed |
| `neighbourhood_raw`, `neighbourhood` | Source token and whitespace-normalized neighborhood; blank → Unknown |
| `neighbourhood_is_known` | Whether neighborhood is not Unknown |
| `room_type_raw`, `room_type`, `room_type_is_known` | Source token, canonical four-category room label or Unknown, known flag |
| `bedrooms_raw`, `bedrooms` | Source token; valid nonnegative integral count or unavailable |
| `bedroom_status` | valid / missing / malformed / invalid_noninteger / invalid_range |
| `bedroom_is_zero` | Valid source bedrooms equals zero; does not include missing |
| `bedroom_segment` | Studio / 1 bedroom / 2 bedroom / 3 bedroom / 4 bedroom / 5 bedroom / 6+ bedrooms / Unknown. UI preserves canonical spelling for stable filters. |
| `minimum_nights`, `minimum_nights_status` | Nonnegative integer and validation status; zero retained but stay cohort Unknown |
| `stay_type` | 1–29 → Short stay (<30 nights); ≥30 → Long stay (30+ nights); otherwise Unknown |
| `price_raw`, `price_usd`, `price_status` | Raw token, valid positive USD or unavailable; valid / missing / malformed / invalid_nonpositive |
| `has_valid_price` | `price_status == valid` |
| `availability_30/60/90/365` | Nonnegative integer no greater than named horizon |
| `availability_*_status` | Integer-validation status; invalid values become unavailable |
| `number_of_reviews`, `number_of_reviews_ltm`, `number_of_reviews_l30d` | Nonnegative integers for total / last 12 months / last 30 days |
| `number_of_reviews*_status` | Integer-validation status |
| `reviews_per_month`, `reviews_per_month_status` | Nonnegative decimal or unavailable; valid / missing / malformed / invalid_range |
| `review_scores_value`, `review_scores_value_status` | Decimal within 0–5 or unavailable; valid / missing / malformed / invalid_range |
| `review_scores_value_zero` | Valid value score is exactly zero; retained and flagged |
| `pricing_eligible` | Valid price + known neighborhood/room + valid bedroom |
| `segment_key` | Stable readable neighborhood, room, bedroom bucket separated by ` | ` |

Input SHA-256 hashes apply to every record originating from that file and are stored in `canonical_cleaning_report.json`. No raw data are modified.

## Canonical segment artifact

`canonical_price_segments.csv`: unique `(snapshot_date, neighbourhood, room_type, bedroom_segment)` with known dimensions. `listing_rows` counts all records in that comparable group; `priced_rows` counts positive valid prices. `price_coverage = priced_rows / listing_rows` with full precision. `median_price_usd`, `p25_price_usd`, `p75_price_usd`, `price_iqr_usd`, `min_price_usd`, `max_price_usd` use valid prices only. IQR = P75−P25, using linear interpolation. `is_small_sample = priced_rows < 20` is fixed.

## Cleaning report

`canonical_cleaning_report.json`: schema version, grain/key, input filenames/hashes, row conservation, price statuses, bedroom missingness/zero counts, source counts, actual scrape dates, raw-unchanged flags, output schemas and artifact fingerprints, eligibility and outlier policies. The report does not hash itself. A combined fingerprint including the report is calculated by the loader and included in exports.

## Comparison, detail and shortlist evidence

Export dates use `snapshot_march` / `snapshot_june`. Each per-date metric has `_march` / `_june` suffix; `peer_` indicates pooled LA peers **including the local neighborhood** under identical room/bedroom/stay/source filters. Missing opposite dates remain null.

| Fields | Definition |
| --- | --- |
| `listing_rows`, `priced_rows`, `price_coverage`, price summaries, `is_small_sample` | Same definitions as canonical segment artifact; also calculated for peer populations |
| `availability_90_median`, `reviews_ltm_median`, `value_score_median`, `minimum_nights_median` | Medians among valid observations of each context measure, regardless of price missingness |
| Corresponding `*_valid_n` | Separate observation denominator for each context measure |
| `local_bedroom_base_rows`, `peer_bedroom_base_rows` | Population before bedroom exclusions, with selected room and optional stay/source filters; local adds neighborhood |
| `local_unknown_bedroom_rows/share`, `peer_unknown_bedroom_rows/share` | Unknown/invalid-bedroom count and fraction of that pre-bedroom population |
| `previous_scrape_share`, `unknown_source_share` | Source-category share in known-dimension local group; peer prefix for peer group |
| `sufficient_data` | Both local and peer priced counts meet adjustable minimum and peer median >0; independent of fixed `<20` flag |
| `premium_pct` | `100 × (local median / peer median − 1)` if sufficient data; otherwise unavailable |
| `premium_unavailable_reason` | Human-readable threshold/benchmark explanation |
| `change_usd`, `change_pct` | June−March median, and `100 × change / March median`; no missing/zero-baseline fill |
| `persistence_status` | Persistent premium / Persistent discount / Reversed / Neutral / Insufficient evidence |
| `direction`, `review_score` | Premium/Discount for persistent rows; score = min absolute two-date premiums in percentage points. Context is not scored. |
| `rank` | 1-based position in visible direction result; deterministic tie order |
| `minimum_priced`, `coverage_warning_threshold` | Current adjustable count and coverage fraction (0–1) |
| `stay_filter`, `source_filter`, `peer_definition` | Explicit analysis population/settings |
| `warnings` | Date/population-specific coverage, fixed small sample, current evidence threshold, bedroom composition, Studio, source cautions |
| `canonical_fingerprint` | SHA-256 of the three current canonical artifact contents/names, including report |

Premium/change fields use **percentage units**, so −40 means −40%, while coverage/share fields use **fractions**, so 0.8 means 80%. Scores are percentage points. CSVs retain full floating precision; UI prices use two decimals and percentage displays use one where practical. Diagnostic shares/flags remain available in full evidence. No unavailable value is substituted with zero or infinity.
