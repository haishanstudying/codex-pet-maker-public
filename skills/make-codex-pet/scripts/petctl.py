#!/usr/bin/env python3
"""Small persistent controller for the Codex v2 pet pipeline."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


HERE = Path(__file__).resolve().parent
STATE_NAME = "pipeline-state.json"
STANDARD = {
    "idle",
    "running-right",
    "running-left",
    "waving",
    "jumping",
    "failed",
    "waiting",
    "running",
    "review",
}
LOOK = {"look-cardinals", "look-row-9", "look-row-10"}


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def emit(value: dict, code: int = 0) -> None:
    print(json.dumps(value, ensure_ascii=False, separators=(",", ":")))
    raise SystemExit(code)


def run_dir(value: str) -> Path:
    return Path(value).expanduser().resolve()


def state_paths(root: Path) -> tuple[Path, Path]:
    return root / STATE_NAME, root / "imagegen-jobs.json"


def load_run(root: Path) -> tuple[dict, dict]:
    state_path, manifest_path = state_paths(root)
    if not state_path.is_file() or not manifest_path.is_file():
        emit({"ok": False, "error": "run is not initialized"}, 2)
    return read_json(state_path), read_json(manifest_path)


def save_run(root: Path, state: dict, manifest: dict) -> None:
    state_path, manifest_path = state_paths(root)
    write_json(state_path, state)
    write_json(manifest_path, manifest)


def execute(*args: str) -> None:
    command = [sys.executable, str(HERE / args[0]), *args[1:]]
    result = subprocess.run(command, text=True, capture_output=True)
    if result.returncode:
        detail = (result.stderr or result.stdout or "command failed").strip()[-500:]
        raise RuntimeError(f"{args[0]}: {detail}")


def job_map(manifest: dict) -> dict[str, dict]:
    return {job["id"]: job for job in manifest["jobs"]}


def set_manifest_status(manifest: dict, job_id: str, status: str, source: str | None = None) -> None:
    for job in manifest["jobs"]:
        if job["id"] == job_id:
            job["status"] = status
            if source:
                job["source_path"] = source
                job["completed_at"] = now()
            return
    raise KeyError(job_id)


def mark_failure(root: Path, state: dict, manifest: dict, job_id: str, reason: str) -> None:
    item = state["jobs"][job_id]
    item["lastError"] = reason[-500:]
    item["status"] = "blocked" if item["attempts"] >= item["maxAttempts"] else "pending"
    set_manifest_status(manifest, job_id, item["status"])
    state["status"] = "blocked" if item["status"] == "blocked" else "active"
    state["updatedAt"] = now()
    save_run(root, state, manifest)


def command_init(args: argparse.Namespace) -> None:
    root = run_dir(args.run_dir)
    command = [
        sys.executable,
        str(HERE / "prepare_pet_run.py"),
        "--output-dir",
        str(root),
        "--pet-name",
        args.pet_name,
        "--style-preset",
        args.style_preset,
        "--chroma-key",
        args.chroma_key,
        "--force",
    ]
    if args.reference:
        command += ["--reference", str(Path(args.reference).expanduser().resolve())]
    if args.description:
        command += ["--description", args.description]
    if args.pet_notes:
        command += ["--pet-notes", args.pet_notes]
    if args.style_notes:
        command += ["--style-notes", args.style_notes]
    result = subprocess.run(command, text=True, capture_output=True)
    if result.returncode:
        emit({"ok": False, "error": (result.stderr or result.stdout).strip()[-500:]}, 1)

    manifest = read_json(root / "imagegen-jobs.json")
    jobs = {}
    for job in manifest["jobs"]:
        max_attempts = 3 if job["id"] in LOOK else 2
        jobs[job["id"]] = {
            "status": "pending",
            "attempts": 0,
            "maxAttempts": max_attempts,
            "lastError": None,
        }
    state = {
        "schemaVersion": 1,
        "mode": args.mode,
        "status": "active",
        "createdAt": now(),
        "updatedAt": now(),
        "jobs": jobs,
        "standardReady": False,
        "deterministicReady": False,
        "visualApproved": False,
        "visualNotes": None,
        "package": None,
        "installed": None,
    }
    write_json(root / STATE_NAME, state)
    emit({"ok": True, "run": str(root), "jobs": len(jobs), "mode": args.mode})


def command_next(args: argparse.Namespace) -> None:
    root = run_dir(args.run_dir)
    state, manifest = load_run(root)
    if all(state["jobs"][name]["status"] == "complete" for name in STANDARD) and not state["standardReady"]:
        emit({"action": "build-standard"})
    for job in manifest["jobs"]:
        item = state["jobs"][job["id"]]
        if item["status"] in {"complete", "blocked"}:
            continue
        if all(state["jobs"][dep]["status"] == "complete" for dep in job.get("depends_on", [])):
            prompt_key = (
                "retry_prompt_file"
                if item["attempts"] and "retry_prompt_file" in job
                else "prompt_file"
            )
            emit(
                {
                    "action": "generate",
                    "job": job["id"],
                    "kind": job["kind"],
                    "attempt": item["attempts"] + 1,
                    "maxAttempts": item["maxAttempts"],
                    "prompt": str(root / job[prompt_key]),
                    "manifest": str(root / "imagegen-jobs.json"),
                }
            )
    blocked = [job_id for job_id, item in state["jobs"].items() if item["status"] == "blocked"]
    if blocked:
        emit({"action": "blocked", "jobs": blocked}, 1)
    if all(item["status"] == "complete" for item in state["jobs"].values()):
        emit({"action": "finalize" if state["standardReady"] else "build-standard"})
    emit({"action": "waiting", "reason": "dependencies are incomplete"})


def incremental_check(root: Path, job_id: str) -> None:
    if job_id in STANDARD:
        row_root = root / "qa" / "rows" / job_id
        execute(
            "extract_strip_frames.py",
            "--decoded-dir",
            str(root / "decoded"),
            "--output-dir",
            str(row_root / "frames"),
            "--states",
            job_id,
            "--method",
            "auto",
        )
        execute(
            "inspect_frames.py",
            "--frames-root",
            str(row_root / "frames"),
            "--json-out",
            str(row_root / "review.json"),
            "--states",
            job_id,
            "--require-components",
        )
        review = read_json(row_root / "review.json")
        if review.get("errors"):
            raise RuntimeError("; ".join(review["errors"][:3]))
    elif job_id == "look-cardinals":
        request = read_json(root / "pet_request.json")
        key = request["chroma_key"]["hex"]
        execute(
            "extract_cardinal_anchors.py",
            "--strip",
            str(root / "decoded" / "look-cardinals.png"),
            "--output-dir",
            str(root / "decoded" / "look-anchors"),
            "--chroma-key",
            key,
            "--json-out",
            str(root / "qa" / "cardinal-anchors.json"),
        )
        execute(
            "compose_cardinal_anchor_strip.py",
            "--anchors-dir",
            str(root / "decoded" / "look-anchors"),
            "--output",
            str(root / "decoded" / "look-anchors-approved.png"),
        )
    elif job_id == "look-row-9":
        request = read_json(root / "pet_request.json")
        execute(
            "assemble_extended_atlas.py",
            "--base-atlas",
            str(root / "final" / "spritesheet.webp"),
            "--look-row-9",
            str(root / "decoded" / "look-row-9.png"),
            "--chroma-key",
            request["chroma_key"]["hex"],
            "--chroma-threshold",
            "96",
            "--registered-row-output",
            str(root / "qa" / "look-row-9-registered.png"),
            "--registration-manifest-output",
            str(root / "qa" / "look-row-9-registration.json"),
        )


def command_record(args: argparse.Namespace) -> None:
    root = run_dir(args.run_dir)
    source = Path(args.source).expanduser().resolve()
    if not source.is_file():
        emit({"ok": False, "error": "generated source is missing"}, 2)
    state, manifest = load_run(root)
    jobs = job_map(manifest)
    if args.job not in jobs:
        emit({"ok": False, "error": "unknown job"}, 2)
    item = state["jobs"][args.job]
    if item["status"] == "complete":
        emit({"ok": True, "job": args.job, "status": "already-complete"})
    item["attempts"] += 1
    destination = root / jobs[args.job]["output_path"]
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)
    if args.job == "base":
        canonical = root / "references" / "canonical-base.png"
        canonical.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(destination, canonical)
    try:
        incremental_check(root, args.job)
    except Exception as exc:
        mark_failure(root, state, manifest, args.job, str(exc))
        emit(
            {
                "ok": False,
                "job": args.job,
                "status": state["jobs"][args.job]["status"],
                "attempts": item["attempts"],
                "error": str(exc)[-300:],
            },
            1,
        )
    item["status"] = "complete"
    item["lastError"] = None
    set_manifest_status(manifest, args.job, "complete", str(source))
    state["updatedAt"] = now()
    save_run(root, state, manifest)
    emit({"ok": True, "job": args.job, "status": "complete", "attempts": item["attempts"]})


def command_repair(args: argparse.Namespace) -> None:
    root = run_dir(args.run_dir)
    state, manifest = load_run(root)
    if args.job not in state["jobs"]:
        emit({"ok": False, "error": "unknown job"}, 2)
    item = state["jobs"][args.job]
    item["lastError"] = args.reason
    item["status"] = "blocked" if item["attempts"] >= item["maxAttempts"] else "pending"
    set_manifest_status(manifest, args.job, item["status"])
    state["status"] = "blocked" if item["status"] == "blocked" else "active"
    state["updatedAt"] = now()
    save_run(root, state, manifest)
    emit(
        {"ok": item["status"] != "blocked", "job": args.job, "status": item["status"]},
        1 if item["status"] == "blocked" else 0,
    )


def command_standard(args: argparse.Namespace) -> None:
    root = run_dir(args.run_dir)
    state, manifest = load_run(root)
    if any(state["jobs"][name]["status"] != "complete" for name in STANDARD):
        emit({"ok": False, "error": "standard rows are incomplete"}, 2)
    try:
        execute(
            "extract_strip_frames.py",
            "--decoded-dir",
            str(root / "decoded"),
            "--output-dir",
            str(root / "frames"),
            "--states",
            "all",
            "--method",
            "auto",
        )
        execute(
            "inspect_frames.py",
            "--frames-root",
            str(root / "frames"),
            "--json-out",
            str(root / "qa" / "review.json"),
            "--require-components",
        )
        execute(
            "compose_atlas.py",
            "--frames-root",
            str(root / "frames"),
            "--output",
            str(root / "final" / "spritesheet.png"),
            "--webp-output",
            str(root / "final" / "spritesheet.webp"),
        )
        execute(
            "make_contact_sheet.py",
            str(root / "final" / "spritesheet.webp"),
            "--output",
            str(root / "qa" / "contact-sheet.png"),
        )
        execute(
            "render_animation_previews.py",
            "--frames-root",
            str(root / "frames"),
            "--output-dir",
            str(root / "qa" / "previews"),
        )
    except Exception as exc:
        emit({"ok": False, "error": str(exc)[-400:]}, 1)
    state["standardReady"] = True
    state["updatedAt"] = now()
    save_run(root, state, manifest)
    emit({"ok": True, "standardReady": True, "contactSheet": str(root / "qa" / "contact-sheet.png")})


def first_idle(root: Path) -> Path | None:
    files = sorted((root / "frames" / "idle").glob("*.png"))
    return files[0] if files else None


def command_finalize(args: argparse.Namespace) -> None:
    root = run_dir(args.run_dir)
    state, manifest = load_run(root)
    if not state["standardReady"] or any(item["status"] != "complete" for item in state["jobs"].values()):
        emit({"ok": False, "error": "generation is incomplete"}, 2)
    request = read_json(root / "pet_request.json")
    key = request["chroma_key"]["hex"]
    final_png = root / "final" / "spritesheet-extended.png"
    final_webp = root / "final" / "spritesheet-extended.webp"
    clean_png = root / "final" / "spritesheet-extended-clean.png"
    clean_webp = root / "final" / "spritesheet-extended-clean.webp"
    command = [
        "assemble_extended_atlas.py",
        "--base-atlas",
        str(root / "final" / "spritesheet.webp"),
        "--registered-row-9",
        str(root / "qa" / "look-row-9-registered.png"),
        "--row-9-registration",
        str(root / "qa" / "look-row-9-registration.json"),
        "--look-row-10",
        str(root / "decoded" / "look-row-10.png"),
        "--chroma-key",
        key,
        "--chroma-threshold",
        "96",
        "--output",
        str(final_png),
        "--webp-output",
        str(final_webp),
        "--manifest-output",
        str(root / "final" / "spritesheet-extended.json"),
    ]
    idle = first_idle(root)
    if idle:
        command += ["--neutral-cell", str(idle)]
    try:
        execute(*command)
        execute(
            "despill_chroma_edges.py",
            str(final_png),
            "--output",
            str(clean_png),
            "--webp-output",
            str(clean_webp),
            "--chroma-key",
            key,
            "--json-out",
            str(root / "qa" / "chroma-despill-extended.json"),
        )
        shutil.copy2(clean_png, final_png)
        shutil.copy2(clean_webp, final_webp)
        execute(
            "validate_atlas.py",
            str(final_webp),
            "--json-out",
            str(root / "final" / "validation-extended.json"),
            "--chroma-key",
            key,
            "--require-v2",
        )
        execute(
            "make_contact_sheet.py",
            str(final_webp),
            "--output",
            str(root / "qa" / "contact-sheet-extended.png"),
        )
        execute(
            "make_direction_qa_sheet.py",
            str(final_webp),
            "--output",
            str(root / "qa" / "look-directions.png"),
        )
        execute(
            "make_direction_blind_qa_sheet.py",
            str(final_webp),
            "--output",
            str(root / "qa" / "direction-blind-pairs.png"),
            "--answer-key",
            str(root / "qa" / "direction-blind-answer-key.json"),
        )
        execute(
            "measure_direction_continuity.py",
            str(final_webp),
            "--json-out",
            str(root / "qa" / "look-continuity.json"),
        )
    except Exception as exc:
        emit({"ok": False, "error": str(exc)[-400:]}, 1)
    state["deterministicReady"] = True
    state["updatedAt"] = now()
    save_run(root, state, manifest)
    emit(
        {
            "ok": True,
            "deterministicReady": True,
            "contactSheet": str(root / "qa" / "contact-sheet-extended.png"),
            "directions": str(root / "qa" / "look-directions.png"),
        }
    )


def command_approve(args: argparse.Namespace) -> None:
    root = run_dir(args.run_dir)
    state, manifest = load_run(root)
    if not state["deterministicReady"]:
        emit({"ok": False, "error": "final deterministic validation has not passed"}, 2)
    semantics = Path(args.semantics).expanduser().resolve()
    if not semantics.is_file():
        emit({"ok": False, "error": "direction semantics JSON is required"}, 2)
    semantics_data = read_json(semantics)
    directions = semantics_data.get("directions", [])
    if len(directions) != 16 or any(item.get("verdict") == "fail" for item in directions):
        emit({"ok": False, "error": "direction semantics must contain 16 non-failing verdicts"}, 2)
    destination = root / "qa" / "direction-semantics.json"
    if semantics != destination:
        shutil.copy2(semantics, destination)
    state["visualApproved"] = args.result == "pass"
    state["visualNotes"] = args.notes
    state["status"] = "ready" if state["visualApproved"] else "needs-repair"
    state["updatedAt"] = now()
    save_run(root, state, manifest)
    emit({"ok": state["visualApproved"], "visualApproved": state["visualApproved"]}, 0 if state["visualApproved"] else 1)


def package_files(root: Path, destination: Path) -> dict:
    state, _ = load_run(root)
    if not state["deterministicReady"] or not state["visualApproved"]:
        emit({"ok": False, "error": "final visual approval is required"}, 2)
    request = read_json(root / "pet_request.json")
    pet_id = request["pet_id"]
    destination.mkdir(parents=True, exist_ok=True)
    shutil.copy2(root / "final" / "spritesheet-extended.webp", destination / "spritesheet.webp")
    pet = {
        "id": pet_id,
        "displayName": request["display_name"],
        "description": request["description"],
        "spriteVersionNumber": 2,
        "spritesheetPath": "spritesheet.webp",
    }
    write_json(destination / "pet.json", pet)
    return pet


def command_package(args: argparse.Namespace) -> None:
    root = run_dir(args.run_dir)
    destination = run_dir(args.output)
    pet = package_files(root, destination)
    state, manifest = load_run(root)
    state["package"] = str(destination)
    state["updatedAt"] = now()
    save_run(root, state, manifest)
    emit({"ok": True, "package": str(destination), "pet": pet["id"]})


def command_install(args: argparse.Namespace) -> None:
    root = run_dir(args.run_dir)
    request = read_json(root / "pet_request.json")
    codex_home = Path(os.environ.get("CODEX_HOME", Path.home() / ".codex")).expanduser().resolve()
    destination = codex_home / "pets" / request["pet_id"]
    pet = package_files(root, destination)
    state, manifest = load_run(root)
    state["installed"] = str(destination)
    state["status"] = "installed"
    state["updatedAt"] = now()
    save_run(root, state, manifest)
    emit({"ok": True, "installed": str(destination), "pet": pet["id"]})


def command_status(args: argparse.Namespace) -> None:
    root = run_dir(args.run_dir)
    state, _ = load_run(root)
    counts: dict[str, int] = {}
    for item in state["jobs"].values():
        counts[item["status"]] = counts.get(item["status"], 0) + 1
    emit(
        {
            "status": state["status"],
            "jobs": counts,
            "standardReady": state["standardReady"],
            "deterministicReady": state["deterministicReady"],
            "visualApproved": state["visualApproved"],
            "installed": state["installed"],
        }
    )


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    commands = result.add_subparsers(dest="command", required=True)

    init = commands.add_parser("init")
    init.add_argument("--run-dir", required=True)
    init.add_argument("--reference")
    init.add_argument("--pet-name", default="Custom Pet")
    init.add_argument("--description")
    init.add_argument("--pet-notes")
    init.add_argument("--style-preset", default="auto")
    init.add_argument("--style-notes")
    init.add_argument("--chroma-key", default="auto")
    init.add_argument("--mode", choices=["balanced", "fast", "strict"], default="balanced")
    init.set_defaults(handler=command_init)

    for name, handler in (("next", command_next), ("build-standard", command_standard), ("finalize", command_finalize), ("status", command_status)):
        sub = commands.add_parser(name)
        sub.add_argument("--run-dir", required=True)
        sub.set_defaults(handler=handler)

    record = commands.add_parser("record-generation")
    record.add_argument("--run-dir", required=True)
    record.add_argument("--job", required=True)
    record.add_argument("--source", required=True)
    record.set_defaults(handler=command_record)

    repair = commands.add_parser("repair")
    repair.add_argument("--run-dir", required=True)
    repair.add_argument("--job", required=True)
    repair.add_argument("--reason", required=True)
    repair.set_defaults(handler=command_repair)

    approve = commands.add_parser("approve")
    approve.add_argument("--run-dir", required=True)
    approve.add_argument("--result", choices=["pass", "fail"], required=True)
    approve.add_argument("--notes", required=True)
    approve.add_argument("--semantics", required=True)
    approve.set_defaults(handler=command_approve)

    package = commands.add_parser("package")
    package.add_argument("--run-dir", required=True)
    package.add_argument("--output", required=True)
    package.set_defaults(handler=command_package)

    install = commands.add_parser("install")
    install.add_argument("--run-dir", required=True)
    install.set_defaults(handler=command_install)
    return result


if __name__ == "__main__":
    parsed = parser().parse_args()
    parsed.handler(parsed)
