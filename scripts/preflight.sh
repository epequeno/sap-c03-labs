#!/usr/bin/env bash
# Identity, Region, and the budget guardrail from the lab ground rules.
# Set SAP_LABS_SKIP_BUDGETS=1 to deploy without a detectable budget.
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"

root="$(repo_root)"
cd "$root"

echo "== identity"
if ! id_json="$(aws sts get-caller-identity --output json 2>/dev/null)"; then
  echo "no AWS credentials in this shell. Set a profile first: export AWS_PROFILE=<name>" >&2
  exit 1
fi
account="$(jq -r '.Account' <<<"$id_json")"
principal="$(jq -r '.Arn' <<<"$id_json")"
printf 'account    %s\nprincipal  %s\n' "$account" "$principal"

region="${AWS_REGION:-${AWS_DEFAULT_REGION:-unset}}"
printf 'region     %s\n' "$region"
if [[ "$region" != "us-east-1" ]]; then
  echo "warning: labs assume us-east-1; CDK will deploy where CDK_DEFAULT_REGION points" >&2
fi

echo
echo "== budget"
budgets="$(aws budgets describe-budgets --account-id "$account" \
  --query 'Budgets[].BudgetName' --output text 2>/dev/null || true)"
if [[ -n "${budgets//[[:space:]]/}" ]]; then
  printf 'budgets    %s\n' "$budgets"
else
  echo "budgets    none visible to this principal"
fi

echo "== cost anomaly detection"
monitors="$(aws ce get-anomaly-monitors --query 'AnomalyMonitors[].MonitorName' \
  --output text 2>/dev/null || true)"
if [[ -n "${monitors//[[:space:]]/}" ]]; then
  printf 'monitors   %s\n' "$monitors"
else
  echo "monitors   none readable (needs ce:GetAnomalyMonitors)"
fi

if [[ -z "${budgets//[[:space:]]/}" && -z "${monitors//[[:space:]]/}" ]]; then
  echo
  echo "Neither a budget nor an anomaly monitor is visible. The lab ground rules put both" >&2
  echo "before the first deploy. Create a \$30 monthly budget and an anomaly monitor, or" >&2
  echo "re-run with SAP_LABS_SKIP_BUDGETS=1 if the account already has them at org level." >&2
  [[ "${SAP_LABS_SKIP_BUDGETS:-0}" == "1" ]] || exit 1
fi

echo
echo "ok"
