#!/usr/bin/env python3
"""Read openspec/specs/ and hand Astro the one thing it must not get wrong:
which requirements are proven, and which are only claimed.

This is the data pass. It parses the specs, classifies every requirement,
checks that cited evidence exists, and writes site/src/data/specs.json plus
any binary evidence into site/public/. Astro turns that into the site; see
scripts/build_site.py, which runs both and enforces the budgets.

Runs on stdlib alone: no third-party packages, no network.

    ./scripts/render_specs.py            # writes site/src/data/specs.json

Conventions this renderer is coupled to, both established by
.skills/k230-spec-change/SKILL.md:

  <!-- UNVERIFIED: reason -->   a requirement nothing has grounded yet
  *Grounding: ... `path` ...*   what was observed or read, cited by path

A requirement carrying neither is *undeclared*: the renderer refuses to call it
grounded, records a defect, and the build exits non-zero naming the file and
the requirement. The site is still written, and shows the defect, because a
front door that reports "three requirements never said" is more useful than no
front door at all.
"""

from __future__ import annotations

import argparse
import html
import json
import re
import shutil
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

# --------------------------------------------------------------------------
# Budgets.
#
# Measured 2026-09-20 on `solomon`, an AMD Ryzen 9 5950X (32 threads),
# Python 3.14.7, rendering the tree recorded in docs/evidence/spec-site-build.txt.
# The budgets are set an order of magnitude above the measurement on purpose:
# the taxonomy in .skills/k230-spec-change/SKILL.md allows fifteen capabilities
# and this tree has far fewer, so a breach should mean something changed rather
# than that the numbers were always tight.
# --------------------------------------------------------------------------
MAX_GENERATION_SECONDS = 5.0
MAX_OUTPUT_BYTES = 4 * 1024 * 1024

GROUNDED = "grounded"
UNVERIFIED = "unverified"
UNDECLARED = "undeclared"

STATUS_ORDER = (GROUNDED, UNVERIFIED, UNDECLARED)
STATUS_LABEL = {
    GROUNDED: "grounded",
    UNVERIFIED: "unverified",
    UNDECLARED: "no status declared",
}

UNVERIFIED_MARKER = re.compile(r"<!--\s*UNVERIFIED\b\s*:?\s*(.*?)\s*-->", re.S)
GROUNDING_LINE = re.compile(r"(?m)^\s*\*{0,2}Grounding\b[^\n]*?:")
# Not the convention, and deliberately not accepted as one: three archived
# requirements opened with `*Grounded on hardware. ...*`, which classifies as
# undeclared and failed every build for a day. Widening the classifier to take
# it would also take `Grounded once the photograph is committed`, which is a
# promise rather than a citation -- so the near miss is detected only to say so
# in the error, and the prose is what gets fixed.
NEAR_MISS_GROUNDING = re.compile(r"(?m)^\s*\*{0,2}(Ground(?:ed|s|ing)\b[^\n]{0,40})")
REQUIREMENT_HEADING = re.compile(r"(?m)^###\s+Requirement:\s*(.+?)\s*$")
SCENARIO_HEADING = re.compile(r"(?m)^####\s+Scenario:\s*(.+?)\s*$")
SECTION_HEADING = re.compile(r"(?m)^##\s+(.+?)\s*$")

# A citation is a path: at least one slash, and a filename with an extension.
# Narrow on purpose -- `/dev/ttyACM0` and `openspec/specs/` are prose, not
# citations, and must not be mistaken for grounding.
CODE_PATH = re.compile(r"^[A-Za-z0-9_.@+-]+(?:/[A-Za-z0-9_.@+-]+)+$")
BARE_DOCS_PATH = re.compile(r"\bdocs/[A-Za-z0-9_./@+-]*[A-Za-z0-9_@+-]\.[A-Za-z0-9]+")

TEXT_SUFFIXES = {
    ".txt", ".log", ".md", ".json", ".yaml", ".yml", ".csv", ".dts", ".dtsi",
    ".c", ".h", ".py", ".sh", ".nix", ".rs", ".conf", ".cfg", ".toml",
}
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg"}

