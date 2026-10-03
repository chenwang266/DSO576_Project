# Los Angeles detailed-listings cleaning pipeline

`scripts/clean_listings.py` creates a reproducible, non-destructive analytical layer from the two Inside Airbnb *detailed listings* downloads.

## Run

Keep source files under `data/raw/` (which is ignored by Git) and run:

```bash
python3 scripts/clean_listings.py \
  --march data/raw/listings-2026-03-16.csv.gz \
  --june data/raw/listings-2026-06-15.csv.gz \
  --output-dir data/processed
```

Inputs are read only; the command writes only these derived files to `data/processed/`:

| File | Use |
| --- | --- |
| `la_listings_cleaned.csv` | Listing-level filtering, audit, and dashboard detail. Includes valid-price flags rather than silently deleting invalid prices. |
| `la_price_segments.csv` | Price comparison by snapshot, neighbourhood, room type, and bedroom segment. Statistics use positive numeric prices only. |
| `la_price_segment_changes.csv` | Full March-to-June comparison of segment summaries. Includes segment entry/exit coverage, listing-count change, and price-statistic changes. |
| `la_matched_listing_price_trends.csv` | March-to-June inner match on `listing_id`, with price changes and an indicator when segment dimensions changed. |
| `cleaning_report.json` | Row counts, null/invalid-price coverage, matching coverage, and output inventory. |

## Cleaning contract

- Snapshot labels and dates are assigned from the command arguments: `march_2026` / `2026-03-16` and `june_2026` / `2026-06-15`.
- `cleaning_report.json` records each raw input's byte count and SHA-256 fingerprint, making the run auditable while leaving those files unchanged.
- Listing IDs must be numeric and unique within each source snapshot. The pipeline stops if they are not, avoiding arbitrary deduplication that could corrupt panel matches.
- Currency strings are parsed to `price_usd`; missing, malformed, zero, and negative prices become null and are flagged by `has_valid_price`.
- Neighbourhood and room-type values are trimmed; blank values become `Unknown`. Bedrooms are retained as an integer where valid and grouped into `Studio`, `1 bedroom` through `5 bedroom`, `6+ bedrooms`, or `Unknown`.
- The pipeline retains all source rows and does not apply an outlier cap. Segment summaries explicitly use valid positive prices, keeping high-price treatment transparent and available for a dashboard control.
- A matched listing is an ID in both snapshots. It remains in the match output even if one price is invalid; `has_valid_price_both` controls whether the change metrics are meaningful. `segment_changed` prevents false like-for-like interpretation when a listing's segment changes.

## Required source columns

`id`, `neighbourhood_cleansed`, `room_type`, `bedrooms`, and `price` are required. The pipeline carries common optional detailed-listings fields when available, including property type, capacity, availability, review counts, rating, and license.
