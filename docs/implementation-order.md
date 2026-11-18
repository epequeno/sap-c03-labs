# Implementation order

Exam: **2026-12-17**. Seven labs, one at a time. Each lab is deployed, evidenced, and destroyed in the same session.

The order is driven by cost and by the number of external prerequisites, not by folder number. Cheapest and least blocked first; the highest-cost and highest-availability-risk labs get a feasibility gate before they are scheduled.

## Order

| # | Lab | Cost cap | Main gate |
|---|---|---|---|
| 1 | `02-multitenant-api` | <$1 | None. Validates deploy, tags, evidence, teardown. |
| 2 | `03-governance` | <$2 | Organizations admin. If absent, record the blocked `organizations:*` call and commit the SCP/trail/bucket policy JSON as the artifact. |
| 3 | `04-lakehouse` | <$2 | Clean Rooms needs a second account. If absent, commit the collaboration design and run the Lake Formation denial locally. |
| 4 | `06-pipeline` | <$3 | GitHub connection needs OAuth. Use an S3 source instead; it teaches the same pipeline gate. |
| 5 | `05-resilience` | $3–6 | Route 53 failover needs a domain. Confirm one exists before scheduling; otherwise the failover path becomes a design artifact. |
| 6 | `01-agentic-rag` | $5–10 | Bedrock model access and S3 Vectors availability. Check both first; OpenSearch Serverless has a minimum OCU cost. |
| 7 | `07-network` | $2–4 | Optional. Transit Gateway must already exist; NAT gateways are the cost trap. |

Running every lab at its cap totals $28 against the $30 budget. Keep each lab inside its cap; a single overrun removes the margin for the rest.

Lab 03 gate result (2026-11-18): `organizations:DescribeOrganization` succeeds, but `organizations:ListRoots` and `organizations:ListPolicies` return `AccessDeniedException`. The project profile is a member account; Lab 03 is artifact-only and no stack is registered.

## Gates before scheduling

Run these read-only checks before writing a stack:

- **01:** `aws bedrock list-foundation-models --region us-east-1` and confirm the chosen vector store exists in the account.
- **03:** `aws organizations describe-organization` with the lab profile.
- **04:** confirm a second sandbox account can be invited to Clean Rooms.
- **05:** confirm a public hosted zone and a certificate for the failover name.
- **06:** decide S3 source vs GitHub connection before writing the pipeline.
- **07:** `aws ec2 describe-transit-gateways`; if none, keep the route-table artifact.

A failed gate is not a blocker. The lab README records the blocked call and ships the design artifact, as the repo rules require.

## Cadence

| Week | Labs |
|---|---|
| 2026-11-17 | `02` |
| 2026-11-24 | `03`, `04` |
| 2026-12-01 | `06`, `05` |
| 2026-12-08 | `01`, `07` optional |

The final week is for evidence review and practice questions, not new infrastructure.

## Local gate

Until remote CI is added, every change runs:

```bash
just verify   # blocking: ruff check, ruff format --check, pytest, cdk synth
just quality  # verify plus cfn-lint (advisory)
just nag 02   # cdk-nag findings (advisory)
```

No dedicated budget resource is created. Cost caps are enforced by same-day teardown, `just destroy`, and the spend recorded in each lab's `cost.md`.

Evidence is redacted before commit: account IDs, ARNs, principal names, request IDs, and raw bearer tokens never enter the public repo.
