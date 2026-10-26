# Los Angeles Airbnb Pricing Review Dashboard

**DSO 576 — Phase 2 One-Shot Build Specification**  
**Team:** Chen Wang, Christos Georgaklis, Vincent Liang, Riley Lyu, Will Samuels  
**Repository:** https://github.com/chenwang266/DSO576_Project

## 1. Build instruction and vision

Read this specification and inspect the repository without relying on earlier conversations. Reuse compatible code after validation. Phase 2 requires canonical data, reusable backend analysis, tests, and this specification; the complete interface is the Phase 3 target. Record assumptions, approval status, missing inputs, and actual validation results in `DECISIONS.md`; never invent data, approvals, or passing tests.

Help an Airbnb Marketplace Strategy Manager identify Los Angeles neighborhood-property segments for **human pricing review**. Combine comparable prices, repeated-snapshot evidence, and data-quality/context signals in one tool. Do not estimate optimal prices, revenue, occupancy, demand, or causal effects.

| Use case | Select/input → dashboard shows → decision |
| --- | --- |
| Inspect | Snapshot and segment → price distribution, benchmark, coverage, context → investigate this segment? |
| Compare | Same segment across March/June → prices, premiums, changes, warnings → does the pattern repeat? |
| Prioritize | Filters and evidence threshold → ranked persistent premiums/discounts → which segments need review? |
| Export | Shortlist row → detail and evidence CSV → document follow-up evidence. |

## 2. Data and cleaning

Use only Inside Airbnb LA detailed-listings snapshots **2026-03-16** and **2026-06-15**, supplied as `.csv`/`.csv.gz` through configurable paths. LA means the source extract's geography. Exclude December, calendar/review-detail ingestion, live feeds, maps, recruitment, accounts, paid services, and databases. Missing inputs require setup guidance; never download substitutes silently. Preserve raw files and verify SHA-256 before/after cleaning.

Grain: **one listing per snapshot**, unique on `(snapshot_date, listing_id)`. Read raw fields as strings; trim IDs, reject missing IDs, and fail on duplicates within a snapshot. Preserve nominal date separately from `last_scraped`.

Required source fields: `id`, `price`, `neighbourhood_cleansed`, `room_type`, `bedrooms`, `availability_30/60/90/365`, `number_of_reviews_ltm`, `number_of_reviews_l30d`, `review_scores_value`. Optional fields include `minimum_nights`, `source`, scrape/review dates, total reviews, and reviews per month. Missing optional fields remain unavailable; missing required fields fail visibly.

| Field | Canonical rule |
| --- | --- |
| Price | Strict USD parsing; retain `price_raw`, `price_usd`, and status: valid/missing/malformed/invalid_nonpositive. Only valid positive prices enter statistics. |
| Neighborhood/room | Collapse neighborhood whitespace; blank → Unknown. Room types: Entire home/apt, Private room, Shared room, Hotel room; otherwise Unknown. Retain raw labels. |
| Bedrooms | Nonnegative integers: 0 → Studio, 1–5 separate, ≥6 → 6+ bedrooms; invalid/missing → Unknown. Retain raw/status; never impute missing as Studio. |
| Minimum nights | Nonnegative integers; 1–29 → Short stay (<30 nights), ≥30 → Long stay (30+ nights), zero/missing/invalid → Unknown. |
| Availability/reviews | Nullable nonnegative integers; availability cannot exceed its named horizon. Retain validation statuses. |
| Value score | Range 0–5; preserve missingness and flag zero. |
| Provenance | Keep source file/row, source category, actual scrape date, and input hashes. |

Keep missing-price rows and extreme positive prices; no imputation, caps, or source/stay exclusions by default. Pricing eligibility is valid price + known neighborhood/room + valid bedrooms. Segment = neighborhood × room type × bedroom segment; retain a stable `segment_key`. Unknown dimensions remain in listings but cannot form comparable segments.

Produce three canonical artifacts under configurable `data/processed/`:

- **`canonical_listings_clean.csv`:** all listing-snapshot rows; identifiers, provenance, raw/clean dimensions, statuses, context, `has_valid_price`, `pricing_eligible`, and reference cleaner fields.
- **`canonical_price_segments.csv`:** date + segment; `listing_rows`, `priced_rows`, `price_coverage`, `median_price_usd`, `p25_price_usd`, `p75_price_usd`, `price_iqr_usd`, `min_price_usd`, `max_price_usd`, `is_small_sample = priced_rows < 20`.
- **`canonical_cleaning_report.json`:** input/output fingerprints, dates, row counts, price statuses, bedroom completeness, schema, and applied policies.

Coverage includes valid-dimension rows missing prices; statistics use eligible prices only. Source reference counts (March/June): rows **46,088/43,751**, missing prices **8,910/5,565**, zero bedrooms **2,570/9**, missing bedrooms **3,196/9,572**. Recalculate rather than hard-code. Warn that bedroom coding/completeness changes can distort Studio comparisons; do not interpret them as supply changes.

## 3. Analysis definitions

Local population = selected snapshot/neighborhood/room/bedrooms plus optional stay/source filters. Peer population = same non-geographic filters across **all LA neighborhoods, including the selected neighborhood**. Label that inclusion explicitly. Pool listings, never neighborhood medians. Context uses its own valid observations, including listings without valid prices.

| Output | Calculation |
| --- | --- |
| Counts/coverage | Valid-dimension listing count; eligible-priced count; priced/listings, null if denominator zero. |
| Price summary | Median, P25/P75 with linear interpolation; IQR = P75−P25. |
| Premium (%) | `100 × (local median / peer median − 1)`; positive peer median and sufficient priced counts in both populations required. |
| Context | Local/peer median and valid count: availability_90, reviews_ltm, value score, minimum nights. |
| Histogram | 20 equal-width bins of eligible local prices, median marker; one bin for constant prices; empty state otherwise. |
| Change | June−March median; percentage = `100 × change / March`, unavailable for missing/nonpositive baseline. |

