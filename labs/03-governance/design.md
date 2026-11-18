# Lab 3 — governance design note

## Gate result

`AWS_PROFILE=arch` resolves to a member account in an AWS Organization. `organizations:DescribeOrganization` succeeds, but `organizations:ListRoots` and `organizations:ListPolicies` return `AccessDeniedException`. The management account is not accessible from this profile, so no sandbox OU, SCP, or organization trail can be created.

The rules call for a documented blocked path, not a fake deploy. The reviewed policies are committed under `artifacts/`; the denied calls are captured under `evidence/`; no stack is registered for this lab.

## Intended control order

1. **SCP on a sandbox OU** — deny every action outside `us-east-1` and `us-west-2`, except global services, and deny `organizations:LeaveOrganization`. Preventive, evaluated before IAM and resource policies.
2. **S3 bucket policy** — the trail bucket accepts CloudTrail writes only from the organization trail, rejects writes outside the trail's home Region, and denies insecure transport. Preventive on the data plane.
3. **CloudTrail organization trail** — writes the denied request to the central bucket. Detective, after the request.
4. **AWS Config** — records resource state and changes. Detective, after the request. The account's existing `default` recorder is stopped, so this lab does not start it.
5. **IAM Access Analyzer** — finds resource policies that grant public or cross-account access. Offline analysis, not a request-path control.

## Which control fires

The SCP fires first. An explicit deny in an SCP is evaluated before identity and resource policies, so the request never reaches S3, DynamoDB, or the resource policy. The bucket policy fires only if the SCP allows the request to reach the bucket. CloudTrail and Config are after the fact; they do not stop the request. Access Analyzer is periodic.

The overlap is real but not redundant: the SCP prevents the action; the bucket policy protects the data if the SCP is detached, if the principal is outside the OU, or if the bucket is created in a non-approved Region. In a normal request both denies cannot be observed at once because the first one wins. To demonstrate the bucket-policy deny, use an identity outside the SCP scope or a bucket in a non-approved Region; do not weaken the SCP just to make the test pass.

## Data-residency nuance

`aws:RequestedRegion` in an S3 bucket policy is the Region the request is sent to, which for S3 is the bucket's Region, not the caller's Region. The SCP is the control that stops a caller from creating or using a bucket outside the approved Regions. The bucket policy is the backstop if a bucket already exists in the wrong Region. That is why both artifacts exist.

## If this runs in a management account

1. Create a sandbox OU and a member test account; attach `scp-deny-region.json` to the OU.
2. Create an organization trail into a new S3 bucket; apply `trail-bucket-policy.json`.
3. From the member account, attempt `aws s3api create-bucket --bucket ... --region eu-west-1`; expect `AccessDenied` naming the SCP.
4. Find the denied event in CloudTrail; confirm `errorCode` is `AccessDenied` and the event is in the trail bucket.
5. Apply `data-residency-bucket-policy.json` to a bucket in a non-approved Region, or use an identity outside the SCP, and attempt an upload; expect `AccessDenied`.
6. Enable the Config recorder and an aggregator for the sandbox account; start and stop within the lab.
7. Create an Access Analyzer; confirm no public or cross-account findings on the test bucket.
8. Pull one AWS Artifact report; store metadata and hash, not the PDF.

## Teardown

Remove the SCP from the OU, delete the trail, empty and delete the bucket, stop the Config recorder, delete the aggregator, and delete the analyzer. The artifacts and evidence remain in git; no AWS resources remain.
