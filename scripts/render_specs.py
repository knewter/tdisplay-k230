#!/usr/bin/env python3
"""Render openspec/specs/ into a static site whose first statement is how much
of this board's behaviour is unproven.

Runs on stdlib alone: no third-party packages, no network, no CI. One command.

    ./scripts/render_specs.py            # writes public/
    ./scripts/render_specs.py --out /tmp/site

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
import os
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


class UnclassifiedRequirement(Exception):
    """A requirement whose verification status the renderer cannot determine.

    Raised rather than defaulting, because the count of unverified requirements
    is the only reason this site exists and a count that silently under-reports
    is worse than no site.
    """

    def __init__(self, source: str, requirement: str) -> None:
        self.source = source
        self.requirement = requirement
        super().__init__(
            f"{source}: requirement {requirement!r} declares no verification "
            f"status: it carries neither an `<!-- UNVERIFIED -->` marker nor a "
            f"`*Grounding: ...*` citation"
        )


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


def strip_markers(text: str) -> str:
    """Remove UNVERIFIED comments. Their prose often names evidence that is
    intended rather than committed ("Grounded once docs/evidence/x.txt ..."),
    and treating that as a citation would report a missing file for every
    requirement that is honestly waiting on one."""
    return UNVERIFIED_MARKER.sub(" ", text)


def classify(source: str, name: str, body: str) -> tuple[str, str]:
    """Return (status, reason) for one requirement body, or raise.

    Never returns GROUNDED by default: a body with no marker and no grounding
    citation raises UnclassifiedRequirement.
    """
    marker = UNVERIFIED_MARKER.search(body)
    if marker:
        reason = " ".join(marker.group(1).split())
        return UNVERIFIED, reason or "no reason given"
    if GROUNDING_LINE.search(strip_markers(body)):
        return GROUNDED, ""
    raise UnclassifiedRequirement(source, name)


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
    text = path.read_text(encoding="utf-8")
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
    caps.sort(key=lambda c: (c.group, c.name))
    return caps, defects


# --------------------------------------------------------------------------
# A small Markdown subset: paragraphs, bullets, `code`, *em*, **strong**.
# Enough for spec prose, and nothing that needs a dependency.
# --------------------------------------------------------------------------

SENTINEL = "\x00%d\x00"


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
        if re.match(r"^\*{0,2}Grounding\b", joined):
            inner = joined
            if inner.startswith("*") and inner.endswith("*"):
                inner = inner[1:-1].strip()
            parts.append(
                '<div class="grounding"><span class="grounding-tag">grounding</span>'
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
        slug = re.sub(r"[^A-Za-z0-9]+", "-", path).strip("-").lower()
        return f"evidence-{slug}.html"

    def __call__(self, path: str) -> str | None:
        if not path.startswith("docs/"):
            return None
        if not (self.repo_root / path).is_file():
            return None
        page = self.page_for(path)
        self.wanted[path] = page
        return page


def tape(counts: dict[str, int], *, small: bool = False) -> str:
    total = sum(counts.values())
    cls = "tape tape-small" if small else "tape"
    if total == 0:
        return f'<div class="{cls} tape-empty" aria-hidden="true"></div>'
    segs = []
    for status in STATUS_ORDER:
        n = counts[status]
        if not n:
            continue
        pct = 100.0 * n / total
        segs.append(
            f'<span class="seg seg-{status}" style="flex:{n} 1 0"'
            f' title="{n} {esc(STATUS_LABEL[status])} ({pct:.0f}%)"></span>'
        )
    return f'<div class="{cls}" role="img" aria-label="{esc(tape_label(counts))}">{"".join(segs)}</div>'


def tape_label(counts: dict[str, int]) -> str:
    return ", ".join(f"{counts[s]} {STATUS_LABEL[s]}" for s in STATUS_ORDER if counts[s])


def chip(status: str) -> str:
    return f'<span class="chip chip-{status}">{esc(STATUS_LABEL[status])}</span>'


HEAD = """<title>{title}</title>
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;600&family=IBM+Plex+Sans+Condensed:wght@500;600;700&family=IBM+Plex+Serif:ital,wght@0,400;0,500;1,400&display=swap">
<link rel="stylesheet" href="styles.css">
"""


def page(title: str, body: str) -> str:
    return HEAD.format(title=esc(title)) + body


def footer(report: Report) -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    return (
        '<footer class="footer">'
        f'<p class="mono">generated {esc(stamp)} &middot; '
        f"{report.pages} pages &middot; "
        f"{report.output_bytes / 1024:.0f} KiB of {report.max_bytes / 1024 / 1024:.0f} MiB budget &middot; "
        f"{report.seconds:.2f} s of {report.max_seconds:.1f} s budget</p>"
        '<p class="mono dim">Rendered from <code>openspec/specs/</code>. '
        "In-flight proposals are not published.</p>"
        "</footer>"
    )


def requirement_block(req: Requirement, link: Linker) -> str:
    out = [f'<article class="req req-{req.status}" id="{esc(slugify(req.name))}">']
    out.append('<div class="req-head">')
    out.append(chip(req.status))
    out.append(f"<h3>{esc(req.name)}</h3>")
    out.append("</div>")

    if req.status == UNVERIFIED:
        out.append(
            '<div class="why"><span class="why-tag">why it is unverified</span>'
            f"<p>{esc(req.reason)}</p></div>"
        )
    elif req.status == UNDECLARED:
        out.append(
            '<div class="why why-defect"><span class="why-tag">build defect</span>'
            "<p>This requirement declares neither an <code>UNVERIFIED</code> marker "
            "nor a grounding citation. The renderer will not call it grounded, and "
            "the build that produced this page exited non-zero naming it.</p></div>"
        )

    if req.prose:
        out.append(f'<div class="prose">{md_block(req.prose, link)}</div>')

    if req.evidence:
        items = "".join(
            f'<li><a class="cite" href="{esc(link(path))}"><code>{esc(path)}</code></a></li>'
            for path in req.evidence
        )
        out.append(
            f'<div class="evidence"><span class="evidence-tag">evidence in this repository</span>'
            f"<ul>{items}</ul></div>"
        )

    if req.scenarios:
        out.append('<div class="scenarios"><span class="scenarios-tag">scenarios</span>')
        for scenario in req.scenarios:
            out.append(
                f'<div class="scenario"><h4>{esc(scenario.title)}</h4>'
                f"{md_block(scenario.body, link)}</div>"
            )
        out.append("</div>")

    out.append("</article>")
    return "".join(out)


def slugify(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")[:60] or "x"


def capability_page(cap: Capability, report: Report, link: Linker) -> str:
    counts = cap.tally()
    unproven = counts[UNVERIFIED] + counts[UNDECLARED]
    total = sum(counts.values())
    body = [
        '<nav class="crumbs"><a href="index.html">&larr; all capabilities</a>'
        f'<span class="mono dim">{esc(cap.source)}</span></nav>',
        '<header class="cap-head">',
        f'<p class="eyebrow">{esc(cap.group)}</p>',
        f"<h1>{esc(cap.name)}</h1>",
    ]
    if cap.purpose:
        body.append(f'<div class="purpose">{md_block(cap.purpose, link)}</div>')
    body.append("</header>")

    body.append('<section class="cap-verdict">')
    if total:
        body.append(
            f'<p class="verdict-small"><strong>{unproven}</strong> of {total} '
            f"requirement{'s' if total != 1 else ''} here {'are' if unproven != 1 else 'is'} not proven.</p>"
        )
    else:
        body.append('<p class="verdict-small">No requirements.</p>')
    body.append(tape(counts))
    body.append(legend(counts))
    body.append("</section>")

    body.append('<section class="reqs">')
    for req in cap.requirements:
        body.append(requirement_block(req, link))
    body.append("</section>")
    body.append(footer(report))
    return page(f"{cap.name} — K230 Verification Ledger", "".join(body))


def legend(counts: dict[str, int]) -> str:
    items = []
    for status in STATUS_ORDER:
        if not counts[status] and status == UNDECLARED:
            continue
        items.append(
            f'<li class="legend-{status}"><span class="swatch"></span>'
            f'<span class="legend-n">{counts[status]}</span>'
            f'<span class="legend-l">{esc(STATUS_LABEL[status])}</span></li>'
        )
    return f'<ul class="legend">{"".join(items)}</ul>'


def index_page(report: Report, link: Linker) -> str:
    counts = report.tally()
    total = report.total_requirements
    unverified = counts[UNVERIFIED]
    undeclared = counts[UNDECLARED]

    body: list[str] = []

    # The count comes first. Everything else on this page is downstream of it.
    body.append('<section class="verdict">')
    body.append('<p class="eyebrow">LILYGO T-Display-K230 &middot; specification ledger</p>')
    if total == 0:
        body.append(
            '<h1 class="count count-empty"><span class="n">0</span>'
            '<span class="of">requirements published yet</span></h1>'
        )
        body.append(
            '<p class="lede">Nothing has been archived into '
            "<code>openspec/specs/</code>. Capabilities appear here as changes "
            "are archived, and each requirement arrives either grounded in "
            "something observed or marked unverified.</p>"
        )
    else:
        body.append(
            f'<h1 class="count"><span class="n">{unverified}</span>'
            f'<span class="of">of {total} requirement{"s" if total != 1 else ""} '
            f"{'are' if unverified != 1 else 'is'} unverified</span></h1>"
        )
        if undeclared:
            body.append(
                f'<p class="alarm"><strong>{undeclared}</strong> more '
                f"declare{'s' if undeclared == 1 else ''} no status at all — "
                "neither grounded nor marked. The build that produced this page "
                "failed and named them.</p>"
            )
        body.append(
            '<p class="lede">On this board the documentation and the hardware '
            "disagree routinely. A datasheet described a working radio whose "
            "enable line is never driven. So a requirement counts as grounded "
            "only when something was observed on the board, or vendor source was "
            "read and cited by path — never because a datasheet says so.</p>"
        )
    body.append(tape(counts))
    body.append(legend(counts))
    body.append("</section>")

    if report.capabilities:
        body.append('<section class="ledger">')
        body.append('<h2 class="section-title">Capabilities</h2>')
        current = None
        for cap in report.capabilities:
            if cap.group != current:
                current = cap.group
                body.append(f'<h3 class="group">{esc(cap.group)}<span class="rule"></span></h3>')
            c = cap.tally()
            n = sum(c.values())
            unproven = c[UNVERIFIED] + c[UNDECLARED]
            first = first_sentence(cap.purpose)
            body.append(
                f'<a class="row" href="{esc(cap.slug)}.html">'
                f'<span class="row-name">{esc(cap.name)}</span>'
                f'<span class="row-purpose">{esc(first)}</span>'
                f'<span class="row-tape">{tape(c, small=True)}</span>'
                f'<span class="row-count"><strong>{unproven}</strong>/{n}'
                f'<span class="row-count-l">unproven</span></span>'
                "</a>"
            )
        body.append("</section>")

    if report.defects:
        body.append('<section class="defects">')
        body.append('<h2 class="section-title">Build defects</h2>')
        body.append(
            '<p class="defect-lede">These stopped the build from succeeding. '
            "A requirement with no declared status, or one citing evidence that "
            "is not committed, is a defect in the requirement.</p>"
        )
        body.append("<ul>")
        for defect in report.defects:
            body.append(
                f'<li><span class="defect-kind">{esc(defect.kind)}</span>'
                f'<span class="mono">{esc(defect.source)}</span>'
                f"<span>{esc(defect.requirement)}</span></li>"
            )
        body.append("</ul></section>")

    body.append(footer(report))
    return page("K230 Verification Ledger", "".join(body))


def first_sentence(text: str) -> str:
    flat = " ".join(text.split())
    if not flat:
        return ""
    match = re.search(r"^(.+?[.])(\s|$)", flat)
    out = match.group(1) if match else flat
    return out if len(out) <= 180 else out[:177] + "..."


def evidence_page(repo_root: Path, path: str, report: Report) -> tuple[str, bytes | None]:
    source = repo_root / path
    suffix = source.suffix.lower()
    head = (
        '<nav class="crumbs"><a href="index.html">&larr; all capabilities</a>'
        f'<span class="mono dim">{esc(path)}</span></nav>'
        '<header class="cap-head"><p class="eyebrow">evidence</p>'
        f"<h1>{esc(source.name)}</h1>"
        f'<p class="purpose mono dim">Committed at <code>{esc(path)}</code>. '
        "This is what grounds the requirements that cite it.</p></header>"
    )
    if suffix in IMAGE_SUFFIXES:
        asset = "asset-" + re.sub(r"[^A-Za-z0-9.]+", "-", path).strip("-").lower()
        body = f'<div class="ev-image"><img src="{esc(asset)}" alt="{esc(path)}"></div>'
        return page(f"{source.name} — evidence", head + body + footer(report)), source.read_bytes()
    text = source.read_text(encoding="utf-8", errors="replace")
    body = f'<pre class="ev-text">{esc(text)}</pre>'
    return page(f"{source.name} — evidence", head + body + footer(report)), None


# --------------------------------------------------------------------------
# Build
# --------------------------------------------------------------------------


def build_site(
    repo_root: Path,
    out: Path,
    *,
    max_seconds: float = MAX_GENERATION_SECONDS,
    max_bytes: int = MAX_OUTPUT_BYTES,
) -> Report:
    started = time.monotonic()
    caps, defects = load_capabilities(repo_root)
    report = Report(
        capabilities=caps,
        defects=defects,
        max_seconds=max_seconds,
        max_bytes=max_bytes,
    )
    link = Linker(repo_root)

    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)

    written: dict[str, str | bytes] = {}
    for cap in caps:
        written[f"{cap.slug}.html"] = capability_page(cap, report, link)
    # Evidence pages are discovered while rendering capabilities.
    for path, page_name in sorted(link.wanted.items()):
        markup, blob = evidence_page(repo_root, path, report)
        written[page_name] = markup
        if blob is not None:
            asset = "asset-" + re.sub(r"[^A-Za-z0-9.]+", "-", path).strip("-").lower()
            written[asset] = blob
    written["index.html"] = index_page(report, link)
    written["styles.css"] = STYLES

    for name, payload in written.items():
        target = out / name
        if isinstance(payload, bytes):
            target.write_bytes(payload)
        else:
            target.write_text(payload, encoding="utf-8")

    report.pages = sum(1 for n in written if n.endswith(".html"))
    report.output_bytes = sum(
        p.stat().st_size for p in out.rglob("*") if p.is_file()
    )
    report.seconds = time.monotonic() - started

    # Rewrite the pages whose footer quotes the final measurements.
    (out / "index.html").write_text(index_page(report, link), encoding="utf-8")
    for cap in caps:
        (out / f"{cap.slug}.html").write_text(
            capability_page(cap, report, link), encoding="utf-8"
        )
    report.output_bytes = sum(
        p.stat().st_size for p in out.rglob("*") if p.is_file()
    )
    return report


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
    parser.add_argument("--out", default=None, help="output directory (default: public/)")
    parser.add_argument("--repo", default=None, help="repository root")
    parser.add_argument("--max-seconds", type=float, default=MAX_GENERATION_SECONDS)
    parser.add_argument("--max-bytes", type=int, default=MAX_OUTPUT_BYTES)
    parser.add_argument(
        "--quiet", action="store_true", help="only print the summary line"
    )
    args = parser.parse_args(argv)

    repo_root = Path(args.repo).resolve() if args.repo else find_repo_root(Path.cwd())
    out = Path(args.out).resolve() if args.out else repo_root / "public"

    report = build_site(
        repo_root,
        out,
        max_seconds=args.max_seconds,
        max_bytes=args.max_bytes,
    )
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
        f"{out}: {report.pages} pages, {report.output_bytes} bytes, "
        f"{report.seconds:.3f} s"
    )
    print(
        f"{counts[UNVERIFIED]} of {report.total_requirements} requirements unverified"
    )

    status = 0
    try:
        check_budgets(report)
    except BudgetExceeded as exc:
        print(f"error: {exc}", file=sys.stderr)
        status = 1

    if report.defects:
        print("", file=sys.stderr)
        for defect in report.defects:
            print(f"error: {defect.detail}", file=sys.stderr)
        print(
            f"error: {len(report.defects)} requirement defect(s); "
            "the site was written but the build failed",
            file=sys.stderr,
        )
        status = 2
    return status


STYLES = """
:root {
  color-scheme: light;
  --ground:    #eceff0;
  --surface:   #ffffff;
  --surface-2: #f4f6f6;
  --ink:       #11181a;
  --ink-2:     #3d4a4c;
  --muted:     #66767a;
  --rule:      #d2dadb;
  --rule-2:    #e3e9ea;
  --grounded:  #0d7358;
  --grounded-f:#0d735826;
  --unverified:#a85c07;
  --unverified-f:#a85c0722;
  --undeclared:#a8271f;
  --undeclared-f:#a8271f1f;
  --accent:    #0d7358;
  --shadow:    0 1px 2px #11181a0f, 0 8px 24px -16px #11181a3d;
  --mono: "IBM Plex Mono", ui-monospace, "SFMono-Regular", Menlo, monospace;
  --sans: "IBM Plex Sans Condensed", "IBM Plex Sans", system-ui, sans-serif;
  --serif: "IBM Plex Serif", Georgia, "Times New Roman", serif;
}
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) {
    color-scheme: dark;
    --ground:    #0b0f10;
    --surface:   #141a1b;
    --surface-2: #1a2223;
    --ink:       #e7eeed;
    --ink-2:     #b9c6c5;
    --muted:     #869695;
    --rule:      #263234;
    --rule-2:    #1e2829;
    --grounded:  #46c39d;
    --grounded-f:#46c39d1f;
    --unverified:#e0a04a;
    --unverified-f:#e0a04a1f;
    --undeclared:#ee6b62;
    --undeclared-f:#ee6b621f;
    --accent:    #46c39d;
    --shadow:    0 1px 2px #00000055, 0 10px 30px -18px #000000aa;
  }
}
:root[data-theme="dark"] {
  color-scheme: dark;
  --ground:    #0b0f10;
  --surface:   #141a1b;
  --surface-2: #1a2223;
  --ink:       #e7eeed;
  --ink-2:     #b9c6c5;
  --muted:     #869695;
  --rule:      #263234;
  --rule-2:    #1e2829;
  --grounded:  #46c39d;
  --grounded-f:#46c39d1f;
  --unverified:#e0a04a;
  --unverified-f:#e0a04a1f;
  --undeclared:#ee6b62;
  --undeclared-f:#ee6b621f;
  --accent:    #46c39d;
  --shadow:    0 1px 2px #00000055, 0 10px 30px -18px #000000aa;
}

