"""Lab 2 — multi-tenant serverless API.

Question: given one pooled API and two tenants, where does the isolation
boundary live, and what does enforcing it cost per request?

Target shape: API Gateway -> Lambda -> DynamoDB, Cognito user pools for
identity, tenant_id carried in the access token. Enforcement in three
places on purpose, because the exam asks which one is sufficient:

  1. the Lambda, which must not trust a tenant_id from the request body;
  2. a DynamoDB condition expression, so a compromised handler still cannot
     read across tenants;
  3. optionally a per-tenant KMS key for a premium tier, to price the
     difference between logical and cryptographic isolation.

Failure to demonstrate: tenant A's token requests tenant B's record, and the
403 plus the CloudWatch log line are captured. That negative test is the
artifact; the happy path is not.

Deliberately not in this stack: WAF, custom domain, multi-Region. They add
cost and teach nothing that the exam asks here.

Exam mapping: 1.1.13, 2.1.2, 2.1.3, 2.2.1, 3.3.1.
Artifact standard: labs/02-multitenant-api/README.md.
Cost cap: under $1. Destroy the same day.
"""

from __future__ import annotations

import aws_cdk as cdk
from aws_cdk import aws_logs


class Lab02MultitenantApi(cdk.Stack):
    def __init__(self, scope: cdk.App, construct_id: str, **kwargs: object) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Structured request logs. Short retention on purpose: this stack is
        # torn down the same day, and the evidence copy is the JSON captured
        # by scripts/evidence.sh, not the log group itself.
        aws_logs.LogGroup(
            self,
            "RequestLogs",
            retention=aws_logs.RetentionDays.ONE_DAY,
            removal_policy=cdk.RemovalPolicy.DESTROY,
        )

        # Remainder of the body still to write, in this order:
        #   Cognito user pool + two app clients, one per tenant
        #   DynamoDB table: pk = tenant_id, sk = record_id, on-demand billing
        #   Lambda handler reading tenant_id from the token only
        #   API Gateway HTTP API with a Cognito authorizer
        #   One negative test recorded as evidence before teardown
