"""Lab 2 — multi-tenant serverless API.

Question: given one pooled API and two tenants, where does the isolation
boundary live, and what does enforcing it cost per request?

Target shape: Cognito user pool -> HTTP API (JWT authorizer) -> Lambda ->
DynamoDB. Tenants are Cognito groups (`tenant-a`, `tenant-b`); the Lambda
reads the group from the validated token and never from the request path or
body.

The request path carries a tenant id only so the negative test can ask for a
different tenant and observe the handler refuse it:

  1. the Lambda derives the DynamoDB partition key from the token group;
  2. the path tenant must match the token tenant, else 403;
  3. DynamoDB key scoping means a handler that only uses the token cannot
     address another tenant's item. A condition expression would guard
     writes; this read-only lab does not need one.

A per-tenant KMS key is the cryptographic-isolation premium tier. It is not
built here: it changes the cost and the key-policy surface, and the exam only
needs the logical boundary demonstrated.

Failure to demonstrate: tenant A's token requests tenant B's record, and the
403 plus the CloudWatch `tenant_mismatch` log line are captured.

Deliberately not in this stack: WAF, custom domain, multi-Region. They add
cost and teach nothing that the exam asks here.

Exam mapping: 1.1.13, 2.1.2, 2.1.3, 2.2.1, 3.3.1.
Artifact standard: labs/02-multitenant-api/README.md.
Cost cap: under $1. Destroy the same day.
"""

from __future__ import annotations

import aws_cdk as cdk
from aws_cdk import aws_apigatewayv2 as apigwv2
from aws_cdk import aws_apigatewayv2_authorizers as authorizers
from aws_cdk import aws_apigatewayv2_integrations as integrations
from aws_cdk import aws_cognito as cognito
from aws_cdk import aws_dynamodb as dynamodb
from aws_cdk import aws_lambda as lambda_
from aws_cdk import aws_logs


class Lab02MultitenantApi(cdk.Stack):
    def __init__(self, scope: cdk.App, construct_id: str, **kwargs: object) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Structured request logs. One-day retention: the evidence copy is the
        # JSON captured by scripts/evidence.sh, not the log group itself.
        log_group = aws_logs.LogGroup(
            self,
            "RequestLogs",
            retention=aws_logs.RetentionDays.ONE_DAY,
            removal_policy=cdk.RemovalPolicy.DESTROY,
        )

        # One pool, one app client, one admin-managed group per tenant. The app
        # client identifies the application, not the tenant; the group is the
        # authorization boundary that travels in the token.
        user_pool = cognito.UserPool(
            self,
            "TenantUsers",
            self_sign_up_enabled=False,
            sign_in_aliases=cognito.SignInAliases(email=True),
            deletion_protection=False,
            removal_policy=cdk.RemovalPolicy.DESTROY,
        )
        for suffix in ("A", "B"):
            tenant = f"tenant-{suffix.lower()}"
            cognito.CfnUserPoolGroup(
                self,
                f"Group{suffix}",
                group_name=tenant,
                user_pool_id=user_pool.user_pool_id,
            )
        client = user_pool.add_client(
            "ApiClient",
            auth_flows=cognito.AuthFlow(admin_user_password=True),
            generate_secret=False,
        )

        # Tenant is the partition key, so a handler that derives the key from
        # the token cannot address another tenant's item.
        table = dynamodb.Table(
            self,
            "Records",
            partition_key=dynamodb.Attribute(
                name="tenant_id", type=dynamodb.AttributeType.STRING
            ),
            sort_key=dynamodb.Attribute(
                name="record_id", type=dynamodb.AttributeType.STRING
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            removal_policy=cdk.RemovalPolicy.DESTROY,
        )

        handler = lambda_.Function(
            self,
            "Handler",
            runtime=lambda_.Runtime.PYTHON_3_13,
            handler="handler.handler",
            code=lambda_.Code.from_asset("lambda/lab02"),
            timeout=cdk.Duration.seconds(10),
            environment={"TABLE_NAME": table.table_name},
            log_group=log_group,
        )
        table.grant_read_write_data(handler)

        authorizer = authorizers.HttpJwtAuthorizer(
            "CognitoAuthorizer",
            jwt_issuer=(
                f"https://cognito-idp.{self.region}.amazonaws.com/"
                f"{user_pool.user_pool_id}"
            ),
            jwt_audience=[client.user_pool_client_id],
        )
        api = apigwv2.HttpApi(self, "Api")
        api.add_routes(
            path="/tenants/{tenantId}/records/{recordId}",
            methods=[apigwv2.HttpMethod.GET],
            integration=integrations.HttpLambdaIntegration(
                "HandlerIntegration", handler
            ),
            authorizer=authorizer,
        )

        cdk.CfnOutput(self, "ApiUrl", value=api.api_endpoint)
        cdk.CfnOutput(self, "UserPoolId", value=user_pool.user_pool_id)
        cdk.CfnOutput(self, "UserPoolClientId", value=client.user_pool_client_id)
        cdk.CfnOutput(self, "TableName", value=table.table_name)
        cdk.CfnOutput(self, "LogGroupName", value=log_group.log_group_name)
