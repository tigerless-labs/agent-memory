"""One setup pipeline; host and provider modules supply only their differences."""

from __future__ import annotations

import pathlib

from agent_memory.core.errors import FieldError, ValidationError
from agent_memory.core.store import Store

from . import doctor, moments, muse_sdk, openrouter, setup


def run(
    store: Store,
    host: str,
    *,
    settings_path: pathlib.Path | None = None,
    provider: str | None = None,
    model: str | None = None,
    mcp: bool = False,
    live: bool = True,
    sdk: bool = False,
) -> dict[str, object]:
    """Detect -> validate -> Store -> merge -> hooks/skill/MCP -> provider -> preflight."""
    host = setup.canonical_host(host)
    if sdk:
        if host != moments.HOST_MUSE_CODE or provider != openrouter.PROVIDER:
            raise ValidationError(
                [FieldError("sdk", "requires --host muse-code --provider openrouter")]
            )
        if settings_path is not None or mcp:
            raise ValidationError(
                [
                    FieldError(
                        "sdk",
                        "uses invocation-scoped settings and automatic MCP; "
                        "omit --settings and --mcp",
                    )
                ]
            )
        return muse_sdk.run(store, provider=provider, model=model, live=live)
    if provider and host != moments.HOST_MUSE_CODE:
        raise ValidationError(
            [FieldError("provider", "provider setup is currently supported only for muse-code")]
        )
    target = settings_path or setup.default_settings_path(host)
    try:
        version = setup.probe(host)
    except ValidationError as error:
        return _failed(host, store, target, "HOST_BINARY_MISSING", str(error))
    try:
        store.init()
    except OSError as error:
        return _failed(host, store, target, "STORE_NOT_WRITABLE", str(error), version=version)
    try:
        target = setup.install(
            host,
            target,
            store.root,
            provider=provider,
            model=model,
            mcp=mcp,
        )
    except ValidationError as error:
        mcp_failed = any(item.field == "mcp" for item in error.errors)
        code = "MCP_INVALID" if mcp_failed else "HOST_CONFIG_INVALID"
        return _failed(host, store, target, code, str(error), version=version)
    provider_status: dict[str, object] | None = None
    if provider == openrouter.PROVIDER:
        credential = openrouter.detect_credential()
        if credential is None:
            provider_status = {
                "ready": False,
                "code": "OPENROUTER_CREDENTIAL_MISSING",
                "detail": "set OPENROUTER_API_KEY or store an OpenRouter key with muse auth",
            }
        else:
            proxy = openrouter.ensure_proxy(credential)
            provider_status = {
                "ready": proxy.ready,
                "code": "PROXY_REACHABLE" if proxy.ready else "PROXY_UNREACHABLE",
                "detail": proxy.detail,
                **({"next": proxy.command} if proxy.command else {}),
            }
    report = doctor.run(
        store,
        host,
        settings_path=target,
        provider=provider,
        model=model,
        mcp=mcp,
        live=live,
    )
    payload = report.as_dict()
    payload.update(
        {
            "installed": str(target),
            "version": version,
            "provider": provider or "host-default",
            "mcp": "configured" if mcp else "not requested",
        }
    )
    if provider_status is not None:
        payload["provider_setup"] = provider_status
    return payload


def _failed(
    host: str,
    store: Store,
    target: pathlib.Path,
    code: str,
    detail: str,
    *,
    version: str = "",
) -> dict[str, object]:
    return {
        "status": doctor.FAILED,
        "host": host,
        "version": version,
        "store": str(store.root),
        "settings": str(target),
        "checks": [{"code": code, "ok": False, "detail": detail, "required": True}],
    }