* { box-sizing: border-box; }

body {
  margin: 0;
  background: var(--ground);
  color: var(--ink);
  font-family: var(--serif);
  font-size: 16px;
  line-height: 1.6;
  padding-block: clamp(28px, 6vw, 72px);
  padding-left: max(16px, calc(50vw - 460px));
  padding-right: max(16px, calc(50vw - 460px));
  -webkit-font-smoothing: antialiased;
}

a { color: var(--accent); }
a:focus-visible, .row:focus-visible {
  outline: 2px solid var(--accent);
  outline-offset: 3px;
  border-radius: 2px;
}
code, .mono { font-family: var(--mono); font-variant-ligatures: none; }
code {
  font-size: 0.86em;
  background: var(--surface-2);
  border: 1px solid var(--rule-2);
  border-radius: 3px;
  padding: 0.05em 0.32em;
  word-break: break-word;
}
a.cite code {
  border-color: color-mix(in srgb, var(--accent) 40%, var(--rule));
  background: color-mix(in srgb, var(--accent) 8%, var(--surface-2));
  color: var(--accent);
}
a.cite { text-decoration: none; }
a.cite:hover code { background: color-mix(in srgb, var(--accent) 16%, var(--surface-2)); }

.eyebrow {
  font-family: var(--mono);
  font-size: 11px;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: var(--muted);
  margin: 0 0 14px;
}

