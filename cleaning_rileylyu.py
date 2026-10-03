"""Module 6 reproducible cleaning and validation. Run with Python 3.13."""

# Notebook validation block 1
import pandas as pd
from pathlib import Path

# Resolve inputs relative to this script, independent of working directory.
data_folder = Path(__file__).resolve().parent / "group data" / "2026-06-15"
if not data_folder.is_dir():
    raise FileNotFoundError("Download the source files into: " + str(data_folder))

def display(value):
    print(value.to_string() if hasattr(value, "to_string") else str(value))

print("Data folder:", data_folder.resolve())
listings = pd.read_csv(data_folder / "listings.csv.gz", low_memory=False)
calendar = pd.read_csv(data_folder / "calendar.csv.gz", low_memory=False)
reviews = pd.read_csv(data_folder / "reviews.csv.gz", low_memory=False)
neighborhoods = pd.read_csv(data_folder / "neighbourhoods.csv", low_memory=False)

tables = {"Listings": listings, "Calendar": calendar,
          "Reviews": reviews, "Neighborhoods": neighborhoods}
for name, table in tables.items():
    print(name, "shape:", table.shape)
    display(table.head())


# Notebook validation block 2
# Inspect all rows, not just head().
for name, table in tables.items():
    print("\n" + name)
    print("Columns:", table.columns.tolist())
    print("Data types:")
    print(table.dtypes.to_string())
    print("Missing values:")
    print(table.isna().sum().to_string())
    print("Exact duplicate rows:", table.duplicated().sum())


# Notebook validation block 3
print("Listings: missing id:", listings["id"].isna().sum())
print("Listings: repeated id:", listings["id"].duplicated().sum())
print("Calendar: missing key values:")
print(calendar[["listing_id", "date"]].isna().sum())
print("Calendar: repeated listing-date:",
      calendar.duplicated(subset=["listing_id", "date"]).sum())

if "id" in reviews.columns:
    print("Reviews: missing review id:", reviews["id"].isna().sum())
    print("Reviews: repeated review id:", reviews["id"].duplicated().sum())
else:
    print("Reviews: no review id column; review key uniqueness cannot be checked.")
    print("Repeated listing-date rows (not proof of duplicate reviews):",
          reviews.duplicated(subset=["listing_id", "date"]).sum())

print("Neighborhoods: missing neighbourhood:",
      neighborhoods["neighbourhood"].isna().sum())
print("Neighborhoods: repeated neighbourhood:",
      neighborhoods["neighbourhood"].duplicated().sum())


# Notebook validation block 5
keys = {"Listings": ["id"], "Calendar": ["listing_id", "date"],
        "Reviews": ["id"], "Neighborhoods": ["neighbourhood"]}
baseline_rows = []
baseline_missing_rows = []
for name, table in tables.items():
    baseline_rows.append({
        "table": name, "rows": len(table), "columns": len(table.columns),
        "missing_key_rows": table[keys[name]].isna().any(axis=1).sum(),
        "duplicate_keys": table.duplicated(subset=keys[name]).sum()
    })
    for column in table.columns:
        baseline_missing_rows.append({
            "table": name, "column": column,
            "missing_count": table[column].isna().sum()
        })
baseline = pd.DataFrame(baseline_rows)
baseline_missing = pd.DataFrame(baseline_missing_rows)
display(baseline)
display(baseline_missing)


# Notebook validation block 6
listings_clean = listings.copy()
calendar_clean = calendar.copy()
reviews_clean = reviews.copy()
neighborhoods_clean = neighborhoods.copy()
clean_tables = {"Listings": listings_clean, "Calendar": calendar_clean,
                "Reviews": reviews_clean, "Neighborhoods": neighborhoods_clean}


# Notebook validation block 7
listings_clean["price_numeric"] = pd.to_numeric(
    listings_clean["price"].astype("string")
    .str.replace("$", "", regex=False)
    .str.replace(",", "", regex=False),
    errors="coerce"
)
price_failures = (listings["price"].notna()
                  & listings_clean["price_numeric"].isna()).sum()
