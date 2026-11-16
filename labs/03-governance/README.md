# Lab 3 — Multi-account governance

**Stack:** not written. `infra/stacks/lab03_governance.py`.

## Question

Which control actually stops the action — the SCP, the resource policy, the permission boundary or the guardrail service — and what evidence does an auditor get when it fires?

## Constraints

- **No changes to existing SCPs or org-wide services.** Create a sandbox OU and a new SCP, then remove them.
- Cost cap **under $2**. CloudTrail and Config only; **no Security Lake**, no org-wide GuardDuty.
- If the account has no Organizations administration, do not fake it: produce the SCP, trail policy and bucket policy as reviewed JSON plus a design note, and record the blocked API call.

## Build

Sandbox OU with an SCP denying a specific action in a test Region. An organization CloudTrail trail into a central S3 bucket whose policy rejects any non-approved Region. A Config aggregator. An IAM Access Analyzer. One AWS Artifact report pulled as evidence.

## Failure to demonstrate

The SCP denies a test action; the trail records the denied call; the bucket policy rejects an upload naming a disallowed Region. All three observed, not described.

## Evidence

SCP JSON, `AccessDenied` output, the trail object, the Config aggregator result, the Artifact PDF, the data-residency policy.

## Exam mapping

2.3.1–2.3.6 (governance and controls), 2.4.2–2.4.5 (compliance and data residency), 5.1.1–5.1.4 (IaC and config management).

## Still to fill

- [ ] Stack, or the documented blocked path if org admin is unavailable
- [ ] Diagram, committed as Mermaid or SVG
- [ ] Deploy section with the exact commands
- [ ] Evidence folder committed
- [ ] `cost.md` with teardown timestamp
- [ ] Interview line: which control fires first, and where the overlap is wasted
