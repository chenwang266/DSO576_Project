# Visual dashboard analysis and local application

The [public Sites dashboard](https://la-pricing-review-visual.belovedferret.chatgpt.site/) is mirrored in `../site/dist`. This folder contains its reproducible Python data preparation, verification and local Streamlit interface. The separate repository-root `streamlit_app.py` continues to use its own setup instructions.

From this folder, run:

```bash
uv sync --locked
uv run python scripts/canonical_clean.py --march ../data/raw/listings-2026-03-16.csv.gz --june ../data/raw/listings-2026-06-15.csv.gz --output-dir data/processed
uv run pytest -q
uv run streamlit run app.py
```

The raw snapshots already tracked in the parent repository are used read-only. Generated canonical files stay local. See [the data dictionary](DATA_DICTIONARY.md), [decisions](DECISIONS.md), [audit resolutions](ISSUE_RESOLUTION.md), and [deployment steps](../DEPLOYMENT.md). The run targets Python 3.11–3.13 and the pinned uv environment. `requirements.txt` mirrors the locked runtime dependencies for pip-based environments.

To refresh the Site mirror after regenerating canonical data:

```bash
uv run python scripts/export_site_data.py --output ../site/dist/assets
uv run python scripts/verify_site.py --site ../site
```

The parity check requires Node.js on your PATH. The static Site itself requires only a browser and HTTP hosting. Its visitor selections stay in memory and do not require a server or sign-in.
