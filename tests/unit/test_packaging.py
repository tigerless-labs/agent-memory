import pathlib
import tomllib

PACKAGES = pathlib.Path(__file__).resolve().parents[2] / "packages"
MODEL_CLIENT_MARKERS = (
    "openai",
    "anthropic",
    "google-genai",
    "google-generativeai",
    "vertexai",
    "litellm",
    "langchain",
    "llama-index",
    "transformers",
    "sentence-transformers",
    "cohere",
    "mistralai",
    "ollama",
    "huggingface",
)


def _dependencies(package: str) -> list[str]:
    manifest = tomllib.loads((PACKAGES / package / "pyproject.toml").read_text(encoding="utf-8"))
    return manifest["project"]["dependencies"]


def test_core_declares_no_runtime_dependencies_at_all():
    assert _dependencies("core") == []


def test_vector_backend_is_an_explicit_optional_extra():
    manifest = tomllib.loads((PACKAGES / "core" / "pyproject.toml").read_text(encoding="utf-8"))
    assert manifest["project"]["optional-dependencies"]["vector"] == ["fastembed>=0.7,<1"]


def test_no_package_manifest_declares_a_model_client():
    for package in sorted(path.name for path in PACKAGES.iterdir() if path.is_dir()):
        lowered = " ".join(_dependencies(package)).lower()
        assert not [marker for marker in MODEL_CLIENT_MARKERS if marker in lowered], package


def test_core_source_imports_no_model_client():
    core_src = PACKAGES / "core" / "src"
    for path in core_src.rglob("*.py"):
        text = path.read_text(encoding="utf-8").lower()
        for marker in MODEL_CLIENT_MARKERS:
            assert f"import {marker}" not in text, f"{path}: {marker}"


def test_every_package_imports_cleanly_on_an_empty_store():
    import importlib

    for module in (
        "agent_memory.core.config",
        "agent_memory.core.store",
        "agent_memory.core.recall",
        "agent_memory.core.indexer",
        "agent_memory.core.archive",
    ):
        importlib.import_module(module)
