# Lab 1 — Agentic RAG with Guardrails

**Stack:** not written. `infra/stacks/lab01_agentic_rag.py`, registered in `infra/app.py`.

## Question

Given a corpus the customer controls, where do the safety boundaries sit in a retrieval-augmented agent, and which of them survive a prompt that tries to defeat them?

## Constraints

- `us-east-1`, sandbox account, one day.
- Cost cap **$5–10**. OpenSearch Serverless carries a minimum OCU cost: if S3 Vectors is unavailable in the account, keep the stack alive under two hours and destroy it immediately.
- No customer data. Corpus is synthetic and committed under this folder.
- One Region only. Multi-Region retrieval is a design note, not a deploy.

## Build

S3 corpus → Bedrock Knowledge Base → vector store (S3 Vectors preferred, OpenSearch Serverless otherwise). A small agent path through AgentCore Gateway or Runtime. Bedrock Guardrails with a denied topic and a prompt-injection filter. CloudWatch logs and the cost tag.

## Failure to demonstrate

A prompt asking the agent to ignore its instructions or reveal another tenant's data. Capture the guardrail block and the safe response, plus the log line that shows the block rather than a silent refusal.

## Evidence

Knowledge Base ID, retrieved chunks for one query, allowed vs blocked prompts side by side, token counts, CloudWatch metrics, cost report, architecture diagram.

## Exam mapping

1.2.1–1.2.4 (GenAI and agentic design), 2.5.1–2.5.3 (responsible AI), 3.1.4 (AI cost), 5.3.5 (AI/ML metrics).

## Still to fill

- [ ] Diagram, committed as Mermaid or SVG
- [ ] Deploy section with the exact commands
- [ ] Evidence folder committed
- [ ] `cost.md` with teardown timestamp
- [ ] Interview line: the trade-off, not the service list
