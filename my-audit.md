# Individual audit — Will Samuels

| Item | Value |
| --- | --- |
| Auditor | Will Samuels (wsamuels-usc) |
| Requirement audited | `BUILD_SPEC.md` §1 *Build instruction and vision*, use case **Prioritize**: "Filters and evidence threshold → ranked persistent premiums/discounts → which segments need review?" |
| Feature audited | Review shortlist (ranked persistent premiums/discounts) |
| Number audited | Segment **premium (%)** and the shortlist **review score** built from it (min of absolute March/June premium) |
| Spec version | `main` @ `be155ab` (BUILD_SPEC.md) |
| Implementation checked | `origin/chenwang` @ `e021c6a`: `phase2/analysis.py`, `phase2/outputs/ranked_review_list.csv`, `phase2/outputs/segment_comparison.csv` |
| Raw data used | Inside Airbnb LA detailed listings on `origin/wsamuels`: `data/raw/3_15.csv.gz` (SHA-256 `ffdef08a…76fc6`) and `data/raw/6_15.csv.gz` (SHA-256 `ebc99e8a…4dec5`) |
| Reproducible check | [audit_checks/wsamuels_premium_check.py](audit_checks/wsamuels_premium_check.py) |
| Change requests | AUDIT-WS-01, AUDIT-WS-02, AUDIT-WS-03 in [change-requests.md](change-requests.md) |

**Scope note:** The Streamlit dashboard in §4 does not exist on any branch yet. The only Phase 2 implementation of the Prioritize flow is Chen's backend on `origin/chenwang`, so I audited the shortlist it exports: the table the Review Shortlist tab would display. I did not audit the Phase 1 HTML dashboard on `phase1-dashboard`.

---

## 1. Feature audit as its user

### Intended user and task

**User:** Airbnb Marketplace Strategy Manager for Los Angeles (§1).
**Task:** Set filters and an evidence threshold, then get a ranked list of neighborhood × room type × bedroom segments whose price premium or discount relative to LA peers shows up in **both** March and June. The manager uses that list to decide which segments to send for *human pricing review*. The list is not meant to set prices.

To use the list, the manager needs to know three things for each row: (a) whether the gap repeats across both snapshots, (b) how large the gap is, and (c) whether the evidence is weak enough to treat with caution, for example small counts, low coverage, or bedroom-coding changes.

### What I did

1. Read §1, then the parts of §3 and §4 that define Prioritize (persistence, score, ranking, warnings, premium/discount/both toggle).
2. Opened `ranked_review_list.csv` (315 rows) and read it the way the manager would: top rows first, then looked for the direction, status, and warning information §4 requires.
3. Recomputed four shortlist segments from the raw files with my own code (Section 2).

### What works (reproducible)

| Check | Result |
| --- | --- |
| Only persistent segments are ranked | All 315 rows have `persistent_pattern = True` and a non-null `review_score`. 130 are premiums and 185 are discounts. |
| Ranked by conservative magnitude, descending | Rank 1 is Avalon / Entire home / 1BR, score 228.65 (March +228.65%, June +276.95%). Scores are non-increasing down the list. |
| Ties are broken deterministically | Sort is `review_score` desc, then neighbourhood, room type, bedrooms (`analysis.py`, `ranked_review_list`). |
| Peer group includes the selected neighborhood and pools listings | `_aggregate(base, PEERS)` groups on snapshot + room + bedrooms only, so the selected neighborhood is included. My independent computation matches it (below). |
| Evidence threshold of 20 is applied to both local and peer populations | `sufficient_data = price_n ≥ 20 & peer_price_n ≥ 20`. |
| Spec's default start segment behaves sensibly | Hollywood / Entire home / 1BR is a **persistent discount** (−3.70% March, −10.95% June) with score 3.70, so it ranks near the bottom of the discounts. |

### What is missing or misleading

