# SAP-C03 labs

Seven small, disposable AWS labs that cover the SAP-C03 task list. Each one is deployed from CDK, evidenced, and destroyed the same day. This is scaffold: the repo, the tooling, and one seeded README per lab exist; the stack bodies are the study work.

The lab plan and study notes stay out of this repo; each lab README carries the question, artifact standard, and exam mapping.

## Rules

- **Sandbox account only.** Never production, never a shared org account.
- Primary Region `us-east-1`, DR Region `us-west-2`.
- Every resource carries `Project=sap-c03-labs`, `Lab=<NN>`, `Owner=steven`, `TearDown=<date>`. The app applies them; do not add resources outside a stack.
- **≤ $10 per lab**, **≤ $30 total**. Everything is destroyed the same day.
- Do not modify existing SCPs or org-wide services. Create a new OU/SCP or a standalone stack, then remove it.
- Do not deploy Control Tower, Security Lake, or org-wide GuardDuty for a lab. Use the lightweight equivalent and say so in the lab README.
- If a feature is unavailable in the account or Region, record the blocked API call and produce a design artifact instead of forcing it.

## Use

```bash
just preflight          # identity, Region, budget and anomaly-monitor check
just deploy 02          # uv sync, synth, deploy, then capture evidence
just evidence 02        # re-capture without deploying
just destroy 02         # cdk destroy, then assert no tagged resources remain
```

Commands default to the `arch` profile and `us-east-1`, set in `scripts/lib.sh`; the `synth` recipe sources the same file. Override with `AWS_PROFILE=<profile>` for a one-off. Credentials come from that profile and are never stored in the repo.

One stack exists at a time, selected by CDK context: `cdk deploy -c lab=02`. The app registers only stacks that have been written, so `lab=01` fails loudly until `infra/stacks/lab01_agentic_rag.py` exists.

## Layout

```
infra/
  app.py                     # stack registry, tags, one stack per run
  cdk.json
  stacks/
    lab02_multitenant_api.py # written
labs/
  01-agentic-rag/            # README seeded with the artifact standard
  ...
  07-network/
scripts/
  lib.sh                     # lab number -> slug, shared helpers
  preflight.sh
  deploy.sh
  evidence.sh
  teardown.sh
```

CDK lives under `infra/`; one convention per repo wins.

## Artifact standard

Every lab README carries:

1. **Question** — the architecture decision the lab tests.
2. **Constraints** — cost, Region, account, availability target.
3. **Diagram** — committed, Mermaid or SVG.
4. **Deploy** — exact commands and prerequisites.
5. **Evidence** — CLI output, screenshots, logs, metrics, test results, under `labs/<slug>/evidence/<utc-timestamp>/`.
6. **Failure** — one deliberately broken or denied path, with the observed result.
7. **Cost** — actual spend from Cost Explorer, and the teardown timestamp, in `labs/<slug>/cost.md`.
8. **Exam mapping** — task and skill numbers from the SAP-C03 guide.
9. **Interview line** — one paragraph on the trade-off, not a service list.

`scripts/teardown.sh` writes the teardown timestamp into `cost.md` and fails if any tagged resource survives.

## Public-repo hygiene

This repo is public. Before committing:

- No credentials, tokens, private keys, or `cdk.context.json`.
- Redact account IDs, ARNs, principal names, request IDs, and resource names that identify an account in captured evidence.
- Keep `.env` and local profile configuration out of git. Only the profile name belongs in `scripts/lib.sh`.

## Cost visibility

Tag-based cost queries need `Project` (and optionally `Lab`) activated as cost allocation tags in the Billing console. Until then `aws ce` returns nothing for the tag filter, and `evidence.sh` records that error rather than pretending the spend is zero.
