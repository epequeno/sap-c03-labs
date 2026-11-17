# SAP-C03 labs

Seven small, disposable AWS labs that cover the SAP-C03 task list. Each one is deployed from CDK, evidenced, and destroyed the same day. Lab 02 is implemented; labs 01 and 03–07 are seeded with the artifact standard and are the study work.

The lab plan and study notes stay out of this repo; each lab README carries the question, artifact standard, and exam mapping. Implementation order and feasibility gates: `docs/implementation-order.md`.

## Rules

- **Sandbox account only.** Never production, never a shared org account.
- Primary Region `us-east-1`, DR Region `us-west-2`.
- Every resource carries `Project=sap-c03-labs`, `Lab=<NN>`, `Owner=steven`, `TearDown=<date>`. The app applies them; do not add resources outside a stack.
- **≤ $10 per lab**, **≤ $30 total**. Everything is destroyed the same day. No dedicated budget resource is created; same-day teardown and the recorded spend are the control.
- Do not modify existing SCPs or org-wide services. Create a new OU/SCP or a standalone stack, then remove it.
- Do not deploy Control Tower, Security Lake, or org-wide GuardDuty for a lab. Use the lightweight equivalent and say so in the lab README.
- If a feature is unavailable in the account or Region, record the blocked API call and produce a design artifact instead of forcing it.

## Use

```bash
just verify             # local gate: ruff, pytest, synth
just preflight          # identity, Region, and visible budget/monitor
just deploy 02          # uv sync, synth, deploy, then capture evidence
just evidence 02        # re-capture without deploying
just destroy 02         # cdk destroy, then assert no tagged resources remain
```

Local CI is `just verify`: `ruff check`, `ruff format --check`, `pytest`, and `cdk synth`. Remote CI is deferred until the labs are finalized.

Commands default to the `arch` profile and `us-east-1`, set in `scripts/lib.sh`; the `synth` recipe sources the same file. Override with `AWS_PROFILE=<profile>` for a one-off. Credentials come from that profile and are never stored in the repo.

One stack exists at a time, selected by CDK context: `cdk deploy -c lab=02`. The app registers only stacks that have been written, so `lab=01` fails loudly until `infra/stacks/lab01_agentic_rag.py` exists.

## Layout

```
infra/
  app.py                     # stack registry, tags, one stack per run
  cdk.json
  lambda/lab02/handler.py    # lab 2 request handler
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
  evidence.d/                # lab-specific evidence hooks
  teardown.sh
tests/                       # handler and stack tests
docs/implementation-order.md
LICENSE
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
- Redact account IDs, ARNs, principal names, request IDs, and raw bearer tokens in captured evidence. `evidence.sh` redacts the caller identity and account ID by default; lab hooks must not write raw tokens.
- Keep `.env` and local profile configuration out of git. Only the profile name belongs in `scripts/lib.sh`.
- Run `just verify` before committing.

## License

MIT. See `LICENSE`.

## Cost visibility

Tag-based cost queries need `Project` (and optionally `Lab`) activated as cost allocation tags in the Billing console. A linked account that cannot list cost allocation tags returns an error, and the scripts record that error rather than pretending the spend is zero.
