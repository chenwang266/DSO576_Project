# Short-Term Rental Marketplace Health: Pricing Guidance Dashboard

## Data source

This project uses Inside Airbnb's Los Angeles detailed-listings data from these snapshots:

- March 16, 2026
- June 15, 2026

The raw files were downloaded on October 2, 2026.

(December 4, 2025 was inspected during Phase 1 but excluded from the pricing cleaning pipeline because its detailed-listings file contained no usable price values.)

## Raw data

Place the downloaded source files at:

```text
data/raw/listings-2026-03-16.csv.gz
data/raw/listings-2026-06-15.csv.gz
```

The `data/` directory is excluded from Git. Raw source files are not committed and the cleaning pipeline reads them without modifying them.

## Cleaning pipeline

Run the cleaning pipeline from the project root:

```bash
python3 scripts/clean_listings.py \
  --march data/raw/listings-2026-03-16.csv.gz \
  --june data/raw/listings-2026-06-15.csv.gz \
  --output-dir data/processed
```

## Dependencies

- Python 3
- `pandas` (the validated run used version 2.3.3)

## Expected outputs

- `data/processed/la_listings_cleaned.csv` — listing-level data for both snapshots, with standardized dimensions, parsed prices, and validity flags.
- `data/processed/la_price_segments.csv` — price summaries by snapshot, neighbourhood, room type, and bedroom segment.
- `data/processed/la_price_segment_changes.csv` — full-snapshot March-to-June segment comparisons, including segment coverage, listing-count changes, and price-statistic changes.
- `data/processed/la_matched_listing_price_trends.csv` — March-to-June matched-listing data keyed by listing ID, including price changes and segment-change flags.
- `data/processed/cleaning_report.json` — input fingerprints, row counts, missing/invalid-price coverage, matching coverage, and output inventory.

## Reproducibility

During validation, rerunning the pipeline from the raw files reproduced all five outputs byte-for-byte.

## Git submission information

- Branch name: `vincent_liang`
- Branch URL: https://github.com/chenwang266/DSO576_Project/tree/vincent_liang
- Submitted cleaning-work commit ID: `ebbe07cece3f00f25a67fd5628d0b35019869416`