price_evidence = pd.DataFrame([{
    "conversion_failures": price_failures,
    "missing_before": listings["price"].isna().sum(),
    "missing_after": listings_clean["price_numeric"].isna().sum(),
    "min": listings_clean["price_numeric"].min(),
    "max": listings_clean["price_numeric"].max(),
    "zero_or_negative": (listings_clean["price_numeric"] <= 0).sum()
}])
display(price_evidence)
print("Original and converted examples:")
display(listings_clean[["id", "price", "price_numeric"]].head(5))
print("Missing-price examples (retained):")
display(listings_clean.loc[listings_clean["price"].isna(),
                           ["id", "price", "price_numeric"]].head(3))
assert price_failures == 0
assert listings["price"].isna().equals(listings_clean["price_numeric"].isna())


# Notebook validation block 8
date_specs = [
    ("Listings", listings_clean, "last_scraped", "last_scraped_dt"),
    ("Calendar", calendar_clean, "date", "date_dt"),
    ("Reviews", reviews_clean, "date", "date_dt")
]
date_rows = []
for name, table, original, parsed in date_specs:
    table[parsed] = pd.to_datetime(
        table[original], format="%Y-%m-%d", errors="coerce"
    )
    failures = (table[original].notna() & table[parsed].isna()).sum()
    parsed_text = table[parsed].dt.strftime("%Y-%m-%d")
    matching = (table[original].eq(parsed_text)
                | (table[original].isna() & table[parsed].isna()))
    date_rows.append({
        "table": name, "parsing_failures": failures,
        "mismatched_rows": (~matching).sum(),
        "missing_before": table[original].isna().sum(),
        "missing_after": table[parsed].isna().sum(),
        "min_date": table[parsed].min(), "max_date": table[parsed].max()
    })
    assert failures == 0
    assert matching.all()
    del parsed_text, matching
date_evidence = pd.DataFrame(date_rows)
display(date_evidence)
print("Listings last_scraped frequencies:")
display(listings_clean["last_scraped_dt"].value_counts(dropna=False).sort_index())


# Notebook validation block 9
missing_specs = [
    ("Listings", "price"), ("Listings", "bedrooms"),
    ("Listings", "minimum_nights"), ("Listings", "review_scores_value"),
    ("Reviews", "reviewer_name"), ("Reviews", "comments")
]
missing_rows = []
for name, column in missing_specs:
    before = tables[name][column].isna().sum()
    after = clean_tables[name][column].isna().sum()
    missing_rows.append({"table": name, "column": column,
                         "missing_before": before, "missing_after": after})
    assert before == after
missing_evidence = pd.DataFrame(missing_rows)
display(missing_evidence)


# Notebook validation block 10
key_rows = []
for name, table in clean_tables.items():
    key_rows.append({
        "table": name, "key": " + ".join(keys[name]),
        "missing_key_rows": table[keys[name]].isna().any(axis=1).sum(),
        "duplicate_keys": table.duplicated(subset=keys[name]).sum()
    })
key_evidence = pd.DataFrame(key_rows)
display(key_evidence)
assert (key_evidence["missing_key_rows"] == 0).all()
assert (key_evidence["duplicate_keys"] == 0).all()


# Notebook validation block 11
range_columns = ["price_numeric", "bedrooms", "minimum_nights",
                 "review_scores_value", "availability_90", "accommodates"]
range_checks = {
    "price_numeric": listings_clean["price_numeric"] <= 0,
    "bedrooms": listings_clean["bedrooms"] < 0,
    "minimum_nights": listings_clean["minimum_nights"] <= 0,
    "review_scores_value": ((listings_clean["review_scores_value"] < 0)
                            | (listings_clean["review_scores_value"] > 5)),
    "availability_90": ((listings_clean["availability_90"] < 0)
                        | (listings_clean["availability_90"] > 90)),
    "accommodates": listings_clean["accommodates"] <= 0
}
range_rows = []
for column in range_columns:
    range_rows.append({
        "column": column, "min": listings_clean[column].min(),
        "max": listings_clean[column].max(),
        "outside_meaningful_bounds": range_checks[column].sum()
    })
    if range_checks[column].any():
        print("Investigate:", column)
        display(listings_clean.loc[range_checks[column], ["id", column]].head(5))
