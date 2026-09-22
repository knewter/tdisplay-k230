#!/usr/bin/env python3
"""Tests for the spec-site renderer.

    python3 -m unittest discover -s tests -v

Stdlib only, so it runs in any shell with python3 and no network.
"""

from __future__ import annotations

import importlib.util
import json
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

    def test_grounded_on_hardware_is_a_near_miss_and_the_error_says_so(self) -> None:
        """`*Grounded on hardware. ...*` is what three archived requirements
        actually said. It is not the convention, it must not be accepted as
        one -- `Grounded once ... is committed` is a promise, not a citation --
        and the error has to name the near miss or the next person spends the
        day the last one did."""
        body = (
            "*Grounded on hardware. The vendored chain loaded our kernel "
            "(`docs/evidence/hardware-userspace.md`).*\n\n"
            "The chain SHALL load the kernel this project builds.\n"
        )
        with self.assertRaises(render_specs.UnclassifiedRequirement) as caught:
            render_specs.classify("f.md", "R", body)
        message = str(caught.exception)
        self.assertIn("Grounded on hardware.", message)
        self.assertIn("`*Grounding: observed on hardware. ...*`", message)

    def test_no_near_miss_is_reported_when_the_prose_never_mentions_grounding(self) -> None:
        with self.assertRaises(render_specs.UnclassifiedRequirement) as caught:
            render_specs.classify("f.md", "R", UNDECLARED_BODY)
        self.assertNotIn("close but", str(caught.exception))

    def test_marker_wins_over_a_forward_looking_grounding_sentence(self) -> None:
        body = (
            "<!-- UNVERIFIED: nothing built yet. Grounded once "
            "docs/evidence/cross-build.txt records a closure. -->\n\n"
            "The build SHALL cross-compile.\n"
        )
        status, _ = render_specs.classify("f.md", "R", body)
        self.assertEqual(status, UNVERIFIED)

    def test_a_marker_quoted_in_a_code_span_is_not_a_marker(self) -> None:
        """docs/spec-site discusses the convention, and quoting one must not
        be mistaken for using one."""
        body = (
            "A path named only inside an `<!-- UNVERIFIED -->` marker is not a "
            "citation.\n\n"
            "*Grounding: `docs/rtsmart-boot-log.txt` records it.*\n"
        )
        status, _ = render_specs.classify("f.md", "R", body)
        self.assertEqual(status, GROUNDED)

    def test_a_real_marker_is_stripped_from_the_rendered_prose(self) -> None:
        with TempRepo() as root:
            write_spec(root, "display/panel", "### Requirement: A\n" + UNVERIFIED_BODY)
            data, _ = render_specs.build_data(root)
            req = data["capabilities"][0]["requirements"][0]
            self.assertNotIn("UNVERIFIED", req["proseHtml"])
            self.assertIn("nothing has been drawn on this panel", req["reason"])

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


# -- what the data pass hands Astro -----------------------------------------


class TestData(unittest.TestCase):
    def test_every_capability_and_requirement_reaches_the_json(self) -> None:
        with TempRepo() as root:
            (root / "docs").mkdir()
            (root / "docs" / "rtsmart-boot-log.txt").write_text("U-Boot SPL 2022.10\n")
            write_spec(root, "display/panel", "### Requirement: A\n" + UNVERIFIED_BODY)
            write_spec(root, "system/console", "### Requirement: B\n" + GROUNDED_BODY)
            data, report = render_specs.build_data(root)
            self.assertEqual(data["total"], 2)
            self.assertEqual(data["tally"], {"grounded": 1, "unverified": 1, "undeclared": 0})
            self.assertEqual(
                [c["slug"] for c in data["capabilities"]],
                ["system-console", "display-panel"],
                "groups follow the taxonomy order, not the alphabet",
            )
            panel = next(c for c in data["capabilities"] if c["slug"] == "display-panel")
            req = panel["requirements"][0]
            self.assertEqual(req["status"], UNVERIFIED)
            self.assertIn("nothing has been drawn", req["reason"])
            self.assertNotIn("UNVERIFIED", req["proseHtml"])
            self.assertEqual([s["title"] for s in req["scenarios"]], ["Something is drawn"])

    def test_evidence_becomes_a_link_and_a_page_of_its_own(self) -> None:
        with TempRepo() as root:
            (root / "docs").mkdir()
            (root / "docs" / "rtsmart-boot-log.txt").write_text("U-Boot SPL 2022.10\n")
            write_spec(root, "system/console", "### Requirement: B\n" + GROUNDED_BODY)
            data, _ = render_specs.build_data(root)
            req = data["capabilities"][0]["requirements"][0]
            self.assertEqual(
                req["evidence"],
                [
                    {
                        "path": "docs/rtsmart-boot-log.txt",
                        "slug": "docs-rtsmart-boot-log-txt",
                        "href": "@@BASE@@evidence/docs-rtsmart-boot-log-txt/",
                    }
                ],
            )
            self.assertIn("@@BASE@@evidence/docs-rtsmart-boot-log-txt/", req["proseHtml"])
            self.assertEqual(data["evidence"][0]["kind"], "text")
            self.assertIn("U-Boot SPL 2022.10", data["evidence"][0]["text"])

    def test_the_data_pass_reads_openspec_specs_and_nothing_else(self) -> None:
        with TempRepo() as root:
            (root / "openspec" / "changes" / "a-change" / "specs" / "x" / "y").mkdir(
                parents=True
            )
            (
                root / "openspec" / "changes" / "a-change" / "specs" / "x" / "y" / "spec.md"
            ).write_text("## ADDED Requirements\n\n### Requirement: Draft\n" + GROUNDED_BODY)
            data, _ = render_specs.build_data(root)
            self.assertEqual(data["capabilities"], [])
            self.assertNotIn("a-change", json.dumps(data))

    def test_a_defect_reaches_the_json_so_the_site_can_show_it(self) -> None:
        with TempRepo() as root:
            write_spec(root, "image/boot-chain", "### Requirement: Paths differ\n" + UNDECLARED_BODY)
            data, _ = render_specs.build_data(root)
            self.assertEqual(data["tally"]["undeclared"], 1)
            self.assertEqual(len(data["defects"]), 1)
            self.assertEqual(data["defects"][0]["kind"], "undeclared")

    def test_the_command_exits_non_zero_on_a_defect_but_still_writes(self) -> None:
        with TempRepo() as root:
            write_spec(root, "image/boot-chain", "### Requirement: Paths differ\n" + UNDECLARED_BODY)
            out = root / "specs.json"
            status = render_specs.main(
                ["--repo", str(root), "--json", str(out), "--assets", str(root / "a"), "--quiet"]
            )
            self.assertEqual(status, 2)
            self.assertTrue(out.is_file())


# -- budgets ----------------------------------------------------------------


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


if __name__ == "__main__":
    unittest.main()
