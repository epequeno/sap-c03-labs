#!/usr/bin/env bash
# Deploy one lab, then capture evidence in the same run.
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"

lab="${1:-}"
require_lab "$lab"
root="$(repo_root)"
cd "$root"
export AWS_PROFILE="$SAP_LABS_PRIMARY_PROFILE"

if [[ "$lab" == "04" ]]; then
  primary_account="$(aws sts get-caller-identity --query Account --output text)"
  secondary_account="$(AWS_PROFILE="$SAP_LABS_SECONDARY_PROFILE" \
    aws sts get-caller-identity --query Account --output text)"
  if [[ "$primary_account" == "$secondary_account" ]]; then
    printf 'lab 04 primary and secondary profiles resolve to the same account\n' >&2
    exit 1
  fi
fi

./scripts/preflight.sh

echo
echo "== synth"
uv sync --quiet
(cd infra && uv run cdk synth -c lab="$lab" --quiet)

echo
echo "== deploy $(stack_name "$lab")"
(cd infra && uv run cdk deploy -c lab="$lab" --require-approval never)

echo
echo "== evidence"
./scripts/evidence.sh "$lab"
