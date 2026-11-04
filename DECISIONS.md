# Decisions, assumptions and validation record

This build implements **Phase 2** of [BUILD_SPEC.md](BUILD_SPEC.md) (canonical data, reusable backend analysis, tests) and, since 2026-11-04, the **Phase 3** Streamlit dashboard (see "Phase 3 dashboard" below). It has not yet been deployed publicly. Everything below records what was actually run, assumed or left open. Nothing here is a team approval.

## Provenance

- Base commit: `main@ab3f030ea55e2bd33d53464007e89264e32fbaf0` (2026-10-26). The Phase 2 files are uncommitted on top of this commit until the team commits them. Record that commit in this section when it is made.
- Built on 2026-10-28 by Claude Code (Opus 5.5) at Will Samuels' request, working only from BUILD_SPEC.md and an inspection of the repository. A student still needs to review this build, and team adoption is not assumed.
- Phase 3 (dashboard) added on 2026-11-04 by Claude Code (Opus 5.5) at Will Samuels' request, still uncommitted on top of the same base commit.
- Environment: Python 3.13.15, pandas 2.3.3, numpy 2.5.4, uv 0.12.5, macOS on an Apple M1. Dependencies are pinned in `uv.lock`.

## Repository and input audit

- Main held documents (spec, change requests), the raw snapshots and an earlier team cleaner's outputs (`data/processed/la_*.csv`, `cleaning_report.json`). There was no code on main.
- Remote branches checked:
  - `origin/audit-riley-chapter3@4bdd0a3`, `generated_dashboard/`: an earlier spec-generated candidate built against the same BUILD_SPEC.
  - `origin/chenwang@e021c6a`, `phase2/`: an older backend that predates the final spec.
