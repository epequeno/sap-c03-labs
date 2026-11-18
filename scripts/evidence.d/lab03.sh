#!/usr/bin/env bash
# Lab 3 evidence: prove the Organizations admin gate is closed, record the
# current detective controls, and pull one AWS Artifact report's metadata.
# The PDF is not committed: AWS Artifact reports are confidential and sizeable.
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/../lib.sh"

out="${1:?evidence directory}"

# The common evidence script writes an empty stack.json when DescribeStacks
# fails. This lab has no stack; keep the error and drop the empty placeholder.
if [[ ! -s "$out/stack.json" ]]; then
  rm -f "$out/stack.json"
fi

# The project profile can read the organization summary but not administer it.
# Capture the successful read and the two denied administration calls.
if aws organizations describe-organization --output json \
  2>"$out/organizations-describe-organization.err" \
  | jq '{Organization: {Id: .Organization.Id, FeatureSet: .Organization.FeatureSet, MasterAccountId: "<account-id>"}}' \
  >"$out/organizations-describe-organization.json"; then
  rm -f "$out/organizations-describe-organization.err"
else
  echo "organizations:DescribeOrganization failed" >"$out/organizations-describe-organization.err"
fi

capture_blocked() {
  local name="$1"
  shift
  if "$@" >"$out/$name.json" 2>"$out/$name.err"; then
    rm -f "$out/$name.err"
  else
    rm -f "$out/$name.json"
    printf 'blocked: %s\n' "$*" >"$out/$name.status"
  fi
}

capture_blocked organizations-list-roots \
  aws organizations list-roots --output json
capture_blocked organizations-list-policies \
  aws organizations list-policies --filter SERVICE_CONTROL_POLICY --output json

aws cloudtrail describe-trails --output json \
  | jq '{trailList: [(.trailList // [])[] | {
      Name,
      HomeRegion,
      IsOrganizationTrail,
      S3BucketName: ((.S3BucketName // "") | gsub("[0-9]{12}"; "<account-id>"))
    }]}' \
  >"$out/cloudtrail-trails.json"

aws configservice describe-configuration-recorder-status --output json \
  | jq '{ConfigurationRecordersStatus: [(.ConfigurationRecordersStatus // [])[] | {
      name,
      recording,
      lastStatus,
      lastStartTime,
      lastStopTime
    }]}' \
  >"$out/config-recorder-status.json"

aws configservice describe-configuration-recorders --output json \
  | jq '{ConfigurationRecorders: [(.ConfigurationRecorders // [])[] | {
      name,
      roleARN: "<role-arn>",
      allSupported,
      recordingGroup
    }]}' \
  >"$out/config-recorders.json"

aws accessanalyzer list-analyzers --output json \
  | jq '{analyzers: [(.analyzers // [])[] | {name, type, status}]}' \
  >"$out/access-analyzers.json"

# Pull one report for its metadata and hash. The presigned URL and term token
# stay in shell variables and are never written to evidence.
report_name="System and Organization Controls (SOC) 2 Report"
reports="$(aws artifact list-reports --output json)"
report_meta="$(jq -c --arg n "$report_name" \
  '(.reports // [])[] | select(.name == $n) | {id, name, category, arn}' \
  <<<"$reports" | head -n 1)"
if [[ -z "$report_meta" ]]; then
  printf 'report not found: %s\n' "$report_name" >"$out/artifact-report.err"
else
  report_id="$(jq -r '.id' <<<"$report_meta")"
  term_token="$(aws artifact get-term-for-report --report-id "$report_id" \
    --query termToken --output text)"
  report_url="$(aws artifact get-report --report-id "$report_id" \
    --term-token "$term_token" --query documentPresignedUrl --output text)"
  tmp="$(mktemp --suffix=.pdf)"
  trap 'rm -f "$tmp"' EXIT
  if curl -fsSL "$report_url" -o "$tmp"; then
    bytes="$(stat -c %s "$tmp")"
    sha="$(sha256sum "$tmp" | awk '{print $1}')"
    jq -n --argjson report "$report_meta" --arg sha "$sha" --argjson bytes "$bytes" \
      '{report: $report, downloaded: true, bytes: $bytes, sha256: $sha,
        note: "PDF downloaded for verification; not committed because AWS Artifact reports are confidential."}' \
      >"$out/artifact-report.json"
  else
    printf 'download failed for %s\n' "$report_name" >"$out/artifact-report.err"
  fi
  rm -f "$tmp"
  trap - EXIT
fi
