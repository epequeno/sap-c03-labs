# sap-c03-labs: one lab deployed, evidenced, destroyed
set shell := ["bash", "-uc"]

default:
    @just --list

sync:
    @uv sync --quiet

fmt:
    @uv run ruff format .
    @uv run ruff check --fix .

lint:
    @uv run ruff check .
    @uv run ruff format --check .

test:
    @uv run pytest -q

verify: lint test synth

cfn-lint:
    @if ls infra/cdk.out/*.template.json >/dev/null 2>&1; then \
      uv run cfn-lint infra/cdk.out/*.template.json || \
        echo "cfn-lint findings are advisory (non-blocking)"; \
    else \
      echo "no synthesized template for cfn-lint"; \
    fi

quality: verify cfn-lint

nag lab="02":
    @source ./scripts/lib.sh && export AWS_PROFILE="$SAP_LABS_PRIMARY_PROFILE" && cd infra && \
      out="$(uv run cdk synth -c lab="{{lab}}" -c nag=1 --quiet 2>&1)"; \
      rc=$?; printf '%s\n' "$out"; \
      if [ $rc -ne 0 ]; then echo "cdk-nag findings are advisory (non-blocking)"; fi

synth lab="02":
    @source ./scripts/lib.sh && export AWS_PROFILE="$SAP_LABS_PRIMARY_PROFILE" && cd infra && \
      uv run cdk synth -c lab="{{lab}}" --quiet

deploy lab="02":
    @./scripts/deploy.sh {{lab}}

member-deploy lab="04":
    @./scripts/lab04_member.sh {{lab}} deploy

member-destroy lab="04":
    @./scripts/lab04_member.sh {{lab}} destroy

evidence lab="02":
    @./scripts/evidence.sh {{lab}}

destroy lab="02":
    @./scripts/teardown.sh {{lab}}

preflight:
    @./scripts/preflight.sh

labs:
    @for d in labs/*/; do printf '%s\n' "${d%/}"; done
