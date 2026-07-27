# Context Replay Benchmark

This benchmark measures orchestration context for the isolated synthetic
`Shape Scout` run. It compares repeated full-plan reconstruction with the
Plugin's persistent state-machine workflow.

## Result

| Metric | Repeated planning | Plugin workflow |
|---|---:|---:|
| Visual jobs | 13 | 13 |
| Generation attempts | 13 | 13 |
| Retries | 0 | 0 |
| Orchestration-context tokens | 109,515 | 11,964 |
| Completed-stage re-plans | 13 | 0 |
| Largest controller action | — | 872 bytes |

The measured orchestration-context reduction is **89.08%**.

The conservative repeated-planning baseline reloads the Skill instructions,
references, request, complete job graph, and state before each visual job, then
adds only that job's prompt. An exhaustive variant that reloads all prompt
templates on every step measures 245,219 tokens, a 95.12% reduction.

This is a deterministic local context replay using `o200k_base`. It is not a
measurement of API billing, hidden reasoning, image-generation tokens, cached
input, or model output.

## Reproduce

Use a completed synthetic run containing `pet_request.json`,
`imagegen-jobs.json`, `pipeline-state.json`, and its `prompts/` directory:

```powershell
python -m pip install -r benchmarks/requirements.txt
python benchmarks/context_replay.py `
  --plugin-root . `
  --run-dir <synthetic-run-directory> `
  --output benchmark-result.json
```

The script reads text and JSON only. It does not inspect image pixels, send
network requests, or modify the run directory. Machine-specific absolute paths
are scrubbed before tokenization, and the published result contains metrics
only.

The checked-in result is
[`benchmarks/results/shape-scout-rc1.json`](benchmarks/results/shape-scout-rc1.json).
