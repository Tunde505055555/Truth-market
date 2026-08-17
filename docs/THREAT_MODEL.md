# Threat model

| Threat | Mitigation |
| --- | --- |
| **Prompt injection in fetched pages** | Bodies are placed between explicit `BEGIN/END EVIDENCE (UNTRUSTED)` fences; the system text states the region is data and instructions inside it must never be followed. The claim itself is supplied outside the fence. |
| **Malicious / sockpuppet sources** | Domains are allowlisted deterministically before any fetch, and duplicate domains are rejected so "3 sources" cannot be one site three times. |
| **Unbounded payloads / gas griefing** | Claim text ≤ 600 chars, page bodies ≤ 4000 chars, excerpts ≤ 300–400 chars, at most 8 sources, summary/reasoning ≤ 1200 chars. |
| **SSRF / internal endpoints** | https-only plus allowlist; no user-controlled scheme or host reaches `web.render`. |
| **Model sampling noise forking consensus** | Confidence is bucketed to 10-point steps and only `verdict` + buckets + ordered stances enter the comparison digest; prose is excluded. |
| **Malformed model output** | `_extract_json` takes the outermost JSON object; unknown verdict/stance strings coerce to `INCONCLUSIVE` / `UNCLEAR`; missing stance entries are padded so the array always matches the source count. |
| **Overconfident verdicts** | A `TRUE` with no supporting source and a `FALSE` with no refuting source are downgraded to `INCONCLUSIVE` with confidence capped at 50. |
| **Non-convergence / liveness** | Appeals are bounded by `max_rounds` (1–5); exhaustion moves the claim to `DEADLOCKED`, settleable only by the pre-appointed arbiter. |
| **Privileged override** | `arbiter_settle` reverts unless status is `DEADLOCKED` and the caller is the arbiter; the owner can only change the evidence allowlist, never a verdict. |
| **Verdict mutation after the fact** | `finalize` moves a claim to `FINAL`; `verify` requires `SUBMITTED` and `appeal` requires `RULED`, so no path rewrites a finalised ruling. |
| **Non-determinism leaking into deterministic code** | No timestamps, randomness, floats or iteration over unordered Python dicts; all JSON serialisation uses `sort_keys=True` and compact separators. |