range_evidence = pd.DataFrame(range_rows)
display(range_evidence)


# Notebook validation block 12
calendar_unmatched = ~calendar["listing_id"].isin(listings["id"])
unmatched_calendar_ids = calendar.loc[
    calendar_unmatched, "listing_id"
].drop_duplicates()
listings_without_calendar = listings.loc[
    ~listings["id"].isin(calendar["listing_id"]), "id"
]
coverage_evidence = pd.DataFrame([{
    "distinct_unmatched_calendar_ids": len(unmatched_calendar_ids),
    "calendar_rows_for_unmatched_ids": calendar_unmatched.sum(),
    "listings_without_calendar": len(listings_without_calendar)
}])
display(coverage_evidence)
print("Sample Calendar IDs not in Listings:")
display(unmatched_calendar_ids.head(10))
print("Sample Listings IDs not in Calendar:")
display(listings_without_calendar.head(10))


# Notebook validation block 13
approved_columns = {
    "Listings": ["price_numeric", "last_scraped_dt"],
    "Calendar": ["date_dt"], "Reviews": ["date_dt"], "Neighborhoods": []
}
reconciliation_rows = []
for name, raw in tables.items():
    cleaned = clean_tables[name]
    added = [column for column in cleaned.columns if column not in raw.columns]
    originals_unchanged = cleaned[raw.columns].equals(raw)
    reconciliation_rows.append({
        "table": name, "raw_rows": len(raw), "clean_rows": len(cleaned),
        "row_change": len(cleaned) - len(raw),
        "original_columns_unchanged": originals_unchanged,
        "added_columns": ", ".join(added),
        "only_approved_columns_added": added == approved_columns[name]
    })
    assert len(cleaned) == len(raw)
    assert originals_unchanged
    assert added == approved_columns[name]
reconciliation = pd.DataFrame(reconciliation_rows)
display(reconciliation)


# Notebook validation block 20
decision_log = pd.DataFrame([
    {"rule": "Price numeric conversion", "reason": "Currency text cannot support numerical price comparisons", "check": "0 failures; missing mask preserved; original price unchanged", "type": "Type conversion", "status": "Implemented"},
    {"rule": "Explicit date parsing", "reason": "Support date windows while retaining actual scrape dates", "check": "0 failures and 0 round-trip mismatches", "type": "Type conversion", "status": "Implemented"},
    {"rule": "Retain missing values", "reason": "Unknown bedroom/price/score is not zero; no justified imputation", "check": "Missing counts before and after identical", "type": "Missing-data decision", "status": "Implemented: keep"},
    {"rule": "Retain unique source records", "reason": "All four table keys are unique", "check": "Exact duplicates and repeated keys checked separately", "type": "Duplicate decision", "status": "Implemented: keep"},
    {"rule": "Eligibility indicators only", "reason": "State metric denominators and unknown bedroom coverage without deleting records", "check": "Flags equal the stated nonmissing conditions on every row", "type": "Analysis scope", "status": "Apply below"},
    {"rule": "Monthly quote investigation flag", "reason": "Extreme low prices include ambiguous Average monthly price quotes", "check": "Flag matches the literal quote text; raw price remains unchanged", "type": "Limitation flag", "status": "Apply below; interpretation unresolved"},
    {"rule": "Retain extremes and zero scores", "reason": "Some extremes are plausible; correction lacks source evidence", "check": "Raw columns identical; examples retained", "type": "Validation / limitation", "status": "Keep, investigate"},
    {"rule": "Keep unmatched Calendar and extended windows", "reason": "181 unmatched IDs and 14 extended windows are not proven errors", "check": "No row-count change; coverage/window evidence retained", "type": "Limitation", "status": "Keep"},
    {"rule": "Do not repair host_profile_id from float", "reason": "Possible integer precision loss needs original text verification", "check": "Not used as a merge or analytical key", "type": "Limitation", "status": "Unresolved"}
])
display(decision_log)
text_rows = []
for name, column in [
    ("Listings", "neighbourhood_cleansed"), ("Listings", "room_type"),
    ("Listings", "property_type"), ("Neighborhoods", "neighbourhood")
]:
    values = clean_tables[name][column].astype("string")
    changed = values.notna() & values.ne(values.str.strip())
    blank = values.notna() & values.str.strip().eq("")
    text_rows.append({"table": name, "column": column,
                      "surrounding_whitespace": changed.sum(),
                      "blank_nonmissing": blank.sum()})
    if changed.any():
        print("Investigate whitespace; original values retained:", name, column)
        display(clean_tables[name].loc[changed, [column]].head())
