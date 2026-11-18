"""Lab 4 — second-account resources for the Clean Rooms collaboration.

This stack is deployed with the `epdev` profile and `-c member=1`. It owns
only the query-results bucket and the role Clean Rooms uses to write those
results. The collaboration, membership, configured table, and analysis rule
are created by the two-account evidence script.

Exam mapping: 1.5.1–1.5.7, 3.4.
"""

from __future__ import annotations

import aws_cdk as cdk
from aws_cdk import aws_iam as iam
from aws_cdk import aws_s3 as s3


class Lab04Member(cdk.Stack):
    def __init__(self, scope: cdk.App, construct_id: str, **kwargs: object) -> None:
        super().__init__(scope, construct_id, **kwargs)

        results = s3.Bucket(
            self,
            "ResultsBucket",
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            encryption=s3.BucketEncryption.S3_MANAGED,
            enforce_ssl=True,
            auto_delete_objects=True,
            removal_policy=cdk.RemovalPolicy.DESTROY,
            lifecycle_rules=[
                s3.LifecycleRule(
                    expiration=cdk.Duration.days(1),
                    abort_incomplete_multipart_upload_after=cdk.Duration.days(1),
                )
            ],
        )

        role = iam.Role(
            self,
            "CleanRoomsResultsRole",
            assumed_by=iam.ServicePrincipal("cleanrooms.amazonaws.com"),
            description="Lab 04 Clean Rooms query-results writer.",
        )
        results.grant_read_write(role)
        role.add_to_policy(
            iam.PolicyStatement(
                actions=["s3:GetBucketLocation"],
                resources=[results.bucket_arn],
            )
        )

        cdk.CfnOutput(self, "ResultsBucketName", value=results.bucket_name)
        cdk.CfnOutput(self, "ResultsRoleArn", value=role.role_arn)
