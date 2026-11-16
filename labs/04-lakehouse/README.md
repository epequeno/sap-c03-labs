# Lab 4 — Lakehouse and Clean Rooms

**Stack:** not written. `infra/stacks/lab04_lakehouse.py`.

## Question

Where does the data boundary live in a lakehouse — the bucket policy, the Lake Formation grant, or the query engine — and what does a denial look like to the analyst who hits it?

## Constraints

- `us-east-1`, sandbox account, **under $2**.
- Glue Data Catalog and Athena only; no EMR cluster. EMR pricing is not the lesson and a cluster is the fastest way to break the cost cap.
- Clean Rooms needs a second account or an invited collaborator. If neither exists, document the collaboration design and say so in this README.

## Build

S3 raw and curated buckets. Glue Data Catalog table over the curated prefix. Athena workgroup. One Iceberg table with a snapshot to inspect. Lake Formation grants for a second principal, then a column-level denial. If a second account is available, a Clean Rooms collaboration and an aggregate-only query.

## Failure to demonstrate

Lake Formation denies a column and the Athena query fails with the permission error — captured, with the grant that would have allowed it shown alongside.

## Evidence

Glue table schema, Athena output, Iceberg snapshot list, Lake Formation grant and deny, the Clean Rooms query result or the design note, cost report.

## Exam mapping

1.5.1–1.5.7 (data and analytics architecture), 3.4 (storage and analytics cost).

## Still to fill

- [ ] Stack
- [ ] Diagram, committed as Mermaid or SVG
- [ ] Deploy section with the exact commands
- [ ] Evidence folder committed
- [ ] `cost.md` with teardown timestamp
- [ ] Interview line: coarse-grained IAM vs fine-grained Lake Formation, and the operational price of the second
