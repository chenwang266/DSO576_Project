# DSO576_Project
Short-Term Rental Marketplace Health: **LA Airbnb Pricing Review**

This repo helps an Airbnb Marketplace Strategy Manager pick Los Angeles neighbourhood × room type × bedroom segments for **human pricing review**. It compares advertised prices with an inclusive LA peer group, checks whether the pattern repeats from March to June 2026, and flags data-quality problems. It does not estimate optimal prices, revenue, occupancy, demand or causal effects.

The specification is [BUILD_SPEC.md](BUILD_SPEC.md). Build status, assumptions, approvals and validation evidence are in [DECISIONS.md](DECISIONS.md), and the column definitions are in [DATA_DICTIONARY.md](DATA_DICTIONARY.md).

**Phase status:** Phase 2 (canonical data, reusable backend analysis, tests) is complete. The Phase 3 Streamlit dashboard (`app.py`, `src/charts.py`, `src/presentation.py`) is built and tested locally; see [DECISIONS.md](DECISIONS.md) for what is verified and what still needs team review.

## Setup

Requirements: [uv](https://docs.astral.sh/uv/). uv installs Python 3.13 if it is not already present.

```bash
uv sync --locked
```

### Input data

The cleaner reads only these two Inside Airbnb Los Angeles *detailed* listings snapshots:

| Snapshot | Default path | SHA-256 |
| --- | --- | --- |
| March, 2026-03-16 | `data/raw/listings-2026-03-16.csv.gz` | `ffdef08afe58b62e57cffb9da0f1daa97bf76e223fe98ce9e2022dd330976fc6` |
| June, 2026-06-15 | `data/raw/listings-2026-06-15.csv.gz` | `ebc99e8a5ff2f60cbd91323571c2bdf1f8c2c74fe3ac9669d7c9a24d2294dec5` |

The team distributes these files, and the generated canonical files, through this **private** GitHub repository. Do not publish them to a public repository. If a file is missing, the cleaner stops, says which file it expected, and tells you how to supply it. It never downloads substitute data. To use other locations, pass `--march` and `--june`, or edit `config/project.json`. Plain `.csv` inputs work too.

## Regenerate canonical data

```bash
uv run python scripts/canonical_clean.py --march data/raw/listings-2026-03-16.csv.gz --june data/raw/listings-2026-06-15.csv.gz --output-dir data/processed
```

All arguments are optional. Without them, the cleaner uses the paths in `config/project.json`. It writes three files to `data/processed/`:

- `canonical_listings_clean.csv`: one row per listing per snapshot, 89,839 rows
- `canonical_price_segments.csv`: one row per date × segment, unfiltered
- `canonical_cleaning_report.json`: fingerprints, counts, statuses, schema and policies

The cleaner checks the raw SHA-256 before and after cleaning and checks that every row is kept. Its output is byte-for-byte reproducible. It takes about 6 seconds.

The older `data/processed/la_*.csv` and `cleaning_report.json` came from an earlier team cleaner. The new backend does not read them.

## Test

```bash
uv run pytest
```

Synthetic tests cover the cleaning rules, loading, filters, pricing, history, ranking, formatting, charts and CSV exports. `tests/test_app.py` drives `app.py` with Streamlit's `AppTest` and checks the shown numbers against the backend. `tests/test_full_data.py` checks the real canonical files against an independent standard-library recomputation from the raw files. If the data files are missing, those tests are **skipped**, not passed.

## Use the backend (Python)

```python
from src.config import load_settings
from src.data_access import load_canonical
from src.filters import OptionalFilters, SegmentSelection
from src.pricing import segment_metrics, segment_detail
from src.history import compare_snapshots, rank_shortlist

s = load_settings()
data = load_canonical(s.processed_dir, s.dates)
detail = segment_detail(data.listings, SegmentSelection("2026-06-15", "Hollywood", "Entire home/apt", "1 bedroom"))
metrics = segment_metrics(data.listings, OptionalFilters(stay=None, source=None), min_priced=s.min_priced_count)
comparison = compare_snapshots(metrics, s.dates, coverage_warning=s.coverage_warning)
shortlist = rank_shortlist(comparison, direction="both")   # "premium" | "discount" | "both"
```

## Launch the dashboard

```bash
uv run streamlit run app.py
```

It opens at http://localhost:8501 with **June / Hollywood / Entire home/apt / 1 bedroom / all stays and sources / minimum 20 / coverage warning 80%**. The sidebar holds the snapshot, segment, optional stay/source filters, thresholds and **Reset to defaults**. Three tabs:

- **Segment Detail**: counts, coverage, median/IQR, premium vs the inclusive LA peer, histogram, local/peer table, context and warnings, for the selected snapshot. The snapshot choice only affects this tab.
- **March–June Comparison**: both dates side by side, changes, persistence label and row warnings.
- **Review Shortlist**: persistent premiums/discounts ranked by score, with a premium/discount/both control. Selecting a row opens it in Segment Detail and keeps the stay/source/threshold settings. Downloads: the visible shortlist and the selected segment's evidence, both CSV with the settings, dates, denominators, warnings and full precision.

Each tab has a **Data Quality & Methodology** expander.

## Deploy publicly (Streamlit Community Cloud)

The app reads the canonical files from `data/processed/`, so they must be on the branch you deploy. This repository is private; Community Cloud can deploy from it once your GitHub account has granted Streamlit access, and **the app URL itself is public** (it shows aggregated, CC BY 4.0 Inside Airbnb figures, never host details or coordinates).

1. Commit and push `app.py`, `src/`, `config/`, `data/processed/canonical_*`, `pyproject.toml`, `uv.lock` and `.python-version` to the branch you want to deploy.
2. Sign in at https://share.streamlit.io with GitHub, choose **Create app → Deploy a public app from GitHub**.
3. Repository `chenwang266/DSO576_Project`, branch as pushed, main file `app.py`.
4. Under **Advanced settings**, choose **Python 3.13** (the project requires `>=3.13,<3.14`). Community Cloud installs dependencies from `uv.lock`. No secrets are needed.
5. Deploy. The first start installs packages and loads the data; peak memory measured locally is about 370 MB.

## Layout

| Path | Role |
| --- | --- |
| `config/project.json` | Snapshot paths and dates, output directory, thresholds and default selection |
| `src/config.py` | Loads and validates settings |
| `src/cleaning.py`, `scripts/canonical_clean.py` | Turn the raw files into the canonical files (library and CLI) |
| `src/data_access.py` | Canonical schema, typed loading and validation, SHA-256 fingerprints |
| `src/filters.py` | Local and inclusive-peer populations, stay/source filters, selectable options |
| `src/pricing.py` | The one aggregation routine, premium, histogram, segment detail |
| `src/history.py` | March–June comparison, persistence, row warnings, shortlist ranking |
| `src/charts.py` | Plotly figures built from backend outputs (no Streamlit) |
| `src/presentation.py` | Number formatting, shortlist display, CSV exports, methodology text (no Streamlit) |
| `app.py` | Streamlit dashboard: selection, caching, layout |
| `tests/` | pytest suite |

The backends never import Streamlit or Plotly, and they never change their inputs. `src/charts.py` uses Plotly but not Streamlit; only `app.py` imports Streamlit.
