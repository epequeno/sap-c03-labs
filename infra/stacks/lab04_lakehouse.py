"""Lab 4 — lakehouse and Clean Rooms.

Question: where does the data boundary live in a lakehouse — the bucket
policy, the Lake Formation grant, or the query engine — and what does a
denial look like to the analyst who hits it?

This stack creates the raw/curated S3 layout, the Glue table, the Athena
workgroup, and two roles:

  * the analyst role, which is granted only the visible columns by the
    evidence script;
  * the Clean Rooms service role, which can read the curated table and is
    associated to the collaboration.

The evidence script adds Lake Formation permissions, creates the Iceberg
table, and drives the two-account Clean Rooms collaboration. The member
stack in the second account owns the results bucket and results role.

Exam mapping: 1.5.1–1.5.7, 3.4.
Cost cap: under $2. Destroy the same day.
"""

from __future__ import annotations

from pathlib import Path

import aws_cdk as cdk
from aws_cdk import aws_athena as athena
from aws_cdk import aws_glue as glue
from aws_cdk import aws_iam as iam
from aws_cdk import aws_s3 as s3
from aws_cdk import aws_s3_deployment as s3deploy

DATABASE = "lab04_lakehouse"
TABLE = "events"
DATA_DIR = Path(__file__).resolve().parents[2] / "labs" / "04-lakehouse" / "data"
COLUMNS = [
    ("event_id", "bigint"),
    ("user_id", "string"),
    ("category", "string"),
    ("amount", "double"),
    ("secret_note", "string"),
]
VISIBLE_COLUMNS = ["event_id", "user_id", "category", "amount"]


