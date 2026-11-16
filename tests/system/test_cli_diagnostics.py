import json
import pathlib

import pytest
from agent_memory.adapters import doctor, host_setup, setup
from agent_memory.cli.main import EXIT_ERROR, EXIT_OK, main
from agent_memory.core.store import Store


@pytest.mark.parametrize("command", ["doctor", "setup", "multi-setup"])
@pytest.mark.parametrize("failed", [False, True])
@pytest.mark.parametrize("as_json", [False, True])
def test_diagnostics_preserve_checks_and_readiness(
    command: str,
    failed: bool,
    as_json: bool,
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    root = tmp_path / "store"
    checks = (
        doctor.Check("STORE_INITIALIZED", True, "Store is initialized"),
        doctor.Check(
            "HOST_CONFIG_INVALID" if failed else "HOST_CONFIG_OK",
            not failed,
            "Host settings checked",
        ),
        doctor.Check("WRITE_JOBS_DEGRADED", False, "One dead job", required=False),
    )

    def report(store: Store, host: str, **kwargs: object) -> doctor.Report:
        return doctor.Report(host, store.root, tmp_path / f"{host}.json", checks)

    def installed_report(store: Store, host: str, **kwargs: object) -> dict[str, object]:
        return report(store, host, **kwargs).as_dict()

    def detected_hosts() -> list[str]:
        return ["codex", "claude-code"]

    monkeypatch.setattr(doctor, "run", report)
    monkeypatch.setattr(host_setup, "run", installed_report)
    monkeypatch.setattr(setup, "detect", detected_hosts)
    argv = ["--store", str(root)]
    if as_json:
        argv.append("--json")
    argv.extend(["setup"] if command == "multi-setup" else [command, "--host", "codex"])

    code = main(argv)

    captured = capsys.readouterr()
    assert code == (EXIT_ERROR if failed else EXIT_OK)
    assert captured.err == ""
    if as_json:
        payload = json.loads(captured.out)
        reports = payload["hosts"].values() if command == "multi-setup" else [payload]
        for item in reports:
            assert item["checks"] == [check.as_dict() for check in checks]
    else:
        for check in checks:
            assert check.code in captured.out
            assert check.detail in captured.out
        assert "STORE_INITIALIZED: PASS" in captured.out
        assert f"{checks[1].code}: {'FAIL' if failed else 'PASS'}" in captured.out
        assert "WRITE_JOBS_DEGRADED: WARN" in captured.out
        assert "score=" not in captured.out
        if command == "multi-setup":
            first, second = captured.out.split("claude-code:", 1)
            assert "codex:" in first
            assert all(check.code in first and check.code in second for check in checks)
