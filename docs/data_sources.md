# Data Sources

## Inside Airbnb

The project uses data from Inside Airbnb for Los Angeles.

Relevant dataset snapshots are dated:

- December 4, 2025
- March 16, 2026
- June 15, 2026

Downloaded datasets are stored locally and are not committed to GitHub.

## Snapshot files used for pricing analysis

The detailed-listings extracts for the dashboard are preserved as read-only inputs under `data/raw/`:

- `listings-2026-03-16.csv.gz` — [Inside Airbnb detailed listings](https://data.insideairbnb.com/united-states/ca/los-angeles/2026-03-16/data/listings.csv.gz)
- `listings-2026-06-15.csv.gz` — [Inside Airbnb detailed listings](https://data.insideairbnb.com/united-states/ca/los-angeles/2026-06-15/data/listings.csv.gz)

Derived artifacts belong in `data/processed/` and are created by `scripts/clean_listings.py`; raw files are not edited by that pipeline.
