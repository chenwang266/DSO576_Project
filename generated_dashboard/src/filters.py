def filter_listings(data, *, snapshot=None, neighbourhood=None, room_type=None,
                    bedrooms=None, stay=None, source=None):
    result = data
    for key, value in [('snapshot_date', snapshot), ('neighbourhood', neighbourhood),
                       ('room_type', room_type), ('bedrooms', bedrooms), ('stay', stay), ('source', source)]:
        if value is not None:
            result = result.loc[result[key].eq(value).fillna(False)]
    return result.copy()
