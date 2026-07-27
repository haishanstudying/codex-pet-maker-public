#!/usr/bin/env python3
"""Fail when a plugin tree contains private/generated material."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.dont_write_bytecode = True

from demo_assets import APPROVED_PUBLIC_IMAGES, approved_public_image


BINARY_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp", ".tif", ".tiff"}
FORBIDDEN_PARTS = {".git", "generated_images", "decoded", "frames", "final", "qa", "runs", "work", "outputs"}
ABSOLUTE_PATHS = (
    re.compile(r"[A-Za-z]:[\\/]+Users[\\/]+", re.IGNORECASE),
    re.compile(r"/(?:Users|home)/[^/\s]+/"),
)


def scan(root: Path, deny_tokens: list[str]) -> dict:
    issues: list[dict[str, str]] = []
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root)
        if any(part.lower() in FORBIDDEN_PARTS for part in relative.parts):
            issues.append({"file": str(relative), "reason": "forbidden generated directory"})
            continue
        if not path.is_file():
            continue
        if path.suffix.lower() in BINARY_EXTENSIONS:
            if relative.as_posix() not in APPROVED_PUBLIC_IMAGES:
                issues.append({"file": str(relative), "reason": "binary image is not allowed"})
            elif not approved_public_image(path, relative):
                issues.append({"file": str(relative), "reason": "approved public image hash mismatch"})
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            issues.append({"file": str(relative), "reason": "unexpected binary file"})
            continue
        for pattern in ABSOLUTE_PATHS:
            if pattern.search(text):
                issues.append({"file": str(relative), "reason": "absolute user path"})
                break
        lowered = text.lower()
        for token in deny_tokens:
            if token.lower() in lowered:
                issues.append({"file": str(relative), "reason": f"denied token: {token}"})
    return {"ok": not issues, "root": str(root), "files": sum(1 for path in root.rglob("*") if path.is_file()), "issues": issues}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root")
    parser.add_argument("--deny-token", action="append", default=[])
    parser.add_argument("--json-out")
    args = parser.parse_args()
    report = scan(Path(args.root).resolve(), args.deny_token)
    text = json.dumps(report, indent=2, ensure_ascii=False) + "\n"
    if args.json_out:
        Path(args.json_out).write_text(text, encoding="utf-8")
    print(text, end="")
    raise SystemExit(0 if report["ok"] else 1)


if __name__ == "__main__":
    main()