# The taxonomy in .skills/k230-spec-change/SKILL.md, in the order the board
# comes up: what produces an image, what boots, what a person sees, what talks,
# what runs on top, and how any of it is written down. Alphabetical would put
# `display` before `image`, which is backwards for a bring-up.
GROUP_ORDER = ("image", "system", "display", "radio", "runtime", "docs")
GROUP_BLURB = {
    "image": "how an image is produced and what the board loads",
    "system": "the NixOS closure, and getting a prompt",
    "display": "anything a person looks at or presses",
    "radio": "getting packets off the board",
    "runtime": "what we run on top once it boots",
    "docs": "how these specs reach a reader",
}


def group_rank(group: str) -> tuple[int, str]:
    if group in GROUP_ORDER:
        return (GROUP_ORDER.index(group), "")
    return (len(GROUP_ORDER), group)


class UnclassifiedRequirement(Exception):
    """A requirement whose verification status the renderer cannot determine.

    Raised rather than defaulting, because the count of unverified requirements
    is the only reason this site exists and a count that silently under-reports
    is worse than no site.
    """

    def __init__(self, source: str, requirement: str, near_miss: str = "") -> None:
        self.source = source
        self.requirement = requirement
        self.near_miss = near_miss
        detail = (
            f"{source}: requirement {requirement!r} declares no verification "
            f"status: it carries neither an `<!-- UNVERIFIED -->` marker nor a "
            f"`*Grounding: ...*` citation"
        )
        if near_miss:
            detail += (
                f"; it does begin a paragraph {near_miss!r}, which is close but "
                f"is not the convention -- the renderer looks for the word "
                f"`Grounding` followed by a colon on the same line, so write "
                f"`*Grounding: observed on hardware. ...*`"
            )
        super().__init__(detail)


class MissingEvidence(Exception):
    """A requirement cites evidence that is not committed."""

    def __init__(self, source: str, requirement: str, path: str) -> None:
        self.source = source
        self.requirement = requirement
        self.path = path
        super().__init__(
            f"{source}: requirement {requirement!r} cites evidence {path!r}, "
            f"which is not in the repository"
        )


class BudgetExceeded(Exception):
    """Generation ran long or the output grew past what was budgeted."""


# --------------------------------------------------------------------------
# Model
# --------------------------------------------------------------------------


@dataclass
class Scenario:
    title: str
    body: str


@dataclass
class Requirement:
    name: str
    status: str
    reason: str
    prose: str
    scenarios: list[Scenario] = field(default_factory=list)
    citations: list[str] = field(default_factory=list)
    evidence: list[str] = field(default_factory=list)
    source: str = ""


@dataclass
class Capability:
    group: str
    name: str
    purpose: str
    requirements: list[Requirement]
    source: str

    @property
    def slug(self) -> str:
        return f"{self.group}-{self.name}"

    @property
    def ident(self) -> str:
        return f"{self.group}/{self.name}"

    def tally(self) -> dict[str, int]:
        counts = {s: 0 for s in STATUS_ORDER}
        for req in self.requirements:
            counts[req.status] += 1
        return counts


@dataclass
class Defect:
    kind: str
    source: str
    requirement: str
    detail: str


@dataclass
class Report:
    capabilities: list[Capability]
    defects: list[Defect]
    seconds: float = 0.0
    output_bytes: int = 0
    pages: int = 0
    max_seconds: float = MAX_GENERATION_SECONDS
    max_bytes: int = MAX_OUTPUT_BYTES

    def tally(self) -> dict[str, int]:
        counts = {s: 0 for s in STATUS_ORDER}
        for cap in self.capabilities:
            for status, n in cap.tally().items():
                counts[status] += n
        return counts

    @property
    def total_requirements(self) -> int:
        return sum(self.tally().values())


# --------------------------------------------------------------------------
# Parsing
# --------------------------------------------------------------------------


def mask_code(text: str) -> str:
    """Blank out `code spans`, preserving offsets.

    A requirement may *talk about* the conventions -- "a path named only inside
    an `<!-- UNVERIFIED -->` marker is not a citation" -- and quoting one must
    not be mistaken for using one. Offsets are preserved so a match found in
    the masked text can be sliced out of the original.
    """
    return re.sub(r"`[^`\n]*`", lambda m: " " * len(m.group(0)), text)


def find_marker(text: str) -> re.Match[str] | None:
    hit = UNVERIFIED_MARKER.search(mask_code(text))
    if not hit:
        return None
    return UNVERIFIED_MARKER.match(text, hit.start())


