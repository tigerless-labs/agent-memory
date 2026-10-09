import pytest
from agent_memory.core import schema
from agent_memory.core.errors import ValidationError


@pytest.mark.parametrize("type_name", ["archive", "schemas", "dream-reports"])
def test_schema_type_cannot_occupy_reserved_storage(store, type_name):
    custom = schema.MemorySchema(type_name, "Useful custom type", ("subject",))
    with pytest.raises(ValidationError):
        schema.validate(custom, store.config)
