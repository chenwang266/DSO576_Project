"""Targeted read-only checks that inform the proposed cleaning rules."""
import json
import numpy as np
import pandas as pd

pd.set_option("display.width", 220)
pd.set_option("display.max_rows", 300)
RAW = {"2026-03": "data/raw/3_15.csv.gz", "2026-06": "data/raw/6_15.csv.gz"}
S = {k: pd.read_csv(v, dtype=str, keep_default_na=False) for k, v in RAW.items()}


def num(s):
    return pd.to_numeric(s.replace("", np.nan), errors="coerce")


for k, df in S.items():
    print(f"\n######## {k} ########")
    blank = lambda c: (df[c].str.strip() == "")
    # price format
    p = df["price"]
    nonblank = p[p != ""]
    print("price values not matching ^\\$[\\d,]+\\.\\d\\d$:", (~nonblank.str.match(r"^\$[\d,]+\.\d\d$")).sum())
    pn = num(p.str.replace(r"[$,]", "", regex=True))
    print("price numeric: min", pn.min(), "max", pn.max(), "| <=0:", (pn <= 0).sum(), "| <10:", (pn < 10).sum(),
          "| >=5000:", (pn >= 5000).sum(), "| >=10000:", (pn >= 10000).sum())
    print("price quantiles:", pn.quantile([.001, .01, .05, .25, .5, .75, .95, .99, .999]).round(2).to_dict())
    q = num(df["price_quote_price_per_night"])
    both = pn.notna() & q.notna()
    print("price vs quote_per_night: both present", both.sum(), "| abs diff >0.01:", ((pn - q).abs() > 0.01)[both].sum(),
          "| price missing but quote present:", (pn.isna() & q.notna()).sum(), "| price present quote missing:", (pn.notna() & q.isna()).sum())
    print("price missing by source:\n", pd.crosstab(df["source"], pn.isna(), margins=True))
    print("price missing by has_availability:\n", pd.crosstab(df["has_availability"], pn.isna()))
    print("price missing by room_type (% missing):\n", pn.isna().groupby(df["room_type"]).mean().round(3))
    print("price missing vs estimated_revenue missing agree:", (pn.isna() == blank("estimated_revenue_l365d")).all())
    print("avail_30 median price-missing vs present:", num(df.availability_30)[pn.isna()].median(), num(df.availability_30)[pn.notna()].median(),
          "| reviews_ltm median:", num(df.number_of_reviews_ltm)[pn.isna()].median(), num(df.number_of_reviews_ltm)[pn.notna()].median())
    # price_quote_raw currency
    cur = df["price_quote_raw"].str.extract(r'"currency": "?([A-Z]+|null)"?')[0]
    print("quote currency:", cur.value_counts(dropna=False).to_dict())
    # nights / sentinels
    for c in ["minimum_nights", "maximum_nights", "maximum_maximum_nights", "minimum_maximum_nights", "maximum_nights_avg_ntm"]:
        v = num(df[c])
        print(f"{c}: ==2147483647: {(v == 2147483647).sum()}  >1125: {(v > 1125).sum()}  null: {v.isna().sum()}")
    mn = num(df.minimum_nights)
    print("minimum_nights dist: 1-29:", ((mn >= 1) & (mn < 30)).sum(), " >=30:", (mn >= 30).sum(), " >365:", (mn > 365).sum())
    print("minimum_nights > maximum_nights:", (mn > num(df.maximum_nights)).sum())
    # reviews logic
    nr, ltm, l30, ly = (num(df[c]) for c in ["number_of_reviews", "number_of_reviews_ltm", "number_of_reviews_l30d", "number_of_reviews_ly"])
    print("ltm>total:", (ltm > nr).sum(), " l30d>ltm:", (l30 > ltm).sum(), " ly>total:", (ly > nr).sum())
    rs = num(df.review_scores_rating)
    print("rating null & reviews==0:", (rs.isna() & (nr == 0)).sum(), " rating null & reviews>0:", (rs.isna() & (nr > 0)).sum(),
          " rating present & reviews==0:", (rs.notna() & (nr == 0)).sum())
    print("rating == 0:", (rs == 0).sum(), " rating<1:", (rs < 1).sum(), "| example reviews for rating==0:", nr[rs == 0].head(5).tolist())
    fr = pd.to_datetime(df.first_review.replace("", np.nan), errors="coerce")
    lr = pd.to_datetime(df.last_review.replace("", np.nan), errors="coerce")
    ls = pd.to_datetime(df.last_scraped, errors="coerce")
    print("first_review>last_review:", (fr > lr).sum(), " last_review>last_scraped:", (lr > ls).sum(),
          " first_review range:", fr.min(), fr.max(), " parse fails:", (fr.isna() & (df.first_review != "")).sum())
    # availability logic
    a30, a60, a90, a365 = (num(df[c]) for c in ["availability_30", "availability_60", "availability_90", "availability_365"])
    print("a30<=a60<=a90<=a365 violations:", ((a30 > a60) | (a60 > a90) | (a90 > a365)).sum())
    occ = num(df.estimated_occupancy_l365d)
    print("occupancy dist: ==0:", (occ == 0).sum(), " ==255:", (occ == 255).sum(), " max:", occ.max(),
          "| occupancy>0 & reviews_ltm==0:", ((occ > 0) & (ltm == 0)).sum())
    rev = num(df.estimated_revenue_l365d)
    implied = (occ * pn)
    print("revenue == occ*price agree (within $1):", ((rev - implied).abs() <= 1)[rev.notna() & pn.notna()].mean().round(4))
    # host logic
    print("calc_host_count != entire+private+shared:", (num(df.calculated_host_listings_count) !=
          num(df.calculated_host_listings_count_entire_homes) + num(df.calculated_host_listings_count_private_rooms) +
          num(df.calculated_host_listings_count_shared_rooms)).sum())
    print("host_listings_count == 0:", (num(df.host_listings_count) == 0).sum())
    # beds/bedrooms/bathrooms
    for c in ["bedrooms", "beds", "bathrooms"]:
        v = num(df[c])
        print(f"{c}: ==0 {(v == 0).sum()}  null {v.isna().sum()}  max {v.max()}")
    bt = df.bathrooms_text
    btn = num(bt.str.extract(r"^([\d.]+)")[0])
    half = bt.str.contains("half", case=False)
    bth = num(df.bathrooms)
    bothb = bth.notna() & btn.notna()
    print("bathrooms vs bathrooms_text numeric: both", bothb.sum(), " disagree", (bth != btn)[bothb].sum(),
          " bathrooms null but text has number:", (bth.isna() & btn.notna()).sum(), " half-bath text:", half.sum())
    print("bathrooms_text values w/o leading number:", bt[btn.isna() & (bt != "")].value_counts().to_dict())
    print("accommodates==0:", (num(df.accommodates) == 0).sum(), " bedrooms>accommodates:", (num(df.bedrooms) > num(df.accommodates)).sum())
    # coordinates
    lat, lon = num(df.latitude), num(df.longitude)
    print("lat range", lat.min(), lat.max(), " lon range", lon.min(), lon.max())
    # text hygiene
    ctrl = r"[\x00-\x1f\x7f\u200b-\u200f\ufeff]"
    for c in ["neighbourhood_cleansed", "property_type", "room_type", "neighbourhood_group_cleansed", "host_name", "name"]:
        s = df[c]
        n_ctrl = s.str.contains(ctrl, regex=True).sum()
        print(f"{c}: lead/trail ws {(s != s.str.strip()).sum()}  double-space {s.str.contains('  ').sum()}  "
              f"control chars {n_ctrl}  "
              f"case-variant groups {s.nunique() - s.str.lower().str.strip().nunique()}")
    # constant/empty/duplicate columns
    const = [c for c in df if df[c].nunique() <= 1]
    print("empty-or-constant columns:", {c: df[c].iloc[0] for c in const})
    print("minimum_minimum_nights identical to minimum_nights:", (df.minimum_minimum_nights == df.minimum_nights).all(),
          "| maximum_maximum_nights identical to maximum_nights:", (df.maximum_maximum_nights == df.maximum_nights).all(),
          "| host_url derivable from host_id:", (df.host_url == "https://www.airbnb.com/users/show/" + df.host_id).all(),
          "| listing_url derivable from id:", (df.listing_url == "https://www.airbnb.com/rooms/" + df.id).all(),
          "| calendar_last_scraped == last_scraped:", (df.calendar_last_scraped == df.last_scraped).mean().round(4))
    # near duplicates
    near = ["host_id", "name", "neighbourhood_cleansed", "property_type", "accommodates", "bedrooms", "price", "latitude", "longitude"]
    print("near-duplicate rows (same", near, ", different id):", df.duplicated(near, keep=False).sum())
    near2 = ["host_id", "name", "neighbourhood_cleansed", "property_type", "accommodates", "price"]
    print("looser near-dup (host,name,nbhd,ptype,accom,price):", df.duplicated(near2, keep=False).sum())
    # id format
    print("id all digits:", df.id.str.fullmatch(r"\d+").all(), " max id length:", df.id.str.len().max(),
          " ids > 2^53 (lose precision as float):", (df.id.astype(float) > 2**53).sum())
    print("license sentinels:", df.license[df.license.str.contains(r"000000|123456|^pending|^n/?a$|^none$|^tbd$", case=False, regex=True)].value_counts().head(10).to_dict())
    # placeholder text in categoricals
    for c in df.columns:
        hits = df[c].str.strip().str.lower().isin(["n/a", "na", "none", "null", "unknown", "tbd", "-", "?"]).sum()
        if hits:
            print(f"placeholder strings in {c}: {hits}")
    print("property_type count (all):")
    print(df.property_type.value_counts().to_string())

# cross-snapshot
a, b = S["2026-03"], S["2026-06"]
ia, ib = set(a.id), set(b.id)
print("\n######## cross-snapshot ########")
print("ids in Mar:", len(ia), " Jun:", len(ib), " both:", len(ia & ib), " Mar only:", len(ia - ib), " Jun only:", len(ib - ia))
print("columns identical:", list(a.columns) == list(b.columns))
m = a.merge(b, on="id", suffixes=("_m", "_j"))
for c in ["neighbourhood_cleansed", "property_type", "room_type", "accommodates", "bedrooms", "price"]:
    print(f"overlapping ids where {c} changed:", (m[c + "_m"] != m[c + "_j"]).sum())
print("neighbourhoods Mar-only:", sorted(set(a.neighbourhood_cleansed) - set(b.neighbourhood_cleansed)),
      " Jun-only:", sorted(set(b.neighbourhood_cleansed) - set(a.neighbourhood_cleansed)))
