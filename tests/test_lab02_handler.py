from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any

HANDLER_PATH = Path(__file__).parents[1] / "infra/lambda/lab02/handler.py"
SPEC = importlib.util.spec_from_file_location("lab02_handler", HANDLER_PATH)
assert SPEC is not None and SPEC.loader is not None
handler_module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(handler_module)


def _event(groups: Any, path_tenant: str = "tenant-a") -> dict[str, Any]:
    return {
        "requestContext": {
            "authorizer": {"jwt": {"claims": {"cognito:groups": groups}}}
        },
        "pathParameters": {"tenantId": path_tenant, "recordId": "record-1"},
    }


def test_tenant_from_claims_accepts_string_and_list() -> None:
    assert (
        handler_module.tenant_from_claims({"cognito:groups": "[tenant-a]"})
        == "tenant-a"
    )
    assert (
        handler_module.tenant_from_claims({"cognito:groups": ["tenant-b"]})
        == "tenant-b"
    )


def test_tenant_from_claims_rejects_missing_or_ambiguous() -> None:
    assert handler_module.tenant_from_claims({}) is None
    assert (
        handler_module.tenant_from_claims({"cognito:groups": "[tenant-a, tenant-b]"})
        is None
    )


def test_handler_denies_path_tenant_mismatch() -> None:
    result = handler_module.handler(_event("[tenant-a]", "tenant-b"), None)
    assert result["statusCode"] == 403
    assert "tenant_mismatch" in result["body"]
