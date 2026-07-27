#!/usr/bin/env python3
"""Copy only review-safe plugin source files into a clean directory."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

sys.dont_write_bytecode = True

from demo_assets import APPROVED_DEMO_IMAGES, approved_demo_image


ALLOWED_SUFFIXES = {".json", ".md", ".py", ".txt", ".yaml", ".yml"}
ALLOWED_NAMES = {"LICENSE", "NOTICE"}
SKIP_PARTS = {"__pycache__", ".pytest_cache", ".git"}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source")
    parser.add_argument("destination")
    parser.add_argument("--manifest")
    args = parser.parse_args()
    source = Path(args.source).resolve()
    destination = Path(args.destination).resolve()
    if destination.exists():
        shutil.rmtree(destination)
    copied: list[str] = []
    for path in source.rglob("*"):
        relative = path.relative_to(source)
        if any(part in SKIP_PARTS for part in relative.parts) or not path.is_file():
            continue
        if path.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp", ".tif", ".tiff"}:
            if relative.as_posix() not in APPROVED_DEMO_IMAGES or not approved_demo_image(path, relative):
                raise SystemExit(f"refusing unapproved image: {relative}")
        elif path.suffix.lower() not in ALLOWED_SUFFIXES and path.name not in ALLOWED_NAMES:
            raise SystemExit(f"refusing non-allowlisted file: {relative}")
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)
        copied.append(relative.as_posix())
    if args.manifest:
        Path(args.manifest).write_text(
            json.dumps({"ok": True, "files": sorted(copied)}, indent=2) + "\n",
            encoding="utf-8",
        )
    print(destination)


if __name__ == "__main__":
    main()
