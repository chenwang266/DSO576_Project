"""Population selection from canonical listings. Pure functions; inputs are never mutated."""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

PEER_DEFINITION = (
    "LA peer = same snapshot, room type, bedroom segment and stay/source filters across all LA neighbourhoods, "
    "including the selected neighbourhood. Listings are pooled; neighbourhood medians are never averaged."
)


@dataclass(frozen=True)
class OptionalFilters:
    """Stay/source refinements applied identically to local and peer populations and to both snapshots."""
    stay: str | None = None
    source: str | None = None

    def describe(self) -> dict[str, str]:
        return {"stay_filter": self.stay or "All stays", "source_filter": self.source or "All sources"}


@dataclass(frozen=True)
class SegmentSelection:
    snapshot: str
    neighbourhood: str
    room_type: str
    bedroom_segment: str


def _match(data: pd.DataFrame, column: str, value) -> pd.Series:
    return data[column].eq(value).fillna(False).astype(bool)


def apply_optional_filters(data: pd.DataFrame, filters: OptionalFilters = OptionalFilters()) -> pd.DataFrame:
    mask = pd.Series(True, index=data.index)
    if filters.stay is not None:
        mask &= _match(data, "stay_category", filters.stay)
    if filters.source is not None:
        mask &= _match(data, "source_category", filters.source)
    return data.loc[mask]


def peer_population(data: pd.DataFrame, snapshot: str, room_type: str, bedroom_segment: str,
                    filters: OptionalFilters = OptionalFilters()) -> pd.DataFrame:
    """All LA listings in the snapshot with the same room type, bedroom segment and filters (local included)."""
    rows = apply_optional_filters(data, filters)
    mask = (_match(rows, "snapshot_date", snapshot) & _match(rows, "room_type", room_type)
            & _match(rows, "bedroom_segment", bedroom_segment) & rows.has_valid_dimensions.fillna(False).astype(bool))
    return rows.loc[mask]


def local_population(data: pd.DataFrame, selection: SegmentSelection,
                     filters: OptionalFilters = OptionalFilters()) -> pd.DataFrame:
    peers = peer_population(data, selection.snapshot, selection.room_type, selection.bedroom_segment, filters)
    return peers.loc[_match(peers, "neighbourhood", selection.neighbourhood)]


def neighbourhood_room_rows(data: pd.DataFrame, snapshot: str, neighbourhood: str | None, room_type: str,
                            filters: OptionalFilters = OptionalFilters()) -> pd.DataFrame:
    """Listings sharing snapshot/room (and neighbourhood if given) regardless of bedroom validity.

    Used for bedroom-completeness context: how many otherwise-matching listings were excluded as Unknown bedrooms.
    """
    rows = apply_optional_filters(data, filters)
    mask = _match(rows, "snapshot_date", snapshot) & _match(rows, "room_type", room_type)
    if neighbourhood is not None:
        mask &= _match(rows, "neighbourhood", neighbourhood)
    return rows.loc[mask]


def available_options(data: pd.DataFrame) -> dict[str, list]:
    """Selectable categories drawn from validated comparable listings. Studio and Unknown are never merged."""
    comparable = data.loc[data.has_valid_dimensions.fillna(False).astype(bool)]
    bedroom = (comparable[["bedroom_segment", "bedroom_order"]].drop_duplicates()
               .sort_values("bedroom_order").bedroom_segment.tolist())
    return {
        "snapshots": sorted(data.snapshot_date.dropna().unique().tolist()),
        "neighbourhoods": sorted(comparable.neighbourhood.unique().tolist()),
        "room_types": sorted(comparable.room_type.unique().tolist()),
        "bedroom_segments": bedroom,
        "stays": sorted(data.stay_category.dropna().unique().tolist()),
        "sources": sorted(data.source_category.dropna().unique().tolist()),
    }
