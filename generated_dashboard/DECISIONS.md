# Build and audit decisions

## Version and provenance

Generated locally on October 25, 2026 (America/Los_Angeles), from the team's BUILD_SPEC.md on main, for Riley Lyu's Chapter 3 audit. This is a new AI-generated candidate build, not a claim that the team has approved or deployed it. Existing HTML dashboards and Chen Wang's older backend were inspected as context; this app has its own canonical schema and calculation path.

Application source fingerprint: `54f049cb052cc0dfb2d334ae302f3d1c82422bd002b526cc4a72b79980701a7b`. Individual source hashes are in audit_full_data_results.json. Tests and the independent raw-file oracle were added after initial implementation. No faulty calculation was deliberately inserted to manufacture an audit finding.

## Data

Only the two authorized local Inside Airbnb detailed-listings inputs were used. No downloads or substitute market observations. Canonical outputs stay local under ignored data/processed; public Git contains code and aggregate check evidence only. Team sharing of canonical data through the course-authorized workflow remains outstanding.

- March input SHA-256: `ffdef08afe58b62e57cffb9da0f1daa97bf76e223fe98ce9e2022dd330976fc6`
- June input SHA-256: `ebc99e8a5ff2f60cbd91323571c2bdf1f8c2c74fe3ac9669d7c9a24d2294dec5`
- Rows: March 46,088; June 43,751; combined 89,839. Raw hashes verified unchanged after processing.
- Missing optional values stay missing; source missingness is labeled Unknown. Raw and normalized labels and field statuses are retained. Six or more bedrooms form bucket 6. Unknown bedrooms are not Studio.

## Actual validation

Executed from this folder with the locked Python 3.13 environment:

```powershell
uv run python scripts/canonical_clean.py
uv run pytest -q --junitxml=audit_test_results.xml
uv run python tests/audit_full_data.py
```

- Cleaner completed on both real inputs with row conservation and unchanged raw hashes.
- 17 pytest cases passed, including synthetic boundary cases and real Streamlit app widget interactions using a clearly labeled synthetic canonical fixture.
- Independent csv/gzip loops read the raw files and use Python statistics.median, without calling the canonical cleaner or pandas aggregation. Hollywood and Venice medians, counts, coverage, inclusive peer median, premium and price changes matched the backend.
- Full-real-data AppTest passed four interaction states: default Hollywood/June, switch detail to March, switch neighborhood to Venice, Reset. Displayed comparisons matched the raw-file oracle.
- Initial real-data AppTest execution took 9.004 seconds in this run. This is not browser cold-load timing; no claim is made that cold-load/cached-update targets are met.

## Limits and approvals

Browser pixel layout, narrow-screen visuals, every export/shortlist interaction, fresh-clone data provisioning, end-to-end production deployment, and a fresh-agent build review have not been verified. The app is local Streamlit as required, not a hosted Sites replacement. The teacher's individual audit is narrower than full project acceptance. The evidence does not establish compliance with every build requirement.

Threshold 20, coverage warning 80%, inclusive peers and persistence score follow the supplied spec; team approval of these exploratory defaults remains unconfirmed. The original spec was used unchanged. No teammate request is marked resolved: Will Samuels' existing requests address a different, older implementation.

No defect was found in the tested Chapter 3 comparison feature and price-change arithmetic. The small-case and two-neighborhood evidence supports only the checked cases, not all possible data. Student review of audit judgments remains necessary; execution and drafting were performed by Codex and must be attributed accordingly.