def strip_markers(text: str) -> str:
    """Remove UNVERIFIED comments. Their prose often names evidence that is
    intended rather than committed ("Grounded once docs/evidence/x.txt ..."),
    and treating that as a citation would report a missing file for every
    requirement that is honestly waiting on one."""
    out: list[str] = []
    last = 0
    for hit in UNVERIFIED_MARKER.finditer(mask_code(text)):
        out.append(text[last : hit.start()])
        out.append(" ")
        last = hit.end()
    out.append(text[last:])
    return "".join(out)


def near_miss(body: str) -> str:
    """The opening of a paragraph that looks like a grounding line and is not.

    Reported in the error so the drift names itself. The convention lives in
    .skills/k230-spec-change/SKILL.md; this is what makes a change to it a
    legible build failure rather than a puzzling one.
    """
    hit = NEAR_MISS_GROUNDING.search(mask_code(strip_markers(body)))
    if not hit:
        return ""
    return " ".join(hit.group(1).split())


def classify(source: str, name: str, body: str) -> tuple[str, str]:
    """Return (status, reason) for one requirement body, or raise.

    Never returns GROUNDED by default: a body with no marker and no grounding
    citation raises UnclassifiedRequirement.
    """
    marker = find_marker(body)
    if marker:
        reason = " ".join(marker.group(1).split())
        return UNVERIFIED, reason or "no reason given"
    if GROUNDING_LINE.search(mask_code(strip_markers(body))):
        return GROUNDED, ""
    raise UnclassifiedRequirement(source, name, near_miss(body))


def code_spans(text: str) -> list[str]:
    return re.findall(r"`([^`\n]+)`", text)


def citations(body: str) -> list[str]:
    """Paths a requirement cites, in order, deduplicated."""
    text = strip_markers(body)
    found: list[str] = []
    for span in code_spans(text):
        span = span.strip()
        if CODE_PATH.match(span) and "." in span.rsplit("/", 1)[-1]:
            found.append(span)
    for match in BARE_DOCS_PATH.finditer(re.sub(r"`[^`\n]+`", " ", text)):
        found.append(match.group(0))
    out: list[str] = []
    for path in found:
        if path not in out:
            out.append(path)
    return out


def evidence_citations(body: str) -> list[str]:
    """The subset of citations that name a file this repository must hold.

    `docs/` is where this project commits what it observed; everything else a
    requirement cites lives in the vendored SDK clone, which is gitignored.
    """
    return [p for p in citations(body) if p.startswith("docs/")]


def split_requirements(text: str) -> list[tuple[str, str]]:
    matches = list(REQUIREMENT_HEADING.finditer(text))
    out: list[tuple[str, str]] = []
    for i, match in enumerate(matches):
        start = match.end()
        end = len(text)
        if i + 1 < len(matches):
            end = matches[i + 1].start()
        else:
            nxt = SECTION_HEADING.search(text, start)
            if nxt:
                end = nxt.start()
        out.append((match.group(1), text[start:end].strip()))
    return out


def split_scenarios(body: str) -> tuple[str, list[Scenario]]:
    matches = list(SCENARIO_HEADING.finditer(body))
    if not matches:
        return body.strip(), []
    prose = body[: matches[0].start()].strip()
    scenarios: list[Scenario] = []
    for i, match in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(body)
        scenarios.append(Scenario(match.group(1), body[match.end() : end].strip()))
    return prose, scenarios


def section(text: str, title: str) -> str:
    for match in SECTION_HEADING.finditer(text):
        if match.group(1).strip().lower() == title.lower():
            nxt = SECTION_HEADING.search(text, match.end())
            end = nxt.start() if nxt else len(text)
            return text[match.end() : end].strip()
    return ""


def parse_capability(repo_root: Path, path: Path, specs_dir: Path) -> tuple[Capability, list[Defect]]:
    text = printable(path.read_text(encoding="utf-8"))
    rel = path.relative_to(repo_root).as_posix()
    parts = path.relative_to(specs_dir).parts
    group = parts[0] if len(parts) > 1 else "ungrouped"
    name = parts[-2] if len(parts) > 1 else path.stem

    defects: list[Defect] = []
    requirements: list[Requirement] = []
    for req_name, body in split_requirements(text):
        try:
            status, reason = classify(rel, req_name, body)
        except UnclassifiedRequirement as exc:
            status, reason = UNDECLARED, ""
            defects.append(Defect("undeclared", rel, req_name, str(exc)))
        prose, scenarios = split_scenarios(body)
        cites = citations(body)
        evidence: list[str] = []
        for cite in evidence_citations(body):
            if (repo_root / cite).is_file():
                evidence.append(cite)
            else:
                defects.append(
                    Defect(
                        "missing-evidence",
                        rel,
                        req_name,
                        str(MissingEvidence(rel, req_name, cite)),
                    )
                )
        requirements.append(
            Requirement(
                name=req_name,
                status=status,
                reason=reason,
                prose=prose,
                scenarios=scenarios,
                citations=cites,
                evidence=evidence,
                source=rel,
            )
        )

    return (
        Capability(
            group=group,
            name=name,
            purpose=section(text, "Purpose"),
            requirements=requirements,
            source=rel,
        ),
        defects,
    )


