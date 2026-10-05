# Clean Los Angeles listing-snapshot data

Grain: one row per listing per snapshot. Key: id + snapshot_date. All raw rows are retained; no prices or capacity values are imputed, capped, or deleted. Category labels and neighbourhood groups are unchanged. Both source CSVs are read-only.

## Loading and representations

Use pandas.read_csv(..., dtype={'id':'string', 'host_id':'string', 'scrape_id':'string', 'license':'string'}, keep_default_na=False) followed by explicit blank-only missing conversion according to this schema. License remains an exact raw string, including blank and N/A. Empty CSV numeric/date/Boolean cells mean missing. CSV cannot encode types; IDs must never pass through Excel numeric inference or floats. Script ingestion reads every raw token as a string, then maps blank tokens to missing in every source field except license. The omitted host_verifications field additionally maps literal None to missing, explaining its entirely missing status in the original inspection. Thus the eight literal N/A licenses remain preserved while license_status marks them missing.

price_raw preserves source currency text. price removes $ and thousands commas only; amount and fractional units are unchanged. No quote-to-price fallback exists. Source price is interpreted as a currency amount per listed night; quote currency evidence is USD when specified, but quote dates/fee semantics vary, so no currency conversion or fee normalization is performed. price_quote_total_price is a stay-total amount, not a nightly rate. price_quote_price_per_night is separate. Latitude/longitude remain decimal degrees. Night limits and availability are nights/days, reviews_per_month is reviews/month, review_scores_* remain 0–5. estimated_occupancy_l365d remains estimated days in the past 365 days and estimated_revenue_l365d remains a modeled currency estimate, not realized earnings. Do not derive observed bookings from unavailable days.

All six retained dates and snapshot_date serialize as YYYY-MM-DD. Dates are not timezone-converted. snapshot_date is filename-derived and actual scrape dates remain separate. t -> True, f -> False, blank -> missing for the four retained t/f fields; no missing-to-false fill. Integral count fields use nullable Int64; fractional measures use nullable Float64. No capacity imputation or bathroom-text extraction is performed. Source row number is a 1-based CSV data-record ordinal, not a physical line number.

## Policy and derived fields

- stay_type: short if minimum_nights <30, long if >=30, unknown if missing. No pooling of neighbourhood_cleansed x room_type segments.
- primary_pricing_eligible: short AND price present AND source == city scrape. Missing prices do not enter medians. Low/high prices and possible inactivity remain eligible for price statistics.
- demand_eligible: short AND city scrape AND NOT flag_possible_inactivity; price is not required. Long stays are separately summarized as a cohort and their flagged counts reported; no inactive row contributes to primary demand proxies.
- Priced coverage: nonmissing prices / all rows for each segment and cohort. Primary coverage denominator is all short city-scrape rows, including missing prices. Medians retain outliers. Do not combine cohorts or snapshots without explaining the changed population.
- no_reviews: number_of_reviews ==0. reviews_per_month and review dates stay null; a zero review count does not establish zero demand.
- flag_missing_price / flag_missing_minimum_nights: missing parsed source values.
- flag_price_low / flag_price_high: price <10 / price >5000, respectively. Missing prices yield unknown in comparison flags. Boundaries 10 and 5000 are not flagged. flag_price_zero is price ==0; flag_price_nonpositive is price <=0.
- flag_previous_scrape: source == previous scrape.
- flag_possible_inactivity: number_of_reviews_ltm ==0 AND availability_365 >=300. This is a suspicion, not proven inactivity.
- flag_occupancy_at_255: estimated_occupancy_l365d ==255, noting an apparent ceiling; no correction.
- flag_extreme_maximum_nights: maximum_nights >1125; preserves possible sentinel values.
- flag_zero_rating: review_scores_rating ==0. Missing ratings yield unknown.
- flag_scrape_date_discrepancy: last_scraped differs from calendar_last_scraped. flag_scraped_after_snapshot records multi-day collection rather than an error. flag_review_after_scrape uses the row's actual last_scraped.
- flag_impossible_value: union of nonpositive/fractional stay minima/maxima, min > max, negative/fractional review and capacity count fields, negative bathrooms/rates/revenue/occupancy, occupancy >365, bad cumulative calendar bounds/order, review-count order, coordinate bounds, scores outside [0,5], reversed review/quote dates, or review dates after actual scrape. These are screens, not repair instructions. Unknown comparisons are ignored in this union, and missingness is separately reported.
- license_status: missing for blank or case-insensitive N/A; exempt for text containing exempt; hsr_registered for case-insensitive HSR##-######; other_identifier for other populated tokens. hsr_registered denotes format only, not registry verification; other_identifier can include unrecognized prose.
- license_normalized: uppercase ONLY full matches of HSR##-######, PRP/NRP##-#####, STR##-#### or #####, SRH[-]####-#####, HS-######-####, or digits-only identifiers. Other tokens are missing here and remain intact in license. No whitespace or separator rewrites. flag_license_normalized records changed case; flag_license_whitespace compares raw with stripped/collapsed whitespace; flag_license_unrecognized means populated nonexempt license outside these patterns. Placeholder-like HSR suffixes 000000 and 123456 are flagged by flag_license_placeholder, never invalidated.

