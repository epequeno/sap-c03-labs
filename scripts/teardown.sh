#!/usr/bin/env bash
# Destroy one lab, prove nothing tagged survived, record the spend and the timestamp.
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"

lab="${1:-}"
require_lab "$lab"
root="$(repo_root)"
slug="${LAB_SLUGS[$lab]}"
stack="$(stack_name "$lab")"
cd "$root"

echo "== destroy $stack"
(cd infra && uv run cdk destroy -c lab="$lab" --force)

echo
echo "== verify nothing tagged survived"
remaining="$(aws resourcegroupstaggingapi get-resources \
  --tag-filters "Key=Project,Values=sap-c03-labs" "Key=Lab,Values=$lab" \
  --query 'ResourceTagMappingList[].ResourceARN' --output text)"
if [[ -n "${remaining//[[:space:]]/}" ]]; then
  echo "still tagged after destroy — investigate before leaving the account:" >&2
  printf '%s\n' "$remaining" >&2
  exit 1
fi

cost_md="$root/labs/$slug/cost.md"
if [[ ! -f "$cost_md" ]]; then
  {
    printf '# Lab %s — cost\n\n' "$lab"
    printf 'Actual spend from Cost Explorer, filtered on `Project=sap-c03-labs`.\n'
    printf 'Tag-based queries need the `Project` tag activated as a cost allocation tag.\n'
  } >"$cost_md"
fi

total="not readable"
tmp="$(mktemp)"
start="$(date -u -d '7 days ago' +%F)"
end="$(date -u -d 'tomorrow' +%F)"
if aws ce get-cost-and-usage \
  --time-period "Start=$start,End=$end" \
  --granularity DAILY \
  --metrics UnblendedCost \
  --filter '{"Tags":{"Key":"Project","Values":["sap-c03-labs"]}}' \
  --output json >"$tmp" 2>/dev/null; then
  total="$(jq -r '[.ResultsByTime[].Total.UnblendedCost.Amount | tonumber] | add // 0' "$tmp") USD"
fi
rm -f "$tmp"

{
  printf '\n## %s — teardown\n\n' "$(date -u +%FT%TZ)"
  printf -- '- `cdk destroy` exited 0 for `%s`.\n' "$stack"
  printf -- '- Tag query for `Project=sap-c03-labs`, `Lab=%s`: empty.\n' "$lab"
  printf -- '- Spend to date, 7-day window: %s\n' "$total"
} >>"$cost_md"

echo
echo "torn down; cost recorded in $cost_md"
