# Lab 5 — Resilience and DR with FIS

**Stack:** not written. `infra/stacks/lab05_resilience.py`.

## Question

What is the measured difference between the RTO you designed for and the RTO you get, and which dependency moves it?

## Constraints

- Primary `us-east-1`, DR `us-west-2`. **Active-passive only**; active-active teaches the same exam point at triple the cost.
- Cost cap **$3–6**. Smallest task sizes, destroy inside the lab window.
- No production data, no Crossplane-style replication of anything the lab does not need.

## Build

A small Fargate or serverless service in two Regions, active-passive. Route 53 health check with failover routing. DynamoDB global table or S3 cross-Region replication. AWS Backup Vault Lock. A Fault Injection Service experiment template that stops or faults the primary.

## Failure to demonstrate

The primary is faulted and traffic moves. Record the actual failover timeline against the target RTO/RPO, including the gap — the gap is the finding.

## Evidence

Health-check history, FIS experiment IDs and timeline, measured RTO and RPO, backup lock confirmation, cost report.

## Exam mapping

4.2.1–4.2.6 (DR and resilience), 4.3.1–4.3.5 (validation and recovery), 5.4.1–5.4.5 (operational readiness).

## Still to fill

- [ ] Stack
- [ ] Diagram, committed as Mermaid or SVG
- [ ] Deploy section with the exact commands
- [ ] Evidence folder committed, with the timeline
- [ ] `cost.md` with teardown timestamp
- [ ] Interview line: what broke the RTO, and what you changed because of it
