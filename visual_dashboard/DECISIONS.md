# Decisions, provenance and implementation status

## Authority and scope

The user's request is to optimize the first-week dashboard against the later BUILD_SPEC and reasonably resolve the team's documented issues, producing a submittable final version. Attached document instructions are treated as project requirements/reference material, not permission to post, message teammates, merge branches, publish data, or claim approvals.

Sources: `DSO576_Project-main (1).zip` (archive commit comment `ab3f030ea55e2bd33d53464007e89264e32fbaf0`), `DSO576_Project-phase1-dashboard.zip` (archive commit comment `72e912a63dea3c375aaa13e7fd98106b718705b9`), and the existing local `cleaning-review/canonical_clean.py` and its tests. The source build specification and latest zipped change-request history are preserved. The original HTML is in `reference/`.

The supplied newer archive contains data, spec and issue history but no runnable dashboard backend. The existing canonical cleaner was reused after validation and upgraded. New reusable modules and a complete Streamlit UI were built locally. No referenced remote candidate code was fetched or assumed present. Claims about older branches remain historical; this package documents its own verified resolution in ISSUE_RESOLUTION.md.

## Implemented policies and approval status

These are the specification's conservative defaults, **implemented for this final submission; separate team policy approval is not established**:

- Include all source and stay cohorts by default; provide optional filters recalculated from listings.
- Keep every source row and positive advertised price; no price imputation, outlier removal or cap.
- Preserve zero review-value scores with an explicit flag; valid score range 0–5.
- Require known neighborhood, known room type and valid bedrooms for comparable segments; retain missing-price rows in coverage denominators and context.
- Bedroom groups: Studio, 1–5 separately, 6+ bedrooms, Unknown. Preserve valid raw numeric bedrooms ≥6 in the canonical listing field, while segment and peer keys always use the bucket. Missing bedrooms never become Studio.
- Inclusive pooled LA peers, linear-interpolated quartiles, raw medians preserved below the exploratory minimum.
- Fixed small-sample flag `<20` is independent of the adjustable minimum (default 20). Both local and peer priced counts must meet that minimum to produce a premium; coverage is warning-only (default <80%).
- Persistent same-sign premiums/discounts only; score = smaller absolute premium, descending. Ties: neighborhood, room, numerical bedroom order. Context does not affect score. Direction filtering occurs after global ranking inputs are calculated; displayed ranks restart at 1 within the visible direction.
- Bedroom composition warnings: per-snapshot local/peer unknown share ≥25%, or June deterioration ≥10 percentage points. These diagnostic cutoffs operationalize AUDIT-WS-01 and are proposed, not significance tests. Studio always receives the source-coding warning. Both original shares and denominators are exported even below warning cutoffs.
- Source cautions identify local/peer previous-scrape shares; actual scrape dates are shown separately from nominal dates.

## Changes to the reused cleaner

Removed blanket `.round(2)` from canonical segment aggregates: full precision is needed for ratios, exports and audit reconciliation. Added the fixed `is_small_sample`, output content fingerprints, per-status counts, zero/missing-bedroom counts, actual dates/source distribution, and raw before/after hash verification. Recognizable negative USD values are classified as nonpositive and excluded, preserving raw tokens. Duplicate IDs and missing required fields fail visibly. Missing optional fields remain unknown/unavailable.

## Performance and caching

Backend modules do not import Streamlit or mutate caller frames. One `snapshot_summary()` routine supplies both dates for detail/comparison/ranking. Every rerun fingerprints all three canonical files; cached data and comparisons use content hash, directory, stay/source, adjustable minimum and coverage threshold. Ranking is independent of detail selection; switching detail snapshot never changes the cached comparison. No time-to-live cache can mask a content change.

Measured local results, machine/environment and timing scope are in reports. Server startup, dependency installation and browser/network rendering are outside backend timing. Streamlit AppTest cold and cached reruns are measured separately. Never generalize these as a cross-device guarantee.

## Verification and remaining limits

Synthetic acceptance cases, actual data reconciliation, each actionable audit reproduction, independent csv/statistics raw recount, and Streamlit integration are executable in the package. A clean temporary extraction is checked using only submitted files and the pinned environment. This is a clean-extraction reproducibility check, **not a separate fresh-agent or human review**. No subagents were used. The literal fresh-agent handoff in the supplied spec remains unperformed; no such approval is claimed.

No Git commit was created and no remote main was modified. Exact submitted source hashes identify the local artifact. The attached change-request statuses are preserved rather than rewriting teammates' historical evidence. All fixes are documented as verified in this local final build; team merge status is unknown.

Results are repeated cross-sections. They may reflect composition, missingness, source or coding changes. They do not establish pricing errors, effects, optimal prices, occupancy, demand or revenue. The June Studio cohort is sparse. Warning cutoffs and source/outlier defaults are disclosed assumptions; user/team acceptance of the final package does not fabricate prior policy approval.

## November 4 visual revision and Sites companion

The user requested more analysis charts and less customer-facing table density, then explicitly invoked Sites. The Streamlit app now leads with interpreted charts and keeps detailed evidence expandable. The public Site publishes only backend-generated segment aggregates, not raw listing/host/location records. Its independent source commit and native deployment status are recorded separately; the Python submission is still identified by its own manifest hashes. Original source attribution, data policies and approval status remain unchanged. The Site browser adapter is verified across 12 stay/source bundles at three threshold configurations; missing opposite-date fields remain null. Original audit fixes are regressed in the 55-test suite.
