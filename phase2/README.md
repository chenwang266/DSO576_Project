# Phase 2 pricing analysis

User: an Airbnb Marketplace Strategy Manager selects Los Angeles neighborhood-property segments for human pricing review. Public listing signals do not establish optimal prices, occupancy, or revenue effects. Team reconciliation remains pending; this is chenwang's implementation.

## Run

From the repository root, with pandas installed:

```sh
python module6_submission/code/clean_data.py
python module6_submission/code/validate_data.py
python phase2/analysis.py
python -m unittest discover -s phase2 -v
```

The analysis writes `outputs/segment_metrics.csv`, `outputs/segment_comparison.csv`, and `outputs/ranked_review_list.csv`. These are regenerated artifacts; reusable functions live in `analysis.py`. No dashboard interface or server is required to run them.

## Definitions and decisions

- Source row: one listing-snapshot, unique by `(snapshot_date, id)`.
- Segment: snapshot + neighborhood + room type + bedrooms. Studio is zero bedrooms. Unknown bedrooms remain in cleaned data but are excluded from segment and peer calculations. Missing group keys are excluded rather than guessed.
- Peer: all LA listings with the same snapshot, room type, and bedrooms, including the selected neighborhood. Optional property-type and accommodates refinements apply equally to local and peer listings. Never pass a neighborhood-only subset to `segment_metrics`, because it needs the LA comparison population.
- `filter_listings` returns listing rows for distributions and interactive filters. `None` means no filter. `segment_metrics` returns every segment under optional refinements; select the desired neighborhood from its result.
- Price: positive observed advertised price. Listing count includes unpriced rows; price count and price statistics use nonmissing prices only. Quartiles use pandas linear interpolation. Context medians use their own nonmissing counts across segment listings, including unpriced rows.
- Premium percent: `100 * (local median / peer median - 1)`. Require at least 20 priced listings in both groups by default. Otherwise the premium is missing and not ranked. The threshold is provisional, configurable with `min_priced`, and requires team review. Raw counts and medians remain available for low-count labels in the interface.
- Context: median availability_90, number_of_reviews_ltm, review_scores_value, and minimum_nights, each with a nonmissing denominator. Availability is not occupancy; value rating is distinct from overall rating.
- Persistence: eligible premium has the same strictly positive or strictly negative sign in both March and June. Zero, missing, or reversed signs are not persistent. Snapshot comparisons are repeated cross-sections, not matched-listing effects.
- Review score: smaller absolute premium percentage across the two snapshots, only for persistent segments. Rank descending, then neighborhood, room type, and bedrooms for deterministic ties. Context is displayed alongside the score; no unvalidated context weights. This is a review heuristic, not evidence of incorrect pricing.
- High-price sensitivity: `exclude_high_prices=True` removes prices over $2,000 from both populations; default retains them. Counts then refer to the filtered population. Optional controls are function arguments; export CLI currently uses default populations and permits `--min-priced`.
- Functions have no hidden global data or UI state. The eventual interface can cache `load_data` and call the pure analysis functions. The default export precomputes the unrefined segment tables; optional refinements must be recalculated from listing rows.

## Acceptance checks

Targeted tests cover independently known quartiles, listing versus priced counts, LA peer medians, zero bedrooms, unknown bedrooms, low counts, empty filters, shared peer refinements, extreme-price sensitivity, sign reversal, missing snapshots, and deterministic ranking.

Full-data validation independently compares every retained value rating and price against the original rows and checks keys, bounds, row counts, joins, and denominators. See `validation.json` for the additional Phase 2 checks.

## Module 6 history

The existing October 5 report PDF/Markdown and submission ZIP are historical submissions. Current cleaning outputs were extended on October 18 for Phase 2: 29 source fields plus 28 provenance/quality fields = 57 columns. The additional columns are `review_scores_value` and `invalid_review_scores_value`. The historical report's 55-column counts do not describe this revision. Its PDF and ZIP have not been republished. Current rules and execution evidence take precedence for Phase 2.

Notebook status: current notebook outputs were cleared because this runtime lacks nbformat. Direct cleaning/validation, two-process reproducibility, and backend tests passed; notebook execution is explicitly NOT_RUN for this revision.
