from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any

import aws_cdk as cdk
from aws_cdk.assertions import Template

STACK_PATH = Path(__file__).parents[1] / "infra/stacks/lab04_lakehouse.py"
SPEC = importlib.util.spec_from_file_location("lab04_stack", STACK_PATH)
assert SPEC is not None and SPEC.loader is not None
stack_module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(stack_module)


def _template() -> Template:
    app = cdk.App()
    stack = stack_module.Lab04Lakehouse(
        app,
        "TestLab04",
        env=cdk.Environment(account="123456789012", region="us-east-1"),
    )
    return Template.from_stack(stack)


def _named(resources: dict[str, Any], name: str) -> dict[str, Any]:
    for resource in resources.values():
        if resource["Properties"].get("Name") == name:
            return resource
    raise AssertionError(f"resource named {name!r} not found")


def _table(resources: dict[str, Any], name: str) -> dict[str, Any]:
    for resource in resources.values():
        if resource["Properties"]["TableInput"].get("Name") == name:
            return resource
    raise AssertionError(f"table named {name!r} not found")


def test_curated_and_cleanrooms_tables_are_separate() -> None:
    template = _template()
    tables = template.find_resources("AWS::Glue::Table")
    curated = _table(tables, "events")
    cleanrooms = _table(tables, "events_cleanrooms")
    assert (
        curated["Properties"]["TableInput"]["StorageDescriptor"]["Location"]
        != cleanrooms["Properties"]["TableInput"]["StorageDescriptor"]["Location"]
    )
    assert [
        column["Name"]
        for column in cleanrooms["Properties"]["TableInput"]["StorageDescriptor"][
            "Columns"
        ]
    ] == ["event_id", "user_id", "category", "amount", "secret_note"]


def test_athena_workgroup_caps_scans_and_uses_v3() -> None:
    workgroup = _named(
        _template().find_resources("AWS::Athena::WorkGroup"), "lab04-lakehouse"
    )
    config = workgroup["Properties"]["WorkGroupConfiguration"]
    assert config["BytesScannedCutoffPerQuery"] == 10_000_000
    assert config["EnforceWorkGroupConfiguration"] is True
    assert config["EngineVersion"]["SelectedEngineVersion"] == "Athena engine version 3"


def test_buckets_are_private_and_disposable() -> None:
    buckets = _template().find_resources("AWS::S3::Bucket")
    assert len(buckets) == 3
    for bucket in buckets.values():
        assert bucket["Properties"]["PublicAccessBlockConfiguration"] == {
            "BlockPublicAcls": True,
            "BlockPublicPolicy": True,
            "IgnorePublicAcls": True,
            "RestrictPublicBuckets": True,
        }
        assert bucket["DeletionPolicy"] == "Delete"


def test_outputs_expose_the_cleanrooms_table() -> None:
    template = _template()
    output = template.find_outputs("CleanRoomsTableName")["CleanRoomsTableName"]
    assert output["Value"] == "events_cleanrooms"
