#!/usr/bin/env python3
"""Tests for the spec-site renderer.

    python3 -m unittest discover -s tests -v

Stdlib only, so it runs in any shell with python3 and no network.
"""

from __future__ import annotations

import importlib.util
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

_spec = importlib.util.spec_from_file_location(
    "render_specs", REPO / "scripts" / "render_specs.py"
)
assert _spec and _spec.loader
render_specs = importlib.util.module_from_spec(_spec)
sys.modules["render_specs"] = render_specs
_spec.loader.exec_module(render_specs)

GROUNDED = render_specs.GROUNDED
UNVERIFIED = render_specs.UNVERIFIED
UNDECLARED = render_specs.UNDECLARED


GROUNDED_BODY = """
The board SHALL present its console on the CH342 bridge at 115200 8N1.

*Grounding: observed on this board. `docs/rtsmart-boot-log.txt` was captured
this way.*

#### Scenario: The board is connected

- **WHEN** the board is connected with a data cable
- **THEN** two CDC-ACM ports appear
"""

UNVERIFIED_BODY = """
<!-- UNVERIFIED: nothing has been drawn on this panel under Linux.
Grounded by a committed photograph. -->

The system SHALL present the panel as a working framebuffer at 568x1232.

#### Scenario: Something is drawn

- **WHEN** a pattern is written to the framebuffer
- **THEN** it is visible on the physical panel
"""

UNDECLARED_BODY = """
The project SHALL record what differs between the emulated and hardware boot
paths, so that a failure is diagnosed against a written expectation.

#### Scenario: The two paths disagree

- **WHEN** an image boots under QEMU but not on the board
- **THEN** the recorded differences are the first place to look
"""


def write_spec(root: Path, capability: str, body: str, purpose: str = "A purpose.") -> Path:
    path = root / "openspec" / "specs" / capability / "spec.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"## Purpose\n\n{purpose}\n\n## Requirements\n{body}", encoding="utf-8"
    )
    return path


class TempRepo:
    """A throwaway repository tree: openspec/config.yaml plus whatever the
    test writes under openspec/specs/ and docs/."""

    def __enter__(self) -> Path:
        self.dir = Path(tempfile.mkdtemp(prefix="spec-site-test-"))
        (self.dir / "openspec").mkdir()
        (self.dir / "openspec" / "config.yaml").write_text("schema: spec-driven\n")
        return self.dir

    def __exit__(self, *exc: object) -> None:
        shutil.rmtree(self.dir, ignore_errors=True)


# -- task 1.1 ---------------------------------------------------------------


class TestClassification(unittest.TestCase):
    def test_grounding_citation_is_grounded(self) -> None:
        status, reason = render_specs.classify("f.md", "R", GROUNDED_BODY)
        self.assertEqual(status, GROUNDED)
        self.assertEqual(reason, "")

    def test_unverified_marker_is_unverified_and_keeps_its_reason(self) -> None:
        status, reason = render_specs.classify("f.md", "R", UNVERIFIED_BODY)
        self.assertEqual(status, UNVERIFIED)
        self.assertIn("nothing has been drawn on this panel", reason)

    def test_neither_raises_rather_than_defaulting_to_grounded(self) -> None:
        with self.assertRaises(render_specs.UnclassifiedRequirement) as caught:
            render_specs.classify(
                "openspec/specs/image/boot-chain/spec.md",
                "The hardware boot path differs",
                UNDECLARED_BODY,
            )
        message = str(caught.exception)
        self.assertIn("openspec/specs/image/boot-chain/spec.md", message)
        self.assertIn("The hardware boot path differs", message)

    def test_marker_wins_over_a_forward_looking_grounding_sentence(self) -> None:
        body = (
            "<!-- UNVERIFIED: nothing built yet. Grounded once "
            "docs/evidence/cross-build.txt records a closure. -->\n\n"
            "The build SHALL cross-compile.\n"
        )
        status, _ = render_specs.classify("f.md", "R", body)
        self.assertEqual(status, UNVERIFIED)

    def test_an_undeclared_requirement_becomes_a_build_defect_not_grounded(self) -> None:
        with TempRepo() as root:
            write_spec(root, "image/boot-chain", "### Requirement: Paths differ\n" + UNDECLARED_BODY)
            caps, defects = render_specs.load_capabilities(root)
            self.assertEqual(caps[0].requirements[0].status, UNDECLARED)
            self.assertEqual([d.kind for d in defects], ["undeclared"])


