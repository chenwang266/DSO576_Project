"""End-to-end checks of app.py with Streamlit's AppTest. Full-data checks skip (not pass) without canonical files."""
import json
import shutil
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from src import presentation as fmt
from src.config import load_settings
from src.data_access import CANONICAL_FILES, load_canonical
from src.filters import OptionalFilters, SegmentSelection
from src.history import compare_snapshots, rank_shortlist
from src.pricing import segment_detail, segment_metrics

APP = str(Path(__file__).resolve().parents[1] / "app.py")
SETTINGS = load_settings()
needs_canonical = pytest.mark.skipif(
    not (SETTINGS.processed_dir / "canonical_listings_clean.csv").exists(), reason="canonical artifacts not generated")


def _run(**state) -> AppTest:
    at = AppTest.from_file(APP, default_timeout=180)
    for key, value in state.items():
        at.session_state[key] = value
    return at.run()


def _metrics(at) -> dict:
    return {m.label: m.value for m in at.metric}


def _config(tmp_path, processed: Path) -> Path:
    raw = json.loads((Path(APP).parent / "config" / "project.json").read_text())
    raw["processed_dir"] = str(processed)
    path = tmp_path / "project.json"
    path.write_text(json.dumps(raw))
    return path


def test_missing_canonical_files_show_setup_guidance(tmp_path, monkeypatch):
    empty = tmp_path / "processed"
    empty.mkdir()
    monkeypatch.setenv("LA_PRICING_CONFIG", str(_config(tmp_path, empty)))
    at = _run()
    assert not at.exception
    assert "Setup needed" in at.error[0].value and "canonical_clean.py" in at.error[0].value


@needs_canonical
def test_default_view_matches_backend():
    at = _run()
    assert not at.exception
    assert at.session_state["snapshot"] == "2026-06-15" and at.session_state["neighbourhood"] == "Hollywood"
    assert at.session_state["room_type"] == "Entire home/apt" and at.session_state["bedroom_segment"] == "1 bedroom"
    data = load_canonical(SETTINGS.processed_dir, SETTINGS.dates)
    detail = segment_detail(data.listings, SegmentSelection("2026-06-15", "Hollywood", "Entire home/apt", "1 bedroom"))
    shown = _metrics(at)
    assert shown["Listings (valid dimensions)"] == fmt.fmt_count(detail["local"]["listing_rows"])
    assert shown["Priced listings"] == fmt.fmt_count(detail["local"]["priced_rows"])
    assert shown["Price coverage"] == fmt.fmt_share(detail["local"]["price_coverage"])
    assert shown["Median price"] == fmt.fmt_usd(detail["local"]["median_price_usd"]) == "$160.87"
    assert shown["Premium vs LA peer"] == fmt.fmt_pct(detail["premium_pct"], signed=True)
    for warning in detail["warnings"]:
        assert warning in [w.value for w in at.warning]


@needs_canonical
def test_comparison_and_shortlist_tabs_match_backend():
    at = _run(view="March–June Comparison")
    assert not at.exception
    shown = _metrics(at)
    assert shown["March median"] == "$162.91" and shown["June median"] == "$160.87"
    assert shown["Change (USD)"] == "-$2.04" and shown["Change (%)"] == "-1.3%"

    at.session_state["view"] = "Review Shortlist"
    at.session_state["direction"] = "Discount"
    at.run()
    assert not at.exception
    data = load_canonical(SETTINGS.processed_dir, SETTINGS.dates)
    comparison = compare_snapshots(segment_metrics(data.listings, OptionalFilters()), SETTINGS.dates)
    expected = rank_shortlist(comparison, "discount")
    assert len(at.dataframe[0].value) == len(expected) == 185
    assert at.dataframe[0].value.Segment.tolist()[:3] == [
        fmt.segment_label(*k) for k in expected[["neighbourhood", "room_type", "bedroom_segment"]].head(3).itertuples(
            index=False)]


@needs_canonical
def test_filters_persist_across_tabs_and_unavailable_selection_is_explained():
    at = _run(stay="Long stay (30+ nights)", min_priced=5)
    at.session_state["view"] = "Review Shortlist"
    at.run()
    assert at.session_state["stay"] == "Long stay (30+ nights)" and at.session_state["min_priced"] == 5
    assert any("Long stay (30+ nights)" in c.value and "minimum 5 priced" in c.value for c in at.caption)

    at = _run(neighbourhood="Atlantis")
    assert not at.exception
    assert any("'Atlantis' is not available" in w.value for w in at.sidebar.warning)


@needs_canonical
def test_reset_restores_defaults():
    at = _run(neighbourhood="Venice", stay="Long stay (30+ nights)", coverage_pct=50)
    at.sidebar.button[0].click().run()
    assert at.session_state["neighbourhood"] == "Hollywood" and at.session_state["stay"] == "All stays"
    assert at.session_state["coverage_pct"] == 80


@needs_canonical
def test_changed_canonical_files_invalidate_cache(tmp_path, monkeypatch):
    processed = tmp_path / "processed"
    processed.mkdir()
    for name in CANONICAL_FILES:
        shutil.copy2(SETTINGS.processed_dir / name, processed / name)
    monkeypatch.setenv("LA_PRICING_CONFIG", str(_config(tmp_path, processed)))
    at = _run()
    assert "46,088 listings" in at.expander[0].markdown[0].value

    report = json.loads((processed / "canonical_cleaning_report.json").read_text())
    report["snapshots"][0]["rows"] = 12345
    (processed / "canonical_cleaning_report.json").write_text(json.dumps(report))
    at = _run()
    assert "12,345 listings" in at.expander[0].markdown[0].value
