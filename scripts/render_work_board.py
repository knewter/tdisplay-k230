#!/usr/bin/env python3
"""Render a dated public work snapshot from committed OpenSpec files.

The normal mode reads HEAD through Git, even if the checkout is dirty. The
explicit --working-tree mode exists for fixture and pre-commit tests only.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import posixpath
import re
import subprocess
import sys
from pathlib import Path

CHANGE_ROOT = "openspec/changes/"
STATUS_PATH = "docs/work-board-status.json"
LANES = ("planned", "in-progress", "verification", "archived")
SOURCE = ("not-started", "in-progress", "source-landed", "archived")
PHYSICAL = ("not-applicable", "not-recorded", "pending", "verified")
SAFE_TEXT = re.compile(r"^[^\x00-\x1f]*$")
SECRET_TEXT = re.compile(r"(?:/home/|/mnt/|/tmp/|/dev/tty|(?:password|token|secret|ssid)\s*[:=]|(?:\d{1,3}\.){3}\d{1,3})", re.I)
PRIVATE_DOC = re.compile(r"/(?:home|mnt)/|(?:password|token|secret|ssid)\s*[:=]\s*\S+|(?:\d{1,3}\.){3}\d{1,3}")
MAX_DOCUMENT_BYTES = 128 * 1024
IMAGE_TYPES = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".svg"}
VIDEO_TYPES = {".mp4", ".webm", ".mov", ".m4v"}
TASK = re.compile(r"^- \[([ xX])\] (.+)$", re.M)
TASK_ID = re.compile(r"^\d+[a-z]?(?:\.\d+[a-z]?)*\s+", re.I)


class WorkError(ValueError):
    pass


def parse_status(raw: str) -> dict:
    """Reject repeated keys before JSON can silently discard an override."""
    def unique_object(pairs: list[tuple[str, object]]) -> dict:
        result = {}
        for key, value in pairs:
            if key in result:
                raise WorkError(f"duplicate work-board status JSON key: {key!r}")
            result[key] = value
        return result

    return json.loads(raw, object_pairs_hook=unique_object)


def git(repo: Path, *args: str) -> str:
    result = subprocess.run(["git", "-C", str(repo), *args], text=True, capture_output=True)
    if result.returncode:
        raise WorkError(result.stderr.strip() or f"git {' '.join(args)} failed")
    return result.stdout


def safe_path(path: str) -> str:
    if not isinstance(path, str) or not path or path.startswith("/") or "\\" in path:
        raise WorkError(f"unsafe public path: {path!r}")
    parts = Path(path).parts
    if any(p in (".", "..") for p in parts) or path.startswith(("http:", "https:")):
        raise WorkError(f"unsafe public path: {path!r}")
    if SECRET_TEXT.search(path):
        raise WorkError(f"private public path: {path!r}")
    return path


def safe_copy(value: object, where: str) -> str:
    if not isinstance(value, str) or not value.strip() or not SAFE_TEXT.fullmatch(value) or SECRET_TEXT.search(value):
        raise WorkError(f"unsafe or empty public text at {where}")
    return value.strip()


def document(tree: "SourceTree", path: str, label: str) -> dict:
    value = tree.read(path)
    if len(value.encode("utf-8")) > MAX_DOCUMENT_BYTES:
        raise WorkError(f"work document exceeds {MAX_DOCUMENT_BYTES} bytes: {path}")
    if PRIVATE_DOC.search(value):
        raise WorkError(f"work document contains a private path/address/credential: {path}")
    return {"path": path, "label": label, "markdown": value}


class SourceTree:
    def __init__(self, repo: Path, working_tree: bool = False):
        self.repo = repo
        self.working_tree = working_tree
        self.revision = git(repo, "rev-parse", "HEAD").strip()
        if working_tree:
            listed = git(repo, "ls-files", "--cached", "--others", "--exclude-standard").splitlines()
            self.paths = {p for p in listed if (repo / p).is_file() and not (repo / p).is_symlink()}
        else:
            entries = git(repo, "ls-tree", "-r", "-z", self.revision).split("\0")
            self.paths = {entry.split("\t", 1)[1] for entry in entries
                          if entry.startswith(("100644 ", "100755 "))}

    def read(self, path: str) -> str:
        safe_path(path)
        if path not in self.paths:
            raise WorkError(f"uncommitted or missing public path: {path}")
        if self.working_tree:
            source = self.repo / path
            if source.stat().st_size > MAX_DOCUMENT_BYTES:
                raise WorkError(f"work document exceeds {MAX_DOCUMENT_BYTES} bytes: {path}")
            return source.read_text(encoding="utf-8")
        size = int(git(self.repo, "cat-file", "-s", f"{self.revision}:{path}").strip())
        if size > MAX_DOCUMENT_BYTES:
            raise WorkError(f"work document exceeds {MAX_DOCUMENT_BYTES} bytes: {path}")
        return git(self.repo, "show", f"{self.revision}:{path}")


def title_from(proposal: str, ident: str) -> str:
    # A proposal's first paragraph is explanatory prose, not a concise title.
    # IDs are committed, stable, and already written as readable sentences.
    if not proposal.strip():
        raise WorkError(f"empty proposal: {ident}")
    return re.sub(r"^\d{4}-\d{2}-\d{2}-", "", ident).replace("-", " ").capitalize()


def first_gate(tasks: str, archived: bool) -> str:
    for checked, body in TASK.findall(tasks):
        if checked == " ":
            try:
                body = TASK_ID.sub("", body)
                plain = re.sub(r"\[([^]]+)\]\([^)]+\)", r"\1", body)
                plain = plain.replace("`", "").replace("**", "")
                plain = re.sub(r"\s+", " ", plain).strip()
                safe_copy(plain, "next task")
                if len(plain) > 205:
                    plain = plain[:202].rsplit(" ", 1)[0].rstrip(" ,.;") + "…"
                return plain
            except WorkError:
                return "Review the next unchecked task in the linked task list"
    return "Review the archived record and cited scope" if archived else "Review completed tasks and archive evidence"


def referenced_evidence(tree: SourceTree, source: str, text: str) -> list[str]:
    """Resolve local document citations, never fetch arbitrary URLs."""
    from urllib.parse import unquote, urlsplit
    candidates = re.findall(r"\]\(<?([^\s)>]+)", text)
    candidates += re.findall(r"\bdocs/(?:evidence|design)/[^\s`<>\"')\],;]+", text)
    found = []
    for raw in candidates:
        parsed = urlsplit(raw)
        if parsed.scheme or parsed.netloc or raw.startswith("/"):
            continue
        path = unquote(parsed.path).rstrip(".")
        path = posixpath.normpath(path if path.startswith("docs/") else
                                  posixpath.join(posixpath.dirname(source), path))
        if not path.startswith(("docs/evidence/", "docs/design/")):
            continue
        try:
            safe_path(path)
        except WorkError:
            continue
        if path in tree.paths:
            found.append(path)
        elif raw.endswith("/"):
            found.extend(sorted(p for p in tree.paths if posixpath.dirname(p) == path))
    return list(dict.fromkeys(found))


def discover_evidence(tree: SourceTree, item: dict, cover: dict | None) -> None:
    records = list(item["evidence"])
    for doc in item["details"]:
        records.extend(referenced_evidence(tree, doc["path"], doc["markdown"]))
    # Only a cited record's own sibling media is associated automatically.
    # Do not recursively sweep neighbouring experiments or unrelated folders.
    for path in list(dict.fromkeys(records)):
        if Path(path).suffix.lower() == ".md":
            records.extend(p for p in sorted(tree.paths)
                           if posixpath.dirname(p) == posixpath.dirname(path)
                           and Path(p).suffix.lower() in IMAGE_TYPES | VIDEO_TYPES)
            try:
                records.extend(referenced_evidence(tree, path, tree.read(path)))
            except WorkError:
                pass  # oversized records remain directly linked
    public_records = []
    for path in dict.fromkeys(records):
        try:
            safe_path(path)
        except WorkError:
            continue
        public_records.append(path)
    records = public_records
    if cover is not None:
        if not isinstance(cover, dict) or set(cover) != {"path", "caption", "provenance"}:
            raise WorkError(f"invalid cover metadata for {item['id']}")
        path = safe_path(cover["path"])
        if path not in records or Path(path).suffix.lower() not in IMAGE_TYPES | VIDEO_TYPES:
            raise WorkError(f"cover is not associated committed media for {item['id']}: {path}")
        safe_copy(cover["caption"], "cover caption")
        if cover["provenance"] not in ("Board capture", "QEMU capture", "Host capture", "Design mockup", "Evidence — see record"):
            raise WorkError(f"invalid cover provenance for {item['id']}")
        records.remove(path)
        records.insert(0, path)
    item["evidence"] = records
    item["media"] = []
    for path in records:
        suffix = Path(path).suffix.lower()
        if suffix not in IMAGE_TYPES | VIDEO_TYPES:
            continue
        item["media"].append({
            "path": path, "kind": "image" if suffix in IMAGE_TYPES else "video",
            "caption": cover["caption"] if cover and cover["path"] == path else Path(path).stem.replace("-", " ").replace("_", " "),
            "provenance": cover["provenance"] if cover and cover["path"] == path else
                ("Design mockup" if path.startswith("docs/design/") else "Evidence — see record"),
        })


def snapshot(tree: SourceTree, status: dict, generated: str) -> dict:
    if not isinstance(status, dict) or status.get("schema") != 1 or not isinstance(status.get("overrides"), dict):
        raise WorkError("status schema must be 1 with an overrides object")
    all_changes: dict[str, dict] = {}
    proposal_paths = sorted(p for p in tree.paths if p.startswith(CHANGE_ROOT) and p.endswith("/proposal.md"))
    for proposal_path in proposal_paths:
        rest = proposal_path[len(CHANGE_ROOT):]
        archived = rest.startswith("archive/")
        change_dir = proposal_path.removesuffix("/proposal.md")
        ident = change_dir.split("/")[-1]
        if ident in all_changes:
            raise WorkError(f"duplicate work ID: {ident}")
        proposal = tree.read(proposal_path)
        task_path = f"{change_dir}/tasks.md"
        design_path = f"{change_dir}/design.md"
        for required in (design_path, task_path):
            if required not in tree.paths:
                raise WorkError(f"missing work document for {ident}: {required}")
        tasks = tree.read(task_path)
        checked = TASK.findall(tasks)
        done = sum(flag != " " for flag, _ in checked)
        delta = sorted(p for p in tree.paths if p.startswith(f"{change_dir}/specs/") and p.endswith("/spec.md"))
        if not delta:
            raise WorkError(f"missing delta specification for {ident}: {change_dir}/specs/")
        details = [document(tree, proposal_path, "Proposal"), document(tree, design_path, "Design"),
                   document(tree, task_path, "Tasks")]
        details.extend(document(tree, path, "Delta spec: " + path.split("/specs/", 1)[1].removesuffix("/spec.md")) for path in delta)
        accepted = ["openspec/specs/" + p.split("/specs/", 1)[1] for p in delta]
        accepted = [p for p in accepted if p in tree.paths]
        item = {
            "id": ident, "title": title_from(proposal, ident), "archived": archived,
            "proposal": proposal_path, "tasksPath": task_path if task_path in tree.paths else None,
            "acceptedSpecs": accepted, "done": done, "total": len(checked),
            "details": details,
            "lane": "archived" if archived else ("planned" if done == 0 else "in-progress"),
            "source": "archived" if archived else ("not-started" if done == 0 else "in-progress"),
            "physical": "not-applicable" if archived else "not-recorded", "next": first_gate(tasks, archived),
            "dependencies": [], "evidence": [], "rationale": None, "reviewRevision": None,
        }
        all_changes[ident] = item

    for ident, override in status["overrides"].items():
        if ident not in all_changes:
            raise WorkError(f"stale override for unknown work ID: {ident}")
        if not isinstance(override, dict):
            raise WorkError(f"override must be an object: {ident}")
        allowed = {"lane", "source", "physical", "next", "dependencies", "evidence", "rationale", "reviewRevision", "cover"}
        if set(override) - allowed:
            raise WorkError(f"unknown override fields for {ident}: {sorted(set(override)-allowed)}")
        if not {"lane", "source", "physical", "next", "rationale", "reviewRevision"} <= set(override):
            raise WorkError(f"incomplete reviewed override: {ident}")
        item = all_changes[ident]
        if override["lane"] not in LANES or override["source"] not in SOURCE or override["physical"] not in PHYSICAL:
            raise WorkError(f"invalid status for {ident}")
        if item["archived"] != (override["lane"] == "archived"):
            raise WorkError(f"contradictory archive lane for {ident}")
        if item["archived"] and override["source"] != "archived":
            raise WorkError(f"contradictory archived source for {ident}")
        if override["lane"] == "planned" and (item["done"] or override["source"] != "not-started"):
            raise WorkError(f"contradictory planned status for {ident}")
        if override["lane"] == "archived" and item["total"] and item["done"] != item["total"]:
            raise WorkError(f"archived change has open tasks: {ident}")
        review = safe_copy(override["reviewRevision"], f"{ident}.reviewRevision")
        if not re.fullmatch(r"[0-9a-f]{7,40}", review):
            raise WorkError(f"invalid review revision for {ident}")
        try:
            git(tree.repo, "cat-file", "-e", f"{review}^{{commit}}")
        except WorkError as exc:
            raise WorkError(f"review revision unavailable for {ident}: {review}; fetch full history") from exc
        if subprocess.run(["git", "-C", str(tree.repo), "merge-base", "--is-ancestor", review, tree.revision]).returncode:
            raise WorkError(f"review revision is not an ancestor of snapshot: {ident}")
        deps = override.get("dependencies", [])
        evidence = override.get("evidence", [])
        if not isinstance(deps, list) or not isinstance(evidence, list):
            raise WorkError(f"dependencies/evidence must be lists: {ident}")
        for dep in deps:
            if dep == ident or dep not in all_changes:
                raise WorkError(f"unknown/self dependency for {ident}: {dep}")
        for path in evidence:
            if not isinstance(path, str) or not path.startswith("docs/evidence/") or safe_path(path) not in tree.paths:
                raise WorkError(f"missing/uncommitted evidence for {ident}: {path}")
        item.update({
            "lane": override["lane"], "source": override["source"], "physical": override["physical"],
            "next": safe_copy(override["next"], f"{ident}.next"),
            "dependencies": deps, "evidence": evidence,
            "rationale": safe_copy(override["rationale"], f"{ident}.rationale"),
            "reviewRevision": review,
        })

    visiting: set[str] = set()
    visited: set[str] = set()

    def check_dependencies(ident: str) -> None:
        if ident in visiting:
            raise WorkError(f"cyclic dependency involving {ident}")
        if ident in visited:
            return
        visiting.add(ident)
        for dep in all_changes[ident]["dependencies"]:
            check_dependencies(dep)
        visiting.remove(ident)
        visited.add(ident)

    for ident in all_changes:
        check_dependencies(ident)
        discover_evidence(tree, all_changes[ident], status["overrides"].get(ident, {}).get("cover"))

    order = {lane: i for i, lane in enumerate(LANES)}
    items = sorted(all_changes.values(), key=lambda i: (order[i["lane"]], i["id"]))
    return {"sourceRevision": tree.revision, "generated": generated, "sourceMode": "working-tree" if tree.working_tree else "committed HEAD", "trackedPaths": sorted(tree.paths), "items": items,
            "lanes": [{"id": lane, "count": sum(i["lane"] == lane for i in items)} for lane in LANES]}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--working-tree", action="store_true", help="explicit pre-commit/fixture mode")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    try:
        tree = SourceTree(args.repo.resolve(), args.working_tree)
        raw = tree.read(STATUS_PATH) if STATUS_PATH in tree.paths else '{"schema": 1, "overrides": {}}'
        generated = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        data = snapshot(tree, parse_status(raw), generated)
        output = args.output or args.repo / "site/src/data/work.json"
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"work board: {len(data['items'])} items from {data['sourceRevision'][:12]} ({data['sourceMode']})")
        return 0
    except (WorkError, json.JSONDecodeError) as exc:
        print(f"work board error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