/* ---- the count: the first thing on the page ---- */
.verdict { margin: 0 0 clamp(36px, 6vw, 56px); }
.count {
  margin: 0;
  display: flex;
  align-items: baseline;
  flex-wrap: wrap;
  gap: 0 0.4em;
  font-family: var(--sans);
  font-weight: 600;
  letter-spacing: -0.015em;
  text-wrap: balance;
}
.count .n {
  font-size: clamp(64px, 17vw, 128px);
  line-height: 0.82;
  color: var(--unverified);
  font-variant-numeric: tabular-nums;
  font-weight: 700;
}
.count .of {
  font-size: clamp(20px, 4.2vw, 30px);
  line-height: 1.15;
  color: var(--ink);
  max-width: 14ch;
}
.count-empty .n { color: var(--muted); }
.count-empty .of { max-width: 18ch; }

.lede {
  margin: 20px 0 0;
  max-width: 62ch;
  color: var(--ink-2);
  font-size: 15.5px;
}
.alarm {
  margin: 18px 0 0;
  max-width: 62ch;
  padding: 10px 14px;
  border-left: 3px solid var(--undeclared);
  background: var(--undeclared-f);
  color: var(--ink);
  font-size: 15px;
}
.alarm strong { color: var(--undeclared); font-variant-numeric: tabular-nums; }

