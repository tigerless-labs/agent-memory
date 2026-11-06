from agent_memory.core import reconcile, sessions


def test_default_fact_date_uses_latest_instant_not_lexical_zone_order(store):
    pointer = store.archive.append_session(
        "zoned",
        [
            {"text": "Earlier evidence", "at": "2026-01-05T10:00:00+02:00"},
            {"text": "Later evidence", "at": "2026-01-05T09:00:00Z"},
        ],
    )
    messages = sessions.resolve(store.layout, pointer)
    sheet = reconcile.build(store, "zoned", messages)
    spec = reconcile.to_record_spec(
        {"op": "new", "type": "fact", "fields": {"subject": "zone"}, "abstract": "Time fixture"},
        sheet,
    )
    assert spec["valid_from"] == "2026-01-05T09:00:00Z"
