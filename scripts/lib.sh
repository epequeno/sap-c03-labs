# Shared helpers for the SAP-C03 lab scripts.
# Sourced, never executed. Callers set their own shell options.

# This project runs against the `arch` sandbox account. Every script and every
# child process (aws, cdk) inherits these. Override any of them explicitly to
# point a one-off command somewhere else.
export AWS_PROFILE="${AWS_PROFILE:-arch}"
export AWS_REGION="${AWS_REGION:-us-east-1}"
export AWS_DEFAULT_REGION="${AWS_DEFAULT_REGION:-$AWS_REGION}"
export CDK_DEFAULT_REGION="${CDK_DEFAULT_REGION:-$AWS_REGION}"

declare -A LAB_SLUGS=(
  ["01"]="01-agentic-rag"
  ["02"]="02-multitenant-api"
  ["03"]="03-governance"
  ["04"]="04-lakehouse"
  ["05"]="05-resilience"
  ["06"]="06-pipeline"
  ["07"]="07-network"
)

SAP_LABS_ORDER="01 02 03 04 05 06 07"

repo_root() {
  cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd
}

require_lab() {
  local lab="${1:-}"
  if [[ -z "$lab" || -z "${LAB_SLUGS[$lab]:-}" ]]; then
    printf 'usage: %s <lab> (one of: %s)\n' "${0##*/}" "$SAP_LABS_ORDER" >&2
    exit 2
  fi
}

stack_name() {
  printf 'SapC03Lab%s' "$1"
}
