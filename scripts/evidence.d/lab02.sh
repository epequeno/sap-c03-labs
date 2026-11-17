#!/usr/bin/env bash
# Lab 2 evidence: two tenant users, one record per tenant, a 200 on the
# matching path and a 403 on the mismatched path. Raw JWTs never touch disk.
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/../lib.sh"

out="${1:?evidence directory}"
stack_json="$out/stack.json"

output() {
  jq -r --arg key "$1" '.Outputs[]? | select(.OutputKey == $key) | .OutputValue' \
    "$stack_json"
}

api_url="$(output ApiUrl)"
pool_id="$(output UserPoolId)"
client_id="$(output UserPoolClientId)"
table="$(output TableName)"
log_group="$(output LogGroupName)"

for value in "$api_url" "$pool_id" "$client_id" "$table" "$log_group"; do
  if [[ -z "$value" ]]; then
    echo "lab02 evidence: stack output missing; see $stack_json" >&2
    exit 1
  fi
done
api_url="${api_url%/}"

password_for() {
  printf 'Lab2-%saA1!' "$(openssl rand -hex 12)"
}

seed_user() {
  local username="$1" group="$2" password="$3"
  if ! aws cognito-idp admin-get-user \
    --user-pool-id "$pool_id" --username "$username" >/dev/null 2>&1; then
    aws cognito-idp admin-create-user \
      --user-pool-id "$pool_id" \
      --username "$username" \
      --user-attributes Name=email,Value="$username" \
      Name=email_verified,Value=true \
      --message-action SUPPRESS >/dev/null
  fi
  aws cognito-idp admin-set-user-password \
    --user-pool-id "$pool_id" \
    --username "$username" \
    --password "$password" \
    --permanent >/dev/null
  aws cognito-idp admin-add-user-to-group \
    --user-pool-id "$pool_id" \
    --username "$username" \
    --group-name "$group" >/dev/null 2>&1 || true
}

token_for() {
  local username="$1" password="$2" response
  response="$(aws cognito-idp admin-initiate-auth \
    --user-pool-id "$pool_id" \
    --client-id "$client_id" \
    --auth-flow ADMIN_USER_PASSWORD_AUTH \
    --auth-parameters USERNAME="$username",PASSWORD="$password")"
  jq -r '.AuthenticationResult.IdToken' <<<"$response"
}

claims_for() {
  python3 - "$1" <<'PY'
import base64
import json
import sys

payload = sys.argv[1].split(".")[1]
payload += "=" * (-len(payload) % 4)
print(json.dumps(json.loads(base64.urlsafe_b64decode(payload)), indent=2))
PY
}

call_api() {
  local token="$1" path="$2" label="$3"
  curl -sS -o "$out/$label.body.json" -w '%{http_code}' \
    -H "Authorization: Bearer $token" \
    "$api_url$path" >"$out/$label.status"
}

assert_status() {
  local expected="$1" label="$2" actual
  actual="$(<"$out/$label.status")"
  if [[ "$actual" != "$expected" ]]; then
    echo "lab02 evidence: $label expected $expected, got $actual" >&2
    exit 1
  fi
}

password_a="$(password_for)"
password_b="$(password_for)"
seed_user tenant-a@example.com tenant-a "$password_a"
seed_user tenant-b@example.com tenant-b "$password_b"

token_a="$(token_for tenant-a@example.com "$password_a")"
token_b="$(token_for tenant-b@example.com "$password_b")"
claims_for "$token_a" >"$out/token-claims-a.json"
claims_for "$token_b" >"$out/token-claims-b.json"

aws dynamodb put-item \
  --table-name "$table" \
  --item '{"tenant_id":{"S":"tenant-a"},"record_id":{"S":"record-a"},"payload":{"S":"tenant a record"}}'
aws dynamodb put-item \
  --table-name "$table" \
  --item '{"tenant_id":{"S":"tenant-b"},"record_id":{"S":"record-b"},"payload":{"S":"tenant b record"}}'

log_start_ms="$(( $(date -u +%s) * 1000 ))"
call_api "$token_a" "/tenants/tenant-a/records/record-a" happy-a
call_api "$token_a" "/tenants/tenant-b/records/record-b" denied-a-to-b
call_api "$token_b" "/tenants/tenant-b/records/record-b" happy-b

assert_status 200 happy-a
assert_status 403 denied-a-to-b
assert_status 200 happy-b

aws dynamodb get-item \
  --table-name "$table" \
  --key '{"tenant_id":{"S":"tenant-a"},"record_id":{"S":"record-a"}}' \
  --output json >"$out/item-a.json"
aws dynamodb get-item \
  --table-name "$table" \
  --key '{"tenant_id":{"S":"tenant-b"},"record_id":{"S":"record-b"}}' \
  --output json >"$out/item-b.json"

# Give the Lambda log a moment to reach CloudWatch, then copy the refusal.
count=0
for _ in 1 2 3 4 5 6; do
  sleep 5
  aws logs filter-log-events \
    --log-group-name "$log_group" \
    --start-time "$log_start_ms" \
    --filter-pattern 'tenant_mismatch' \
    --output json >"$out/tenant-mismatch-logs.json"
  count="$(jq '.events | length' "$out/tenant-mismatch-logs.json")"
  if [[ "$count" -gt 0 ]]; then
    break
  fi
done
if [[ "$count" -eq 0 ]]; then
  echo "lab02 evidence: tenant_mismatch log not found in CloudWatch" >&2
  exit 1
fi

echo "lab02: happy-a=$(<"$out/happy-a.status") denied-a-to-b=$(<"$out/denied-a-to-b.status") happy-b=$(<"$out/happy-b.status")"