## Audit and reproducibility

validation_report.json includes exact source hashes, row/duplicate accounting, raw and output missingness, price/quote overlap, source-specific price coverage BEFORE eligibility, changed-cell counts and examples per transformation, overlapping-row totals, flag counts by snapshot, summary tables and sample coverage. Existing-cell change counts compare serialized string representations; dtype-only changes with identical text are separately visible in dtype inventories. Added columns report populated row counts. Dropped source columns are listed below; dropped rows are zero. No per-cell log or dropped_rows artifact is emitted, per Christos's instructions. Original source tokens can always be traced by source_file + source_row_number.

Run `python scripts/clean_listings.py --verify-reproducibility` to regenerate twice, compare SHA-256 of all four artifacts, and reload string keys. No run timestamps or temporary output paths enter artifact contents. Versions are recorded, so byte-identical verification assumes the same environment.

Sample: at most 50 rows, first available row of each difficult case per snapshot, deduplicated, then a seeded (576) supplement. reason records all matching case predicates. Report unavailable case types rather than manufacturing examples.

## Omitted columns

Entirely blank fields, omitted for lack of information: neighborhood_overview, host_since, host_response_time, host_response_rate, host_acceptance_rate, host_thumbnail_url, host_neighbourhood, host_total_listings_count, host_verifications, neighbourhood, calendar_updated, instant_bookable. The omitted host_verifications field uses literal None rather than blanks.

Unused descriptive/profile/image/amenity fields, omitted for analysis scope: name, description, picture_url, host_url, host_profile_id, host_profile_url, host_name, hosts_time_as_user_years, hosts_time_as_user_months, hosts_time_as_host_years, hosts_time_as_host_months, host_location, host_about, host_picture_url, amenities.

## Output field schema

