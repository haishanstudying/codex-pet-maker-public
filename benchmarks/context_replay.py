#!/usr/bin/env python3
"""Measure orchestration context for a completed synthetic pet run.

This benchmark reads text and JSON only. It never reads image pixels, sends
network requests, or writes into the run directory.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import tiktoken


ENCODING = "o200k_base"


def scrub(value: Any, run_dir: Path) -> Any:
    """Remove machine-specific paths while preserving equivalent text size."""
    if isinstance(value, dict):
        return {key: scrub(item, run_dir) for key, item in value.items()}
    if isinstance(value, list):
        return [scrub(item, run_dir) for item in value]
    if isinstance(value, str):
        normalized = value.replace("\\", "/")
        root = str(run_dir).replace("\\", "/")
        if normalized.lower().startswith(root.lower()):
            return "<RUN_DIR>" + normalized[len(root) :]
        if len(normalized) >= 3 and normalized[1:3] == ":/":
            return "<LOCAL_PATH>"
    return value


def compact_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def text_file(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def tokens(encoding: tiktoken.Encoding, text: str) -> int:
    return len(encoding.encode(text))


def action_for(job: dict[str, Any], state: dict[str, Any]) -> str:
    job_state = state["jobs"][job["id"]]
    action = {
        "action": "generate",
        "job": job["id"],
        "kind": job["kind"],
        "prompt": job["prompt_file"],
        "inputs": [
            {"path": item["path"], "role": item["role"]}
            for item in job.get("input_images", [])
        ],
        "output": job["output_path"],
        "attempt": job_state["attempts"],
        "maxAttempts": job_state["maxAttempts"],
    }
    return compact_json(action)


def run_benchmark(plugin_root: Path, run_dir: Path) -> dict[str, Any]:
    encoding = tiktoken.get_encoding(ENCODING)
    skill_root = plugin_root / "skills" / "make-codex-pet"
    skill_files = [skill_root / "SKILL.md", *sorted((skill_root / "references").glob("*.md"))]
    skill_context = "\n\n".join(text_file(path) for path in skill_files)

    request = scrub(json.loads(text_file(run_dir / "pet_request.json")), run_dir)
    jobs_document = scrub(json.loads(text_file(run_dir / "imagegen-jobs.json")), run_dir)
    state = scrub(json.loads(text_file(run_dir / "pipeline-state.json")), run_dir)
    jobs = jobs_document["jobs"]

    prompt_files = sorted((run_dir / "prompts").rglob("*.md"))
    all_prompts = "\n\n".join(text_file(path) for path in prompt_files)
    request_text = compact_json(request)
    jobs_text = compact_json(jobs_document)
    state_text = compact_json(state)

    # Plugin replay: load stable instructions/request once, then emit one compact
    # next action plus only that job's prompt.
    initial_context = "\n\n".join([skill_context, request_text])
    action_payloads: list[str] = []
    incremental_tokens = tokens(encoding, initial_context)
    selected_prompt_tokens = 0
    for job in jobs:
        action = action_for(job, state)
        prompt = text_file(run_dir / job["prompt_file"])
        action_payloads.append(action)
        incremental_tokens += tokens(encoding, action)
        prompt_count = tokens(encoding, prompt)
        selected_prompt_tokens += prompt_count
        incremental_tokens += prompt_count

    # Conservative baseline: reconstruct instructions, request, complete job
    # graph, and state before every job, but include only the selected prompt.
    core_plan = "\n\n".join([skill_context, request_text, jobs_text, state_text])
    baseline_tokens = (
        tokens(encoding, core_plan) * len(jobs) + selected_prompt_tokens
    )
    # Exhaustive baseline also reloads every available prompt on every step.
    exhaustive_plan = "\n\n".join(
        [skill_context, request_text, jobs_text, state_text, all_prompts]
    )
    exhaustive_tokens = tokens(encoding, exhaustive_plan) * len(jobs)

    reduction = 100 * (baseline_tokens - incremental_tokens) / baseline_tokens
    return {
        "schema_version": 1,
        "workload": "synthetic completed pet run",
        "tokenizer": ENCODING,
        "visual_jobs": len(jobs),
        "generation_attempts": sum(state["jobs"][job["id"]]["attempts"] for job in jobs),
        "retries": sum(
            max(0, state["jobs"][job["id"]]["attempts"] - 1) for job in jobs
        ),
        "inputs": {
            "skill_files": len(skill_files),
            "prompt_files": len(prompt_files),
            "selected_job_prompts": len(jobs),
        },
        "baseline": {
            "method": (
                "core plan reloaded before every visual job; only the selected "
                "job prompt included"
            ),
            "tokens": baseline_tokens,
            "full_plan_replays": len(jobs),
        },
        "exhaustive_baseline": {
            "method": "core plan and all prompt templates reloaded before every job",
            "tokens": exhaustive_tokens,
            "context_token_reduction_percent": round(
                100 * (exhaustive_tokens - incremental_tokens) / exhaustive_tokens,
                2,
            ),
        },
        "plugin": {
            "method": "stable context once, then compact action plus selected prompt",
            "tokens": incremental_tokens,
            "completed_stage_replans": 0,
            "selected_prompt_tokens": selected_prompt_tokens,
            "max_controller_output_bytes": max(
                len(payload.encode("utf-8")) for payload in action_payloads
            ),
        },
        "context_token_reduction_percent": round(reduction, 2),
        "scope_note": (
            "Deterministic local orchestration-context replay; not API billing, "
            "hidden reasoning, image-generation, cached-input, or output tokens."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--plugin-root", type=Path, required=True)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    result = run_benchmark(args.plugin_root.resolve(), args.run_dir.resolve())
    rendered = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