/* ---- the tape: one bar, proportional, the page's strongest signal ---- */
.tape {
  display: flex;
  height: 14px;
  margin-top: 26px;
  gap: 2px;
  background: var(--rule-2);
  border: 1px solid var(--rule);
  padding: 2px;
  border-radius: 2px;
  overflow: hidden;
}
.tape-small { height: 8px; margin-top: 0; padding: 1px; gap: 1px; }
.tape-empty { background: repeating-linear-gradient(135deg, var(--rule-2) 0 6px, var(--surface-2) 6px 12px); }
.seg { display: block; min-width: 3px; border-radius: 1px; }
.seg-grounded   { background: var(--grounded); }
.seg-unverified { background: var(--unverified); }
.seg-undeclared { background: var(--undeclared); }

.legend {
  list-style: none;
  display: flex;
  flex-wrap: wrap;
  gap: 6px 22px;
  margin: 12px 0 0;
  padding: 0;
  font-family: var(--mono);
  font-size: 12px;
}
.legend li { display: flex; align-items: center; gap: 7px; }
.legend .swatch { width: 9px; height: 9px; border-radius: 1px; flex: none; }
.legend-grounded .swatch   { background: var(--grounded); }
.legend-unverified .swatch { background: var(--unverified); }
.legend-undeclared .swatch { background: var(--undeclared); }
.legend-n { font-weight: 600; font-variant-numeric: tabular-nums; color: var(--ink); }
.legend-l { color: var(--muted); letter-spacing: 0.02em; }

