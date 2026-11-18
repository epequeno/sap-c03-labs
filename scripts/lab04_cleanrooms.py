#!/usr/bin/env python3
"""Lab 04 two-account evidence and cleanup.

The primary stack owns the lakehouse; the member stack owns the Clean Rooms
results bucket and role. This script adds the Lake Formation grants, runs the
Athena queries as the analyst role, creates the Clean Rooms collaboration and
membership, runs the aggregate query, and records the denial paths.

It is intentionally explicit about the account boundary: the primary session
creates the collaboration and configured table; the secondary session joins
the membership and runs the protected query.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
import time
from collections.abc import Callable
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import boto3
from botocore.exceptions import ClientError

PRIMARY_STACK = "SapC03Lab04"
MEMBER_STACK = "SapC03Lab04Member"
COLLABORATION_NAME = "lab04-lakehouse"
CONFIGURED_TABLE_NAME = "lab04-events"
ASSOCIATION_NAME = "events"
ICEBERG_TABLE = "events_iceberg"
VISIBLE_COLUMNS = ["event_id", "user_id", "category", "amount"]
ALL_COLUMNS = [*VISIBLE_COLUMNS, "secret_note"]


def _json_default(value: Any) -> Any:
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


def _redact(value: Any, replacements: dict[str, str]) -> Any:
    if isinstance(value, str):
        for old, new in replacements.items():
            if old:
                value = value.replace(old, new)
        value = re.sub(r"arn:aws:[^\s\"']+", "<arn>", value)
        return value
    if isinstance(value, list):
        return [_redact(item, replacements) for item in value]
    if isinstance(value, dict):
        return {key: _redact(item, replacements) for key, item in value.items()}
    return value


def _write(
    path: Path,
    payload: Any,
    replacements: dict[str, str],
) -> None:
    redacted = _redact(payload, replacements)
    path.write_text(
        json.dumps(redacted, indent=2, default=_json_default) + "\n",
        encoding="utf-8",
    )


def _stack_outputs(session: boto3.Session, stack: str) -> dict[str, str]:
    client = session.client("cloudformation")
    response = client.describe_stacks(StackName=stack)
    outputs = response["Stacks"][0].get("Outputs", [])
    return {item["OutputKey"]: item["OutputValue"] for item in outputs}


def _wait(
    fn: Callable[[], bool],
    timeout: float = 180,
    interval: float = 2,
) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if fn():
            return True
        time.sleep(interval)
    return False


def _role_arn(sts: Any, iam: Any) -> str:
    arn = sts.get_caller_identity()["Arn"]
    if ":assumed-role/" not in arn:
        return arn
    role_name = arn.split(":assumed-role/", 1)[1].split("/", 1)[0]
    return iam.get_role(RoleName=role_name)["Role"]["Arn"]


def _safe(fn: Callable[[], Any], ignored: tuple[str, ...]) -> Any:
    try:
        return fn()
    except ClientError as exc:
        code = exc.response.get("Error", {}).get("Code", "")
        if code in ignored:
            return None
        raise


def _lf_grant(
    lf: Any,
    principal: str,
    resource: dict[str, Any],
    permissions: list[str],
) -> None:
    _safe(
        lambda: lf.grant_permissions(
            Principal={"DataLakePrincipalIdentifier": principal},
            Resource=resource,
            Permissions=permissions,
        ),
        ("AlreadyExistsException",),
    )


def _setup_lakeformation(
    out: Path,
    account: str,
    database: str,
    table: str,
    data_location: str,
    analyst_arn: str,
    cleanrooms_arn: str,
    lf: Any,
    sts: Any,
    iam: Any,
) -> str:
    settings = lf.get_data_lake_settings()["DataLakeSettings"]
    _write(out / "lakeformation-settings-before.json", settings, {})

    bucket_arn = "arn:aws:s3:::" + data_location[5:].split("/", 1)[0]
    admin_arn = _role_arn(sts, iam)
    admins = list(settings.get("DataLakeAdmins", []))
    if not any(item.get("DataLakePrincipalIdentifier") == admin_arn for item in admins):
        admins.append({"DataLakePrincipalIdentifier": admin_arn})
    modified = {**settings, "DataLakeAdmins": admins}
    lf.put_data_lake_settings(DataLakeSettings=modified)
    _write(out / "lakeformation-settings-admin.json", modified, {})

    _safe(
        lambda: lf.register_resource(
            ResourceArn=bucket_arn,
            UseServiceLinkedRole=True,
        ),
        ("AlreadyExistsException",),
    )

    table_resource = {
        "Table": {
            "CatalogId": account,
            "DatabaseName": database,
            "Name": table,
        }
    }
    data_location_resource = {"DataLocation": {"ResourceArn": bucket_arn}}

    # Lake Formation's default grant is IAM_ALLOWED_PRINCIPALS. Remove it so
    # the column grants below are the only path to the table data.
    _safe(
        lambda: lf.revoke_permissions(
            Principal={"DataLakePrincipalIdentifier": "IAM_ALLOWED_PRINCIPALS"},
            Resource=table_resource,
            Permissions=["ALL"],
        ),
        ("InvalidInputException", "EntityNotFoundException"),
    )

    for principal in (admin_arn, cleanrooms_arn):
        _lf_grant(lf, principal, table_resource, ["ALL"])
        _lf_grant(lf, principal, data_location_resource, ["DATA_LOCATION_ACCESS"])

    # Remove a table-level grant left by an earlier run; Lake Formation rejects
    # combining it with the column-level SELECT below.
    _safe(
        lambda: lf.revoke_permissions(
            Principal={"DataLakePrincipalIdentifier": analyst_arn},
            Resource=table_resource,
            Permissions=["ALL"],
        ),
        ("InvalidInputException", "EntityNotFoundException"),
    )

    # Do not add table-level DESCRIBE here. Lake Formation rejects combining a
    # table-level grant with a column-level SELECT for the same principal. The
    # analyst role still has IAM glue:GetTable, and Athena's query works with
    # the column grant alone; secret_note fails as COLUMN_NOT_FOUND.
    _lf_grant(
        lf,
        analyst_arn,
        {
            "TableWithColumns": {
                "CatalogId": account,
                "DatabaseName": database,
                "Name": table,
                "ColumnNames": VISIBLE_COLUMNS,
            }
        },
        ["SELECT"],
    )
    _lf_grant(lf, analyst_arn, data_location_resource, ["DATA_LOCATION_ACCESS"])

    permissions = lf.list_permissions(Resource=table_resource)
    _write(
        out / "lakeformation-permissions.json",
        {
            "PrincipalResourcePermissions": permissions.get(
                "PrincipalResourcePermissions", []
            )
        },
        {},
    )
    return admin_arn


def _start_athena(
    athena: Any,
    workgroup: str,
    sql: str,
    database: str,
) -> tuple[str, dict[str, Any]]:
    response = athena.start_query_execution(
        QueryString=sql,
        WorkGroup=workgroup,
        QueryExecutionContext={"Database": database},
    )
    query_id = response["QueryExecutionId"]
    deadline = time.time() + 180
    while time.time() < deadline:
        execution = athena.get_query_execution(QueryExecutionId=query_id)[
            "QueryExecution"
        ]
        state = execution["Status"]["State"]
        if state in {"SUCCEEDED", "FAILED", "CANCELLED"}:
            return query_id, execution
        time.sleep(2)
    raise TimeoutError(f"Athena query {query_id} did not finish")


def _save_athena(
    out: Path,
    label: str,
    athena: Any,
    workgroup: str,
    sql: str,
    database: str,
    required: bool = True,
) -> dict[str, Any]:
    try:
        query_id, execution = _start_athena(athena, workgroup, sql, database)
    except ClientError as exc:
        payload = {"error": exc.response, "sql": sql}
        _write(out / f"athena-{label}.json", payload, {})
        if required:
            raise
        return payload

    payload = {"queryExecutionId": query_id, "execution": execution, "sql": sql}
    _write(out / f"athena-{label}.json", payload, {})
    if execution["Status"]["State"] == "SUCCEEDED":
        results = athena.get_query_results(QueryExecutionId=query_id)
        _write(out / f"athena-{label}-results.json", results, {})
        rows = results["ResultSet"]["Rows"]
        if rows:
            csv_path = out / f"athena-{label}-results.csv"
            with csv_path.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.writer(handle)
                for row in rows:
                    writer.writerow(
                        [column.get("VarCharValue", "") for column in row["Data"]]
                    )
    elif required:
        reason = execution["Status"].get("StateChangeReason", "query failed")
        raise RuntimeError(f"{label}: {reason}")
    return payload


def _assume(athena_role_arn: str, sts: Any, region: str) -> boto3.Session:
    response = sts.assume_role(
        RoleArn=athena_role_arn,
        RoleSessionName="lab04-analyst",
    )
    credentials = response["Credentials"]
    return boto3.Session(
        aws_access_key_id=credentials["AccessKeyId"],
        aws_secret_access_key=credentials["SecretAccessKey"],
        aws_session_token=credentials["SessionToken"],
        region_name=region,
    )


def _find(
    items: list[dict[str, Any]], name_key: str, name: str
) -> dict[str, Any] | None:
    for item in items:
        if item.get(name_key) == name:
            return item
    return None


def _ensure_collaboration(
    primary: boto3.Session,
    secondary_account: str,
    region: str,
    tags: dict[str, str],
) -> dict[str, Any]:
    client = primary.client("cleanrooms")
    existing = _find(
        client.list_collaborations().get("collaborationList", []),
        "name",
        COLLABORATION_NAME,
    )
    if existing:
        return existing
    response = client.create_collaboration(
        members=[
            {
                "accountId": secondary_account,
                "memberAbilities": ["CAN_RECEIVE_RESULTS"],
                "displayName": "epdev-results",
                "paymentConfiguration": {"queryCompute": {"isResponsible": False}},
            }
        ],
        name=COLLABORATION_NAME,
        description="Lab 04 aggregate-only Clean Rooms collaboration.",
        creatorMemberAbilities=["CAN_QUERY"],
        creatorDisplayName="arch-data-owner",
        dataEncryptionMetadata={
            "allowCleartext": True,
            "allowDuplicates": True,
            "allowJoinsOnColumnsWithDifferentNames": True,
            "preserveNulls": True,
        },
        queryLogStatus="DISABLED",
        creatorPaymentConfiguration={"queryCompute": {"isResponsible": True}},
        allowedResultRegions=[region],
        tags=tags,
    )
    return response["collaboration"]


def _ensure_membership(
    client: Any,
    collaboration_id: str,
    tags: dict[str, str],
    default_result: dict[str, Any] | None = None,
) -> dict[str, Any]:
    existing = _find(
        client.list_memberships().get("membershipSummaries", []),
        "collaborationId",
        collaboration_id,
    )
    if existing:
        return client.get_membership(membershipIdentifier=existing["id"])["membership"]
    kwargs: dict[str, Any] = {
        "collaborationIdentifier": collaboration_id,
        "queryLogStatus": "DISABLED",
        "tags": tags,
    }
    if default_result:
        kwargs["defaultResultConfiguration"] = default_result
    response = client.create_membership(**kwargs)
    return response["membership"]


def _ensure_configured_table(
    primary: boto3.Session,
    region: str,
    database: str,
    table: str,
    tags: dict[str, str],
) -> dict[str, Any]:
    # `table` is the Clean Rooms copy, not the Lake Formation-managed table.
    # Clean Rooms rejects tables that Lake Formation manages.
    client = primary.client("cleanrooms")
    existing = _find(
        client.list_configured_tables().get("configuredTableSummaries", []),
        "name",
        CONFIGURED_TABLE_NAME,
    )
    if existing:
        return client.get_configured_table(configuredTableIdentifier=existing["id"])[
            "configuredTable"
        ]
    response = client.create_configured_table(
        name=CONFIGURED_TABLE_NAME,
        description="Lab 04 visible columns only; secret_note is omitted.",
        tableReference={
            "glue": {
                "region": region,
                "tableName": table,
                "databaseName": database,
            }
        },
        allowedColumns=VISIBLE_COLUMNS,
        analysisMethod="DIRECT_QUERY",
        tags=tags,
    )
    return response["configuredTable"]


def _ensure_analysis_rule(primary: boto3.Session, configured_table_id: str) -> None:
    client = primary.client("cleanrooms")
    try:
        client.get_configured_table_analysis_rule(
            configuredTableIdentifier=configured_table_id,
            analysisRuleType="AGGREGATION",
        )
        return
    except ClientError as exc:
        if exc.response.get("Error", {}).get("Code") != "ResourceNotFoundException":
            raise
    client.create_configured_table_analysis_rule(
        configuredTableIdentifier=configured_table_id,
        analysisRuleType="AGGREGATION",
        analysisRulePolicy={
            "v1": {
                "aggregation": {
                    "aggregateColumns": [
                        {"columnNames": ["event_id"], "function": "COUNT_DISTINCT"},
                        {"columnNames": ["amount"], "function": "SUM"},
                    ],
                    "joinColumns": ["user_id"],
                    "dimensionColumns": ["category"],
                    "scalarFunctions": [],
                    "outputConstraints": [
                        {
                            "columnName": "user_id",
                            "minimum": 2,
                            "type": "COUNT_DISTINCT",
                        }
                    ],
                }
            }
        },
    )


def _ensure_association(
    primary: boto3.Session,
    arch_membership_id: str,
    configured_table_id: str,
    cleanrooms_role_arn: str,
    tags: dict[str, str],
) -> dict[str, Any]:
    client = primary.client("cleanrooms")
    existing = _find(
        client.list_configured_table_associations(
            membershipIdentifier=arch_membership_id
        ).get("configuredTableAssociationSummaries", []),
        "name",
        ASSOCIATION_NAME,
    )
    if existing:
        return client.get_configured_table_association(
            membershipIdentifier=arch_membership_id,
            configuredTableAssociationIdentifier=existing["id"],
        )["configuredTableAssociation"]
    response = client.create_configured_table_association(
        name=ASSOCIATION_NAME,
        membershipIdentifier=arch_membership_id,
        configuredTableIdentifier=configured_table_id,
        roleArn=cleanrooms_role_arn,
        tags=tags,
    )
    return response["configuredTableAssociation"]


def _protected_query(
    client: Any,
    membership_id: str,
    sql: str,
) -> dict[str, Any]:
    response = client.start_protected_query(
        type="SQL",
        membershipIdentifier=membership_id,
        sqlParameters={"queryString": sql},
    )
    query_id = response["protectedQuery"]["id"]
    deadline = time.time() + 300
    while time.time() < deadline:
        query = client.get_protected_query(
            membershipIdentifier=membership_id,
            protectedQueryIdentifier=query_id,
        )["protectedQuery"]
        if query["status"] in {"SUCCESS", "FAILED", "CANCELLED"}:
            return query
        time.sleep(3)
    raise TimeoutError(f"Clean Rooms query {query_id} did not finish")


def _download_result(s3: Any, location: str, destination: Path) -> None:
    if not location.startswith("s3://"):
        return
    bucket, key = location[5:].split("/", 1)
    s3.download_file(bucket, key, str(destination))


def _delete_prefix(s3: Any, bucket: str, prefix: str) -> None:
    paginator = s3.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
        keys = [{"Key": item["Key"]} for item in page.get("Contents", [])]
        if keys:
            s3.delete_objects(Bucket=bucket, Delete={"Objects": keys})


def _download_member_result(
    s3: Any,
    bucket: str,
    prefix: str,
    destination: Path,
) -> dict[str, Any] | None:
    for _ in range(15):
        response = s3.list_objects_v2(Bucket=bucket, Prefix=prefix)
        objects = [
            item
            for item in response.get("Contents", [])
            if item.get("Size", 0) > 0 and not item["Key"].endswith("/_SUCCESS")
        ]
        if objects:
            latest = max(objects, key=lambda item: item["LastModified"])
            s3.download_file(bucket, latest["Key"], str(destination))
            return {"bucket": bucket, "key": latest["Key"]}
        time.sleep(2)
    return None


def _cleanrooms_evidence(
    out: Path,
    primary: boto3.Session,
    secondary: boto3.Session,
    primary_account: str,
    secondary_account: str,
    region: str,
    database: str,
    table: str,
    cleanrooms_table: str,
    workgroup: str,
    cleanrooms_role_arn: str,
    results_bucket: str,
    results_role_arn: str,
    tags: dict[str, str],
) -> dict[str, Any]:
    collaboration = _ensure_collaboration(primary, secondary_account, region, tags)
    collaboration_id = collaboration["id"]

    primary_cr = primary.client("cleanrooms")
    secondary_cr = secondary.client("cleanrooms")

    arch_membership = _ensure_membership(primary_cr, collaboration_id, tags)
    _wait(
        lambda: (
            primary_cr.get_membership(membershipIdentifier=arch_membership["id"])[
                "membership"
            ]["status"]
            == "ACTIVE"
        )
    )
    configured_table = _ensure_configured_table(
        primary, region, database, cleanrooms_table, tags
    )
    _ensure_analysis_rule(primary, configured_table["id"])
    association = _ensure_association(
        primary,
        arch_membership["id"],
        configured_table["id"],
        cleanrooms_role_arn,
        tags,
    )

    secondary_membership = _ensure_membership(
        secondary_cr,
        collaboration_id,
        tags,
        {
            "outputConfiguration": {
                "s3": {
                    "resultFormat": "CSV",
                    "bucket": results_bucket,
                    "keyPrefix": "lab04",
                    "singleFileOutput": True,
                }
            },
            "roleArn": results_role_arn,
        },
    )

    _wait(
        lambda: (
            primary_cr.get_membership(membershipIdentifier=arch_membership["id"])[
                "membership"
            ]["status"]
            == "ACTIVE"
        )
    )
    _wait(
        lambda: (
            secondary_cr.get_membership(
                membershipIdentifier=secondary_membership["id"]
            )["membership"]["status"]
            == "ACTIVE"
        )
    )

    aggregate_sql = (
        "SELECT category, COUNT(DISTINCT event_id) AS events, "
        "SUM(amount) AS total FROM events GROUP BY category ORDER BY category"
    )
    allowed = _protected_query(primary_cr, arch_membership["id"], aggregate_sql)
    _write(out / "cleanrooms-query.json", allowed, {})

    location = allowed.get("result", {}).get("output", {}).get("s3", {}).get("location")
    result_location = None
    if location:
        _download_result(
            secondary.client("s3"), location, out / "cleanrooms-result.csv"
        )
        result_location = {"location": location}
    else:
        result_location = _download_member_result(
            secondary.client("s3"),
            results_bucket,
            "lab04/",
            out / "cleanrooms-result.csv",
        )
        if result_location:
            _write(out / "cleanrooms-result-location.json", result_location, {})

    denied_sql = "SELECT secret_note FROM events LIMIT 1"
    try:
        denied = _protected_query(primary_cr, arch_membership["id"], denied_sql)
        _write(out / "cleanrooms-denied.json", denied, {})
    except ClientError as exc:
        _write(
            out / "cleanrooms-denied.json",
            {"error": exc.response, "sql": denied_sql},
            {},
        )

    summary = {
        "collaboration": {
            "id": collaboration_id,
            "name": collaboration.get("name"),
            "creatorAccountId": primary_account,
            "memberAccountId": secondary_account,
            "status": primary_cr.get_collaboration(
                collaborationIdentifier=collaboration_id
            )["collaboration"]["memberStatus"],
        },
        "archMembership": {
            "id": arch_membership["id"],
            "status": arch_membership["status"],
        },
        "memberMembership": {
            "id": secondary_membership["id"],
            "status": secondary_membership["status"],
        },
        "configuredTable": {
            "id": configured_table["id"],
            "name": configured_table["name"],
            "allowedColumns": configured_table.get("allowedColumns"),
            "analysisMethod": configured_table.get("analysisMethod"),
        },
        "association": {
            "id": association["id"],
            "name": association["name"],
            "configuredTableId": association["configuredTableId"],
        },
        "allowedQuery": {
            "sql": aggregate_sql,
            "status": allowed["status"],
            "resultLocation": result_location,
        },
        "deniedQuery": {
            "sql": denied_sql,
            "captured": (out / "cleanrooms-denied.json").exists(),
        },
    }
    _write(out / "cleanrooms-summary.json", summary, {})
    return summary


def _teardown_cleanrooms(
    primary: boto3.Session,
    secondary: boto3.Session,
    out: Path,
) -> None:
    primary_cr = primary.client("cleanrooms")
    secondary_cr = secondary.client("cleanrooms")
    collaboration_id = None
    if (out / "cleanrooms-summary.json").exists():
        summary = json.loads((out / "cleanrooms-summary.json").read_text())
        collaboration_id = summary.get("collaboration", {}).get("id")
    visible = {
        item["id"]
        for item in primary_cr.list_collaborations().get("collaborationList", [])
    }
    if collaboration_id not in visible:
        existing = _find(
            primary_cr.list_collaborations().get("collaborationList", []),
            "name",
            COLLABORATION_NAME,
        )
        collaboration_id = existing["id"] if existing else None
    if not collaboration_id:
        return

    # The invited member can leave before the creator closes the collaboration.
    for membership in secondary_cr.list_memberships().get("membershipSummaries", []):
        if membership.get("collaborationId") != collaboration_id:
            continue
        _safe(
            lambda mid=membership["id"]: secondary_cr.delete_membership(
                membershipIdentifier=mid
            ),
            ("ResourceNotFoundException",),
        )

    # Remove the creator's table associations, then the configured table.
    primary_memberships = [
        item
        for item in primary_cr.list_memberships().get("membershipSummaries", [])
        if item.get("collaborationId") == collaboration_id
    ]
    for membership in primary_memberships:
        for association in primary_cr.list_configured_table_associations(
            membershipIdentifier=membership["id"]
        ).get("configuredTableAssociationSummaries", []):
            _safe(
                lambda aid=association["id"], mid=membership["id"]: (
                    primary_cr.delete_configured_table_association(
                        configuredTableAssociationIdentifier=aid,
                        membershipIdentifier=mid,
                    )
                ),
                ("ResourceNotFoundException",),
            )

    for configured_table in primary_cr.list_configured_tables().get(
        "configuredTableSummaries", []
    ):
        if configured_table.get("name") == CONFIGURED_TABLE_NAME:
            _safe(
                lambda tid=configured_table["id"]: primary_cr.delete_configured_table(
                    configuredTableIdentifier=tid
                ),
                ("ResourceNotFoundException",),
            )

    # The creator cannot delete their membership while the collaboration is
    # active; close the collaboration first, then remove the membership.
    _safe(
        lambda: primary_cr.delete_collaboration(
            collaborationIdentifier=collaboration_id
        ),
        ("ResourceNotFoundException",),
    )
    for membership in primary_memberships:
        _safe(
            lambda mid=membership["id"]: primary_cr.delete_membership(
                membershipIdentifier=mid
            ),
            ("ResourceNotFoundException", "ConflictException"),
        )


def _teardown_lakeformation(
    lf: Any,
    account: str,
    database: str,
    table: str,
    data_location: str,
    principals: list[str],
    sts: Any,
    iam: Any,
) -> None:
    bucket_arn = "arn:aws:s3:::" + data_location[5:].split("/", 1)[0]
    table_resource = {
        "Table": {
            "CatalogId": account,
            "DatabaseName": database,
            "Name": table,
        }
    }
    data_location_resource = {"DataLocation": {"ResourceArn": bucket_arn}}
    for principal in principals:
        for resource in (table_resource, data_location_resource):
            _safe(
                lambda p=principal, r=resource: lf.revoke_permissions(
                    Principal={"DataLakePrincipalIdentifier": p},
                    Resource=r,
                    Permissions=["ALL"],
                ),
                (
                    "InvalidInputException",
                    "EntityNotFoundException",
                    "AccessDeniedException",
                ),
            )
    _safe(
        lambda: lf.deregister_resource(ResourceArn=bucket_arn),
        (
            "EntityNotFoundException",
            "InvalidInputException",
            "AccessDeniedException",
        ),
    )
    try:
        settings = lf.get_data_lake_settings()["DataLakeSettings"]
        admin_arn = _role_arn(sts, iam)
        admins = [
            item
            for item in settings.get("DataLakeAdmins", [])
            if item.get("DataLakePrincipalIdentifier") != admin_arn
        ]
        if len(admins) != len(settings.get("DataLakeAdmins", [])):
            settings["DataLakeAdmins"] = admins
            lf.put_data_lake_settings(DataLakeSettings=settings)
    except ClientError as exc:
        print(f"warning: Lake Formation admin restore failed: {exc}", file=sys.stderr)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", required=True)
    parser.add_argument("--primary-profile", default="arch")
    parser.add_argument("--secondary-profile", default="epdev")
    parser.add_argument("--region", default="us-east-1")
    parser.add_argument("--teardown", action="store_true")
    args = parser.parse_args()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    primary = boto3.Session(profile_name=args.primary_profile, region_name=args.region)
    secondary = boto3.Session(
        profile_name=args.secondary_profile, region_name=args.region
    )
    primary_account = primary.client("sts").get_caller_identity()["Account"]
    secondary_account = secondary.client("sts").get_caller_identity()["Account"]
    replacements = {
        primary_account: "<account-id>",
        secondary_account: "<account-id>",
    }

    if args.teardown:
        _teardown_cleanrooms(primary, secondary, out)
        try:
            outputs = _stack_outputs(primary, PRIMARY_STACK)
        except ClientError:
            return
        athena = primary.client("athena")
        _safe(
            lambda: athena.start_query_execution(
                QueryString=f"DROP TABLE IF EXISTS {outputs['DatabaseName']}.{ICEBERG_TABLE}",
                WorkGroup=outputs["WorkGroupName"],
                QueryExecutionContext={"Database": outputs["DatabaseName"]},
            ),
            ("InvalidRequestException", "AccessDeniedException"),
        )
        _teardown_lakeformation(
            primary.client("lakeformation"),
            primary_account,
            outputs["DatabaseName"],
            outputs["TableName"],
            outputs["DataLocation"],
            [outputs["AnalystRoleArn"], outputs["CleanRoomsRoleArn"]],
            primary.client("sts"),
            primary.client("iam"),
        )
        return

    outputs = _stack_outputs(primary, PRIMARY_STACK)
    member_outputs = _stack_outputs(secondary, MEMBER_STACK)
    database = outputs["DatabaseName"]
    table = outputs["TableName"]
    cleanrooms_table = outputs["CleanRoomsTableName"]
    workgroup = outputs["WorkGroupName"]
    data_location = outputs["DataLocation"]
    analyst_arn = outputs["AnalystRoleArn"]
    cleanrooms_arn = outputs["CleanRoomsRoleArn"]
    results_bucket = member_outputs["ResultsBucketName"]
    results_role_arn = member_outputs["ResultsRoleArn"]

    lf = primary.client("lakeformation")
    _setup_lakeformation(
        out,
        primary_account,
        database,
        table,
        data_location,
        analyst_arn,
        cleanrooms_arn,
        lf,
        primary.client("sts"),
        primary.client("iam"),
    )

    iceberg_location = data_location.rsplit("/events/", 1)[0] + "/iceberg/"
    iceberg_bucket = data_location[5:].split("/", 1)[0]
    athena = primary.client("athena")
    _save_athena(
        out,
        "iceberg-drop",
        athena,
        workgroup,
        f"DROP TABLE IF EXISTS {database}.{ICEBERG_TABLE}",
        database,
    )
    # An earlier layout placed Iceberg metadata under the CSV table prefix.
    # Remove it so the CSV table scan cannot read manifest files as rows.
    _delete_prefix(primary.client("s3"), iceberg_bucket, "events/iceberg/")
    _save_athena(
        out,
        "iceberg-create",
        athena,
        workgroup,
        f"""
        CREATE TABLE {database}.{ICEBERG_TABLE} (
          event_id bigint,
          user_id string,
          category string,
          amount double,
          secret_note string
        )
        LOCATION '{iceberg_location}'
        TBLPROPERTIES ('table_type'='ICEBERG')
        """,
        database,
    )
    _save_athena(
        out,
        "iceberg-insert",
        athena,
        workgroup,
        f"""
        INSERT INTO {database}.{ICEBERG_TABLE} VALUES
          (1, 'user-1', 'books', 10, 'alpha'),
          (2, 'user-2', 'books', 20, 'beta'),
          (3, 'user-1', 'music', 30, 'gamma'),
          (4, 'user-3', 'music', 40, 'delta'),
          (5, 'user-2', 'books', 5, 'epsilon'),
          (6, 'user-4', 'music', 15, 'zeta')
        """,
        database,
    )
    _save_athena(
        out,
        "iceberg-snapshots",
        athena,
        workgroup,
        f'SELECT * FROM "{database}"."{ICEBERG_TABLE}$snapshots"',
        database,
    )
    _save_athena(
        out,
        "admin-count",
        athena,
        workgroup,
        f"SELECT category, COUNT(*) AS events FROM {database}.{table} GROUP BY category",
        database,
    )

    analyst = _assume(analyst_arn, primary.client("sts"), args.region)
    analyst_athena = analyst.client("athena")
    _save_athena(
        out,
        "analyst-allowed",
        analyst_athena,
        workgroup,
        (
            "SELECT category, COUNT(DISTINCT event_id) AS events, "
            f"SUM(amount) AS total FROM {database}.{table} "
            "GROUP BY category ORDER BY category"
        ),
        database,
        required=False,
    )
    _save_athena(
        out,
        "analyst-denied",
        analyst_athena,
        workgroup,
        f"SELECT secret_note FROM {database}.{table} LIMIT 1",
        database,
        required=False,
    )

    tags = {
        "Project": "sap-c03-labs",
        "Lab": "04",
        "Owner": "steven",
        "TearDown": str(date.today() + timedelta(days=1)),
    }
    _cleanrooms_evidence(
        out,
        primary,
        secondary,
        primary_account,
        secondary_account,
        args.region,
        database,
        table,
        cleanrooms_table,
        workgroup,
        cleanrooms_arn,
        results_bucket,
        results_role_arn,
        tags,
    )

    # The common evidence script redacts the primary account after this hook.
    # Redact both accounts and all ARNs here so the secondary account cannot
    # slip into a committed file.
    for path in sorted(out.glob("*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            continue
        _write(path, payload, replacements)


if __name__ == "__main__":
    main()
