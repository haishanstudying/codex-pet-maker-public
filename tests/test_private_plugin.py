from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from PIL import Image, ImageDraw


PLUGIN = Path(__file__).resolve().parents[1]
SKILL = PLUGIN / "skills" / "make-codex-pet"
PETCTL = SKILL / "scripts" / "petctl.py"
PRIVACY = PLUGIN / "scripts" / "privacy_scan.py"


def call(*args: str, expect: int = 0) -> tuple[dict, str]:
    result = subprocess.run([sys.executable, *args], text=True, capture_output=True)
    if result.returncode != expect:
        raise AssertionError(f"{result.returncode}: {result.stdout}\n{result.stderr}")
    text = result.stdout.strip()
    return json.loads(text), text


def make_reference(path: Path) -> None:
    image = Image.new("RGB", (256, 256), "#f7f1dd")
    draw = ImageDraw.Draw(image)
    draw.ellipse((64, 34, 192, 162), fill="#6f54c7")
    draw.rectangle((92, 150, 164, 224), fill="#efbd49")
    draw.ellipse((92, 82, 112, 102), fill="#ffffff")
    draw.ellipse((144, 82, 164, 102), fill="#ffffff")
    image.save(path)


class PrivatePluginTests(unittest.TestCase):
    def test_controller_is_resumable_and_compact(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            reference = root / "shape-source.png"
            run = root / "run"
            make_reference(reference)
            initialized, output = call(
                str(PETCTL),
                "init",
                "--run-dir",
                str(run),
                "--reference",
                str(reference),
                "--pet-name",
                "Shape Test",
            )
            self.assertTrue(initialized["ok"])
            next_job, output = call(str(PETCTL), "next", "--run-dir", str(run))
            self.assertEqual(next_job["job"], "base")
            self.assertLessEqual(len(output.encode("utf-8")), 1536)

            recorded, _ = call(
                str(PETCTL),
                "record-generation",
                "--run-dir",
                str(run),
                "--job",
                "base",
                "--source",
                str(reference),
            )
            self.assertEqual(recorded["status"], "complete")
            next_job, _ = call(str(PETCTL), "next", "--run-dir", str(run))
            self.assertNotEqual(next_job.get("job"), "base")

    def test_retry_cap_blocks_job(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            reference = root / "shape-source.png"
            run = root / "run"
            make_reference(reference)
            call(
                str(PETCTL),
                "init",
                "--run-dir",
                str(run),
                "--reference",
                str(reference),
                "--pet-name",
                "Retry Test",
            )
            state_path = run / "pipeline-state.json"
            state = json.loads(state_path.read_text(encoding="utf-8"))
            state["jobs"]["idle"]["attempts"] = state["jobs"]["idle"]["maxAttempts"]
            state_path.write_text(json.dumps(state), encoding="utf-8")
            result, _ = call(
                str(PETCTL),
                "repair",
                "--run-dir",
                str(run),
                "--job",
                "idle",
                "--reason",
                "synthetic failure",
                expect=1,
            )
            self.assertEqual(result["status"], "blocked")

    def test_jobs_without_dedicated_retry_prompt_reuse_stage_prompt(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            reference = root / "shape-source.png"
            run = root / "run"
            make_reference(reference)
            call(
                str(PETCTL),
                "init",
                "--run-dir",
                str(run),
                "--reference",
                str(reference),
                "--pet-name",
                "Fallback Test",
            )
            state_path = run / "pipeline-state.json"
            state = json.loads(state_path.read_text(encoding="utf-8"))
            state["jobs"]["base"]["attempts"] = 1
            state_path.write_text(json.dumps(state), encoding="utf-8")
            action, output = call(str(PETCTL), "next", "--run-dir", str(run))
            self.assertEqual(action["job"], "base")
            self.assertEqual(Path(action["prompt"]).name, "base-pet.md")
            self.assertLessEqual(len(output.encode("utf-8")), 1536)
            state = json.loads(state_path.read_text(encoding="utf-8"))
            state["jobs"]["base"]["status"] = "complete"
            for job in (
                "idle",
                "running-right",
                "running-left",
                "waving",
                "jumping",
                "failed",
                "waiting",
                "running",
                "review",
            ):
                state["jobs"][job]["status"] = "complete"
            state["standardReady"] = True
            state["jobs"]["look-cardinals"]["attempts"] = 1
            state_path.write_text(json.dumps(state), encoding="utf-8")
            action, output = call(str(PETCTL), "next", "--run-dir", str(run))
            self.assertEqual(action["job"], "look-cardinals")
            self.assertEqual(Path(action["prompt"]).name, "look-cardinals.md")
            self.assertLessEqual(len(output.encode("utf-8")), 1536)

    def test_standard_rows_route_to_single_build_step(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            reference = root / "shape-source.png"
            run = root / "run"
            make_reference(reference)
            call(
                str(PETCTL),
                "init",
                "--run-dir",
                str(run),
                "--reference",
                str(reference),
                "--pet-name",
                "Routing Test",
            )
            standard = {
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
            state_path = run / "pipeline-state.json"
            manifest_path = run / "imagegen-jobs.json"
            state = json.loads(state_path.read_text(encoding="utf-8"))
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            for name in standard:
                state["jobs"][name]["status"] = "complete"
            for job in manifest["jobs"]:
                if job["id"] in standard:
                    job["status"] = "complete"
            state_path.write_text(json.dumps(state), encoding="utf-8")
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            action, _ = call(str(PETCTL), "next", "--run-dir", str(run))
            self.assertEqual(action, {"action": "build-standard"})

    def test_privacy_scan_accepts_source_and_rejects_media(self) -> None:
        report, _ = call(str(PRIVACY), str(PLUGIN))
        self.assertTrue(report["ok"])
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "private.jpg").write_bytes(b"not really an image")
            report, _ = call(str(PRIVACY), str(root), expect=1)
            self.assertFalse(report["ok"])

    def test_privacy_scan_rejects_tampered_demo_image(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            demo = root / "assets" / "demo" / "shape-scout-reference.png"
            demo.parent.mkdir(parents=True)
            demo.write_bytes(b"tampered")
            report, _ = call(str(PRIVACY), str(root), expect=1)
            self.assertEqual(len(report["issues"]), 1)
            self.assertEqual(
                report["issues"][0]["file"].replace("\\", "/"),
                "assets/demo/shape-scout-reference.png",
            )
            self.assertEqual(
                report["issues"][0]["reason"],
                "approved demo image hash mismatch",
            )

    def test_skill_budget(self) -> None:
        skill = SKILL / "SKILL.md"
        self.assertLessEqual(len(skill.read_bytes()), 12 * 1024)
        self.assertLessEqual(len(skill.read_text(encoding="utf-8").splitlines()), 250)


if __name__ == "__main__":
    unittest.main()
