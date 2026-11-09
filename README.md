# DSO576_Project
Short-Term Rental Marketplace Health

## Phase 3: Los Angeles Airbnb Pricing Review

**[Open the public dashboard](https://la-pricing-review-visual.belovedferret.chatgpt.site/)** · [Deployment and verification](DEPLOYMENT.md)

This tool helps an Airbnb marketplace strategy manager decide which Los Angeles neighborhood × room type × bedroom groups deserve human pricing review. Compare advertised prices to same-date LA peers, check whether premiums or discounts repeat across March and June, review evidence coverage and composition, and export supporting evidence.

The public Site uses aggregate evidence from two Inside Airbnb Los Angeles snapshots (March 16 and June 15, 2026). It supports exploratory pricing review. It does not estimate optimal prices, bookings, occupancy, revenue, demand, or causal effects. Changes in listing composition and missing bedrooms can affect cross-snapshot comparisons.

**Run the deployed frontend locally:** from this repository's root, run `python3 -m http.server 8502 --directory site/dist` and open `http://localhost:8502/`. The source and required aggregate data are in `site/`; no Python analysis server is needed for this view. See [visual analysis and local Streamlit instructions](visual_dashboard/README.md) for the canonical pipeline, tests, and data regeneration. The separate [root Streamlit setup](STREAMLIT_SETUP.md) remains available.

**Demo video:** https://drive.google.com/file/d/1_y--C8Kjcek-AQx0iDLNzHG5sSXjwh9I/view?usp=sharing