# -- task 1.2 ---------------------------------------------------------------


class TestEvidenceCitations(unittest.TestCase):
    def test_extracts_repository_paths_and_ignores_prose(self) -> None:
        body = (
            "The console is `/dev/ttyACM0` and specs live in `openspec/specs/`.\n\n"
            "*Grounding: `docs/rtsmart-boot-log.txt` records it.*\n"
        )
        self.assertEqual(
            render_specs.evidence_citations(body), ["docs/rtsmart-boot-log.txt"]
        )

    def test_ignores_paths_named_only_inside_an_unverified_marker(self) -> None:
        body = (
            "<!-- UNVERIFIED: grounded once docs/evidence/qemu-boot.txt exists. -->\n\n"
            "The system SHALL boot.\n"
        )
        self.assertEqual(render_specs.evidence_citations(body), [])

    def test_a_present_path_is_linked_and_not_a_defect(self) -> None:
        with TempRepo() as root:
            (root / "docs" / "evidence").mkdir(parents=True)
            (root / "docs" / "evidence" / "boot.txt").write_text("U-Boot SPL 2022.10\n")
            write_spec(
                root,
                "system/console",
                "### Requirement: It boots\n\n"
                "The board SHALL boot.\n\n"
                "*Grounding: `docs/evidence/boot.txt` records it.*\n",
            )
            caps, defects = render_specs.load_capabilities(root)
            self.assertEqual(defects, [])
            self.assertEqual(
                caps[0].requirements[0].evidence, ["docs/evidence/boot.txt"]
            )

    def test_an_absent_path_fails_naming_the_requirement_and_the_path(self) -> None:
        with TempRepo() as root:
            write_spec(
                root,
                "system/console",
                "### Requirement: It boots\n\n"
                "The board SHALL boot.\n\n"
                "*Grounding: `docs/evidence/never-captured.txt` records it.*\n",
            )
            _, defects = render_specs.load_capabilities(root)
            self.assertEqual(len(defects), 1)
            self.assertEqual(defects[0].kind, "missing-evidence")
            self.assertIn("It boots", defects[0].detail)
            self.assertIn("docs/evidence/never-captured.txt", defects[0].detail)


# -- task 2.1, 2.2, 2.3, 2.4 ------------------------------------------------


