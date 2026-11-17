#!/usr/bin/env bash
# Capture what the lab actually did, into labs/<slug>/evidence/<utc-timestamp>/.
# Everything here is read-only against AWS.
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"

lab="${1:-}"
require_lab "$lab"
root="$(repo_root)"
slug="${LAB_SLUGS[$lab]}"
stack="$(stack_name "$lab")"
stamp="$(date -u +%Y%m%dT%H%M%SZ)"
out="$root/labs/$slug/evidence/$stamp"

mkdir -p "$out"

aws sts get-caller-identity --output json >"$out/caller-identity.json"

if aws cloudformation describe-stacks --stack-name "$stack" \
  --query 'Stacks[0].{Status:StackStatus,Outputs:Outputs}' \
  --output json >"$out/stack.json" 2>"$out/stack.err"; then
  rm -f "$out/stack.err"
else
  echo "stack $stack could not be described; see $out/stack.err" >&2
fi

aws resourcegroupstaggingapi get-resources \
  --tag-filters "Key=Project,Values=sap-c03-labs" "Key=Lab,Values=$lab" \
  --query 'ResourceTagMappingList[].ResourceARN' \
  --output json >"$out/tagged-resources.json"

# Tag-based cost needs Project activated as a cost allocation tag in Billing.
start="$(date -u -d '7 days ago' +%F)"
end="$(date -u -d 'tomorrow' +%F)"
if aws ce get-cost-and-usage \
  --time-period "Start=$start,End=$end" \
  --granularity DAILY \
  --metrics UnblendedCost \
  --filter '{"Tags":{"Key":"Project","Values":["sap-c03-labs"]}}' \
  --output json >"$out/cost.json" 2>"$out/cost.err"; then
  rm -f "$out/cost.err"
  if aws ce list-cost-allocation-tags --status Active \
    --query 'CostAllocationTags[?TagKey==`Project`].TagKey' \
    --output text 2>/dev/null | grep -qx 'Project'; then
    jq -r '[.ResultsByTime[].Total.UnblendedCost.Amount | tonumber] | add // 0' \
      "$out/cost.json" >"$out/cost-total.txt"
  else
    echo "not readable (Project cost allocation tag is not active)" \
      >"$out/cost-total.txt"
  fi
else
  echo "cost query failed (activate the Project tag, or ce permissions); see $out/cost.err" >&2
fi

# Lab-specific probes run before redaction so their output is covered too.
hook="$root/scripts/evidence.d/lab${lab}.sh"
if [[ -x "$hook" ]]; then
  echo
  echo "== lab evidence"
  "$hook" "$out" "$stack"
fi

# Redact identifiers that must not enter the public repo. The raw identity is
# never committed; the structure of the response is what the evidence needs.
account="$(jq -r '.Account // empty' "$out/caller-identity.json")"
principal="$(jq -r '.Arn // empty' "$out/caller-identity.json")"
if [[ -n "$account" ]]; then
  jq '.Account="<account-id>" | .Arn="<caller-arn>" | .UserId="<user-id>"' \
    "$out/caller-identity.json" >"$out/caller-identity.json.tmp"
  mv "$out/caller-identity.json.tmp" "$out/caller-identity.json"
  if [[ -n "$principal" ]]; then
    find "$out" -type f -print0 | xargs -0 sed -i "s|$principal|<caller-arn>|g"
  fi
  find "$out" -type f -print0 | xargs -0 sed -i "s|$account|<account-id>|g"
fi

echo
echo "evidence -> $out"
find "$out" -maxdepth 1 -type f -printf '  %f\n' | sort
