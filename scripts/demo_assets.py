"""Checksum allowlist for synthetic public demo images."""

from __future__ import annotations

import hashlib
from pathlib import Path


APPROVED_DEMO_IMAGES = {
    "assets/demo/shape-scout-actions.png": "5e8e85fc07746d7aff7fbb12c5945cba687275d9cf65f208738672ed959bb9e7",
    "assets/demo/shape-scout-directions.png": "b3d192eb018b8634427ed13da8186814314fb79fa4936fa697c2e85cfe86762a",
    "assets/demo/shape-scout-reference.png": "7afbeaf453f295daacb935cfa68efdd2ab114fb836a117c66f1dff48b14e9eff",
}


def approved_demo_image(path: Path, relative: Path) -> bool:
    expected = APPROVED_DEMO_IMAGES.get(relative.as_posix())
    return bool(
        expected
        and hashlib.sha256(path.read_bytes()).hexdigest().lower() == expected
    )