- Reuse decision. The candidate's structure and definitions were reviewed and its validated ideas kept: inclusive pooled peer, outer-join history, persistence rules, linear quantiles. The modules were rewritten at the repository root, the layout the spec suggests, to fix the defects that were open against it:
  - **AUDIT-VL-02**: the small-sample flag depended on the adjustable minimum.
  - **AUDIT-VL-01**: shortlist warnings were generic instead of specific to each row.
  - **AUDIT-WS-01**: there was no bedroom-completeness warning.
  - **AUDIT-WS-02**: there was no explicit `6+ bedrooms` label. (The candidate's bucket 6 was correct but unlabelled; the `chenwang` backend did not bucket at all.)
  - Only one population summary path existed in the candidate. There is now one vectorized routine, `pricing.aggregate`, shared by the segment file, segment metrics, peers and detail.
- The repository `chenwang266/DSO576_Project` is **private** (checked with `gh repo view`: `visibility: PRIVATE`). The team already tracks the raw `.csv.gz` files and processed data on main, so this build treats committing to this private repository as the course-authorized data workflow. **Assumption, needs team confirmation.** Data must not be pushed to any public remote.
- Raw inputs, verified with SHA-256. These match the hashes documented in the team's earlier cleaning report and audits.
  - `data/raw/listings-2026-03-16.csv.gz`: `ffdef08afe58b62e57cffb9da0f1daa97bf76e223fe98ce9e2022dd330976fc6`
  - `data/raw/listings-2026-06-15.csv.gz`: `ebc99e8a5ff2f60cbd91323571c2bdf1f8c2c74fe3ac9669d7c9a24d2294dec5`
- No missing inputs. No data was downloaded.
- The legacy processed files were left unchanged because they belong to teammates. They contain `host_id` and coordinates, and the new backend does not read them. The team should decide whether to remove them.

## Interpretations and assumptions (unapproved unless stated)

1. **Thresholds.** The defaults are a minimum priced count of 20 (local and peer separately), a coverage warning below 80%, `is_small_sample = priced_rows < 20`, and a persistence score equal to the minimum absolute March/June premium. They come from the spec. **The team has not recorded approval of them.**
2. **Bedroom-completeness warning** (my addition for AUDIT-WS-01). The spec requires a warning but does not define a rule. I chose:
   - In a comparison row, warn when the unknown-bedroom share moves by 10 percentage points or more between March and June. The share is measured among listings with the same neighbourhood and room type ("local") and among listings with the same room type across LA ("peer").
   - In Segment Detail, warn when either share is at least 10% in that snapshot.
   - The 10% setting is `unknown_bedroom_warning` in `config/project.json`. **Unapproved.**
   - With full data, 71 of 319 shortlist rows are flagged. Venice / Private room / 1 bedroom is flagged as WS-01 expects: the local share goes from 25.5% to 66.2% and the peer share from 19.3% to 62.7%.
   - **Hollywood / Entire home/apt / 1 bedroom is also flagged.** Its local unknown-bedroom share rises from 5.9% to 20.0%, although the LA peer share stays low (2.2% to 8.7%). WS-01's verification step expected no warning here. WS-01 is therefore **not marked resolved**. The team should either accept this result or choose a different rule or threshold.
3. **Source-mix warning** (an addition). When no source filter is applied, a comparison row warns if the segment's `city scrape` share moves by 10 points or more. It uses the same setting. **Unapproved.**
4. **Studio warning.** Every Studio row and every Studio detail carries a bedroom-coding warning: zero-bedroom listings fall from 2,570 in March to 9 in June.
5. **Price parsing.** Accepted forms are an optional `$`, digits with or without correct thousands commas, and up to 2 decimals. A leading `-` on a well-formed number gives `invalid_nonpositive`. Any other form is `malformed`. All real prices match `$x,xxx.xx`.
6. **Integers.** Values such as `3` or `3.0` are accepted. Negative values, and availability above its horizon, are `out_of_range`. Other text is `malformed`. A `minimum_nights` of 0 is a valid integer, but its stay category is Unknown.
7. **"Reference cleaner fields"** was read as the provenance, raw and status columns listed in DATA_DICTIONARY.md. `snapshot_label` is included. The legacy cleaner's `snapshot_name`, `bedroom_segment` text and pipe-delimited `segment_key` were not reproduced: `segment_key` is now JSON so it cannot collide on delimiters.
8. **Unknown-dimension rows** are not counted in segment `listing_rows`. That is the spec's "valid-dimension listing count".
9. **Excluded data.** Host details, listing text and coordinates are left out of the canonical files.
10. **Premium suppression reasons** are applied in priority order: no local prices, local below minimum, peer below minimum, nonpositive peer median.

## Actual validation

All commands were run from the repository root on 2026-10-28.

```bash
uv sync --locked
uv run python scripts/canonical_clean.py --march data/raw/listings-2026-03-16.csv.gz --june data/raw/listings-2026-06-15.csv.gz --output-dir data/processed
uv run pytest
```

- **Cleaner on full data.** It completed with March at 46,088 rows and June at 43,751 (89,839 in total). Raw SHA-256 values were unchanged after cleaning, and every row was kept.
- **Reference counts.** The cleaner recalculated them and all match the spec:

  | | March | June |
  | --- | --- | --- |
  | Rows | 46,088 | 43,751 |
  | Missing prices | 8,910 | 5,565 |
  | Zero bedrooms | 2,570 | 9 |
  | Missing bedrooms | 3,196 | 9,572 |

  There were no malformed or nonpositive prices, no unknown neighbourhoods or room types, and no duplicate or blank IDs in either file.
- **Canonical output SHA-256:**
  - `canonical_listings_clean.csv` (41.6 MB): `a0399e13c9ba6d9f5cc62946bbd958b22f901a3301daa6970365e6eda784a0e6`
  - `canonical_price_segments.csv`: `3549e7d68ef39699baf24f11edf0e7149bcbec72c93d1d2f389b38fae59268e3`. It has 2,160 March and 1,835 June segment rows.
  - `canonical_cleaning_report.json`: `1dfd544967cdf356887148360fed1e4f08e2c88382c40e555c30bfa94b0e736b`
- **Reproducibility.** Three separate full-data runs, one in a different directory, produced byte-identical outputs.
- **pytest.** 62 passed.
  - 55 synthetic tests cover price parsing edge cases, malformed/missing/nonpositive prices, duplicate or blank IDs, missing required fields, invalid/missing/zero/≥6 bedrooms, invalid room types, whitespace in neighbourhoods, availability over its horizon, value scores of 0 and >5, missing optional fields, empty segments, row conservation, unchanged raw hashes, reproducibility, aggregate reconciliation, typed loading, schema/key/Boolean checks, fingerprint change, and config validation.
  - The spec's count case (5 / 4 / 0.8, with a missing-price row still counted in context), the 19/20 small-sample cases and the numeric case (150 / 125 / 175, coverage 2/3, peer 250, −40% at a minimum of 2, unavailable at 20) all pass.
  - History tests cover null March values for June-only segments, same-sign, opposite-sign and zero-sign premiums, failed evidence, deterministic ties (Studio < 1 < 2 < 6+), an empty shortlist, Studio and coverage warnings, a VL-02 regression, consistency between detail and segment metrics, stay/source recalculation from listings, inputs not being mutated, and backends importing without Streamlit.
  - 7 full-data tests check the real data against an independent recomputation from the raw files that uses only the standard library (`csv`, `statistics`). It covers Hollywood Entire 1BR, Hollywood Hills West Entire 6+ and Venice Private 1BR for both dates: counts, medians, peer medians and premiums.
- **Agreement with teammates' independently documented figures:**
  - Hollywood / Entire / 1BR medians are $162.91 and $160.87, a change of −$2.04 (−1.3%), matching AUDIT-RL-01.
  - Hollywood Hills West / Entire / 6+ has 47 and 46 priced listings, peer medians of $1,362.44 and $1,520.26, premiums of +81.05% and +93.87%, and a score of 81.050175. These match WS-02's expected values. Its rank is **34**; WS-02 estimated about 30 and did not verify it.
  - Malibu / Entire / 3BR is rank 5, with March coverage of 68/86 = 79.1% and the row-specific warning `March local price coverage 79.1% is below the 80.0% warning threshold.`, matching VL-01.
  - Direction set to discount returns 185 rows, matching WS-03.
  - The full shortlist has 319 persistent segments: 134 premium and 185 discount. Of the other segments, 34 are Reversed, 1 is Neutral and 1,879 are Insufficient evidence.
- **Fresh-checkout simulation.** Tracked and new files, without the canonical outputs and without `.venv`, were copied to a temporary directory. There, `uv sync --locked` succeeded and `uv run pytest` gave 55 passed and 7 skipped. After running the cleaner, the outputs had identical hashes and `uv run pytest` gave 62 passed. This was not a real `git clone` of a pushed commit.
- **Backend timing.** Measured on an Apple M1, backend only, not the app:

  | Step | Time |
  | --- | --- |
  | Load and validate the canonical files | 1.4–1.8 s |
  | All-segment metrics for both dates | 0.49 s |
  | Comparison | 0.05 s |
  | Ranking | <0.01 s |
  | One segment detail | 0.18 s |
  | Recomputation with stay and source filters | 0.30 s |

  The spec's targets of ≤10 s cold load and ≤2 s cached update are **not yet claimed**. They must be measured on the Phase 3 app.

## Change-request status (from change-requests.md)

None of these requests is marked resolved in change-requests.md. Verification belongs to the request authors.

| Request | Status of this build |
| --- | --- |
| AUDIT-WS-01 | Warning added. Venice is flagged as expected, but Hollywood is also flagged (see assumption 2). Needs a team decision. |
| AUDIT-WS-02 | Addressed. Bedroom segments are explicit `Studio` / `1`–`5` / `6+` / `Unknown`, and the HHW 6+ score is 81.050175. |
| AUDIT-WS-03 | Addressed in the backend: persistence labels, direction, warnings with small-sample and coverage flags, a direction option, and stay/source filters. The interface part waits for Phase 3. |
| AUDIT-VL-01 | Addressed in the backend: row-specific coverage warnings at the current threshold. A test confirms they disappear at a lower threshold while the counts stay the same. |
| AUDIT-VL-02 | Addressed: `is_small_sample` is fixed at `< 20`, separate from `sufficient_evidence`, and a regression test covers it. |

## Phase 3 dashboard (2026-11-04)

Files: `app.py`, `src/charts.py`, `src/presentation.py`, `tests/test_app.py`, `tests/test_presentation.py`, `.python-version`. Streamlit 1.66.1 and Plotly 6.9.0 were already pinned in `uv.lock`; no dependency changes.

**Design choices (unapproved unless stated):**

1. **Layout.** Sidebar with snapshot, neighbourhood, room type, bedrooms, stay and source filters, minimum priced count (number input, 1–1000), coverage warning (slider, 0–100% in 5-point steps) and Reset. Tabs are stateful (`st.tabs(key="view")`) so a shortlist row can open Segment Detail; hidden tabs skip their work.
2. **Snapshot scope.** The snapshot selector only changes Segment Detail. The comparison and shortlist always use both dates with the same optional filters.
3. **Unavailable selections.** Options come from validated comparable listings across both dates. A session value not in the options shows a sidebar warning naming it and falls back to the first option. A valid combination with no listings in the chosen snapshot shows an explanation, not zeros.
4. **Shortlist row selection** writes the segment into the sidebar and switches to Segment Detail; stay, source and thresholds are untouched. Verified by clicking in the browser (Malibu / Entire / 5 bedrooms opened correctly). AppTest cannot simulate dataframe row selection, so there is no automated test of this click.
5. **Exports.** *Visible shortlist*: every backend comparison column at full float precision, prefixed by generation time, canonical fingerprint, both nominal dates, filters, thresholds, direction and the peer definition. *Segment evidence*: a long `section, field, value` CSV of the same settings plus every comparison field for the sidebar segment, and the Segment Detail warnings when exported from that tab.
6. **Formatting.** USD to two decimals, percentages to one, signed premiums and changes. Missing results show `Unavailable` plus a reason. Direction and persistence carry text symbols (▲ ▼ ⇅ • ?) as well as words; chart series use different marker shapes and legends.
7. **Charts.** Local histogram (20 equal-width bins, dashed median line); comparison chart of local and LA-peer medians with P25–P75 whiskers; premium bars per snapshot with an `Unavailable` label instead of a zero bar. The Plotly toolbar is hidden because it overlapped titles on phones.
8. **Caching.** File stats (mtime, size) → SHA-256 combined fingerprint (`st.cache_data`) → validated data (`st.cache_resource`, one entry, treated as read-only) → comparison and detail results (`st.cache_data`) keyed by fingerprint plus every filter and threshold.

**Actual validation (Apple M1, 2026-11-04):**

- `uv run pytest`: **76 passed** (62 earlier + 14 new). The new tests cover formatting, shortlist display order and text labels, full-precision export round trips with settings columns, an empty-shortlist export, evidence export (including a segment with no listings), methodology content, empty/constant histograms, unavailable premiums not drawn as zero, the setup error when canonical files are missing, UI/backend agreement on the default view, the comparison tab and the discount shortlist (185 rows), filter persistence across tabs, the unavailable-selection message, Reset, and cache invalidation after a canonical file changes.
- **UI vs backend.** The default view shows 482 listings, 403 priced, 83.6% coverage, median $160.87, premium −11.0%; the comparison shows $162.91 → $160.87 (−$2.04, −1.3%). Shortlist status counts shown in the app: 134 premium, 185 discount, 34 reversed, 1 neutral, 1,879 insufficient. These match the Phase 2 figures above.
- **Browser check** in the Claude desktop browser pane at 1280×900 and 375×812 (phone emulation): all three tabs render; columns stack on the phone width; tables scroll horizontally inside their frame.
- **Timing (AppTest, headless):** cold first run, including import, data load and validation, **2.4–3.9 s**; switching to an already computed tab **0.03–0.08 s**; changing the stay filter (recompute from listings) **0.36–0.38 s**; returning to cached filters **0.04–0.05 s**. These meet the spec's ≤10 s and ≤2 s targets in this environment. Not measured on Streamlit Community Cloud.
- Peak memory for loading and comparing the full data: about 370 MB resident.

**Deployment.** Planned target is Streamlit Community Cloud from this private repository (steps in README). The repository and data stay private; the deployed app URL is public and shows only aggregated Inside Airbnb figures (CC BY 4.0, attributed in the app). **Not yet deployed**: the code and canonical data must be committed and pushed first, and a team member must sign in to share.streamlit.io. Whether a public app is acceptable for the course is a **team decision**.

## Open items and unapproved defaults

- Team approval is needed for:
  - the thresholds (20, 80%, the score definition)
  - the 10% unknown-bedroom and source-mix rules
  - the data-sharing workflow (committing data to the private repository)
  - publishing the dashboard at a public Streamlit Community Cloud URL
  - whether to remove the legacy processed files that contain host IDs and coordinates
- Still to do:
  - commit and push the Phase 2 and Phase 3 files, then record the commit here
  - deploy to Community Cloud and measure cold/cached timing there
  - a real fresh `git clone` of the pushed commit (only a copied-directory simulation has been run)
- Fresh-agent verification (a new agent given only the repository and the spec) has **not** been performed.
