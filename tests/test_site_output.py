#!/usr/bin/env python3
"""What the built site must be true of, checked against the built site.

These run against `site/dist`, so they need a build first. `scripts/build_site.py`
runs them as its last step; by hand:

    ./scripts/build_site.py            # builds, then runs these
    python3 -m unittest discover -s tests -p 'test_site_output.py'
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
DIST = REPO / "site" / "dist"
SPECS = REPO / "openspec" / "specs"
CHANGES = REPO / "openspec" / "changes"


def built() -> bool:
    return (DIST / "index.html").is_file()


def base_path(markup: str) -> str:
    """The site's base prefix, read out of the page rather than assumed."""
    hit = re.search(r'href="([^"]*)favicon\.svg"', markup)
    return hit.group(1) if hit else "/"


@unittest.skipUnless(built(), "site/dist does not exist; run ./scripts/build_site.py")
class TestBuiltSite(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.index = (DIST / "index.html").read_text(encoding="utf-8")
        cls.base = base_path(cls.index)

    def pages(self) -> list[Path]:
        return sorted(DIST.rglob("index.html"))

    def test_a_page_for_every_capability_spec(self) -> None:
        for spec in sorted(SPECS.rglob("spec.md")):
            parts = spec.relative_to(SPECS).parts
            slug = f"{parts[0]}-{parts[-2]}"
            self.assertTrue(
                (DIST / "c" / slug / "index.html").is_file(),
                f"no page for {'/'.join(parts[:-1])}",
            )

    def test_the_count_comes_before_any_capability_prose(self) -> None:
        body = self.index[self.index.index("<body"):]
        hit = re.search(r"unverified|requirements published yet", body)
        self.assertIsNotNone(hit, "the landing page never states the count")
        count_at = hit.start()
        for later in ("Capabilities", "Evidence on file", "Build defects"):
            at = body.find(later)
            if at != -1:
                self.assertLess(count_at, at, f"the count comes after {later!r}")
        for spec in sorted(SPECS.rglob("spec.md")):
            name = spec.relative_to(SPECS).parts[-2]
            at = body.find(f">{name}<")
            if at != -1:
                self.assertLess(count_at, at, f"the count comes after {name!r}")

    def test_the_count_matches_the_specs(self) -> None:
        """The headline number is the site's whole product; it is checked
        against the spec tree rather than trusted."""
        import importlib.util
        import sys

        spec = importlib.util.spec_from_file_location(
            "render_specs", REPO / "scripts" / "render_specs.py"
        )
        assert spec and spec.loader
        module = importlib.util.module_from_spec(spec)
        sys.modules["render_specs"] = module
        spec.loader.exec_module(module)
        caps, _ = module.load_capabilities(REPO)
        unverified = sum(c.tally()[module.UNVERIFIED] for c in caps)
        total = sum(sum(c.tally().values()) for c in caps)
        if total == 0:
            self.assertIn("requirements published yet", self.index)
        else:
            self.assertRegex(
                re.sub(r"\s+", " ", self.index),
                rf'<span class="n">{unverified}</span>\s*<span class="of">\s*of {total} ',
            )

    def test_every_internal_link_resolves(self) -> None:
        dead: list[str] = []
        for page in self.pages():
            markup = page.read_text(encoding="utf-8")
            for href in re.findall(r'(?:href|src)="([^"#?]+)"', markup):
                if href.startswith(("http://", "https://", "mailto:", "data:", "#")):
                    continue
                if not href.startswith(self.base):
                    dead.append(f"{page.relative_to(DIST)} -> {href} (outside base)")
                    continue
                rel = href[len(self.base) :].strip("/")
                target = DIST / rel if rel else DIST
                if target.is_dir():
                    target = target / "index.html"
                if not target.is_file():
                    dead.append(f"{page.relative_to(DIST)} -> {href}")
        self.assertEqual(dead, [], f"dead links: {dead}")

    def test_every_cited_evidence_file_has_a_page(self) -> None:
        index = (DIST / "index.html").read_text(encoding="utf-8")
        for path in sorted({m for m in re.findall(r"docs/[\w./-]+\.\w+", index)}):
            slug = re.sub(r"[^A-Za-z0-9]+", "-", path).strip("-").lower()
            self.assertTrue(
                (DIST / "evidence" / slug / "index.html").is_file(),
                f"{path} is cited but has no evidence page",
            )

    def test_nothing_from_an_in_flight_proposal_is_published(self) -> None:
        ids = sorted(
            p.name for p in CHANGES.iterdir() if p.is_dir() and p.name != "archive"
        )
        if not ids:
            self.skipTest("no open changes to test against")
        blob = "\n".join(
            p.read_text(encoding="utf-8", errors="replace")
            for p in self.pages()
            if "evidence" not in p.parts
        )
        leaked = [i for i in ids if i in blob]
        self.assertEqual(leaked, [], f"in-flight change ids leaked: {leaked}")

    def test_both_themes_are_defined(self) -> None:
        css = "\n".join(p.read_text(encoding="utf-8") for p in DIST.rglob("*.css"))
        # The CSS is minified, so match on structure rather than spelling.
        for what, pattern in (
            ("a dark media query", r"prefers-color-scheme:\s*dark"),
            ("an explicit dark stamp", r"\[data-theme=[\"\']?dark[\"\']?\]"),
            ("an explicit light stamp", r"\[data-theme=[\"\']?light[\"\']?\]"),
            ("a light palette on bare :root", r":root\s*\{[^}]*--ground:"),
            ("an explicit body background", r"body\s*\{[^}]*background:\s*var\(--ground\)"),
        ):
            self.assertTrue(
                re.search(pattern, css), f"the stylesheet is missing {what}"
            )


if __name__ == "__main__":
    unittest.main()
