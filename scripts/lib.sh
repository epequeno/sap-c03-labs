# Shared helpers for the SAP-C03 lab scripts.
# Sourced, never executed. Callers set their own shell options.

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