class Lab04Lakehouse(cdk.Stack):
    def __init__(self, scope: cdk.App, construct_id: str, **kwargs: object) -> None:
        super().__init__(scope, construct_id, **kwargs)

        bucket_kwargs = {
            "block_public_access": s3.BlockPublicAccess.BLOCK_ALL,
            "encryption": s3.BucketEncryption.S3_MANAGED,
            "enforce_ssl": True,
            "auto_delete_objects": True,
            "removal_policy": cdk.RemovalPolicy.DESTROY,
        }
        raw_bucket = s3.Bucket(self, "RawBucket", **bucket_kwargs)
        curated_bucket = s3.Bucket(self, "CuratedBucket", **bucket_kwargs)
        results_bucket = s3.Bucket(
            self,
            "AthenaResultsBucket",
            lifecycle_rules=[
                s3.LifecycleRule(
                    expiration=cdk.Duration.days(1),
                    abort_incomplete_multipart_upload_after=cdk.Duration.days(1),
                )
            ],
            **bucket_kwargs,
        )

        s3deploy.BucketDeployment(
            self,
            "RawData",
            sources=[s3deploy.Source.asset(str(DATA_DIR))],
            destination_bucket=raw_bucket,
            destination_key_prefix="raw/",
        )
        s3deploy.BucketDeployment(
            self,
            "CuratedData",
            sources=[s3deploy.Source.asset(str(DATA_DIR))],
            destination_bucket=curated_bucket,
            destination_key_prefix="events/",
        )
        s3deploy.BucketDeployment(
            self,
            "CleanRoomsData",
            sources=[s3deploy.Source.asset(str(DATA_DIR))],
            destination_bucket=raw_bucket,
            destination_key_prefix="cleanrooms/",
        )

        database = glue.CfnDatabase(
            self,
            "Catalog",
            catalog_id=self.account,
            database_input=glue.CfnDatabase.DatabaseInputProperty(
                name=DATABASE,
                description="Lab 04 curated event data.",
            ),
        )
        table = glue.CfnTable(
            self,
            "EventsTable",
            catalog_id=self.account,
            database_name=DATABASE,
            table_input=glue.CfnTable.TableInputProperty(
                name=TABLE,
                description="Synthetic events; secret_note is intentionally hidden.",
                table_type="EXTERNAL_TABLE",
                parameters={
                    "classification": "csv",
                    "skip.header.line.count": "1",
                },
                storage_descriptor=glue.CfnTable.StorageDescriptorProperty(
                    columns=[
                        glue.CfnTable.ColumnProperty(name=name, type=type_)
                        for name, type_ in COLUMNS
                    ],
                    location=f"s3://{curated_bucket.bucket_name}/events/",
                    input_format="org.apache.hadoop.mapred.TextInputFormat",
                    output_format=(
                        "org.apache.hadoop.hive.ql.io.HiveIgnoreKeyTextOutputFormat"
                    ),
                    serde_info=glue.CfnTable.SerdeInfoProperty(
                        serialization_library=(
                            "org.apache.hadoop.hive.serde2.lazy.LazySimpleSerDe"
                        ),
                        parameters={"field.delim": ","},
                    ),
                ),
            ),
        )
        table.node.add_dependency(database)

        # Clean Rooms does not accept a Glue table that Lake Formation manages.
        # Keep a second table over the raw bucket, outside the LF-registered
        # location, for the collaboration. The two boundaries are separate.
        cleanrooms_table = glue.CfnTable(
            self,
            "CleanRoomsEventsTable",
            catalog_id=self.account,
            database_name=DATABASE,
            table_input=glue.CfnTable.TableInputProperty(
                name="events_cleanrooms",
                description="Clean Rooms copy; not registered with Lake Formation.",
                table_type="EXTERNAL_TABLE",
                parameters={
                    "classification": "csv",
                    "skip.header.line.count": "1",
                },
                storage_descriptor=glue.CfnTable.StorageDescriptorProperty(
                    columns=[
                        glue.CfnTable.ColumnProperty(name=name, type=type_)
                        for name, type_ in COLUMNS
                    ],
                    location=f"s3://{raw_bucket.bucket_name}/cleanrooms/",
                    input_format="org.apache.hadoop.mapred.TextInputFormat",
                    output_format=(
                        "org.apache.hadoop.hive.ql.io.HiveIgnoreKeyTextOutputFormat"
                    ),
                    serde_info=glue.CfnTable.SerdeInfoProperty(
                        serialization_library=(
                            "org.apache.hadoop.hive.serde2.lazy.LazySimpleSerDe"
                        ),
                        parameters={"field.delim": ","},
                    ),
                ),
            ),
        )
        cleanrooms_table.node.add_dependency(database)

        athena.CfnWorkGroup(
            self,
            "WorkGroup",
            name="lab04-lakehouse",
            description="Lab 04 Athena workgroup; 10 MB scan cap.",
            state="ENABLED",
            recursive_delete_option=True,
            work_group_configuration=athena.CfnWorkGroup.WorkGroupConfigurationProperty(
                enforce_work_group_configuration=True,
                bytes_scanned_cutoff_per_query=10_000_000,
                publish_cloud_watch_metrics_enabled=False,
                result_configuration=athena.CfnWorkGroup.ResultConfigurationProperty(
                    output_location=f"s3://{results_bucket.bucket_name}/",
                ),
                engine_version=athena.CfnWorkGroup.EngineVersionProperty(
                    selected_engine_version="Athena engine version 3",
                ),
            ),
        )

        analyst = iam.Role(
            self,
            "AnalystRole",
            assumed_by=iam.AccountRootPrincipal(),
            description="Lab 04 analyst; Lake Formation grants decide the columns.",
        )
        curated_bucket.grant_read(analyst)
        results_bucket.grant_read_write(analyst)
        analyst.add_to_policy(
            iam.PolicyStatement(
                actions=[
                    "athena:StartQueryExecution",
                    "athena:GetQueryExecution",
                    "athena:GetQueryResults",
                    "athena:GetQueryResultsStream",
                    "athena:StopQueryExecution",
                    "athena:GetWorkGroup",
                    "athena:ListQueryExecutions",
                ],
                resources=["*"],
            )
        )
        analyst.add_to_policy(
            iam.PolicyStatement(
                actions=[
                    "glue:GetDatabase",
                    "glue:GetTable",
                    "glue:GetTables",
                    "glue:GetPartitions",
                    "glue:GetTableVersions",
                ],
                resources=["*"],
            )
        )
        analyst.add_to_policy(
            iam.PolicyStatement(
                actions=["lakeformation:GetDataAccess"],
                resources=["*"],
            )
        )

        cleanrooms = iam.Role(
            self,
            "CleanRoomsServiceRole",
            assumed_by=iam.ServicePrincipal("cleanrooms.amazonaws.com"),
            description="Lab 04 Clean Rooms role for the curated table.",
        )
        curated_bucket.grant_read(cleanrooms)
        raw_bucket.grant_read(cleanrooms)
        cleanrooms.add_to_policy(
            iam.PolicyStatement(
                actions=[
                    "glue:GetDatabase",
                    "glue:GetTable",
                    "glue:GetTables",
                    "glue:GetPartitions",
                    "glue:GetTableVersions",
                ],
                resources=["*"],
            )
        )
        cleanrooms.add_to_policy(
            iam.PolicyStatement(
                actions=["lakeformation:GetDataAccess"],
                resources=["*"],
            )
        )

        cdk.CfnOutput(self, "RawBucketName", value=raw_bucket.bucket_name)
        cdk.CfnOutput(self, "CuratedBucketName", value=curated_bucket.bucket_name)
        cdk.CfnOutput(self, "AthenaResultsBucketName", value=results_bucket.bucket_name)
        cdk.CfnOutput(self, "DatabaseName", value=DATABASE)
        cdk.CfnOutput(self, "TableName", value=TABLE)
        cdk.CfnOutput(self, "CleanRoomsTableName", value="events_cleanrooms")
        cdk.CfnOutput(self, "VisibleColumns", value=",".join(VISIBLE_COLUMNS))
        cdk.CfnOutput(self, "WorkGroupName", value="lab04-lakehouse")
        cdk.CfnOutput(self, "AnalystRoleArn", value=analyst.role_arn)
        cdk.CfnOutput(self, "CleanRoomsRoleArn", value=cleanrooms.role_arn)
        cdk.CfnOutput(
            self,
            "DataLocation",
            value=f"s3://{curated_bucket.bucket_name}/events/",
        )
