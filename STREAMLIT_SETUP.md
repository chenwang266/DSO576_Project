# Deploy the pricing-review dashboard

In Streamlit Community Cloud choose repository `chenwang266/DSO576_Project`,
branch `main`, and main file `streamlit_app.py`. Use Python 3.14 (the locally
tested version). Dependencies are pinned in requirements.txt.

Local launch:

```
python -m pip install -r requirements.txt
streamlit run streamlit_app.py
```

The app reads the two supplied LA snapshots in data/raw without downloading
substitutes, changing the source files, or using the older processed CSVs.
Set AIRBNB_RAW_DIR to use another folder containing the same filenames.
Only analysis fields are retained in memory; personal host details and coordinates
are not displayed or exported. Existing repository data are unchanged.

The entry point uses pricing_backend.py for validation, pooled peer benchmarks,
context, history, ranking and row-specific warnings. There are three tabs and
CSV exports; shortlist segments can be opened with the segment selector beneath
the table. Stay/source filters apply to all views; detail snapshot applies only
to snapshot detail views. Reset restores the specified defaults.

This implements the dashboard entry point, not the complete Phase 2 artifact
pipeline: no canonical artifacts are generated and no team approvals are implied.
Canonical cleaning/report generation and a uv lockfile remain separate work.
The app follows BUILD_SPEC analysis defaults and recalculates from raw snapshots.
No occupancy, revenue, optimal price, or causal interpretation is supported.

Validation: pytest numerical/threshold/history/export-warning checks and
Streamlit AppTest using both repository snapshots. Run with
`python -m pip install pytest` then `python -m pytest -q`.
Browser layout and live Streamlit deployment have not been verified.