text_evidence = pd.DataFrame(text_rows)
display(text_evidence)
print("Categorical examples, unchanged:")
display(listings_clean[["neighbourhood_cleansed", "room_type", "property_type"]].head())


# Notebook validation block 21
listings_clean["has_observed_price"] = listings_clean["price_numeric"].notna()
listings_clean["has_bedroom_segment"] = (
    listings_clean["neighbourhood_cleansed"].notna()
    & listings_clean["room_type"].notna()
    & listings_clean["bedrooms"].notna()
)
listings_clean["eligible_price_bedroom_segment"] = (
    listings_clean["has_observed_price"] & listings_clean["has_bedroom_segment"]
)
listings_clean["monthly_quote_review_flag"] = (
    listings_clean["price_quote_raw"].astype("string")
    .str.contains("Average monthly price", regex=False, na=False)
)
approved_columns["Listings"] = [
    "price_numeric", "last_scraped_dt", "has_observed_price",
    "has_bedroom_segment", "eligible_price_bedroom_segment", "monthly_quote_review_flag"
]
assert listings_clean["has_observed_price"].equals(listings_clean["price_numeric"].notna())
assert listings_clean["has_bedroom_segment"].equals(
    listings_clean[["neighbourhood_cleansed", "room_type", "bedrooms"]].notna().all(axis=1))
assert listings_clean["eligible_price_bedroom_segment"].equals(
    listings_clean["has_observed_price"] & listings_clean["has_bedroom_segment"])
denominator_evidence = pd.DataFrame([
    {"metric": "Observed price mean/median", "valid_records": listings_clean["price_numeric"].count(),
     "missing_records": listings_clean["price_numeric"].isna().sum(),
     "value": listings_clean["price_numeric"].median()},
    {"metric": "Value-score mean including retained zero", "valid_records": listings_clean["review_scores_value"].count(),
     "missing_records": listings_clean["review_scores_value"].isna().sum(),
     "value": listings_clean["review_scores_value"].mean()},
    {"metric": "Price + bedroom segment complete records", "valid_records": listings_clean["eligible_price_bedroom_segment"].sum(),
     "missing_records": (~listings_clean["eligible_price_bedroom_segment"]).sum(), "value": None}
])
display(denominator_evidence)
print("Monthly-quote review flags:", listings_clean["monthly_quote_review_flag"].sum())
print("Means and medians skip missing values; missing scores are not zero.")
print("No definitive segment benchmark is computed until price quote comparability is resolved.")