/* ---- capability ledger ---- */
.section-title {
  font-family: var(--mono);
  font-size: 11px;
  letter-spacing: 0.16em;
  text-transform: uppercase;
  color: var(--muted);
  font-weight: 500;
  margin: 0 0 4px;
}
.group {
  display: flex;
  align-items: center;
  gap: 14px;
  font-family: var(--mono);
  font-size: 12px;
  font-weight: 600;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--ink-2);
  margin: 30px 0 8px;
}
.group .rule { flex: 1; height: 1px; background: var(--rule); }

.row {
  display: grid;
  grid-template-columns: minmax(8ch, 15ch) 1fr 90px 64px;
  align-items: center;
  gap: 18px;
  padding: 14px 16px;
  margin-top: 6px;
  background: var(--surface);
  border: 1px solid var(--rule-2);
  border-radius: 3px;
  text-decoration: none;
  color: inherit;
  transition: border-color .12s, transform .12s;
}
.row:hover { border-color: var(--accent); transform: translateX(2px); }
.row-name {
  font-family: var(--mono);
  font-size: 13.5px;
  font-weight: 600;
  color: var(--ink);
}
.row-purpose {
  font-size: 14px;
  color: var(--muted);
  line-height: 1.45;
}
.row-count {
  font-family: var(--mono);
  font-size: 13px;
  text-align: right;
  font-variant-numeric: tabular-nums;
  color: var(--muted);
}
.row-count strong { color: var(--unverified); font-size: 16px; }
.row-count-l {
  display: block;
  font-size: 9.5px;
  letter-spacing: 0.1em;
  text-transform: uppercase;
}

