"""Profile the raw Inside Airbnb LA snapshots. Read-only: changes nothing."""
import sys
import pandas as pd

pd.set_option("display.width", 250)
pd.set_option("display.max_rows", 500)
pd.set_option("display.max_colwidth", 70)

RAW = {"2026-03": "data/raw/3_15.csv.gz", "2026-06": "data/raw/6_15.csv.gz"}


def profile(name, path):
    raw = pd.read_csv(path, dtype=str, keep_default_na=False)  # everything as text, nothing coerced
    inferred = pd.read_csv(path, low_memory=False)              # pandas' own inference, for dtypes/ranges
    print(f"\n{'=' * 30} {name}  ({path}) {'=' * 30}")
    print("shape:", raw.shape)
    print("exact duplicate rows:", raw.duplicated().sum(), "| duplicated id:", raw["id"].duplicated().sum())

    empty = raw.apply(lambda s: (s.str.strip() == "").sum())
    summary = pd.DataFrame({
        "inferred_dtype": inferred.dtypes.astype(str),
        "null_or_blank": empty,
        "null_pct": (empty / len(raw) * 100).round(2),
        "n_unique": raw.nunique(),
    })
    print("\n--- dtypes / nulls / uniques ---")
    print(summary.to_string())

    print("\n--- numeric ranges (inferred numeric columns) ---")
    num = inferred.select_dtypes("number")
    print(num.describe(percentiles=[.01, .25, .5, .75, .99]).T.to_string())

    print("\n--- top values of categorical / text columns (<=60 unique shown fully-ish) ---")
    for c in raw.columns:
        if c in num.columns:
            continue
        vc = raw[c].value_counts()
        print(f"\n[{c}] unique={raw[c].nunique()}")
        print(vc.head(8).to_string())


if __name__ == "__main__":
    for k, v in RAW.items():
        profile(k, v)
