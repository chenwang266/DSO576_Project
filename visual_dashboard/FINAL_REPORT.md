# Los Angeles Airbnb Pricing Review Dashboard

**DSO 576 — Visual analytics final version (November 4, 2026)**  
**Team:** Chen Wang, Christos Georgaklis, Vincent Liang, Riley Lyu, Will Samuels  
**Data:** Inside Airbnb, Los Angeles, nominal snapshots March 16 and June 15, 2026

## Decision supported

The dashboard helps a Marketplace Strategy Manager select segments for human pricing review. A segment is neighborhood × room type × bedroom group. It combines advertised-price distributions, an inclusive pooled LA benchmark, repeated-snapshot consistency, and availability/review/stay context. It surfaces evidence for investigation rather than recommending a price.

The first-week prototype established the core distribution, benchmark and context views. The final implementation extends them into a reproducible three-tab application with canonical data, consistent filters, transparent ranking, evidence exports and automated verification against the later BUILD_SPEC.

## Data preparation and quality

The two supplied raw archives remain unchanged, with before/after SHA-256 validation. All 89,839 records are preserved in canonical listing data, unique by nominal date and string listing ID. Strict validation preserves raw tokens and status flags. Only valid positive prices with known segment dimensions enter comparable price statistics; missing-price records with valid dimensions remain in listing denominators and context.

| Nominal snapshot | Listing rows | Missing prices | Missing bedrooms | Recorded zero bedrooms |
| --- | ---: | ---: | ---: | ---: |
| March 16, 2026 | 46,088 | 8,910 | 3,196 | 2,570 |
| June 15, 2026 | 43,751 | 5,565 | 9,572 | 9 |

Bedroom coding is a major comparison limitation. Missing private-room bedrooms increase from 2,267/11,754 (19.3%) to 6,640/10,590 (62.7%). Unknown bedrooms remain excluded from comparable sets and never become Studio. The application shows local/peer exclusion shares and warnings rather than interpreting this composition change as supply movement. Recorded zero-bedroom counts also shift sharply; all Studio comparisons carry a specific caution.

Actual March scrape dates span March 16–18. June includes June 15–17 and June 22–23. The report distinguishes nominal dates from those actual dates and discloses previous-scrape source shares.

## Analysis and prioritization

The peer median pools all eligible LA listing prices with the same room/bedroom and optional stay/source filters, including the local neighborhood. No average of neighborhood medians is used. Price coverage is priced rows divided by all known-dimension rows. Context measures use their own valid denominators, including observations without a valid price.

A premium is `100 × (local median / peer median − 1)`. Both local and peer need the adjustable minimum priced count, default 20. Raw medians remain visible below that threshold. The fixed quality flag remains `<20` regardless of the selected minimum. Coverage below 80% warns without excluding rows. Histograms retain the full positive price range with 20 equal-width bins.

A persistent premium has positive qualifying premiums in both snapshots; a persistent discount has negative premiums in both. Opposite signs are Reversed, any zero is Neutral, and unavailable/failed evidence is Insufficient evidence. Only persistent rows rank. Score is the minimum of the two absolute premiums; context never enters the score. Ties resolve by neighborhood, room and numerical bedroom order.

At default settings, the resulting review list has **319 segments: 134 persistent premiums and 185 persistent discounts**. These are exploratory patterns, not statistically significant price errors. They must be considered with coverage, composition, source and context cautions.

## Verified examples and issue closure

- Hollywood / Entire home/apt / 1 bedroom: median $162.91 in March and $160.87 in June, a −$2.04 change (−1.3% displayed). Changing the detail snapshot leaves the two-date comparison unchanged.
- Malibu / Entire home/apt / 3 bedrooms: March has 68 priced of 86 listings, coverage 79.069767…%. Its on-screen/export warning appears at 80% and disappears at 75% without changing evidence counts.
- Altadena / Entire home/apt / 3 bedrooms: June has exactly 20 priced listings. The fixed small-sample flag remains False at both minimum 20 and 30; at minimum 30 its premium is suppressed.
- Hollywood Hills West / Entire home/apt / 6+ bedrooms: 47/46 priced rows across dates, review score 81.050175 percentage points. Grouping every 6+ listing avoids fragmented comparisons.
- Venice / Private room / 1 bedroom: both local/peer bedroom completeness evidence accompanies its observed premium. High June bedroom missingness is visible in the row and export.

Each of the five actionable requests has a regression check; details are in ISSUE_RESOLUTION.md. Original team issue history is preserved. Resolution applies to this final local build; no remote merge is asserted.

## Interface and reproducibility

The application starts at June / Hollywood / Entire home/apt / 1 bedroom, all stays and sources, minimum 20, coverage warning 80%. Segment Detail shows counts, coverage, price/IQR, relative price, full-range distribution and context. March–June Comparison displays both dates, changes, persistence and quality cautions. Review Shortlist ranks all segments independently of the detail selectors, permits direction filtering and row selection, and exports full-precision evidence with settings, dates, denominators, warnings and canonical fingerprint.

Canonical cleaning, reusable backend calculations, data access/validation and interface presentation are separate. Content-based caching invalidates when canonical artifacts or analytical settings change. Pinned project dependencies and exact launch/regeneration/test commands are included. A clean extracted-package check validates the submitted files separately from the working folder.

The revised local suite passed **55 tests**. Website/Python consistency passed **36 combinations and 42,303 segment comparisons**. Measured Streamlit AppTest cold execution was **2.06 seconds**, with cached detail changes **0.36–0.37 seconds**, meeting the specified local timing targets. Cold backend load plus default analysis was **1.07 seconds**. Actual outcomes and timing scope are recorded under reports. Performance is measured locally rather than generalized across machines. Synthetic fixtures cover malformed prices, IDs, optional/invalid fields, missing data, fixed count boundaries, inclusive benchmarks, context denominators, empty segments, outer joins, statuses, ranking ties and histogram behavior. Full-data regressions and independent csv/statistics recounts complement Streamlit UI tests and browser inspection.

## Interpretation and status

These are repeated cross-sections of advertised listings, not matched-listing causal estimates. Prices, composition, bedroom/source coding and missingness can change together. Availability is not occupancy; review counts are not booking demand. The tool does not estimate optimal prices, revenue, demand or causal effects.

The specification's conservative defaults are implemented and disclosed. Prior team approval of policy defaults is not assumed. A separate fresh-agent/human review and remote main merge are not claimed. The deliverable is a runnable, tested local submission package with reproducible evidence and documented assumptions.

## Instructor-feedback revision

The November 4 revision replaces default wide tables with price-range comparisons, separate context charts, two-date price/spread and signed-premium charts, coverage and bedroom-completeness visuals, priority bars, a persistence scatter and a five-status market overview. Customers can first inspect an interpreted chart and then expand supporting evidence. The underlying data, thresholds, ranking rule and audit fixes are unchanged. A public Sites companion provides interactive chart selection and browser CSV export; aggregate bundles are verified against the Python backend. See VISUAL_UPDATE.md for the rationale, chart definitions and validation.