/* ---- defects ---- */
.defects { margin-top: 44px; }
.defect-lede { max-width: 62ch; color: var(--ink-2); font-size: 15px; margin: 10px 0 16px; }
.defects ul { list-style: none; margin: 0; padding: 0; display: grid; gap: 6px; }
.defects li {
  display: grid;
  grid-template-columns: 130px minmax(0, 1fr);
  gap: 4px 14px;
  padding: 12px 14px;
  border-left: 3px solid var(--undeclared);
  background: var(--undeclared-f);
  font-size: 14.5px;
}
.defect-kind {
  grid-row: span 2;
  font-family: var(--mono);
  font-size: 10.5px;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  color: var(--undeclared);
  padding-top: 4px;
}
.defects .mono { font-size: 12px; color: var(--muted); }

/* ---- capability page ---- */
.crumbs {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  gap: 16px;
  flex-wrap: wrap;
  font-family: var(--mono);
  font-size: 12px;
  margin-bottom: 30px;
}
.crumbs a { text-decoration: none; }
.crumbs a:hover { text-decoration: underline; }
.dim { color: var(--muted); }
.cap-head h1 {
  font-family: var(--mono);
  font-size: clamp(30px, 6vw, 44px);
  font-weight: 600;
  letter-spacing: -0.02em;
  margin: 0;
  color: var(--ink);
  overflow-wrap: anywhere;
}
.purpose { margin-top: 14px; max-width: 64ch; color: var(--ink-2); }
.purpose p { margin: 0 0 0.7em; }
.cap-verdict {
  margin: 30px 0 40px;
  padding: 20px;
  background: var(--surface);
  border: 1px solid var(--rule-2);
  border-radius: 3px;
}
.verdict-small {
  margin: 0;
  font-family: var(--sans);
  font-size: 19px;
  font-weight: 500;
}
.verdict-small strong {
  color: var(--unverified);
  font-size: 26px;
  font-variant-numeric: tabular-nums;
}

