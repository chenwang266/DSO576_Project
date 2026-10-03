# Short-Term Rental Marketplace Health: Pricing Guidance Dashboard

Student: Riley Lyu  
Source: Inside Airbnb, Los Angeles - https://insideairbnb.com/get-the-data/  
Snapshot: June 15, 2026  
Branch: cleaning-rileylyu  
Branch URL: https://github.com/chenwang266/DSO576_Project/tree/cleaning-rileylyu  
Submitted commit ID: 

Our project has three Los Angeles snapshots. For this cleaning assignment, I used the most recent snapshot, June 15, 2026, as a first example to inspect and clean the data. The same cleaning process can later be applied to the other snapshots.

## Data and decisions

Place the original files in group data/2026-06-15/:

| File | One row / key |
|---|---|
| listings.csv.gz | Listing / id |
| calendar.csv.gz | Listing-date / listing_id + date |
| reviews.csv.gz | Review / review id |
| neighbourhoods.csv | Neighborhood / neighbourhood |

Raw files stay unchanged. Copies receive numeric price and datetime columns. Missing and unusual values are retained. No merge is performed. Monthly quote meanings, unusual bedrooms, zero scores, host profile ID precision and Calendar coverage/windows remain limitations.

## Run

Use Python 3.13. From project/ in PowerShell:

    py -3.13 -m venv .venv
    .\.venv\Scripts\Activate.ps1
    python -m pip install -r requirements.txt
    python cleaning_rileylyu.py

Dependencies: pandas and ipykernel. For the notebook in VS Code, select project/.venv, Restart Kernel and Run All from project/. Both versions print checks and create only:

    cleaning_outputs/cleaned_listings_sample_50.csv

The sample includes five checked records, missing/zero/extreme cases, then ordinary rows to reach 50 unique listings. It is diagnostic, not statistically representative. Full downloaded datasets and old evidence exports are not part of this submission.

Commit the notebook, script, README, requirements.txt, .gitignore and sample. Module_6_Final_Report_Simple.md is the separate individual PDF draft. Update the commit placeholder after your final commit and give the instructor repository access.
