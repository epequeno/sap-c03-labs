# Lab 2 — Multi-tenant serverless API

**Stack:** scaffolded in `infra/stacks/lab02_multitenant_api.py`. Body not yet written — this is the first lab on the critical path.

## Question

Given one pooled API and two tenants, where does the isolation boundary live, and what does enforcing it cost per request?

## Constraints

- `us-east-1`, sandbox account, **under $1**.
- No custom domain, no WAF, no multi-Region. None of them teach what this lab tests.
- Deployed and destroyed inside one session. It exists to validate the repo, the tags, the evidence capture and the teardown on the cheapest stack available.

## Build

Cognito user pool with one app client per tenant; DynamoDB table keyed `tenant_id` / `record_id` on on-demand billing; a Lambda that reads `tenant_id` from the token and never from the request body; an HTTP API with a Cognito authorizer. Enforcement in three places deliberately: the handler, the DynamoDB condition expression, and optionally a per-tenant KMS key for a premium tier.

## Failure to demonstrate

Tenant A's token requests tenant B's record. Capture the 403 and the CloudWatch log line. That negative test is the artifact; the happy path proves nothing.

## Evidence

Decoded token claims, 200 and 403 results, DynamoDB items, key policy if the premium tier is built, a log sample, the cost report.

## Exam mapping

1.1.13 (multi-tenant isolation), 2.1.2–2.1.3 (identity and authorization), 2.2.1 (encryption), 3.3.1 (cost).

## Still to fill

- [ ] Stack body
- [ ] Diagram, committed as Mermaid or SVG
- [ ] Deploy section with the exact commands
- [ ] Evidence folder committed, including the 403
- [ ] `cost.md` with teardown timestamp
- [ ] Interview line: logical vs cryptographic isolation, and what the second costs