def hand_authored_citations(repo_root: Path) -> list[tuple[str, str]]:
    """Paths under `docs/` named by the hand-authored pages, with their page.

    The hardware notes under `site/src/pages/hardware/` are written by hand and
    are not requirements -- but they cite the same committed evidence, and a
    reader has the same claim on it. Naming the path in the page is what asks
    for it: the file is rendered into the site, the note links to it, and a
    note citing something that is not committed is a defect exactly as a
    requirement citing it would be.
    """
    src = repo_root / "site" / "src"
    found: list[tuple[str, str]] = []
    seen: set[str] = set()
    if not src.is_dir():
        return found
    for page in sorted(src.rglob("*.astro")):
        text = page.read_text(encoding="utf-8", errors="replace")
        for match in BARE_DOCS_PATH.finditer(text):
            path = match.group(0)
            if path in seen:
                continue
            seen.add(path)
            found.append((path, page.relative_to(repo_root).as_posix()))
    return found


def load_capabilities(repo_root: Path) -> tuple[list[Capability], list[Defect]]:
    """Read openspec/specs/ -- and nothing else. openspec/changes/ holds
    in-flight proposals, and a published draft is read as a decision."""
    specs_dir = repo_root / "openspec" / "specs"
    caps: list[Capability] = []
    defects: list[Defect] = []
    if not specs_dir.is_dir():
        return caps, defects
    for path in sorted(specs_dir.rglob("spec.md")):
        cap, cap_defects = parse_capability(repo_root, path, specs_dir)
        caps.append(cap)
        defects.extend(cap_defects)
    caps.sort(key=lambda c: (group_rank(c.group), c.name))
    return caps, defects


# --------------------------------------------------------------------------
# A small Markdown subset: paragraphs, bullets, `code`, *em*, **strong**.
# Enough for spec prose, and nothing that needs a dependency.
# --------------------------------------------------------------------------

SENTINEL = "\x00%d\x00"

# Astro substitutes its base path for this before any HTML reaches a page.
BASE_PLACEHOLDER = "@@BASE@@"


# A serial capture carries the bytes the line carried. docs/rtsmart-boot-log.txt
# holds two NULs. Dropping them would edit the evidence, so they are shown as
# the Unicode control pictures instead -- visible, and safe to serve.
CONTROL_PICTURES = {
    c: chr(0x2400 + c) for c in range(0x20) if c not in (0x09, 0x0A)
} | {0x7F: "\u2421"}


def printable(text: str) -> str:
    return text.translate(CONTROL_PICTURES)


def esc(value: object) -> str:
    return html.escape(str(value), quote=True)


def md_inline(text: str, link: "Linker") -> str:
    stash: list[str] = []

    def keep(markup: str) -> str:
        stash.append(markup)
        return SENTINEL % (len(stash) - 1)

    def code(match: re.Match[str]) -> str:
        raw = match.group(1).strip()
        href = link(raw)
        inner = f"<code>{esc(raw)}</code>"
        if href:
            return keep(f'<a class="cite" href="{esc(href)}">{inner}</a>')
        return keep(inner)

    out = re.sub(r"`([^`\n]+)`", code, text)
    out = esc(out)

    def bare(match: re.Match[str]) -> str:
        raw = match.group(0)
        href = link(raw)
        if href:
            return keep(f'<a class="cite" href="{esc(href)}"><code>{esc(raw)}</code></a>')
        return raw

    out = BARE_DOCS_PATH.sub(bare, out)
    out = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", out, flags=re.S)
    out = re.sub(r"(?<!\*)\*([^*]+?)\*(?!\*)", r"<em>\1</em>", out, flags=re.S)
    for i, markup in enumerate(stash):
        out = out.replace(SENTINEL % i, markup)
    return out


