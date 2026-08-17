# Architecture

## Storage schema

All persisted types are GenVM storage-safe: fixed-width ints (`u8`, `u256`),
`str`, `Address`, `DynArray`, `TreeMap`, and `@allow_storage @dataclass`
structs. No `Optional`, no bare `list`/`dict`, no floats — floats and unions are
the two most common causes of "contract schema" deployment errors.

```
owner            Address
arbiter          Address
allowed_domains  DynArray[str]
min_sources      u8
max_rounds       u8
next_id          u256
claims           TreeMap[u256, Claim]
claims_of        TreeMap[Address, DynArray[u256]]

Claim   = { id u256, author Address, text str, status u8, verdict u8,
            confidence u8, evidence_summary str, round_no u8,
            sources DynArray[Source], rulings DynArray[Ruling] }
Source  = { url str, domain str, stance u8, excerpt str }
Ruling  = { round_no u8, verdict u8, confidence u8, evidence_summary str,
            reasoning str, digest str }
```

Nested collections are never constructed in Python and assigned wholesale.
Rows are materialised in storage first (`TreeMap.get_or_insert_default`,
`DynArray.append_new_get`) and then written field by field.

## Enumerations

| Status         | Code | Verdict           | Code | Stance     | Code |
| -------------- | ---- | ----------------- | ---- | ---------- | ---- |
| SUBMITTED      | 0    | PENDING           | 0    | UNCLEAR    | 0    |
| RULED          | 1    | TRUE              | 1    | SUPPORTS   | 1    |
| FINAL          | 2    | FALSE             | 2    | REFUTES    | 2    |
| DEADLOCKED     | 3    | PARTIALLY_TRUE    | 3    | MIXED      | 3    |
|                |      | INCONCLUSIVE      | 4    |            |      |

## Execution phases of `verify` / `appeal`

1. **Deterministic gate** (`_check_sources`) — identical on every validator:
   https-only, allowlisted domain, distinct domains (independence), count within
   `min_sources`..`MAX_SOURCES`. Runs *before* any network access.
2. **Non-deterministic research block** — inside `run_nondet_unsafe` /
   `prompt_comparative`: each URL is rendered with
   `gl.nondet.web.render(url, mode="text")`, clipped to 4000 chars, fenced and
   labelled untrusted; then a single `gl.nondet.exec_prompt` reconciles them.
3. **Deterministic normalisation** (`_normalize`) — JSON extraction, verdict and
   stance coercion, confidence bucketing, corroboration guard.
4. **Deterministic write-back** — sources replaced, verdict/confidence/summary
   updated, ruling appended, status set to `RULED`.

## Comparison rules

Round 1 validator:

```
digest = {"verdict": int, "confidence": bucket10, "stances": [int, ...]}
accept iff json(digest_mine) == json(digest_leader)   # byte-for-byte
```

Appeal rounds add an LLM-judged principle over the same payload: verdict and
stances must match exactly, buckets must be identical, and the reasoning must
rest on the same evidence for the same stated cause.

## Extending the primitive

`_rule` logic lives in module-level pure helpers (`_normalize`, `_digest`,
`_research_prompt`), so the consensus core can be lifted into another contract
with the storage layer swapped out.
