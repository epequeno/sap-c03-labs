# Shared helpers for the SAP-C03 lab scripts.
# Sourced, never executed. Callers set their own shell options.

# This project runs against the `arch` sandbox account. Every script and every
# child process (aws, cdk) inherits these. Override any of them explicitly to
# point a one-off command somewhere else.
export AWS_PROFILE="${AWS_PROFILE:-arch}"
export AWS_REGION="${AWS_REGION:-us-east-1}"
export AWS_DEFAULT_REGION="${AWS_DEFAULT_REGION:-$AWS_REGION}"
export CDK_DEFAULT_REGION="${CDK_DEFAULT_REGION:-$AWS_REGION}"
# The primary and secondary profiles are explicit so a leaked AWS_PROFILE
# cannot deploy the primary stack into the collaborator account.
export SAP_LABS_PRIMARY_PROFILE="${SAP_LABS_PRIMARY_PROFILE:-arch}"
export SAP_LABS_SECONDARY_PROFILE="${SAP_LABS_SECONDARY_PROFILE:-epdev}"

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

# The Resource Groups Tagging API can list a deleted resource for minutes.
# Trust the service API before declaring an ARN an orphan. Unknown services
# are treated as existing so the teardown stays conservative.
tagged_resource_exists() {
  local arn="$1"
  case "$arn" in
    arn:aws:cognito-idp:*:userpool/*)
      aws cognito-idp describe-user-pool --user-pool-id "${arn##*/}" \
        >/dev/null 2>&1
      ;;
    arn:aws:lambda:*:function:*)
      aws lambda get-function --function-name "${arn#*:function:}" \
        >/dev/null 2>&1
      ;;
    arn:aws:dynamodb:*:table/*)
      aws dynamodb describe-table --table-name "${arn##*/}" >/dev/null 2>&1
      ;;
    arn:aws:logs:*:log-group:*)
      aws logs list-tags-log-group --log-group-name "${arn#*:log-group:}" \
        >/dev/null 2>&1
      ;;
    arn:aws:apigateway:*::/apis/*)
      local api_id="${arn#*/apis/}"
      aws apigatewayv2 get-api --api-id "${api_id%%/*}" >/dev/null 2>&1
      ;;
    arn:aws:cloudformation:*:stack/*)
      local cfn_stack="${arn#*:stack/}"
      aws cloudformation describe-stacks \
        --stack-name "${cfn_stack%%/*}" >/dev/null 2>&1
      ;;
    arn:aws:s3:::*)
      aws s3api head-bucket --bucket "${arn#arn:aws:s3:::}" >/dev/null 2>&1
      ;;
    arn:aws:sns:*:*:*)
      aws sns get-topic-attributes --topic-arn "$arn" >/dev/null 2>&1
      ;;
    arn:aws:kms:*:*:key/*)
      aws kms describe-key --key-id "${arn##*/}" >/dev/null 2>&1
      ;;
    *)
      return 0
      ;;
  esac
}

filter_existing_tagged_resources() {
  local arn
  while IFS= read -r arn; do
    [[ -n "$arn" ]] || continue
    if tagged_resource_exists "$arn"; then
      printf '%s\n' "$arn"
    else
      printf 'stale tag entry: %s\n' "$arn" >&2
    fi
  done
}
