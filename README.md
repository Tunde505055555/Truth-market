# TruthMarket — an evidence-grounded claim verification primitive for GenLayer

Contract-only repository. No frontend, no server-side AI gateway, no consensus
simulator — just the Intelligent Contract, its tests, docs, examples and
deployment tooling.

```
contracts/truth_market.py      the Intelligent Contract (GenVM, py-genlayer v0.2.16)
tests/test_truth_market.py     contract tests (pure-logic + genlayer-test hooks)
scripts/deploy.py              deploy / configure via genlayer-py
scripts/lint.py               GenVM-oriented static lint
examples/claims.json           sample claims + allowlisted source sets
docs/ARCHITECTURE.md           state machine and consensus rules
docs/THREAT_MODEL.md           hostile-input and manipulation analysis
```

## Dependency pin

The contract declares the exact runtime hash required by GenVM v0.2.16:

```python
# v0.2.16
# { "Depends": "py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6" }
```

The comment pair must be the first two lines of the file, before the docstring.

## What it does

A user submits a factual claim. The network researches it against multiple
**independent** allowlisted web sources, reconciles the evidence, and records
on-chain:

| Field              | Meaning                                                     |
| ------------------ | ----------------------------------------------------------- |
| `text`             | the claim as submitted (flattened, capped at 600 chars)      |
| `sources[]`        | url, domain, per-source stance, quoted excerpt              |
| `evidence_summary` | what the sources collectively establish                     |
| `verdict`          | `TRUE` / `FALSE` / `PARTIALLY_TRUE` / `INCONCLUSIVE`        |
| `confidence`       | 0–100, bucketed to 10-point steps for validator agreement   |
| `rulings[]`        | full per-round history incl. reasoning and decision digest  |

## State machine

```text
                submit_claim
                     |
                     v
                 SUBMITTED
                     |  verify(claim_id, urls)        <- round 1, strict digest eq
                     v
                   RULED  --------- finalize() -------> FINAL (immutable)
                     |
                     |  appeal(claim_id, urls)        <- stricter, LLM-judged
                     |     (round_no + 1 <= max_rounds)
                     |
                     +--- rounds exhausted ---------> DEADLOCKED
                                                          |
                                            arbiter_settle() -> FINAL
```

## Consensus design

1. **Comparable decisions.** The model's free-form answer is reduced to
   `verdict`, bucketed `confidence` and an ordered `source_stances` array.
   Validators may write different prose but must agree on the decision.
2. **Tiered strictness.** Round 1 uses `gl.vm.run_nondet_unsafe` with a custom
   validator that compares only the canonical decision digest. Appeal rounds use
   `gl.eq_principle.prompt_comparative`, so the *reasoning* is LLM-judged too.
3. **Corroboration guard.** `TRUE` requires at least one supporting source and
   `FALSE` at least one refuting source, else the verdict is downgraded to
   `INCONCLUSIVE` and confidence capped at 50.
4. **Bounded rounds.** `max_rounds` (1–5) caps appeals; exhaustion routes to
   `DEADLOCKED` and a pre-appointed arbiter. A primitive that can hang forever
   is not usable in production.

## Deployment parameters

```python
TruthMarket(
    arbiter="0x...",                                     # deadlock settler
    allowed_domains=["reuters.com", "apnews.com", ...],   # evidence allowlist
    min_sources=3,
    max_rounds=3,
)
```

Nothing about fact-checking is hardcoded: swap the allowlist and the same
deployment serves oracle disputes, insurance triage, or grant reporting.

## Usage

```bash
python scripts/lint.py                 # GenVM-oriented static checks
python -m pytest tests -q              # contract tests
python scripts/deploy.py --help        # deploy against studio or a network
```
