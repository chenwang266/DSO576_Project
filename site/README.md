# Public Los Angeles Pricing Review dashboard

Live: [Los Angeles Pricing Review](https://la-pricing-review-visual.belovedferret.chatgpt.site/)

This buildless HTML/CSS/JavaScript dashboard runs from `dist/index.html`. From the repository root, run `python3 -m http.server 8502 --directory site/dist`, then open `http://localhost:8502/`. The twelve `dist/assets/evidence-*.json` files contain aggregate segment evidence only. The browser loads the bundle for the selected stay/source filters, applies evidence thresholds, and renders Plotly charts. It does not call Python or store visitor inputs.

See [deployment instructions](../DEPLOYMENT.md) for the exact Sites settings, and [analysis instructions](../visual_dashboard/README.md) for regeneration and validation.
