# Lab 6 — CI/CD and observability

**Stack:** not written. `infra/stacks/lab06_pipeline.py`.

## Question

What stops a bad change from reaching production, and where is that decision recorded when it fires?

## Constraints

- `us-east-1`, sandbox account, **under $3**.
- One pipeline, not a pipeline platform. No CodeCommit repo wars: use a GitHub connection or an S3 source.
- Synthetics canary runs on a short schedule and is deleted with the stack; do not leave it running overnight.

## Build

CDK app → CodePipeline → CodeBuild → ECR, deploying a Lambda or ECS service. Inspector or ECR image scanning in the pipeline. CloudWatch dashboard, a Synthetics canary on the public endpoint, an SLO alarm with an SNS action. If time allows, a Bedrock Evaluations step over a small prompt set as the quality gate.

## Failure to demonstrate

A critical image finding, or a failing canary, blocks promotion. Capture the stopped pipeline, the reason, and the notification — not just the green run.

## Evidence

Pipeline graph, build log, scan findings, canary result, dashboard screenshot, alarm and notification, cost report.

## Exam mapping

5.1.1–5.1.4 (IaC and config), 5.2.1–5.2.5 (CI/CD and deployment strategies), 5.3.1–5.3.7 (observability), 2.3.6 (pipeline authorization).

## Still to fill

- [ ] Stack
- [ ] Diagram, committed as Mermaid or SVG
- [ ] Deploy section with the exact commands
- [ ] Evidence folder committed, including the blocked promotion
- [ ] `cost.md` with teardown timestamp
- [ ] Interview line: the cheapest gate that still catches the failure you care about
