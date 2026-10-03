# Short-Term Rental Marketplace Health: Pricing Guidance Dashboard

DSO 576 Module 6 — individual data cleaning submission.

- Student: Riley Lyu
- Personal branch: cleaning-rileylyu
- Branch URL: https://github.com/chenwang266/DSO576_Project/tree/cleaning-rileylyu
- Submitted commit ID: a7017c78a62b4496a36180bfa0176cd9905b31bb

## Source and scope

Source: [Inside Airbnb](https://insideairbnb.com/get-the-data/), Los Angeles, June 15, 2026 snapshot. Place the original files in `group data/2026-06-15/`:

| File | Grain and key | Expected shape |
|---|---|---|
| `listings.csv.gz` | Detailed Listings: one listing per snapshot; `id` | 43,751 × 90 |
| `calendar.csv.gz` | Detailed Calendar: one listing-date; `listing_id` + `date` | 16,035,198 × 5 |
| `reviews.csv.gz` | Detailed Reviews: one review; review `id` | 1,856,294 × 6 |
| `neighbourhoods.csv` | One neighborhood reference record; `neighbourhood` | 270 × 2 |

The optional GeoJSON is not used. Neither workflow reads older CSVs directly in the project root. Full downloads are not committed; obtain the matching snapshot from the source before running. The source download date is not recorded; the snapshot date is the version identifier.

The project supports an Airbnb Marketplace Strategy Manager prioritizing Los Angeles neighborhood + room type + bedroom segments for pricing review. This homework establishes a reproducible cleaning and validation workflow. No tables are merged, no full analysis table is aggregated, and no optimal-price claim is made.

## Decisions and limitations

Raw files and DataFrames stay unchanged; cleaned copies retain every row and original column. Derived columns are `price_numeric`, `last_scraped_dt`, Calendar/Reviews `date_dt`, and Listings presence/eligibility/monthly-quote review flags. Missing values are retained; extremes are neither capped nor removed. Existing unique keys are not deduplicated. Categorical whitespace checks found no correction necessary. Explicit YYYY-MM-DD parsing and currency parsing have zero failures.

Missing price, bedroom, minimum-stay and value-score counts remain 5,565, 9,572, 11 and 11,266. Eligibility flags identify complete fields without deleting records or certifying price comparability. A monthly-quote flag only identifies the literal `Average monthly price` text; it does not label all monthly quotes as errors.

Unresolved: long-stay monthly quote semantics, exceptional bedroom counts, one zero value score, host profile ID float precision, 181 Calendar IDs outside Listings (66,065 rows), and 14 extended calendar windows. These affect comparability, coverage or future window definitions. No automatic correction is justified. Missing values are skipped by pandas means/medians and valid denominators are explicitly reported. Unknown bedroom groups stay in the source table but are not complete bedroom-price segments.

## Environment and execution

Tested with Python 3.13, pandas 3.0.6 and ipykernel 7.4.0. From this `project` directory in PowerShell:

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python cleaning_rileylyu.py
```

If activation is unavailable, use `.\.venv\Scripts\python.exe` in place of `python`. The script resolves source/output paths relative to itself and can also run from another working directory. It loads all tables and independent copies into memory; use a machine with sufficient RAM for the full Calendar and review text.

For the notebook, open `cleaning_rileylyu.ipynb` in VS Code with the Jupyter extension, choose the project `.venv` interpreter, then **Restart Kernel → Run All**. Start from either this directory or the workspace root. The script reproduces core cleaning, validation, record checks and exports; it omits exploratory investigation blocks already recorded in the notebook. No new rules are introduced.

Outputs are written to `cleaning_outputs/`, replacing generated evidence/sample files only. Missing source files or failed validation assertions stop execution. Neither workflow overwrites a downloaded source file. To verify reproducibility, run from the original inputs twice and compare the output CSV hashes; `reproducibility_checks.json` records completed verification, not an input to the script.

## Expected outputs and commit selection

Commit these core files:

- `cleaning_rileylyu.ipynb`
- `cleaning_rileylyu.py`
- `requirements.txt`
- `README.md`
- `.gitignore`
- `cleaning_outputs/cleaned_listings_sample_50.csv`
- `cleaning_outputs/decision_log.csv`
- `cleaning_outputs/record_checks.csv`
- `cleaning_outputs/final_reconciliation.csv`

The script also recreates these small evidence CSVs; committing them is optional because their evidence is already in the notebook: `baseline.csv`, `baseline_missing.csv`, `price_evidence.csv`, `date_evidence.csv`, `missing_evidence.csv`, `key_evidence.csv`, `range_evidence.csv`, `coverage_evidence.csv`, `text_evidence.csv`, `denominator_evidence.csv`. `reproducibility_checks.json` is optional execution evidence. No full cleaned tables are exported.

The 50-row sample has 50 unique listing IDs. It first includes the five fixed record-check cases, then up to three cases each with missing price/bedrooms/minimum stay/value score, zero bedrooms, 10+ bedrooms, zero score, and 365+ minimum nights, followed by ordinary records until 50. IDs are deduplicated during selection. Only 18 relevant columns are shared; host identities and descriptions are omitted. This deliberately includes difficult cases and is not a statistically representative sample. Current sample includes both price endpoints, 13 missing bedrooms, 3 missing minimum stays, 9 missing prices and 5 missing value scores.

## Submission notes

Commit to your individual branch, not `main` or the shared course repository. Fill in the branch URL, name and submitted commit above and in your PDF. Grant the instructor repository access. Do not commit `group data/`, old root downloads, `.venv/`, caches or logs. `.gitignore` excludes these; ignore rules do not untrack previously committed files.

The final individual PDF is a separate deliverable: include all 14 checklist statuses/evidence, rule/reason/check log, five original/expected/actual checks, limitations and how a Codex suggestion was verified. The notebook contains an evidence map; this preparation does not create the final PDF or push any branch. Phase 1 and assignment Markdown files may be included as optional context.
