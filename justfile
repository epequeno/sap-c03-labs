# sap-c03-labs: one lab deployed, evidenced, destroyed
set shell := ["bash", "-uc"]

default:
    @just --list

sync:
    @uv sync --quiet

synth lab="02":
    @cd infra && uv run cdk synth -c lab="{{lab}}" --quiet

deploy lab="02":
    @./scripts/deploy.sh {{lab}}

evidence lab="02":
    @./scripts/evidence.sh {{lab}}

destroy lab="02":
    @./scripts/teardown.sh {{lab}}

preflight:
    @./scripts/preflight.sh

labs:
    @for d in labs/*/; do printf '%s\n' "${d%/}"; done
