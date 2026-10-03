# # DSO 576 Module 6 - Riley Lyu
# ## 1. Load Data
import pandas as pd

data_folder = "group data/2026-06-15/"
listings = pd.read_csv(data_folder + "listings.csv.gz", low_memory=False)
calendar = pd.read_csv(data_folder + "calendar.csv.gz", low_memory=False)
reviews = pd.read_csv(data_folder + "reviews.csv.gz", low_memory=False)
neighborhoods = pd.read_csv(data_folder + "neighbourhoods.csv", low_memory=False)


# ## 2. Inspect Data
names = ["Listings", "Calendar", "Reviews", "Neighborhoods"]
raw_tables = [listings, calendar, reviews, neighborhoods]
for name, table in [("Listings", listings), ("Calendar", calendar),
                    ("Reviews", reviews), ("Neighborhoods", neighborhoods)]:
    print(name, table.shape)
    print(table.columns)
    print(table.dtypes)
    print(table.isna().sum())
project_fields = ["id", "price", "neighbourhood_cleansed", "room_type", "bedrooms",
                  "property_type", "accommodates", "minimum_nights", "availability_90",
                  "number_of_reviews_ltm", "review_scores_value", "scrape_id", "last_scraped"]
for column in project_fields:
    assert column in listings.columns
print(listings[project_fields].head())


# ### Cleaning decisions before applying them
# ## 3. Clean Price and Dates
listings_clean = listings.copy()
calendar_clean = calendar.copy()
reviews_clean = reviews.copy()
neighborhoods_clean = neighborhoods.copy()
clean_tables = [listings_clean, calendar_clean, reviews_clean, neighborhoods_clean]

listings_clean["price_numeric"] = pd.to_numeric(
    listings_clean["price"].str.replace("$", "", regex=False)
    .str.replace(",", "", regex=False), errors="coerce")
failures = (listings["price"].notna() & listings_clean["price_numeric"].isna()).sum()
print("Price failures:", failures)
print("Missing before/after:", listings["price"].isna().sum(),
      listings_clean["price_numeric"].isna().sum())
print(listings_clean[["id", "price", "price_numeric"]].head())
assert failures == 0
assert (listings["price"].isna() != listings_clean["price_numeric"].isna()).sum() == 0


for name, table, original, parsed in [
    ("Listings", listings_clean, "last_scraped", "last_scraped_dt"),
    ("Calendar", calendar_clean, "date", "date_dt"),
    ("Reviews", reviews_clean, "date", "date_dt")
]:
    table[parsed] = pd.to_datetime(table[original], format="%Y-%m-%d", errors="coerce")
    failures = (table[original].notna() & table[parsed].isna()).sum()
    print(name, "date failures:", failures)
    print("Range:", table[parsed].min(), table[parsed].max())
    assert failures == 0
print(listings_clean[["last_scraped", "last_scraped_dt"]].head())


# ## 4. Check Text
for column in ["neighbourhood_cleansed", "room_type", "property_type"]:
    print(column, "whitespace:", (listings[column] != listings[column].str.strip()).sum())
    print(pd.DataFrame({"before": listings[column].head(),
                        "after": listings_clean[column].head()}))
print("Reference whitespace:", (neighborhoods["neighbourhood"] != neighborhoods["neighbourhood"].str.strip()).sum())


# ## 5. Check Duplicates
keys = [["id"], ["listing_id", "date"], ["id"], ["neighbourhood"]]
for name, table, key in [
    ("Listings", listings_clean, ["id"]),
    ("Calendar", calendar_clean, ["listing_id", "date"]),
    ("Reviews", reviews_clean, ["id"]),
    ("Neighborhoods", neighborhoods_clean, ["neighbourhood"])
]:
    print(name, "exact duplicates:", table.duplicated().sum())
    print("Missing keys:", len(table.loc[table[key[0]].isna()]))
    print("Duplicate keys:", table.duplicated(key).sum())
    assert len(table.loc[table[key[0]].isna()]) == 0
    assert table.duplicated(key).sum() == 0

assert calendar_clean["date"].isna().sum() == 0


# ## 6. Check Missing Values
for name, raw, clean in [
    ("Listings", listings, listings_clean), ("Calendar", calendar, calendar_clean),
    ("Reviews", reviews, reviews_clean), ("Neighborhoods", neighborhoods, neighborhoods_clean)
]:
    print(name)
    print(pd.DataFrame({"before": raw.isna().sum(),
                        "after": clean[raw.columns].isna().sum()}))


# ## 7. Check Suspicious Values
for column in ["price_numeric", "bedrooms", "minimum_nights",
               "review_scores_value", "availability_90", "accommodates"]:
    print(column, "min:", listings_clean[column].min(), "max:", listings_clean[column].max())
