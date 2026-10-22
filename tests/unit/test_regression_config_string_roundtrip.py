from agent_memory.core.config import Config


def test_config_strings_and_field_keys_roundtrip(tmp_path):
    config = Config.default()
    config.executor.command = 'C:\\tools\\runner --message "hello"\nnext\tline'
    config.storage.field_sources["custom field"] = "menu"
    config.save(tmp_path)
    restored = Config.load(tmp_path)
    assert restored.executor.command == config.executor.command
    assert restored.storage.field_sources == config.storage.field_sources
