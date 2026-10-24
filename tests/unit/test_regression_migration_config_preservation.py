from agent_memory.core.config import Config
from agent_memory.core.migrate import migrate


def test_legacy_upgrade_keeps_supported_storage_customization(tmp_path):
    root = tmp_path / "legacy"
    root.mkdir()
    (root / "config.toml").write_text(
        "[storage]\n"
        'domains = ["user", "project"]\n'
        "abstract_max_chars = 99\n"
        'default_project = "custom-project"\n'
        "lock_timeout_seconds = 9.0\n"
    )
    migrate(root)
    config = Config.load(root)
    assert config.storage.abstract_max_chars == 99
    assert config.storage.default_project == "custom-project"
    assert config.storage.lock_timeout_seconds == 9.0
