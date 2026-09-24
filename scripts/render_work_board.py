#!/usr/bin/env python3
"""Render a dated public work snapshot from committed OpenSpec files.

The normal mode reads HEAD through Git, even if the checkout is dirty. The
explicit --working-tree mode exists for fixture and pre-commit tests only.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
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
TASK = re.compile(r"^- \[([ xX])\] (.+)$", re.M)
TASK_ID = re.compile(r"^\d+[a-z]?(?:\.\d+[a-z]?)*\s+", re.I)


class WorkError(ValueError):
    pass


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


class SourceTree:
    def __init__(self, repo: Path, working_tree: bool = False):
        self.repo = repo
        self.working_tree = working_tree
        self.revision = git(repo, "rev-parse", "HEAD").strip()
        if working_tree:
            listed = git(repo, "ls-files", "--cached", "--others", "--exclude-standard").splitlines()
            self.paths = {p for p in listed if (repo / p).is_file()}
        else:
            self.paths = set(git(repo, "ls-tree", "-r", "--name-only", "HEAD").splitlines())

    def read(self, path: str) -> str:
        safe_path(path)
        if path not in self.paths:
            raise WorkError(f"uncommitted or missing public path: {path}")
        if self.working_tree:
            return (self.repo / path).read_text(encoding="utf-8")
        return git(self.repo, "show", f"HEAD:{path}")


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
        tasks = tree.read(task_path) if task_path in tree.paths else ""
        checked = TASK.findall(tasks)
        done = sum(flag != " " for flag, _ in checked)
        delta = sorted(p for p in tree.paths if p.startswith(f"{change_dir}/specs/") and p.endswith("/spec.md"))
        accepted = ["openspec/specs/" + p.split("/specs/", 1)[1] for p in delta]
        accepted = [p for p in accepted if p in tree.paths]
        item = {
            "id": ident, "title": title_from(proposal, ident), "archived": archived,
            "proposal": proposal_path, "tasksPath": task_path if task_path in tree.paths else None,
            "acceptedSpecs": accepted, "done": done, "total": len(checked),
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
        allowed = {"lane", "source", "physical", "next", "dependencies", "evidence", "rationale", "reviewRevision"}
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

    order = {lane: i for i, lane in enumerate(LANES)}
    items = sorted(all_changes.values(), key=lambda i: (order[i["lane"]], i["id"]))
    return {"sourceRevision": tree.revision, "generated": generated, "sourceMode": "working-tree" if tree.working_tree else "committed HEAD", "items": items,
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
        data = snapshot(tree, json.loads(raw), generated)
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
