# Module 6 - individual data cleaning (chenwang266)

Working branch: `chenwang`. This package contains an individual completed checklist and evidence. The assignment also requires the team to reconcile members' work and submit one group PDF; this individual report does not certify team agreement.

## Package contents

1. `report/`: completed PDF and editable Markdown checklist, proposed cleaning decision log, five record checks, and Codex verification response.
2. `code/`: cleaning script, Jupyter notebook, independent validation script, report builder, and pinned environment dependencies.
3. This README: data access, versions, exact commands, expected outputs, and notebook instructions.
4. `data_and_evidence/`: cleaned analytic dataset, 50-row sample, full-data audit, aggregate metrics, outer-join comparison, five record checks, and reproducibility evidence.

## Source and access

Source: Inside Airbnb, Los Angeles detailed listings, snapshot versions March 16 and June 15, 2026. Owner/publisher: Inside Airbnb (Murray Cox and collaborators). Source landing page: https://insideairbnb.com/get-the-data/ ; dictionary linked there. Licensing: CC BY 4.0 according to that page, checked October 5, 2026. Attribute Inside Airbnb in subsequent use. This educational package contains a reduced analytic table and a small inspection sample; personal host/profile details and precise coordinates are excluded. Avoid republishing original dumps; consult https://insideairbnb.com/data-policies/ for community guidance.

The original download/retrieval date was not recorded by the student. October 5, 2026 is the local inspection date, not a claimed retrieval date. Exact uncompressed source-file SHA-256 hashes and scrape windows are in `data_and_evidence/full_data_checks.json`.

The original CSVs are preserved in the parent project folder, outside the ZIP:

- `listings 16 March, 2026.csv`
- `listings 15 June, 2026.csv`

For an extracted ZIP, obtain the **detailed** `listings.csv.gz` versions for Los Angeles from the source page/archive, decompress them, and use the exact filenames above. Do not use the smaller summary `listings.csv`. If the archived version is unavailable, request it at https://insideairbnb.com/data-requests/ or obtain the preserved original files from the student through the course channel. Compare the uncompressed file hashes; revised source versions can change results. Supply the containing directory with `--source-dir`.

## Fresh-session run

From the `project` folder (Python 3.14 was used):

```bash
python3 -m venv .venv-module6
source .venv-module6/bin/activate
python -m pip install -r module6_submission/code/requirements.txt
python module6_submission/code/clean_data.py --source-dir . --output-dir module6_submission/data_and_evidence
python module6_submission/code/validate_data.py --source-dir . --output-dir module6_submission/data_and_evidence
python module6_submission/code/build_report.py
```

From an extracted ZIP, set `--source-dir /path/to/original/csv/folder`; output defaults to the package's `data_and_evidence` folder. No network requests occur during cleaning. No manual spreadsheet edits are required. Cleaning starts from both originals every run.

Expected outputs: `cleaned_listings.csv` (89,839 listing-snapshot rows, 55 columns); `listing_comparison.csv` (51,737 IDs); `sample_cleaned_50.csv` (50 rows, all cleaned columns); `column_audit.csv`; `text_examples.csv`; `neighbourhood_metrics.csv`; `full_data_checks.json`; `record_checks.json`; `independent_validation.json`. `reproducibility.json` records the submitted fresh-process comparison, and `notebook_execution.json` records notebook execution; they are verification evidence rather than cleaning outputs. `build_report.py` uses those files to recreate the report.

## Notebook

Open `code/data_cleaning.ipynb` in Jupyter or VS Code and choose the environment containing the requirements. Use **Restart Kernel and Run All**. The setup cell supports launching from `project`, `module6_submission`, or `code`; edit `SOURCE_DIR` if the originals live elsewhere. The notebook calls the submitted script, runs independent validation, and displays real full-data evidence. The pipeline does not depend on hidden notebook state. The executed notebook is included.

## Interpretation and sample

One row is a listing in a snapshot, unique by `(snapshot_date, id)`. The cleaned data intentionally selects 28 useful original fields and adds provenance/quality indicators. Excluded source fields are listed by purpose in the decision log. IDs remain strings. `source_row` is the one-based CSV record position including the header (not a physical line number for multiline CSV fields). `snapshot_date` is the version label; `last_scraped` is the actual record date.

Missing prices/ratings remain missing; all listings contribute to listing counts, while numeric metrics use their own nonmissing counts. `eligible_price_analysis` also excludes unknown room types; none occur in these sources. Numerical group metrics include retained extreme positive values: use medians and compare results excluding `flag_high_price` when interpreting means. The price sum is a reconciliation statistic, not market revenue. Availability is not occupancy. Paired changes use the 31,893 matched listings with valid prices at both dates.

The 50-row sample prioritizes five difficult checks, the first example of each populated quality flag, then early rows of each snapshot. It is deterministic, not random or representative. All shareable columns of the purpose-specific cleaned table are included. See `full_data_checks.json` for exact selection details. Public listing IDs support verification; host identifiers, names, descriptions, profile links, and exact coordinates are absent.

## GitHub and group submission

The Python files, executed notebook, sample, report, and small evidence files belong on the student's `chenwang` branch. Large original/cleaned data and the ZIP are ignored for Git; the ZIP includes the full cleaned data. Team members must review/reconcile the individual methods before submitting their one group PDF. This package does not invent a consensus or missing stakeholder confirmation.