| # | Observation | Why it matters to the manager | CR |
| --- | --- | --- | --- |
| M1 | **No bedroom-completeness warning, even though June private-room bedroom data mostly disappears.** In June, 6,640 of 10,590 private-room listings (63%) have blank `bedrooms`, compared with 2,267 of 11,754 (19%) in March. The LA private-room 1BR peer pool falls from 8,562 to 3,293 listings. Venice private-room 1BR goes from 121 to 38 listings, and Santa Monica from 196 to 96. For the 37 private-room rows on the shortlist, the median June/March listing ratio is 0.40. | The June half of the "persistent" test for private rooms is computed on a minority subset that may not be representative. Santa Monica private 1BR jumps from +139% to +321%. The manager sees no sign that this change may come from the data. §2 and §4 require bedroom-coding warnings on comparison and shortlist rows. | AUDIT-WS-01 |
| M2 | **Bedrooms are not collapsed to "6+".** The output has separate segments for 6 through 24 bedrooms (271 segment-rows with ≥6 bedrooms). | §2 requires `≥6 → 6+ bedrooms`. Splitting 6+ changes both the local and the peer population. Rank 50 (Hollywood Hills West / Entire home / 6BR, score 50.19) becomes score **81.05** under the spec's 6+ definition, which would put it at about rank 30. | AUDIT-WS-02 |
| M3 | **The shortlist has no direction, status, or warning columns.** The output has no `direction`, no persistence status label, no `is_small_sample`, and no coverage warning. 77 ranked rows have March price coverage below 80% and 28 have June coverage below 80%, with nothing flagging them. The non-ranked statuses (Reversed: 34 segments, Insufficient evidence: 2,006 segment-rows, Neutral) collapse into a single `False`. | §1 asks for ranked *premiums/discounts*, and §3–4 require a premium/discount/both option, a status label, and warnings on every row. Without them the manager has to work out direction from the sign of two columns, and cannot tell "reversed" apart from "not enough data". | AUDIT-WS-03 |
| M4 | Optional filters do not match the spec. The code offers `property_type`, `accommodates`, and `exclude_high_prices`. The spec's stay-length and source filters are not implemented. | "Filters" in the Prioritize row means stay/source in §3. A manager cannot yet shortlist long-stay segments only. | Covered in AUDIT-WS-03 |

---

## 2. Number audit: premium (%) and review score

### What the number should mean

**Premium (%)** = `100 × (local median price / peer median price − 1)`.
- *Local:* valid-priced listings in one snapshot × neighborhood × room type × bedroom segment.
- *Peer:* valid-priced listings with the same snapshot, room type, and bedroom segment across **all** LA neighborhoods, **including** the local one. Listings are pooled; neighborhood medians are not averaged.
- *Units:* percent. *Denominator:* the peer median (USD/night, advertised price).
- *Range:* (−100%, +∞). It can never reach −100% because prices must be > 0. It is undefined if the peer median is ≤ 0 or if either population has fewer than 20 priced listings.
- *Review score:* `min(|premium_March|, |premium_June|)`, defined only when both premiums have the same strict sign. Units are percentage points. It is always ≤ both absolute premiums.

### Sanity checks

- **Range/units:** Across 315 ranked rows, every premium is above −100%, every score is positive, and every score is ≤ both absolute premiums. ✔
- **Denominator:** The peer pool for Entire home / 1BR (11,845 listings in March) is far larger than any local segment, and it changes across snapshots for the same room/bedroom key. That confirms the peer group is pooled at the LA level and recomputed per snapshot. ✔
- **Hand-calculable case (spec §6):** local `[100, 200, missing]`, other neighborhoods `[300, 400]`.
  Local median = (100+200)/2 = **150**. P25 = 100 + 0.25·100 = **125**. P75 = **175**. Coverage = 2/3.
  Inclusive peer `[100, 200, 300, 400]` → median = (200+300)/2 = **250**.
  Premium = 100·(150/250 − 1) = **−40%** at threshold 2, and **unavailable** at threshold 20.
  My script reproduces all six values and asserts them (`toy()`). ✔

### Independent recomputation (my own code, not the team's)

[audit_checks/wsamuels_premium_check.py](audit_checks/wsamuels_premium_check.py) reads the **raw** CSVs as strings and implements the §2–3 rules directly: strict `$` price parsing, positive prices only, room/bedroom categories with `0 → Studio` and `≥6 → 6+`, blank → Unknown, inclusive peer group, and threshold 20. It uses numpy percentiles rather than pandas groupby, and it does not import or copy `analysis.py`.

**Reproduce:**

```bash
git show origin/wsamuels:data/raw/3_15.csv.gz > /tmp/m.csv.gz
git show origin/wsamuels:data/raw/6_15.csv.gz > /tmp/j.csv.gz
python3 audit_checks/wsamuels_premium_check.py /tmp/m.csv.gz /tmp/j.csv.gz
```

Raw row and missingness counts match the spec's reference values exactly: rows 46,088 / 43,751, missing prices 8,910 / 5,565, missing bedrooms 3,196 / 9,572.

| Segment | Snapshot | Local priced / listings | Local median | Peer priced | Peer median | My premium | Team premium | Match |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Hollywood / Entire / 1BR | Mar | 414 / 575 | 162.91 | 9,534 | 169.175 | −3.703266% | −3.703266% | ✔ |
| Hollywood / Entire / 1BR | Jun | 403 / 482 | 160.87 | 9,685 | 180.66 | −10.954279% | −10.954279% | ✔ |
| Avalon / Entire / 1BR (rank 1) | Mar | 53 / 53 | 556.00 | 9,534 | 169.175 | 228.653761% | 228.653761% | ✔ |
| Avalon / Entire / 1BR (rank 1) | Jun | 54 / 54 | 681.00 | 9,685 | 180.66 | 276.951179% | 276.951179% | ✔ |
| Venice / Private / 1BR | Mar | 99 / 121 | 206.00 | 7,684 | 84.00 | 145.238095% | 145.238095% | ✔ |
| Venice / Private / 1BR | Jun | 31 / 38 | 265.07 | 3,019 | 88.00 | 201.215909% | 201.215909% | ✔ |
| Santa Monica / Private / 1BR | Mar | 182 / 196 | 200.75 | 7,684 | 84.00 | 138.988095% | 138.988095% | ✔ |
| Santa Monica / Private / 1BR | Jun | 84 / 96 | 370.44 | 3,019 | 88.00 | 320.954545% | 320.954545% | ✔ |

