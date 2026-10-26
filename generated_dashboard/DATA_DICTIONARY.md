# Canonical data dictionary

One row is one listing at a nominal snapshot. `(snapshot_date, listing_id)` is unique; IDs remain strings.

- `price_raw`, `price_usd`, `price_status`: original string, positive USD or missing, and parsing status.
- `neighbourhood_raw`, `neighbourhood`, `room_type_raw`, `room_type`: original and normalized labels; unknowns explicitly labeled.
- `bedrooms_raw`, `bedrooms`, `bedrooms_status`: original, nullable 0–6 bucket (6 means 6+), status. Zero means Studio, never Unknown.
- `minimum_nights`, `stay`: valid nonnegative integer and short/long/unknown category. Zero is Unknown stay.
- `availability_*`, `number_of_reviews_*`: nullable nonnegative integers, with field-specific validation statuses. Availability is bounded by its horizon.
- `review_scores_value`, `review_scores_value_status`, `value_score_is_zero`: valid score in [0,5], status, explicit zero flag.
- `valid_dimensions`, `has_valid_price`, `pricing_eligible`: explicit Boolean flags; pricing requires both valid dimensions and valid price.
- `segment_key`: JSON encoding of neighborhood, room, bedroom bucket; missing for unknown dimensions.
- `source_file`, `source_row`, `input_sha256`, `source`, `last_scraped`: provenance, source category and actual date. Nominal date is not inferred from scrape date.
- Aggregate `listing_rows` counts valid-dimension rows including missing prices; `priced_rows` counts eligible prices; coverage is their ratio. Price statistics use only positive eligible prices. Each context median has its own nonmissing denominator.
- Comparison suffixes `_march` and `_june` preserve both dates' outputs; missing opposite-date evidence stays null. `change_usd` is June minus March; `change_pct` uses March as denominator. `review_score` is the smaller absolute qualifying premium for persistent patterns only.