def md_block(text: str, link: "Linker") -> str:
    parts: list[str] = []
    for chunk in re.split(r"\n\s*\n", text.strip()):
        lines = [ln.rstrip() for ln in chunk.splitlines() if ln.strip()]
        if not lines:
            continue
        if all(ln.lstrip().startswith(("- ", "* ")) for ln in lines):
            items = "".join(
                f"<li>{md_inline(ln.lstrip()[2:], link)}</li>" for ln in lines
            )
            parts.append(f"<ul>{items}</ul>")
            continue
        joined = " ".join(lines)
        grounding = re.match(r"^\*{0,2}(Grounding\b[^:]*):\s*(.*)$", joined, re.S)
        if grounding:
            tag = " ".join(grounding.group(1).split()).lower()
            inner = grounding.group(2).strip()
            if inner.endswith("*"):
                inner = inner.rstrip("*").strip()
            parts.append(
                f'<div class="grounding"><span class="grounding-tag">{esc(tag)}</span>'
                f"<p>{md_inline(inner, link)}</p></div>"
            )
            continue
        parts.append(f"<p>{md_inline(joined, link)}</p>")
    return "".join(parts)


# --------------------------------------------------------------------------
# Rendering
# --------------------------------------------------------------------------


class Linker:
    """Turns a cited repository path into a link into the generated site.

    Evidence under docs/ is copied into the site so the boot log or photograph
    behind a requirement is one click away from the requirement, wherever the
    site is served from. Vendor source paths are shown but not linked: they
    live in the 2.5 GB SDK clone, which is not committed.
    """

    def __init__(self, repo_root: Path) -> None:
        self.repo_root = repo_root
        self.wanted: dict[str, str] = {}

    def page_for(self, path: str) -> str:
        return re.sub(r"[^A-Za-z0-9]+", "-", path).strip("-").lower()

    def __call__(self, path: str) -> str | None:
        if not path.startswith("docs/"):
            return None
        if not (self.repo_root / path).is_file():
            return None
        slug = self.page_for(path)
        self.wanted[path] = slug
        # BASE_PLACEHOLDER is substituted for Astro's import.meta.env.BASE_URL
        # at render time. The data pass does not know where the site is served
        # from, and should not have to.
        return f"{BASE_PLACEHOLDER}evidence/{slug}/"




# --------------------------------------------------------------------------
# Emit
# --------------------------------------------------------------------------