Review scores also match: Hollywood 3.703266 (Persistent discount), Avalon 228.653761, Venice 145.238095, Santa Monica 138.988095 (Persistent premiums). Hollywood's March count, median, and quartiles also match Chen's own `validation.json` (414, 162.91, 109.81, 232.615).

### Going deeper: the assumption behind the result

The formula is implemented correctly. The risk is in **which listings form the segment**, which comes down to two lines:

1. `_aggregate`: `data = data.dropna(subset=keys)`. Listings with unknown bedrooms are silently removed from both local and peer populations. That is correct per spec. However, June's 63% blank rate for private rooms means the June private-room premium compares a self-selected 37% of listings with a self-selected 37% of peers. If hosts who fill in `bedrooms` charge differently from hosts who leave it blank (the field may be populated differently for room listings in the June scrape), the June premium moves for reasons unrelated to pricing. The Venice and Santa Monica June premiums rise sharply (145→201, 139→321) while their segment sizes fall 60% and 51%. The persistence call could still be right, since both premiums are strongly positive, but the *magnitude* in June is not comparable to March and is shown with no warning. → AUDIT-WS-01.
2. `KEYS = [..., 'bedrooms']` groups on the raw numeric bedroom count with no 6+ collapse. Under the spec definition, Hollywood Hills West / Entire / 6+ has 47 and 46 priced listings, peer medians of $1,362.44 and $1,520.26, and premiums of +81.05% and +93.87%. The team's 6-only segment shows +50.19% and +54.18%, with a score of 50.19 instead of 81.05. → AUDIT-WS-02.

**Effect on the answer:** For 1–5 bedroom segments with good bedroom completeness (most Entire-home rows), the premium and score are correct and the ranking can be trusted. For ≥6-bedroom segments, the score and rank are wrong relative to the spec. For private-room segments, the ranking is probably directionally right, but the June magnitudes are unreliable and the manager is not warned.

---

## 3. Conclusion

- **Premium (%) and review score:** Correctly implemented for the populations the code builds. Verified to 6 decimal places on 8 segment-snapshots against independent code on raw data, plus the spec's hand-calculated case.
- **Prioritize feature:** It partly meets §1. Ranking logic, persistence rule, threshold, and tie-breaking are correct. However, the shortlist (a) uses a non-spec bedroom grouping for ≥6 bedrooms, (b) gives no warning on the private-room segments most affected by June's bedroom missingness, and (c) lacks the direction toggle, status labels, small-sample/coverage warnings, and stay/source filters the manager needs.
- **Change requests filed:** AUDIT-WS-01 (bedroom-completeness warning), AUDIT-WS-02 (6+ bedroom bucket), AUDIT-WS-03 (shortlist status/direction/warning columns and spec filters).

### Remaining uncertainty / not tested

- I recomputed 4 segments (8 segment-snapshots), not all 4,201 segment-rows. Agreement on these is strong evidence, not proof for every row.
- I did not establish *why* June private-room bedrooms are blank, or whether those listings are priced differently. A follow-up check would compare June price distributions for blank-bedroom versus known-bedroom private rooms.
- The rank of about 30 for Hollywood Hills West 6+ is approximate. A full 6+ rerun could also let other 7+ bedroom segments pass the 20-listing threshold and enter the list.
- Not tested: stay/source filters (not implemented), the Streamlit UI, CSV export, caching, and UI/backend agreement (no UI exists yet).
- My price parser is stricter than Chen's (it rejects malformed strings rather than stripping `$` and `,`). Missing-price counts are identical, so this had no effect on these segments.

---

## 4. My contribution and AI use

- **AI use:** I used Claude Code (Claude Opus 5.5) to explore the team branches, write the independent check script from the spec text, run it on the raw files, compare its output with Chen's exported CSVs, and draft this audit and the change requests.
- **My contribution:** I chose the requirement to audit (BUILD_SPEC.md §1) and prompted Claude Code with the assignment's audit guidelines. Claude Code chose the Prioritize use case and the premium/review-score metric within §1, found the implementation on the team branches, and did the analysis, findings, and writing. The raw snapshots used in the check are the ones I committed to `origin/wsamuels` for Module 6, but I did not collect them for this audit. I reran the check using the wsamuels_premium_check.py, and can confirm that outputs were as expected. For example, Hollywood's -3.7% March premium matched Chen's CSV.
- **Committed check:** `audit_checks/wsamuels_premium_check.py`. _b2f05d62715cffcad2a010c73685e0de6b132a7d_