/* ---- requirements ---- */
.reqs { display: grid; gap: 22px; }
.req {
  background: var(--surface);
  border: 1px solid var(--rule-2);
  border-left: 4px solid var(--rule);
  border-radius: 3px;
  padding: 20px 22px 22px;
  box-shadow: var(--shadow);
}
.req-grounded   { border-left-color: var(--grounded); }
.req-unverified { border-left-color: var(--unverified); }
.req-undeclared { border-left-color: var(--undeclared); }
.req-head { display: flex; flex-direction: column; gap: 10px; }
.req-head h3 {
  margin: 0;
  font-family: var(--sans);
  font-size: clamp(19px, 3.4vw, 24px);
  font-weight: 600;
  line-height: 1.22;
  letter-spacing: -0.01em;
  text-wrap: balance;
}
.chip {
  align-self: flex-start;
  font-family: var(--mono);
  font-size: 10px;
  font-weight: 600;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  padding: 3px 8px;
  border-radius: 2px;
}
.chip-grounded   { color: var(--grounded);   background: var(--grounded-f);   border: 1px solid var(--grounded); }
.chip-unverified { color: var(--unverified); background: var(--unverified-f); border: 1px solid var(--unverified); }
.chip-undeclared { color: var(--undeclared); background: var(--undeclared-f); border: 1px solid var(--undeclared); }

