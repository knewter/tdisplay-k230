#!/usr/bin/env python3
"""Check committed work classification and public status boundaries."""

from __future__ import annotations

import importlib.util
from contextlib import redirect_stderr
from io import StringIO
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("render_work_board", ROOT / "scripts/render_work_board.py")
assert spec and spec.loader
work = importlib.util.module_from_spec(spec)
spec.loader.exec_module(work)


def command(repo: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(repo), *args], check=True, text=True, capture_output=True).stdout.strip()


def put(repo: Path, path: str, body: str) -> None:
    target = repo / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(body)


class Fixture(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.repo = Path(self.temp.name)
        command(self.repo, "init", "-q")
        command(self.repo, "config", "user.name", "Site Test")
        command(self.repo, "config", "user.email", "site@example.invalid")
        put(self.repo, "openspec/changes/the-first-thing/proposal.md", "## Why\n\nFirst thing.\n")
        put(self.repo, "openspec/changes/the-first-thing/design.md", "## Approach\n\nA table:\n\n| A | B |\n| - | - |\n| 1 | 2 |\n")
        put(self.repo, "openspec/changes/the-first-thing/tasks.md", "- [x] 1.1 Started\n- [x] 1.1b Follow-up\n- [ ] 1a.2 Test on glass\n")
        put(self.repo, "openspec/changes/the-first-thing/specs/runtime/demo/spec.md", "## ADDED Requirements\n\n### Requirement: Demo\n")
        put(self.repo, "openspec/changes/the-second-thing/proposal.md", "## Why\n\nSecond thing.\n")
        put(self.repo, "openspec/changes/the-second-thing/design.md", "## Design\n\nSecond design.\n")
        put(self.repo, "openspec/changes/the-second-thing/tasks.md", "- [ ] Make it\n")
        put(self.repo, "openspec/changes/the-second-thing/specs/runtime/demo/spec.md", "## ADDED Requirements\n\n### Requirement: Second\n")
        put(self.repo, "openspec/changes/archive/2026-09-23-the-old-thing/proposal.md", "## Why\n\nOld thing.\n")
        put(self.repo, "openspec/changes/archive/2026-09-23-the-old-thing/design.md", "## Design\n\nOld design.\n")
        put(self.repo, "openspec/changes/archive/2026-09-23-the-old-thing/tasks.md", "- [x] 1.1 Done\n")
        put(self.repo, "openspec/changes/archive/2026-09-23-the-old-thing/specs/runtime/demo/spec.md", "## ADDED Requirements\n\n### Requirement: Old\n")
        put(self.repo, "docs/evidence/proof/README.md", "Physical observation with limits.\n")
        command(self.repo, "add", ".")
        command(self.repo, "commit", "-qm", "fixture")
        self.revision = command(self.repo, "rev-parse", "HEAD")

    def data(self, overrides: dict | None = None, working: bool = False) -> dict:
        tree = work.SourceTree(self.repo, working)
        return work.snapshot(tree, {"schema": 1, "overrides": overrides or {}}, "2026-09-23 00:00 UTC")

    def review(self, **changes) -> dict:
        data = {"lane": "verification", "source": "source-landed", "physical": "pending",
                "next": "Test on glass", "rationale": "Committed source is ahead of physical proof.",
                "reviewRevision": self.revision, "evidence": ["docs/evidence/proof/README.md"]}
        data.update(changes)
        return data

    def test_lanes_and_counts_are_derived_from_the_committed_tasks(self) -> None:
        data = self.data()
        items = {item["id"]: item for item in data["items"]}
        self.assertEqual((items["the-first-thing"]["done"], items["the-first-thing"]["total"]), (2, 3))
        self.assertEqual(items["the-first-thing"]["lane"], "in-progress")
        self.assertEqual(items["the-second-thing"]["lane"], "planned")
        self.assertEqual(items["the-second-thing"]["next"], "Make it")
        self.assertEqual(items["2026-09-23-the-old-thing"]["lane"], "archived")
        self.assertEqual(data["sourceRevision"], self.revision)
        self.assertEqual(data["sourceMode"], "committed HEAD")

    def test_duplicate_status_override_fails_before_last_value_can_win(self) -> None:
        put(self.repo, work.STATUS_PATH,
            '{"schema":1,"overrides":{"the-first-thing":{"next":"older"},'
            '"the-first-thing":{"next":"newer"}}}')
        command(self.repo, "add", work.STATUS_PATH)
        command(self.repo, "commit", "-qm", "duplicate status fixture")
        stderr = StringIO()
        with redirect_stderr(stderr):
            result = work.main(["--repo", str(self.repo), "--output", str(self.repo / "work.json")])
        self.assertEqual(result, 2)
        self.assertIn("duplicate work-board status JSON key: 'the-first-thing'", stderr.getvalue())
        self.assertFalse((self.repo / "work.json").exists())

    def test_dirty_task_is_ignored_without_explicit_working_tree_mode(self) -> None:
        put(self.repo, "openspec/changes/the-second-thing/tasks.md", "- [x] Make it\n")
        committed = {item["id"]: item for item in self.data()["items"]}
        preview = {item["id"]: item for item in self.data(working=True)["items"]}
        self.assertEqual(committed["the-second-thing"]["done"], 0)
        self.assertEqual(preview["the-second-thing"]["done"], 1)

    def test_detail_documents_use_the_same_committed_revision(self) -> None:
        put(self.repo, "openspec/changes/the-first-thing/design.md", "## Private uncommitted edit\n")
        item = next(i for i in self.data()["items"] if i["id"] == "the-first-thing")
        self.assertEqual([d["label"] for d in item["details"]], ["Proposal", "Design", "Tasks", "Delta spec: runtime/demo"])
        self.assertIn("| A | B |", item["details"][1]["markdown"])
        self.assertNotIn("Private uncommitted", item["details"][1]["markdown"])

    def test_snapshot_stays_at_captured_revision_when_head_advances(self) -> None:
        tree = work.SourceTree(self.repo)
        put(self.repo, "openspec/changes/the-first-thing/design.md", "## A newer commit\n")
        command(self.repo, "add", ".")
        command(self.repo, "commit", "-qm", "new design")
        data = work.snapshot(tree, {"schema": 1, "overrides": {}}, "test UTC")
        item = next(i for i in data["items"] if i["id"] == "the-first-thing")
        self.assertEqual(data["sourceRevision"], self.revision)
        self.assertIn("| A | B |", item["details"][1]["markdown"])
        self.assertNotIn("newer commit", item["details"][1]["markdown"])

    def test_missing_oversize_and_private_detail_fail_with_path(self) -> None:
        path = "openspec/changes/the-first-thing/design.md"
        (self.repo / path).unlink()
        with self.assertRaisesRegex(work.WorkError, "missing work document.*design.md"):
            self.data(working=True)
        put(self.repo, path, "A" * (work.MAX_DOCUMENT_BYTES + 1))
        with self.assertRaisesRegex(work.WorkError, "exceeds.*design.md"):
            self.data(working=True)
        put(self.repo, path, "Read /home/operator/private-settings")
        with self.assertRaisesRegex(work.WorkError, "private path.*design.md"):
            self.data(working=True)

    def test_large_committed_blob_is_rejected_before_read(self) -> None:
        path = "openspec/changes/the-first-thing/design.md"
        with (self.repo / path).open("wb") as out:
            out.seek(work.MAX_DOCUMENT_BYTES + 4 * 1024 * 1024)
            out.write(b"x")
        command(self.repo, "add", path)
        command(self.repo, "commit", "-qm", "oversize")
        tree = work.SourceTree(self.repo)
        with self.assertRaisesRegex(work.WorkError, "exceeds.*design.md"):
            tree.read(path)

    def test_reviewed_override_keeps_source_and_device_proof_distinct(self) -> None:
        item = next(i for i in self.data({"the-first-thing": self.review()})["items"] if i["id"] == "the-first-thing")
        self.assertEqual((item["lane"], item["source"], item["physical"]), ("verification", "source-landed", "pending"))
        self.assertEqual(item["evidence"], ["docs/evidence/proof/README.md"])

    def test_bad_public_overrides_fail_before_render(self) -> None:
        bad = [
            {"unknown-item": self.review()},
            {"the-first-thing": self.review(evidence=["docs/evidence/absent.md"])},
            {"the-first-thing": self.review(next="Open /home/operator/private")},
            {"the-first-thing": self.review(lane="archived")},
            {"the-first-thing": self.review(dependencies=["the-first-thing"])},
            {"the-first-thing": self.review(reviewRevision="ffffffffffffffff")},
        ]
        for override in bad:
            with self.subTest(override=override), self.assertRaises(work.WorkError):
                self.data(override)

    def test_unknown_and_private_paths_are_rejected(self) -> None:
        for path in ("../secret", "/tmp/log", "docs/../private", "docs/evidence/192.168.1.2.txt"):
            with self.subTest(path=path), self.assertRaises(work.WorkError):
                work.safe_path(path)

    def test_private_task_text_does_not_leak_before_a_safe_override(self) -> None:
        put(self.repo, "openspec/changes/the-first-thing/tasks.md", "- [ ] 1.1 Inspect /dev/ttyACM0 privately\n")
        item = next(i for i in self.data({"the-first-thing": self.review()}, working=True)["items"] if i["id"] == "the-first-thing")
        self.assertEqual(item["next"], "Test on glass")
        fallback = next(i for i in self.data(working=True)["items"] if i["id"] == "the-first-thing")
        self.assertNotIn("/dev/", fallback["next"])

    def test_shallow_clone_names_missing_review_history(self) -> None:
        put(self.repo, "note.md", "newer")
        command(self.repo, "add", "note.md")
        command(self.repo, "commit", "-qm", "later")
        shallow = self.repo / "shallow-checkout"
        subprocess.run(["git", "clone", "-q", "--depth", "1", "--no-local", self.repo.as_uri(), str(shallow)], check=True)
        with self.assertRaisesRegex(work.WorkError, "fetch full history"):
            work.snapshot(work.SourceTree(shallow), {"schema": 1, "overrides": {"the-first-thing": self.review()}}, "test UTC")

    def test_media_arriving_before_archive_is_discovered_at_its_commit(self) -> None:
        record = "docs/evidence/proof/README.md"
        proposal = "openspec/changes/the-first-thing/proposal.md"
        put(self.repo, proposal, "## Why\n\nSee `docs/evidence/proof/README.md`.\n")
        put(self.repo, "docs/evidence/proof/frame.png", "fixture image bytes")
        put(self.repo, "docs/evidence/proof/demo.mp4", "fixture video bytes")
        put(self.repo, "docs/evidence/proof/run.log", "test result")
        put(self.repo, record, "[Run](run.log) and [same image](frame.png).\n")
        put(self.repo, "docs/evidence/unrelated/other.png", "unrelated")
        command(self.repo, "add", proposal, "docs/evidence")
        command(self.repo, "commit", "-qm", "new media while tasks remain open")
        item = next(i for i in self.data()["items"] if i["id"] == "the-first-thing")
        self.assertEqual({m["kind"] for m in item["media"]}, {"image", "video"})
        self.assertEqual(len(item["media"]), 2)
        self.assertIn("docs/evidence/proof/run.log", item["evidence"])
        self.assertNotIn("docs/evidence/unrelated/other.png", item["evidence"])
        self.assertFalse(item["archived"])
        put(self.repo, "docs/evidence/proof/private-uncommitted.webm", "not published")
        item = next(i for i in self.data()["items"] if i["id"] == "the-first-thing")
        self.assertEqual(len(item["media"]), 2)

    def test_reviewed_video_cover_is_first_without_upgrading_device_proof(self) -> None:
        path = "docs/evidence/proof/demo.webm"
        put(self.repo, path, "fixture")
        command(self.repo, "add", path)
        command(self.repo, "commit", "-qm", "video")
        cover = {"path": path, "caption": "Drawer gesture trial", "provenance": "QEMU capture"}
        item = next(i for i in self.data({"the-first-thing": self.review(cover=cover)})["items"] if i["id"] == "the-first-thing")
        self.assertEqual(item["media"][0], cover | {"kind": "video"})
        self.assertEqual(item["physical"], "pending")
        for wrong in ["docs/evidence/missing.png", "../private.png", "https://example.invalid/x.png"]:
            with self.subTest(path=wrong), self.assertRaises(work.WorkError):
                self.data({"the-first-thing": self.review(cover=cover | {"path": wrong})})

    def test_discovery_skips_symlinks_and_private_sibling_names(self) -> None:
        put(self.repo, "docs/evidence/proof/192.168.1.2.png", "private name")
        (self.repo / "docs/evidence/proof/link.png").symlink_to("README.md")
        command(self.repo, "add", "docs/evidence/proof")
        command(self.repo, "commit", "-qm", "non-public media fixtures")
        for working in (False, True):
            item = next(i for i in self.data({"the-first-thing": self.review()}, working=working)["items"]
                        if i["id"] == "the-first-thing")
            self.assertEqual(item["media"], [])

    def test_dependency_cycle_is_rejected(self) -> None:
        overrides = {
            "the-first-thing": self.review(dependencies=["the-second-thing"]),
            "the-second-thing": self.review(dependencies=["the-first-thing"]),
        }
        with self.assertRaisesRegex(work.WorkError, "cyclic dependency"):
            self.data(overrides)


class RealRepository(unittest.TestCase):
    def test_current_status_file_is_valid_against_working_tree(self) -> None:
        status = work.parse_status((ROOT / work.STATUS_PATH).read_text())
        data = work.snapshot(work.SourceTree(ROOT, True), status, "test UTC")
        self.assertGreaterEqual(len(data["items"]), 20)
        self.assertTrue(any(i["lane"] == "verification" for i in data["items"]))
        self.assertTrue(all(i["proposal"].startswith("openspec/changes/") for i in data["items"]))

    def test_every_current_openspec_checkbox_is_counted(self) -> None:
        import re
        data = work.snapshot(work.SourceTree(ROOT, True), work.parse_status((ROOT / work.STATUS_PATH).read_text()), "test UTC")
        for item in data["items"]:
            if not item["tasksPath"]:
                continue
            tasks = (ROOT / item["tasksPath"]).read_text()
            count = len(re.findall(r"^- \[[ xX]\] ", tasks, re.M))
            self.assertEqual(item["total"], count, item["id"])


if __name__ == "__main__":
    unittest.main()
