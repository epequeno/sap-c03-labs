# Lab 02 — cost

Actual spend from Cost Explorer, filtered on `Project=sap-c03-labs`.
Tag-based queries need the `Project` tag activated as a cost allocation tag.

## 2026-11-17T16:18:17Z — teardown

- `cdk destroy` exited 0 for `SapC03Lab02`.
- Tag query for `Project=sap-c03-labs`, `Lab=02`: no live resources; the tag index still listed the deleted Cognito user pool, which `describe-user-pool` confirmed absent.
- Spend to date, 7-day window: not readable (Project cost allocation tag is not active; this linked account cannot list cost allocation tags)