# Notebook validation block 22
record_specs = [
    (2708, "price_numeric", 67.22, "Currency conversion"),
    (2436587, "price_numeric", 72.30, "Currency conversion; minimum_nights stays missing"),
    (6764023, "review_scores_value", 0.0, "Zero score retained"),
    (25870842, "price_numeric", 20583.33, "Extreme price retained"),
    (607365253103904668, "price_numeric", 3.77, "Low price retained; monthly quote flagged")
]
record_rows = []
for listing_id, field, expected, reason in record_specs:
    raw_record = listings.loc[listings["id"].eq(listing_id)].iloc[0]
    actual_record = listings_clean.loc[listings_clean["id"].eq(listing_id)].iloc[0]
    original = raw_record["price"] if field == "price_numeric" else raw_record[field]
    actual = actual_record[field]
    matched = abs(float(actual) - expected) < 0.000001
    extra_check = True
    if listing_id in [2708, 607365253103904668]:
        extra_check = pd.isna(actual_record["bedrooms"]) and not actual_record["eligible_price_bedroom_segment"]
    if listing_id == 2436587:
        extra_check = pd.isna(actual_record["minimum_nights"])
    if listing_id == 607365253103904668:
        extra_check = extra_check and bool(actual_record["monthly_quote_review_flag"])
    record_rows.append({"id": listing_id, "field": field, "original": original,
                        "expected": expected, "actual": actual, "reason": reason,
                        "matches": matched and extra_check})
record_checks = pd.DataFrame(record_rows)
display(record_checks)
assert record_checks["matches"].all()
print("Codex suggestion checked: price parsing has zero failures and an unchanged missing mask on the full dataset; fixed expected currency examples match.")


# Notebook validation block 23
final_rows = []
for name, raw in tables.items():
    cleaned = clean_tables[name]
    originals_unchanged = cleaned[raw.columns].equals(raw)
    added = [c for c in cleaned.columns if c not in raw.columns]
    assert len(cleaned) == len(raw)
    assert originals_unchanged
    assert added == approved_columns[name]
    final_rows.append({"table": name, "starting_rows": len(raw), "final_rows": len(cleaned),
                       "row_difference": len(cleaned) - len(raw),
                       "original_columns_unchanged": originals_unchanged,
                       "added_columns": ", ".join(added)})
final_reconciliation = pd.DataFrame(final_rows)
display(final_reconciliation)
sample_ids = [2708, 2436587, 6764023, 25870842, 607365253103904668]
for condition in [
    listings_clean["price_numeric"].isna(), listings_clean["bedrooms"].isna(),
    listings_clean["minimum_nights"].isna(), listings_clean["review_scores_value"].isna(),
    listings_clean["bedrooms"].eq(0), listings_clean["bedrooms"].ge(10),
    listings_clean["review_scores_value"].eq(0), listings_clean["minimum_nights"].ge(365)
]:
    for listing_id in listings_clean.loc[condition, "id"].head(3):
        if listing_id not in sample_ids:
            sample_ids.append(listing_id)
for listing_id in listings_clean["id"]:
    if len(sample_ids) >= 50:
        break
    if listing_id not in sample_ids:
        sample_ids.append(listing_id)
sample_columns = ["id", "neighbourhood_cleansed", "room_type", "property_type",
                  "bedrooms", "accommodates", "price", "price_numeric",
                  "minimum_nights", "review_scores_value", "number_of_reviews_ltm",
                  "availability_90", "last_scraped", "last_scraped_dt",
                  "has_observed_price", "has_bedroom_segment",
                  "eligible_price_bedroom_segment", "monthly_quote_review_flag"]
cleaned_sample = listings_clean.set_index("id").loc[sample_ids].reset_index()[sample_columns]
assert len(cleaned_sample) == 50
output_folder = data_folder.parent.parent / "cleaning_outputs"
output_folder.mkdir(exist_ok=True)
evidence_outputs = {
    "baseline": baseline, "baseline_missing": baseline_missing,
    "decision_log": decision_log, "price_evidence": price_evidence,
    "date_evidence": date_evidence, "missing_evidence": missing_evidence,
    "key_evidence": key_evidence, "range_evidence": range_evidence,
    "coverage_evidence": coverage_evidence, "text_evidence": text_evidence,
    "denominator_evidence": denominator_evidence, "record_checks": record_checks,
    "final_reconciliation": final_reconciliation, "cleaned_listings_sample_50": cleaned_sample
}
for name, evidence in evidence_outputs.items():
    evidence.to_csv(output_folder / (name + ".csv"), index=False)
print("Evidence output folder:", output_folder.resolve())
print("Exactly 50 diagnostic sample rows exported; no full tables exported.")