print("Nonpositive price:", (listings_clean["price_numeric"] <= 0).sum())
print("Negative bedrooms:", (listings_clean["bedrooms"] < 0).sum())
print("Nonpositive minimum stay:", (listings_clean["minimum_nights"] <= 0).sum())
print("Scores outside 0-5:", ((listings_clean["review_scores_value"] < 0)
                             | (listings_clean["review_scores_value"] > 5)).sum())
print("Availability outside 0-90:", ((listings_clean["availability_90"] < 0)
                                   | (listings_clean["availability_90"] > 90)).sum())
print("Nonpositive capacity:", (listings_clean["accommodates"] <= 0).sum())
print(listings_clean.loc[(listings_clean["review_scores_value"] == 0),
                        ["id", "review_scores_value", "number_of_reviews"]])


# ### Calculation counts
print("Valid prices:", listings_clean["price_numeric"].notna().sum())
print("Price median:", listings_clean["price_numeric"].median())
print("Valid scores:", listings_clean["review_scores_value"].notna().sum())
print("Score mean, retaining zero:", listings_clean["review_scores_value"].mean())


# ## 8. Check Row Counts
row_counts = pd.DataFrame({
    "table": names,
    "starting_rows": [len(listings), len(calendar), len(reviews), len(neighborhoods)],
    "final_rows": [len(listings_clean), len(calendar_clean), len(reviews_clean), len(neighborhoods_clean)]
})
row_counts["change"] = row_counts["final_rows"] - row_counts["starting_rows"]
print(row_counts)
assert (row_counts["change"] != 0).sum() == 0
print("Cleaning uses copies and only adds new columns; no source columns are overwritten.")


# ## 9. Five Record Checks
# Expectations were stated above before checking these five records.
original1 = listings.loc[listings["id"] == 2708, "price"].iloc[0]
actual1 = listings_clean.loc[listings_clean["id"] == 2708, "price_numeric"].iloc[0]

original2 = listings.loc[listings["id"] == 2436587, "minimum_nights"]
actual2 = listings_clean.loc[listings_clean["id"] == 2436587, "minimum_nights"]
missing_match = (original2.isna().sum() == 1) and (actual2.isna().sum() == 1)
print("Missing minimum_nights before and after:")
print(original2)
print(actual2)

original3 = listings.loc[listings["id"] == 6764023, "review_scores_value"].iloc[0]
actual3 = listings_clean.loc[listings_clean["id"] == 6764023, "review_scores_value"].iloc[0]

original4 = listings.loc[listings["id"] == 25870842, "price"].iloc[0]
actual4 = listings_clean.loc[listings_clean["id"] == 25870842, "price_numeric"].iloc[0]

original5 = listings.loc[listings["id"] == 607365253103904668, "price"].iloc[0]
actual5 = listings_clean.loc[listings_clean["id"] == 607365253103904668, "price_numeric"].iloc[0]

record_checks = pd.DataFrame({
    "ID": [2708, 2436587, 6764023, 25870842, 607365253103904668],
    "Field": ["price_numeric", "minimum_nights", "review_scores_value", "price_numeric", "price_numeric"],
    "Original": [original1, original2.iloc[0], original3, original4, original5],
    "Expected": [67.22, "Missing", 0.0, 20583.33, 3.77],
    "Actual": [actual1, actual2.iloc[0], actual3, actual4, actual5],
    "Match": [actual1 == 67.22, missing_match, actual3 == 0.0,
              actual4 == 20583.33, actual5 == 3.77]
})
print(record_checks)
assert record_checks["Match"].sum() == 5
print("NaN in the table means Missing.")
print("Codex price suggestion checked: examples matched; full-column failures 0; missing count unchanged.")


# ## 10. Create 50-Row Sample
check_ids = [2708, 2436587, 6764023, 25870842, 607365253103904668]
missing_cases = listings_clean.loc[
    listings_clean["price_numeric"].isna()
    | listings_clean["bedrooms"].isna()
    | listings_clean["minimum_nights"].isna()
    | listings_clean["review_scores_value"].isna()
].head(6)
unusual_cases = listings_clean.loc[
    (listings_clean["bedrooms"] == 0)
    | (listings_clean["bedrooms"] >= 10)
    | (listings_clean["minimum_nights"] >= 365)
].head(6)
sample = pd.concat([
    listings_clean.loc[listings_clean["id"].isin(check_ids)],
    missing_cases,
    unusual_cases,
    listings_clean.head(50)
])
# Remove repeated selections from this sample only.
sample = sample.loc[~sample["id"].duplicated()].head(50)
sample = sample[project_fields + ["price_numeric", "last_scraped_dt"]]
assert len(sample) == 50
assert sample["id"].duplicated().sum() == 0
assert sample["id"].isin(check_ids).sum() == 5
sample.to_csv("cleaning_outputs/cleaned_listings_sample_50.csv", index=False)
print("Saved 50 sample rows; no full dataset exported.")


# ## 11. Reproducibility Check
assert (row_counts["change"] != 0).sum() == 0
assert record_checks["Match"].sum() == 5
print("All checks passed. Only the sample CSV is exported.")


