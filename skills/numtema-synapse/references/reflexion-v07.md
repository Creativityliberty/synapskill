# Synapse Reflexion Engine v0.7 — Private, opt-in quality gate

## Invariants

- **No public execution:** four anonymous MCP tools only. The `/mcp`, `/sse` and `/messages` HTTP transports must never run or configure Ollama.
- **Opt-in:** `llm_runtime.py` never calls a model unless `--execute`; it never performs the second model review unless `--reflexion` is set.
- **Two gates:** structural/deterministic CoR checks are applied to each draft **before** the review request. Only a draft passing both the deterministic checks and a well-typed review can be accepted.
- **Review is heuristic, not a fact check.** A model's positive verdict is not proof of factual accuracy, legal validity, safety, provenance or compliance. Human review is still necessary when consequential.
- **Correction loop:** when a draft or review is rejected, a bounded, explicit list of issues feeds back to the next attempt. Maximum attempts come from the contract's `max_revisions`; overall Ollama invocations are subject to `--max-calls`.
- **Fail closed:** malformed, contradictory or missing reviewer verdicts do not make a mission pass.
- **No transcript storage:** a review receipt keeps candidate SHA-256, attempt number, issues, suggestions and reviewer model. No persistent DB is opened; these receipts are returned in CLI JSON output and should be treated as potentially sensitive because issue texts can mention inputs.

## Run on a private host with Ollama installed

From project root:

```bash
python3 skills/numtema-synapse/scripts/llm_runtime.py \
  skills/numtema-synapse/examples/blueprint-local-llm.json \
  --model gemma3:1b --reflexion
# Dry run: PLANNED; no model call.

# First install/start Ollama and pull your chosen model(s) on a trusted private host.
python3 skills/numtema-synapse/scripts/llm_runtime.py \
  skills/numtema-synapse/examples/blueprint-local-llm.json \
  --model gemma3:1b --reviewer-model gemma3:1b \
  --reflexion --execute --max-calls 8 --output /tmp/synapse-review-receipt.json
```

If two local models are actually installed, choose a different `--reviewer-model`, for example `--reviewer-model <another-installed-model>`. With the same model, the critic is **a separate invocation with separate instructions**, *not* an independent model, authority or external verification. Different models can reduce correlated reasoning failures but still do not establish factual certainty.

## Critical technical contract

The review model must return **exactly**:

```json
{"passed": false, "issues": ["Promesse non étayée"], "suggestions": ["Supprimer le chiffre sans source"]}
```

`passed` is a JSON boolean; issues/suggestions are bounded arrays of nonblank strings, with at least one issue on failure and no issues on success. Unknown keys, stringified booleans, empty rejection issues, malformed arrays or oversized messages are rejected. The review cannot grant tool permissions.

`report.reflexion[task_id]` lists each attempt: `PASSED`, `REJECTED`, `REJECTED_STRUCTURE` or `REVIEW_INVALID`, with candidate digest and redacted issues. `report.model_calls` includes both author and reviewer calls. `report.assurance` is `structural_and_heuristic_review_only`, deliberately not `factually_verified`.

## Validation evidence

- 0.6 regression tests and 0.7 unit/wire tests are executed locally, using a **simulated local Ollama HTTP server**. This verifies request and response handling, DAG gates and CLI behavior.
- The package does **not** certify any installed Ollama model, external tool, hosted MCP client, deployment or security perimeter.
- On the intended host: test `ollama list`, then execute a fictional mission offline, inspect output and logs, and confirm Coolify still lists exactly four public tools.
