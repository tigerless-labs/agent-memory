from agent_memory.core import schema


def test_existing_store_observes_schema_edit_addition_and_removal(store):
    original = store.schemas.require("fact")
    path = store.schemas.path_for("fact")
    revised = schema.MemorySchema(
        original.type, "Revised fixture description", original.key, original.group, original.mode
    )
    path.write_text(schema.render(revised))
    assert store.schemas.require("fact").description == revised.description
    added = schema.MemorySchema("custom-fixture", "Custom fixture", ("subject",))
    store.schemas.path_for(added.type).write_text(schema.render(added))
    assert store.schemas.require(added.type) == added
    store.schemas.path_for(added.type).unlink()
    assert store.schemas.get(added.type) is None
