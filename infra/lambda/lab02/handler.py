"""Tenant-scoped read handler for Lab 2.

The tenant comes from the Cognito group claim in the validated token. The path
tenant is checked only to produce a deliberate 403 when a caller asks for a
different tenant; it is never used as a DynamoDB key.
"""

from __future__ import annotations

import json
import os
from typing import Any

import boto3

_table = None


def _records_table():
    global _table
    if _table is None:
        _table = boto3.resource("dynamodb").Table(os.environ["TABLE_NAME"])
    return _table


def _response(status: int, body: dict[str, Any]) -> dict[str, Any]:
    return {
        "statusCode": status,
        "headers": {"content-type": "application/json"},
        "body": json.dumps(body),
    }


def _groups(claims: dict[str, Any]) -> list[str]:
    raw = claims.get("cognito:groups")
    if raw is None:
        return []
    if isinstance(raw, list):
        return [str(group) for group in raw]
    text = str(raw).strip()
    if text.startswith("[") and text.endswith("]"):
        text = text[1:-1]
    return [part.strip().strip('"') for part in text.split(",") if part.strip()]


def tenant_from_claims(claims: dict[str, Any]) -> str | None:
    tenants = [group for group in _groups(claims) if group in {"tenant-a", "tenant-b"}]
    if len(tenants) != 1:
        return None
    return tenants[0]


def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    claims = (
        event.get("requestContext", {})
        .get("authorizer", {})
        .get("jwt", {})
        .get("claims", {})
    )
    tenant = tenant_from_claims(claims)
    path_params = event.get("pathParameters") or {}
    path_tenant = path_params.get("tenantId")
    record_id = path_params.get("recordId")

    if tenant is None:
        print(json.dumps({"event": "tenant_claim_invalid"}))
        return _response(403, {"error": "tenant_claim_invalid"})
    if path_tenant != tenant:
        print(
            json.dumps(
                {
                    "event": "tenant_mismatch",
                    "tenant": tenant,
                    "path_tenant": path_tenant,
                    "record_id": record_id,
                }
            )
        )
        return _response(403, {"error": "tenant_mismatch"})
    if not record_id:
        return _response(400, {"error": "record_id_required"})

    item = (
        _records_table()
        .get_item(Key={"tenant_id": tenant, "record_id": record_id})
        .get("Item")
    )
    if item is None:
        return _response(404, {"error": "not_found"})
    return _response(200, {"tenant_id": tenant, "record": item})
