#!/usr/bin/env bash
# Deploy one lab, then capture evidence in the same run.
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"

lab="${1:-}"
require_lab "$lab"
root="$(repo_root)"
cd "$root"

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