| Column | pandas dtype | Meaning / origin |
|---|---|---|
| id | string | Source field; original meaning/units preserved |
| listing_url | string | Source field; original meaning/units preserved |
| scrape_id | string | Source field; original meaning/units preserved |
| last_scraped | string | Source field; original meaning/units preserved |
| source | string | Source field; original meaning/units preserved |
| host_id | string | Source field; original meaning/units preserved |
| host_is_superhost | boolean | Source field; original meaning/units preserved |
| host_listings_count | Int64 | Source field; original meaning/units preserved |
| host_has_profile_pic | boolean | Source field; original meaning/units preserved |
| host_identity_verified | boolean | Source field; original meaning/units preserved |
| neighbourhood_cleansed | string | Source field; original meaning/units preserved |
| neighbourhood_group_cleansed | string | Source field; original meaning/units preserved |
| latitude | Float64 | Source field; original meaning/units preserved |
| longitude | Float64 | Source field; original meaning/units preserved |
| property_type | string | Source field; original meaning/units preserved |
| room_type | string | Source field; original meaning/units preserved |
| accommodates | Int64 | Source field; original meaning/units preserved |
| bathrooms | Float64 | Source field; original meaning/units preserved |
| bathrooms_text | string | Source field; original meaning/units preserved |
| bedrooms | Int64 | Source field; original meaning/units preserved |
| beds | Int64 | Source field; original meaning/units preserved |
| price | Float64 | Source field; original meaning/units preserved |
| price_quote_checkin_date | string | Source field; original meaning/units preserved |
| price_quote_checkout_date | string | Source field; original meaning/units preserved |
| price_quote_total_price | Float64 | Source field; original meaning/units preserved |
| price_quote_price_per_night | Float64 | Source field; original meaning/units preserved |
| price_quote_raw | string | Source field; original meaning/units preserved |
| minimum_nights | Int64 | Source field; original meaning/units preserved |
| maximum_nights | Int64 | Source field; original meaning/units preserved |
| minimum_minimum_nights | Int64 | Source field; original meaning/units preserved |
| maximum_minimum_nights | Int64 | Source field; original meaning/units preserved |
| minimum_maximum_nights | Int64 | Source field; original meaning/units preserved |
| maximum_maximum_nights | Int64 | Source field; original meaning/units preserved |
| minimum_nights_avg_ntm | Float64 | Source field; original meaning/units preserved |
| maximum_nights_avg_ntm | Float64 | Source field; original meaning/units preserved |
| has_availability | boolean | Source field; original meaning/units preserved |
| availability_30 | Int64 | Source field; original meaning/units preserved |
| availability_60 | Int64 | Source field; original meaning/units preserved |
| availability_90 | Int64 | Source field; original meaning/units preserved |
| availability_365 | Int64 | Source field; original meaning/units preserved |
| calendar_last_scraped | string | Source field; original meaning/units preserved |
| number_of_reviews | Int64 | Source field; original meaning/units preserved |
| number_of_reviews_ltm | Int64 | Source field; original meaning/units preserved |
| number_of_reviews_l30d | Int64 | Source field; original meaning/units preserved |
| availability_eoy | Int64 | Source field; original meaning/units preserved |
| number_of_reviews_ly | Int64 | Source field; original meaning/units preserved |
| estimated_occupancy_l365d | Int64 | Source field; original meaning/units preserved |
| estimated_revenue_l365d | Float64 | Source field; original meaning/units preserved |
| first_review | string | Source field; original meaning/units preserved |
| last_review | string | Source field; original meaning/units preserved |
| review_scores_rating | Float64 | Source field; original meaning/units preserved |
| review_scores_accuracy | Float64 | Source field; original meaning/units preserved |
| review_scores_cleanliness | Float64 | Source field; original meaning/units preserved |
| review_scores_checkin | Float64 | Source field; original meaning/units preserved |
| review_scores_communication | Float64 | Source field; original meaning/units preserved |
| review_scores_location | Float64 | Source field; original meaning/units preserved |
| review_scores_value | Float64 | Source field; original meaning/units preserved |
| license | string | Source field; original meaning/units preserved |
| calculated_host_listings_count | Int64 | Source field; original meaning/units preserved |
| calculated_host_listings_count_entire_homes | Int64 | Source field; original meaning/units preserved |
| calculated_host_listings_count_private_rooms | Int64 | Source field; original meaning/units preserved |
| calculated_host_listings_count_shared_rooms | Int64 | Source field; original meaning/units preserved |
| reviews_per_month | Float64 | Source field; original meaning/units preserved |
| snapshot_date | str | Derived; predicate described above or provenance metadata |
| source_file | str | Derived; predicate described above or provenance metadata |
| source_row_number | Int64 | Derived; predicate described above or provenance metadata |
| price_raw | string | Derived; predicate described above or provenance metadata |
| stay_type | string | Derived; predicate described above or provenance metadata |
| flag_missing_price | boolean | Derived; predicate described above or provenance metadata |
| flag_missing_minimum_nights | boolean | Derived; predicate described above or provenance metadata |
| flag_price_low | boolean | Derived; predicate described above or provenance metadata |
| flag_price_high | boolean | Derived; predicate described above or provenance metadata |
| flag_price_zero | boolean | Derived; predicate described above or provenance metadata |
| flag_price_nonpositive | boolean | Derived; predicate described above or provenance metadata |
| flag_previous_scrape | boolean | Derived; predicate described above or provenance metadata |
| flag_possible_inactivity | boolean | Derived; predicate described above or provenance metadata |
| flag_occupancy_at_255 | boolean | Derived; predicate described above or provenance metadata |
| flag_extreme_maximum_nights | boolean | Derived; predicate described above or provenance metadata |
| flag_zero_rating | boolean | Derived; predicate described above or provenance metadata |
| flag_scrape_date_discrepancy | boolean | Derived; predicate described above or provenance metadata |
| flag_scraped_after_snapshot | boolean | Derived; predicate described above or provenance metadata |
| flag_review_after_scrape | boolean | Derived; predicate described above or provenance metadata |
| no_reviews | boolean | Derived; predicate described above or provenance metadata |
| flag_impossible_value | boolean | Derived; predicate described above or provenance metadata |
| license_status | string | Derived; predicate described above or provenance metadata |
| license_normalized | string | Derived; predicate described above or provenance metadata |
| flag_license_normalized | boolean | Derived; predicate described above or provenance metadata |
| flag_license_whitespace | boolean | Derived; predicate described above or provenance metadata |
| flag_license_unrecognized | boolean | Derived; predicate described above or provenance metadata |
| flag_license_placeholder | boolean | Derived; predicate described above or provenance metadata |
| primary_pricing_eligible | boolean | Derived; predicate described above or provenance metadata |
| demand_eligible | boolean | Derived; predicate described above or provenance metadata |
