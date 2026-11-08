"""Shared filters, applied to listings before any aggregation."""

def optional_filters(frame, stay=None, source=None):
    result = frame
    if stay is not None:
        result = result.loc[result.stay_type.eq(stay)]
    if source is not None:
        result = result.loc[result.source.eq(source)]
    return result

def valid_dimensions(frame):
    return frame.loc[frame.neighbourhood_is_known & frame.room_type_is_known & frame.bedroom_status.eq("valid")]

def local_population(frame, snapshot, neighbourhood, room_type, bedroom_segment, stay=None, source=None):
    data = valid_dimensions(optional_filters(frame, stay, source))
    return data.loc[data.snapshot_date.eq(snapshot) & data.neighbourhood.eq(neighbourhood) & data.room_type.eq(room_type) & data.bedroom_segment.eq(bedroom_segment)]
