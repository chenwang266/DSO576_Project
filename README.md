# DSO576_Project
Short-Term Rental Marketplace Health

## Reproduce the cleaned listings

Install `requirements.txt`, then run from the project root:

```sh
python scripts/clean_listings.py --verify-reproducibility
```

The script reads the two original snapshots in `data/raw/` and creates the four approved files in `data/clean/`. It retains all rows, prints audit counts at every step, and verifies that a second run recreates all four artifacts byte-for-byte. Raw files are never modified. `--raw-dir` and `--output-dir` can override locations; output inside the raw directory is rejected.

See [plan.md](plan.md) for Christos's decisions, [cleaning.ipynb](cleaning.ipynb) for executed validation evidence, and `data/clean/data_dictionary.md` for units, flags, eligibility, and safe CSV loading. IDs must be loaded as strings.
