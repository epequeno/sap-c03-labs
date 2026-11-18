#!/usr/bin/env bash
# Lab 4 evidence: the lakehouse queries and the two-account Clean Rooms flow.
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/../lib.sh"

out="${1:?evidence directory}"
root="$(repo_root)"
primary_profile="${SAP_LABS_PRIMARY_PROFILE:-arch}"
secondary_profile="${SAP_LABS_SECONDARY_PROFILE:-epdev}"
member_stack="$(stack_name 04)Member"

if ! AWS_PROFILE="$secondary_profile" aws cloudformation describe-stacks \
  --stack-name "$member_stack" >/dev/null 2>&1; then
  echo "member stack $member_stack absent; deploying it" >&2
  "$root/scripts/lab04_member.sh" 04 deploy
fi

uv run python "$root/scripts/lab04_cleanrooms.py" \
  --out "$out" \
  --primary-profile "$primary_profile" \
  --secondary-profile "$secondary_profile" \
  --region "$AWS_REGION"
