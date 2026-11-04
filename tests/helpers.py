"""Synthetic raw-listing builders. All values here are test inputs, never LA market observations."""
from __future__ import annotations

import csv
import gzip
from pathlib import Path

import pandas as pd

from src.cleaning import clean_snapshot, read_raw
from src.config import Snapshot
from src.data_access import fingerprint

MARCH, JUNE = "2026-03-16", "2026-06-15"
DATES = (MARCH, JUNE)
RAW_FIELDS = ["id", "last_scraped", "source", "host_name", "neighbourhood_cleansed", "latitude", "longitude",
              "room_type", "bedrooms", "price", "minimum_nights", "availability_30", "availability_60",
              "availability_90", "availability_365", "number_of_reviews", "number_of_reviews_ltm",
              "number_of_reviews_l30d", "first_review", "last_review", "review_scores_value", "reviews_per_month"]
_counter = iter(range(10**6))


def raw_row(**overrides) -> dict:
    row = {"id": str(1000 + next(_counter)), "last_scraped": "2026-03-17", "source": "city scrape",
           "host_name": "Synthetic Host", "neighbourhood_cleansed": "Hollywood", "latitude": "34.1",
           "longitude": "-118.3", "room_type": "Entire home/apt", "bedrooms": "1", "price": "$100.00",
           "minimum_nights": "2", "availability_30": "10", "availability_60": "20", "availability_90": "30",
           "availability_365": "100", "number_of_reviews": "5", "number_of_reviews_ltm": "2",
           "number_of_reviews_l30d": "0", "first_review": "2024-01-01", "last_review": "2026-02-01",
           "review_scores_value": "4.5", "reviews_per_month": "0.5"}
    row.update(overrides)
    return row


def write_raw(path: Path, rows: list[dict], fields: list[str] | None = None) -> Path:
    fields = fields or RAW_FIELDS
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "wt", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    return path


def clean_rows(tmp_path: Path, rows: list[dict], date: str = MARCH, fields: list[str] | None = None) -> pd.DataFrame:
    path = write_raw(tmp_path / f"raw-{date}-{next(_counter)}.csv", rows, fields)
    label = "March" if date == MARCH else "June"
    return clean_snapshot(read_raw(path), Snapshot(label, date, path), fingerprint(path))


def listings(tmp_path: Path, by_date: dict[str, list[dict]]) -> pd.DataFrame:
    frames = [clean_rows(tmp_path, rows, date) for date, rows in by_date.items()]
    return pd.concat(frames, ignore_index=True)


def priced(prices, **fields) -> list[dict]:
    """One raw row per price; ``None`` means a blank (missing) price."""
    return [raw_row(price="" if p is None else f"${p:,.2f}", **fields) for p in prices]
