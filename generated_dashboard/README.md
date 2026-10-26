# LA pricing review dashboard

Local Streamlit app generated from the team's BUILD_SPEC.md. No accounts, services, databases, or API keys are needed. Do not publish raw/canonical listing data to public Git.

From this folder in PowerShell:

```powershell
uv sync --locked --python 3.13
uv run python scripts/canonical_clean.py
uv run pytest
uv run streamlit run app.py
```

Configure authorized March/June raw paths in `config/project.json`, relative to this folder, or pass `--march`, `--june`, and `--output-dir` to the cleaner. Defaults use the existing local `../group data/` files. Missing files produce setup instructions rather than substitute data.

After cleaning, the three canonical artifacts are in `data/processed/` (ignored by Git). Share them only through your course-authorized data workflow. The optional environment variable `LA_DASHBOARD_DATA` selects another canonical directory for reproducible testing; synthetic inputs are tests only, never presented as actual LA observations.

`src/` contains UI-independent filters, pricing, history, charts and data access. The app caches canonical data by SHA-256 and aggregations by data, threshold and stay/source settings. Snapshot selection affects detail only. Exports retain full numeric precision. Defaults are exploratory and not statistically validated or recorded as team-approved. See DECISIONS.md for validation and limitations.
