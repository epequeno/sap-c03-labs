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
if aws cloudformation describe-stacks --stack-name "$stack" >/dev/null 2>&1; then
  (cd infra && uv run cdk destroy -c lab="$lab" --force)
else
  echo "stack $stack already absent"
fi

echo
echo "== verify nothing tagged survived"
# The resource tagging API is eventually consistent after a delete. Poll it
# rather than treating a stale entry as an orphaned resource.
remaining=""
raw=""
for _ in 1 2 3 4 5 6 7 8 9 10 11 12; do
  raw="$(aws resourcegroupstaggingapi get-resources \
    --tag-filters "Key=Project,Values=sap-c03-labs" "Key=Lab,Values=$lab" \
    --query 'ResourceTagMappingList[].ResourceARN' --output text)"
  remaining="$(printf '%s\n' "$raw" | filter_existing_tagged_resources)"
  if [[ -z "$remaining" ]]; then
    break
  fi
  sleep 5
done
if [[ -n "${remaining//[[:space:]]/}" ]]; then
  echo "still tagged after destroy — investigate, or wait for the tag index:" >&2
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
  if aws ce list-cost-allocation-tags --status Active \
    --query 'CostAllocationTags[?TagKey==`Project`].TagKey' \
    --output text 2>/dev/null | grep -qx 'Project'; then
    total="$(jq -r '[.ResultsByTime[].Total.UnblendedCost.Amount | tonumber] | add // 0' "$tmp") USD"
  else
    total="not readable (Project cost allocation tag is not active)"
  fi
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
