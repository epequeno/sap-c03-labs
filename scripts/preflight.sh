#!/usr/bin/env bash
# Identity and Region. Budgets are reported when visible but are not required:
# the project enforces cost caps by same-day teardown, not by a budget resource.
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

echo
echo "ok"
