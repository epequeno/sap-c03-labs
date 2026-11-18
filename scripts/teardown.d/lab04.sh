#!/usr/bin/env bash
# Lab 4 teardown: remove Clean Rooms resources and the second-account stack
# before the generic teardown destroys the primary stack.
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/../lib.sh"

lab="${1:-04}"
require_lab "$lab"
root="$(repo_root)"
primary_profile="${SAP_LABS_PRIMARY_PROFILE:-arch}"
secondary_profile="${SAP_LABS_SECONDARY_PROFILE:-epdev}"
evidence="$root/labs/04-lakehouse/evidence"
latest=""
if [[ -d "$evidence" ]]; then
  latest="$(find "$evidence" -mindepth 1 -maxdepth 1 -type d | sort | tail -1)"
fi
if [[ -z "$latest" ]]; then
  latest="$(mktemp -d)"
fi

uv run python "$root/scripts/lab04_cleanrooms.py" \
  --teardown \
  --out "$latest" \
  --primary-profile "$primary_profile" \
  --secondary-profile "$secondary_profile" \
  --region "$AWS_REGION"

"$root/scripts/lab04_member.sh" 04 destroy