def slugify(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")[:60] or "x"


def first_sentence(text: str) -> str:
    flat = " ".join(text.split())
    if not flat:
        return ""
    match = re.search(r"^(.+?[.])(\s|$)", flat)
    out = match.group(1) if match else flat
    return out if len(out) <= 200 else out[:197] + "..."


def tally_dict(counts: dict[str, int]) -> dict[str, int]:
    return {status: counts[status] for status in STATUS_ORDER}


def build_data(repo_root: Path, asset_dir: Path | None = None) -> tuple[dict, Report]:
    caps, defects = load_capabilities(repo_root)
    report = Report(capabilities=caps, defects=defects)
    link = Linker(repo_root)

    capability_data = []
    for cap in caps:
        requirements = []
        for req in cap.requirements:
            requirements.append(
                {
                    "name": req.name,
                    "slug": slugify(req.name),
                    "status": req.status,
                    "reason": req.reason,
                    "proseHtml": md_block(strip_markers(req.prose).strip(), link),
                    "evidence": [
                        {"path": path, "slug": link.page_for(path), "href": link(path)}
                        for path in req.evidence
                    ],
                    "scenarios": [
                        {"title": s.title, "bodyHtml": md_block(s.body, link)}
                        for s in req.scenarios
                    ],
                }
            )
        capability_data.append(
            {
                "group": cap.group,
                "name": cap.name,
                "slug": cap.slug,
                "ident": cap.ident,
                "source": cap.source,
                "blurb": GROUP_BLURB.get(cap.group, ""),
                "purposeHtml": md_block(cap.purpose, link) if cap.purpose else "",
                "purposeFirst": first_sentence(cap.purpose),
                "tally": tally_dict(cap.tally()),
                "requirements": requirements,
            }
        )

    # Evidence the requirements cite is registered by now; what the
    # hand-authored pages cite is registered here, so both kinds reach the
    # site as pages and both are checked for being committed.
    from_requirements = set(link.wanted)
    for path, page in hand_authored_citations(repo_root):
        if link(path) is None:
            defects.append(
                Defect(
                    "missing-evidence",
                    page,
                    "(hand-authored page)",
                    f"{page}: cites evidence {path!r}, which is not in the "
                    f"repository",
                )
            )

    evidence = []
    for path, slug in sorted(link.wanted.items()):
        source = repo_root / path
        entry = {
            "path": path,
            "slug": slug,
            "name": source.name,
            "bytes": source.stat().st_size,
            # Which kind of claim rests on this file. A requirement's evidence
            # is counted in the tally above; a note's is not, and the landing
            # page says so rather than letting the two look alike.
            "citedBy": "requirement" if path in from_requirements else "note",
        }
        if source.suffix.lower() in IMAGE_SUFFIXES:
            asset = f"evidence/{slug}{source.suffix.lower()}"
            entry["kind"] = "image"
            entry["asset"] = asset
            if asset_dir is not None:
                target = asset_dir / asset
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(source.read_bytes())
        else:
            entry["kind"] = "text"
            entry["text"] = printable(
                source.read_text(encoding="utf-8", errors="replace")
            )
        evidence.append(entry)

    groups: list[dict] = []
    for cap in capability_data:
        if not groups or groups[-1]["name"] != cap["group"]:
            groups.append(
                {
                    "name": cap["group"],
                    "blurb": GROUP_BLURB.get(cap["group"], ""),
                    "slugs": [],
                }
            )
        groups[-1]["slugs"].append(cap["slug"])

    data = {
        "generated": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "tally": tally_dict(report.tally()),
        "total": report.total_requirements,
        "groups": groups,
        "capabilities": capability_data,
        "evidence": evidence,
        "defects": [
            {
                "kind": d.kind,
                "source": d.source,
                "requirement": d.requirement,
                "detail": d.detail,
            }
            for d in defects
        ],
    }
    return data, report


def check_budgets(report: Report) -> None:
    breaches = []
    if report.seconds > report.max_seconds:
        breaches.append(
            f"generation took {report.seconds:.3f} s against a budget of "
            f"{report.max_seconds:.3f} s"
        )
    if report.output_bytes > report.max_bytes:
        breaches.append(
            f"output is {report.output_bytes} bytes against a budget of "
            f"{report.max_bytes} bytes"
        )
    if breaches:
        raise BudgetExceeded("budget exceeded: " + "; ".join(breaches))


def find_repo_root(start: Path) -> Path:
    for candidate in [start, *start.parents]:
        if (candidate / "openspec" / "config.yaml").is_file():
            return candidate
    return start


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--repo", default=None, help="repository root")
    parser.add_argument(
        "--json", default=None, help="where to write the data (default: site/src/data/specs.json)"
    )
    parser.add_argument(
        "--assets",
        default=None,
        help="where to copy binary evidence (default: site/public)",
    )
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args(argv)

    repo_root = Path(args.repo).resolve() if args.repo else find_repo_root(Path.cwd())
    out_json = (
        Path(args.json).resolve()
        if args.json
        else repo_root / "site" / "src" / "data" / "specs.json"
    )
    assets = (
        Path(args.assets).resolve() if args.assets else repo_root / "site" / "public"
    )

    data, report = build_data(repo_root, assets)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(data, indent=1, ensure_ascii=False), encoding="utf-8")

    counts = report.tally()
    if not args.quiet:
        for cap in report.capabilities:
            c = cap.tally()
            print(
                f"  {cap.ident:<28} {sum(c.values()):>3} requirements  "
                f"{c[GROUNDED]} grounded  {c[UNVERIFIED]} unverified"
                + (f"  {c[UNDECLARED]} undeclared" if c[UNDECLARED] else "")
            )
    print(
        f"{counts[UNVERIFIED]} of {report.total_requirements} requirements unverified"
        + (f", {counts[UNDECLARED]} undeclared" if counts[UNDECLARED] else "")
    )
    print(f"wrote {out_json}")

    if report.defects:
        print("", file=sys.stderr)
        for defect in report.defects:
            print(f"error: {defect.detail}", file=sys.stderr)
        print(
            f"error: {len(report.defects)} requirement defect(s); the data was "
            "written so the site can show them, but the build failed",
            file=sys.stderr,
        )
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
