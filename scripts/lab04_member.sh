#!/usr/bin/env bash
# Deploy or destroy the Lab 04 auxiliary stack in the second account.
# The primary account stays on AWS_PROFILE (default arch); the member stack
# uses SAP_LABS_SECONDARY_PROFILE (default epdev).
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"

lab="${1:-04}"
action="${2:-deploy}"
require_lab "$lab"
if [[ "$lab" != "04" ]]; then
  printf 'only lab 04 has a member stack\n' >&2
  exit 2
fi
if [[ "$action" != "deploy" && "$action" != "destroy" ]]; then
  printf 'usage: %s 04 [deploy|destroy]\n' "${0##*/}" >&2
  exit 2
fi

root="$(repo_root)"
cd "$root"
profile="$SAP_LABS_SECONDARY_PROFILE"
stack="$(stack_name "$lab")Member"

primary_account="$(aws sts get-caller-identity --query Account --output text)"
secondary_account="$(AWS_PROFILE="$profile" aws sts get-caller-identity \
  --query Account --output text)"
if [[ "$secondary_account" == "$primary_account" ]]; then
  printf 'secondary profile %s resolves to the primary account %s\n' \
    "$profile" "$primary_account" >&2
  exit 1
fi

echo "member account $secondary_account via profile $profile"

if [[ "$action" == "destroy" ]]; then
  if AWS_PROFILE="$profile" aws cloudformation describe-stacks \
    --stack-name "$stack" >/dev/null 2>&1; then
    (
      cd infra
      AWS_PROFILE="$profile" AWS_REGION="$AWS_REGION" \
        AWS_DEFAULT_REGION="$AWS_DEFAULT_REGION" \
        CDK_DEFAULT_REGION="$CDK_DEFAULT_REGION" \
        CDK_DEFAULT_ACCOUNT="$secondary_account" \
        uv run cdk destroy -c lab="$lab" -c member=1 --force
    )
  else
    echo "stack $stack already absent"
  fi
else
  uv sync --quiet
  (
    cd infra
    AWS_PROFILE="$profile" AWS_REGION="$AWS_REGION" \
      AWS_DEFAULT_REGION="$AWS_DEFAULT_REGION" \
      CDK_DEFAULT_REGION="$CDK_DEFAULT_REGION" \
      CDK_DEFAULT_ACCOUNT="$secondary_account" \
      uv run cdk deploy -c lab="$lab" -c member=1 --require-approval never
  )
fi
