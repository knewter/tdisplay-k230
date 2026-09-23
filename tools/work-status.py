#!/usr/bin/env python3
"""Summarise local Git/OpenSpec reconciliation state without mutating Git."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any


class GitError(RuntimeError):
    pass


def git(root: Path, *args: str, allow_failure: bool = False) -> str:
    result = subprocess.run(
        ["git", "-C", str(root), *args],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env={**os.environ, "GIT_OPTIONAL_LOCKS": "0"},
    )
    if result.returncode and not allow_failure:
        raise GitError(result.stderr.strip() or "git " + " ".join(args))
    return result.stdout if result.returncode == 0 else ""


def ref_exists(root: Path, ref: str) -> bool:
    return bool(git(root, "rev-parse", "--verify", "--quiet", ref, allow_failure=True))


def active_proposals(root: Path, revision: str) -> set[str]:
    names = git(root, "ls-tree", "-d", "--name-only", f"{revision}:openspec/changes",
                allow_failure=True).splitlines()
    return {name for name in names if name != "archive"}


def archive_key(change_id: str) -> str:
    """Map archive YYYY-MM-DD-change-id names back to their change ID."""
    if len(change_id) > 11 and change_id[4:5] == "-" and change_id[7:8] == "-":
        prefix = change_id[:10]
        if prefix[:4].isdigit() and prefix[5:7].isdigit() and prefix[8:10].isdigit() and change_id[10] == "-":
            return change_id[11:]
    return change_id


def archived_proposals(root: Path, revision: str) -> set[str]:
    names = git(root, "ls-tree", "-d", "--name-only", f"{revision}:openspec/changes/archive",
                allow_failure=True).splitlines()
    return {archive_key(name) for name in names}


def filesystem_proposals(path: Path) -> dict[str, set[str]]:
    """Read proposal files visible in a worktree, including uncommitted ones."""
    changes = path / "openspec" / "changes"
    active: set[str] = set()
    archived: set[str] = set()
    if not changes.is_dir():
        return {"active": active, "archived": archived}
    for child in changes.iterdir():
        if child.name != "archive" and (child / "proposal.md").is_file():
            active.add(child.name)
    archive = changes / "archive"
    if archive.is_dir():
        for child in archive.iterdir():
            if (child / "proposal.md").is_file():
                archived.add(archive_key(child.name))
    return {"active": active, "archived": archived}


def head(root: Path, revision: str) -> str:
    return git(root, "rev-parse", "--verify", revision).strip()


def relation(root: Path, left: str, right: str) -> str:
    if not ref_exists(root, right):
        return "unavailable"
    if head(root, left) == head(root, right):
        return "equal"
    if subprocess.run(["git", "-C", str(root), "merge-base", "--is-ancestor", left, right]).returncode == 0:
        return "behind"
    if subprocess.run(["git", "-C", str(root), "merge-base", "--is-ancestor", right, left]).returncode == 0:
        return "ahead"
    return "diverged"


def worktrees(root: Path) -> list[dict[str, Any]]:
    blocks = git(root, "worktree", "list", "--porcelain").strip().split("\n\n")
    result: list[dict[str, Any]] = []
    for block in blocks:
        values: dict[str, str] = {}
        for line in block.splitlines():
            key, _, value = line.partition(" ")
            values[key] = value
        path = Path(values["worktree"])
        revision = values.get("HEAD", "HEAD")
        branch = values.get("branch", "(detached)").removeprefix("refs/heads/")
        item: dict[str, Any] = {
            "path": str(path),
            "branch": branch,
            "head": revision,
            "head_active_proposals": sorted(active_proposals(root, revision)),
            "head_archived_proposals": sorted(archived_proposals(root, revision)),
            "available": False,
            "dirty_paths": None,
            "filesystem_active_proposals": [],
            "filesystem_archived_proposals": [],
        }
        if not path.is_dir():
            item["unavailable_reason"] = "worktree path is missing"
            result.append(item)
            continue
        try:
            item["dirty_paths"] = len(
                git(path, "status", "--porcelain=v1", "--untracked-files=all").splitlines()
            )
            filesystem = filesystem_proposals(path)
            item["filesystem_active_proposals"] = sorted(filesystem["active"])
            item["filesystem_archived_proposals"] = sorted(filesystem["archived"])
            item["available"] = True
        except (GitError, OSError):
            item["unavailable_reason"] = "worktree cannot be inspected"
        result.append(item)
    return result


def snapshots(root: Path, tree: list[dict[str, Any]]) -> dict[str, list[str]]:
    entries: list[tuple[str, str]] = []
    for line in git(root, "for-each-ref", "--format=%(refname)%00%(objectname)",
                    "refs/heads", "refs/remotes").splitlines():
        ref, _, revision = line.partition("\0")
        if ref and revision:
            entries.append((ref, revision))
    for item in tree:
        entries.append((f"worktree:{item['path']}", item["head"]))

    found: dict[str, set[str]] = defaultdict(set)
    for label, revision in entries:
        for proposal in active_proposals(root, revision):
            found[proposal].add(f"{label} [active]")
        for proposal in archived_proposals(root, revision):
            found[proposal].add(f"{label} [archived]")
    for item in tree:
        label = f"worktree filesystem:{item['path']}"
        for proposal in item["filesystem_active_proposals"]:
            found[proposal].add(f"{label} [active]")
        for proposal in item["filesystem_archived_proposals"]:
            found[proposal].add(f"{label} [archived]")
    return {proposal: sorted(labels) for proposal, labels in found.items()}


def local_branches(root: Path) -> list[dict[str, Any]]:
    records = git(root, "for-each-ref", "--format=%(refname:short)%00%(upstream:short)",
                  "refs/heads").splitlines()
    branches: list[dict[str, Any]] = []
    for record in records:
        name, _, upstream = record.partition("\0")
        item: dict[str, Any] = {
            "branch": name,
            "upstream": upstream or None,
            "publication_state": "upstream-known" if upstream else "no-upstream",
        }
        if upstream:
            item["ahead"] = int(git(root, "rev-list", "--count", f"{upstream}..{name}").strip())
            item["behind"] = int(git(root, "rev-list", "--count", f"{name}..{upstream}").strip())
        branches.append(item)
    return branches


def report(root: Path) -> dict[str, Any]:
    master_active = active_proposals(root, "master")
    master_archived = archived_proposals(root, "master")
    tree = worktrees(root)
    snapshot_map = snapshots(root, tree)
    accounted_for = master_active | master_archived
    snapshot_only = {
        proposal: labels for proposal, labels in snapshot_map.items()
        if proposal not in accounted_for
    }
    origin_exists = ref_exists(root, "origin/master")
    return {
        "repository": str(root),
        "remote_state": "cached; this command does not fetch",
        "master": {
            "head": head(root, "master"),
            "origin_master": head(root, "origin/master") if origin_exists else None,
            "relation_to_origin_master": relation(root, "master", "origin/master"),
        },
        "master_proposals": {
            "active": sorted(master_active),
            "archived": sorted(master_archived),
        },
        "worktrees": tree,
        "proposals_only_in_snapshots": snapshot_only,
        "local_branches": local_branches(root),
    }


def print_human(data: dict[str, Any]) -> None:
    master = data["master"]
    print(f"Repository: {data['repository']}")
    print(f"Remote state: {data['remote_state']}")
    origin = master["origin_master"] or "absent"
    print(f"master: {master['head'][:12]}  origin/master: {origin[:12] if origin != 'absent' else origin}  "
          f"relation: {master['relation_to_origin_master']}")
    proposals = data["master_proposals"]
    print(f"Master OpenSpec proposals: {len(proposals['active'])} active, {len(proposals['archived'])} archived")
    print("Worktrees:")
    for item in data["worktrees"]:
        print(f"  {item['path']}  branch={item['branch']} head={item['head'][:12]} "
              f"available={item['available']} dirty-paths={item['dirty_paths']} "
              f"head-active={len(item['head_active_proposals'])} "
              f"filesystem-active={len(item['filesystem_active_proposals'])}")
        if not item["available"]:
            print(f"    unavailable: {item['unavailable_reason']}")
    only = data["proposals_only_in_snapshots"]
    print(f"Proposal IDs only outside master (refs, worktree HEADs, and worktree filesystem): {len(only)}")
    for proposal, labels in sorted(only.items()):
        print(f"  {proposal}: {', '.join(labels)}")
    print("Local branches:")
    for item in data["local_branches"]:
        if item["upstream"]:
            print(f"  {item['branch']} -> {item['upstream']} ahead={item['ahead']} behind={item['behind']}")
        else:
            print(f"  {item['branch']} -> no upstream (publication unknown)")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="emit machine-readable status")
    parser.add_argument("--repo", type=Path, default=Path.cwd(), help="repository or a path within it")
    args = parser.parse_args()
    try:
        root = Path(git(args.repo, "rev-parse", "--show-toplevel").strip())
        data = report(root)
    except GitError as error:
        print(f"work-status: {error}", file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps(data, indent=2, sort_keys=True))
    else:
        print_human(data)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