Default minimum priced count **20**: retain raw metrics below threshold, warn, and suppress premium/persistence/ranking. Default coverage warning **<80%**, without exclusions. Thresholds are exploratory, not statistical significance. Preserve full calculation precision.

History outer-joins segments across dates with identical filters. Missing opposite-date metrics stay null; no forward fill. These are repeated cross-sections, not matched-listing causal changes.

Persistence: both qualifying premiums positive → Persistent premium; both negative → Persistent discount; opposite nonzero signs → Reversed; both available with either zero → Neutral; missing/failed threshold → Insufficient evidence. Only persistent segments rank. Score = **minimum absolute March/June premium**; descending, ties by neighborhood, room, numerical bedroom order. Rank all known-bedroom segments under shared optional filters, independently of the detail segment; offer premium/discount/both. Context is explanatory, not scored. An empty shortlist is valid. Record approval status of these defaults.

## 4. Dashboard target

Use Streamlit, pandas, and Plotly. Start at **June / Hollywood / Entire home/apt / 1 bedroom / all stays and sources / minimum 20 / coverage warning 80%**. Sidebar contains these selections and Reset. Populate categories from validated data; unavailable selections show an explicit message. Never merge Studio with Unknown.

| Tab | Required content and interaction |
| --- | --- |
| Segment Detail | Counts, coverage, median/IQR, premium, histogram, local/peer table, context, and warnings. Snapshot selection changes this tab only. |
| March–June Comparison | Both dates' prices/IQR, premiums, counts, coverage/context, changes, persistence, bedroom/source warnings. |
| Review Shortlist | Rank, segment, direction, score, both premiums/counts/coverage/context and warnings. Row selection opens detail and preserves optional filters. Export visible shortlist and selected evidence, including dates/settings/denominators/warnings/full precision. |

Each tab includes expandable Data Quality & Methodology: attribution, nominal/actual dates, counts/missingness, unknown-bedroom exclusions, peer definition, policies, and limits. Show no personal host details/coordinates. Missing results display reasons, not zeros/infinity. Format USD to two decimals and percentages to one; support narrow screens and labels beyond color.

## 5. Architecture and execution

Use repository-compatible Python, uv/lockfile, CSV/JSON, and pytest. About 90k listing rows fit in memory. Keep components independent:

| Component | Input → output |
| --- | --- |
| Config | Paths/dates/thresholds → validated settings. |
| Cleaner | Raw files → canonical artifacts. |
| Data access | Canonical files → typed validated data/report; string IDs, explicit Booleans, schema/key checks. |
| Filters | Dataframe + explicit selections → consistent populations. |
| Pricing | Populations → summaries/peer/distribution/context. |
| History | Shared per-date summaries → comparisons/statuses/ranking. |
| Presentation | Backend outputs → UI/exports; no duplicate formulas. |

Backends never import Streamlit or mutate cached data. Reuse one snapshot aggregation routine; recalculate stay/source refinements from listings, not precomputed medians. Cache by canonical fingerprints plus all filters/settings; invalidate on changes. Measure cold load ≤10 seconds and cached updates ≤2 seconds before claiming performance.

Suggested layout: `app.py`, `src/{data_access,filters,pricing,history,charts}.py`, `scripts/canonical_clean.py`, `tests/`, `config/project.json`, `data/{raw,processed}/`, README, specification, decisions, dictionary, project configuration/lockfile. Reuse equivalent existing paths. Verify actual cleaner capabilities and document exact commands:

```bash
uv sync --locked
uv run python scripts/canonical_clean.py --march data/raw/listings-2026-03-16.csv.gz --june data/raw/listings-2026-06-15.csv.gz --output-dir data/processed
uv run pytest
uv run streamlit run app.py
```

Keep data out of public Git; make canonical data available on main through the course-authorized workflow. Missing files/schema produce actionable setup errors. Do not assume files are already on main.

## 6. Build order and acceptance

Build in order: **repository/input audit → canonical cleaning/validation → shared loading/filtering/pricing → history/ranking → interface/exports → integration and fresh-agent verification**. Keep analysis code outside this specification.

Required checks:

- **Data:** exact string IDs, unique keys, required schema, unchanged raw hashes, row conservation, valid ranges/statuses, reproducibility, and aggregate reconciliation. Cover malformed/missing/nonpositive prices, duplicate IDs, invalid/missing/zero bedrooms, invalid categories, optional missingness, and empty segments.
- **Counts:** four prices + one missing → listings 5, priced 4, coverage 0.8; missing-price rows can contribute valid context. Counts 19/20 produce true/false small-sample flags.
- **Numeric:** local `[100,200,missing]`, others `[300,400]` → local median 150, P25 125, P75 175, coverage 2/3; inclusive peer median 250; premium −40% at threshold 2, unavailable at 20.
- **History/ranking:** June-only segments retain null March; test same/opposite/zero signs, failed evidence, deterministic ties, empty shortlist, and Studio warning.
- **Integration:** consistent filters, UI/backend numerical agreement, standalone backend imports, cache invalidation, selection/filter preservation, accurate CSV exports, clear unavailable states, and working fresh-clone commands.

Provide README setup/regeneration/launch instructions, data dictionary, `DECISIONS.md`, tests, canonical data, and reusable backends. Record actual commit, commands, test outcomes, unresolved approvals, and performance if measured. Give a fresh agent only the repository and this file; log questions/guesses and fix gaps. Never claim implementation, full-data execution, or approval without evidence.
