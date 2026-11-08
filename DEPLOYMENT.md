# Phase 3 deployment — Los Angeles Pricing Review

**Public dashboard:** [Open the live Site](https://la-pricing-review-visual.belovedferret.chatgpt.site/)

The public application is the browser-only visual dashboard. Python prepares the evidence bundles before deployment. Changing a filter loads a bundled JSON file and applies the evidence thresholds in the browser, so the live Site needs no Python server, credentials, database, or visitor account.

| Setting | Value |
| --- | --- |
| Hosting route | Sites, existing Los Angeles Pricing Review project |
| Dashboard source in this GitHub repository | `site/` |
| Hosting manifest | `site/.openai/hosting.json` |
| Static directory relative to the Sites source checkout | `dist` |
| Entry page | `site/dist/index.html` |
| Build and install commands | None; Plotly and 12 prepared evidence bundles are included |
| Local preview from repository root | `python3 -m http.server 8502 --directory site/dist` |
| Visibility | Public; no login required |

Open `http://localhost:8502/` for a local preview. All application asset paths are relative. The public Site serves only prepared neighborhood × room × bedroom aggregates, with no listing IDs, host records, coordinates, or raw archives. The site does not persist visitor inputs.

## Data preparation and updates

Use [visual_dashboard/README.md](visual_dashboard/README.md) to recreate the canonical files from the supplied March 16 and June 15, 2026 Inside Airbnb snapshots, run the tests, and regenerate the aggregate bundles. Publish an updated version of the same Site from its managed Sites checkout with `dist` configured. Push the same sources to this team repository. A GitHub push alone does not republish Sites.

The separate repository-root Streamlit implementation retains its [original deployment instructions](STREAMLIT_SETUP.md). It is not needed to run the Sites version.

## Acceptance

Open the live URL without authentication. Verify a histogram or benchmark chart, change neighborhood and room type, compare the displayed medians and coverage to the local reference, check a filtered CSV export, and try a valid empty combination. Repeat a smoke check on another device before handing in the three Phase 3 links.

The recorded public deployment and checks are in [visual_dashboard/reports](visual_dashboard/reports). The demo video is a separate course deliverable and should be linked in the README when it is available to the instructor.
