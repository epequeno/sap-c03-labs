from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any

import aws_cdk as cdk
from aws_cdk.assertions import Template

STACK_PATH = Path(__file__).parents[1] / "infra/stacks/lab02_multitenant_api.py"
SPEC = importlib.util.spec_from_file_location("lab02_stack", STACK_PATH)
assert SPEC is not None and SPEC.loader is not None
stack_module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(stack_module)


def _template() -> Template:
    app = cdk.App()
    stack = stack_module.Lab02MultitenantApi(
        app,
        "TestLab02",
        env=cdk.Environment(account="123456789012", region="us-east-1"),
    )
    return Template.from_stack(stack)


def _only(template: Template, resource_type: str) -> dict[str, Any]:
    resources = template.find_resources(resource_type)
    assert len(resources) == 1
    return next(iter(resources.values()))


def test_table_is_tenant_scoped_and_disposable() -> None:
    table = _only(_template(), "AWS::DynamoDB::Table")
    assert table["Properties"]["BillingMode"] == "PAY_PER_REQUEST"
    assert table["Properties"]["KeySchema"] == [
        {"AttributeName": "tenant_id", "KeyType": "HASH"},
        {"AttributeName": "record_id", "KeyType": "RANGE"},
    ]
    assert table["DeletionPolicy"] == "Delete"


def test_cognito_has_two_admin_managed_tenant_groups() -> None:
    template = _template()
    groups = {
        resource["Properties"]["GroupName"]
        for resource in template.find_resources("AWS::Cognito::UserPoolGroup").values()
    }
    assert groups == {"tenant-a", "tenant-b"}
    pool = _only(template, "AWS::Cognito::UserPool")
    assert pool["Properties"]["DeletionProtection"] == "INACTIVE"
    assert pool["Properties"]["MfaConfiguration"] == "OPTIONAL"
    assert pool["Properties"]["Policies"]["PasswordPolicy"] == {
        "MinimumLength": 12,
        "RequireLowercase": True,
        "RequireNumbers": True,
        "RequireSymbols": True,
        "RequireUppercase": True,
    }
    assert pool["DeletionPolicy"] == "Delete"


def test_route_requires_jwt_authorizer() -> None:
    template = _template()
    route = _only(template, "AWS::ApiGatewayV2::Route")
    assert route["Properties"]["RouteKey"] == (
        "GET /tenants/{tenantId}/records/{recordId}"
    )
    assert route["Properties"]["AuthorizationType"] == "JWT"
    authorizer = _only(template, "AWS::ApiGatewayV2::Authorizer")
    assert authorizer["Properties"]["AuthorizerType"] == "JWT"
    assert authorizer["Properties"]["IdentitySource"] == [
        "$request.header.Authorization"
    ]


def test_logs_are_short_lived_and_removed() -> None:
    log_group = _only(_template(), "AWS::Logs::LogGroup")
    assert log_group["Properties"]["RetentionInDays"] == 1
    assert log_group["DeletionPolicy"] == "Delete"