.prose { margin-top: 14px; max-width: 66ch; }
.prose p { margin: 0 0 0.85em; }
.prose ul { margin: 0 0 0.85em; padding-left: 1.2em; }
.prose strong { font-weight: 600; }

.why, .grounding, .evidence {
  margin-top: 14px;
  padding: 12px 14px;
  border-radius: 2px;
  font-size: 14.5px;
}
.why { background: var(--unverified-f); border-left: 3px solid var(--unverified); }
.why-defect { background: var(--undeclared-f); border-left-color: var(--undeclared); }
.why p { margin: 0; color: var(--ink); }
.why-tag, .grounding-tag, .evidence-tag, .scenarios-tag {
  display: block;
  font-family: var(--mono);
  font-size: 10px;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  margin-bottom: 6px;
  color: var(--muted);
}
.why .why-tag { color: var(--unverified); }
.why-defect .why-tag { color: var(--undeclared); }
.grounding {
  background: var(--grounded-f);
  border-left: 3px solid var(--grounded);
}
.grounding .grounding-tag { color: var(--grounded); }
.grounding p { margin: 0; color: var(--ink); }
.evidence {
  background: var(--surface-2);
  border: 1px dashed var(--rule);
}
.evidence ul { list-style: none; margin: 0; padding: 0; display: grid; gap: 5px; }

.scenarios {
  margin-top: 20px;
  padding-top: 16px;
  border-top: 1px solid var(--rule-2);
}
.scenario { margin-top: 12px; }
.scenario h4 {
  margin: 0 0 4px;
  font-family: var(--sans);
  font-size: 15px;
  font-weight: 600;
  color: var(--ink-2);
}
.scenario ul { list-style: none; margin: 0; padding: 0; display: grid; gap: 2px; }
.scenario li {
  font-size: 14.5px;
  color: var(--ink-2);
  padding-left: 1px;
}
.scenario li strong {
  font-family: var(--mono);
  font-size: 10.5px;
  font-weight: 600;
  letter-spacing: 0.12em;
  color: var(--accent);
  display: inline-block;
  min-width: 5.2em;
}

/* ---- evidence pages ---- */
.ev-text {
  margin-top: 26px;
  padding: 18px;
  background: var(--surface);
  border: 1px solid var(--rule-2);
  border-radius: 3px;
  font-family: var(--mono);
  font-size: 12.5px;
  line-height: 1.55;
  overflow-x: auto;
  white-space: pre;
  color: var(--ink-2);
}
.ev-image { margin-top: 26px; }
.ev-image img {
  max-width: 100%;
  border: 1px solid var(--rule);
  border-radius: 3px;
}

/* ---- footer ---- */
.footer {
  margin-top: 56px;
  padding-top: 18px;
  border-top: 1px solid var(--rule);
  font-size: 11.5px;
  color: var(--muted);
}
.footer p { margin: 0 0 4px; }
.footer code { background: none; border: none; padding: 0; }

@media (max-width: 700px) {
  .row { grid-template-columns: 1fr auto; gap: 8px 14px; }
  .row-purpose { grid-column: 1 / -1; }
  .row-tape { grid-column: 1 / -1; }
  .row-count { text-align: left; }
  .defects li { grid-template-columns: 1fr; }
  .defect-kind { grid-row: auto; padding-top: 0; }
  .scenario li strong { display: block; min-width: 0; }
}

@media (prefers-reduced-motion: reduce) {
  * { transition: none !important; animation: none !important; }
}
"""


if __name__ == "__main__":
    raise SystemExit(main())