class TestRendering(unittest.TestCase):
    def build(self, root: Path) -> tuple[Path, object]:
        out = root / "public"
        report = render_specs.build_site(root, out)
        return out, report

    def test_one_page_per_capability(self) -> None:
        with TempRepo() as root:
            write_spec(root, "display/panel", "### Requirement: A\n" + UNVERIFIED_BODY)
            write_spec(root, "system/console", "### Requirement: B\n" + GROUNDED_BODY)
            (root / "docs").mkdir(exist_ok=True)
            (root / "docs" / "rtsmart-boot-log.txt").write_text("U-Boot SPL 2022.10\n")
            out, _ = self.build(root)
            self.assertTrue((out / "display-panel.html").is_file())
            self.assertTrue((out / "system-console.html").is_file())

    def test_landing_page_states_the_count_before_any_capability_prose(self) -> None:
        with TempRepo() as root:
            write_spec(
                root,
                "display/panel",
                "### Requirement: A\n" + UNVERIFIED_BODY,
                purpose="Defines what appears on this board's AMOLED.",
            )
            out, _ = self.build(root)
            markup = (out / "index.html").read_text()
            count_at = markup.index("requirement is unverified")
            heading_at = markup.index("Capabilities")
            self.assertLess(count_at, heading_at)
            self.assertLess(count_at, markup.index("panel"))
            self.assertLess(count_at, markup.index("AMOLED"))

    def test_evidence_citations_become_working_links(self) -> None:
        with TempRepo() as root:
            (root / "docs").mkdir()
            (root / "docs" / "rtsmart-boot-log.txt").write_text("U-Boot SPL 2022.10\n")
            write_spec(root, "system/console", "### Requirement: B\n" + GROUNDED_BODY)
            out, _ = self.build(root)
            markup = (out / "system-console.html").read_text()
            hrefs = set(
                m for m in __import__("re").findall(r'href="([^"]+)"', markup)
                if not m.startswith("http")
            )
            self.assertIn("evidence-docs-rtsmart-boot-log-txt.html", hrefs)
            for href in hrefs:
                self.assertTrue((out / href).is_file(), f"dead link: {href}")
            self.assertIn(
                "U-Boot SPL 2022.10",
                (out / "evidence-docs-rtsmart-boot-log-txt.html").read_text(),
            )

    def test_nothing_from_openspec_changes_reaches_the_output(self) -> None:
        """Against the real repository, so the in-flight change ids are real."""
        out = Path(tempfile.mkdtemp(prefix="spec-site-nochanges-")) / "public"
        try:
            render_specs.build_site(REPO, out)
            changes_dir = REPO / "openspec" / "changes"
            ids = sorted(
                p.name
                for p in changes_dir.iterdir()
                if p.is_dir() and p.name != "archive"
            )
            self.assertTrue(ids, "expected at least one in-flight change to test against")
            blob = "\n".join(
                p.read_text(encoding="utf-8", errors="replace")
                for p in out.rglob("*")
                if p.is_file() and p.suffix in {".html", ".css"}
            )
            leaked = [change_id for change_id in ids if change_id in blob]
            self.assertEqual(leaked, [], f"in-flight change ids leaked: {leaked}")
            self.assertNotIn("openspec/changes", blob)
        finally:
            shutil.rmtree(out.parent, ignore_errors=True)


# -- task 3.2 ---------------------------------------------------------------


class TestBudgets(unittest.TestCase):
    def test_time_breach_names_measured_and_budget(self) -> None:
        report = render_specs.Report(
            capabilities=[], defects=[], seconds=9.5, output_bytes=10, max_seconds=5.0
        )
        with self.assertRaises(render_specs.BudgetExceeded) as caught:
            render_specs.check_budgets(report)
        message = str(caught.exception)
        self.assertIn("9.500", message)
        self.assertIn("5.000", message)

    def test_size_breach_names_measured_and_budget(self) -> None:
        report = render_specs.Report(
            capabilities=[],
            defects=[],
            seconds=0.01,
            output_bytes=99999,
            max_seconds=5.0,
            max_bytes=1024,
        )
        with self.assertRaises(render_specs.BudgetExceeded) as caught:
            render_specs.check_budgets(report)
        message = str(caught.exception)
        self.assertIn("99999", message)
        self.assertIn("1024", message)

    def test_a_forced_breach_fails_the_command(self) -> None:
        with TempRepo() as root:
            write_spec(root, "display/panel", "### Requirement: A\n" + UNVERIFIED_BODY)
            status = render_specs.main(
                ["--repo", str(root), "--out", str(root / "public"),
                 "--max-bytes", "1", "--quiet"]
            )
            self.assertNotEqual(status, 0)

    def test_the_real_tree_is_inside_its_budgets(self) -> None:
        out = Path(tempfile.mkdtemp(prefix="spec-site-budget-")) / "public"
        try:
            report = render_specs.build_site(REPO, out)
            render_specs.check_budgets(report)
        finally:
            shutil.rmtree(out.parent, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
