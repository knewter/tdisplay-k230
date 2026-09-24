#!/usr/bin/env python3
"""Acquire pinned Omarchy theme fixtures and inspect sources without editing them."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile


UPSTREAM_URL = "https://github.com/omacom/omarchy.git"
UPSTREAM_REV = "28ceaae70ebac3a0edcc21f2faa77a90dc6d404c"
COMMUNITY_URL = "https://github.com/fuchsblau/omarchy-fuchsblau-theme.git"
COMMUNITY_REV = "aa7fde043ae60603c3ecc6fd6ac3b6674cacab04"
BUILTIN_THEMES = ("catppuccin", "catppuccin-latte")


def run(*argv, cwd=None):
    return subprocess.check_output(argv, cwd=cwd, text=True, stderr=subprocess.PIPE).strip()


def source_dir(root: Path, member: str | None = None) -> Path:
    root = root.resolve(strict=True)
    if member is None:
        theme = root
    else:
        if not member or member in (".", "..") or "/" in member or "\\" in member:
            raise ValueError("invalid collection member")
        theme = (root / "themes" / member).resolve(strict=True)
        if not theme.is_relative_to(root / "themes"):
            raise ValueError("collection member escapes source")
    if not theme.is_dir() or not ((theme / "colors.toml").is_file() or (theme / "alacritty.toml").is_file()):
        raise ValueError("source has no recognized theme palette")
    return theme


def source_digest(theme: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(theme.rglob("*")):
        if ".git" in path.relative_to(theme).parts:
            continue
        if path.is_symlink():
            raise ValueError(f"symlink in source: {path.relative_to(theme)}")
        if path.is_dir():
            continue
        if not path.is_file():
            raise ValueError(f"non-file source entry: {path.relative_to(theme)}")
        name = path.relative_to(theme).as_posix().encode()
        digest.update(len(name).to_bytes(4, "big"))
        digest.update(name)
        with path.open("rb") as stream:
            while chunk := stream.read(1024 * 1024):
                digest.update(chunk)
    return digest.hexdigest()


def inspect(root: Path, member: str | None = None) -> dict:
    theme = source_dir(root, member)
    original_root = root.resolve(strict=True)
    result = {"source": str(original_root), "theme": str(theme),
              "member": member, "sha256": source_digest(theme)}
    if (original_root / ".git").is_file() or (original_root / ".git").is_dir():
        result["revision"] = run("git", "-C", str(original_root), "rev-parse", "HEAD")
        result["git_layout"] = "file" if (original_root / ".git").is_file() else "directory"
    else:
        result["revision"] = None
        result["git_layout"] = "absent"
    return result


def acquire_one(url: str, rev: str, destination: Path, *, members: tuple[str, ...] = ()) -> None:
    if destination.exists():
        raise FileExistsError(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="theme-fetch-", dir=destination.parent) as temporary:
        checkout = Path(temporary) / "checkout"
        subprocess.run(["git", "-c", "core.hooksPath=/dev/null", "clone", "--filter=blob:none",
                        "--no-checkout", url, str(checkout)], check=True, stdout=subprocess.DEVNULL)
        if members:
            subprocess.run(["git", "-C", str(checkout), "sparse-checkout", "set",
                            *(f"themes/{name}" for name in members)], check=True)
        subprocess.run(["git", "-C", str(checkout), "checkout", "--detach", rev],
                       check=True, stdout=subprocess.DEVNULL)
        if run("git", "-C", str(checkout), "rev-parse", "HEAD") != rev:
            raise ValueError("checkout revision mismatch")
        if run("git", "-C", str(checkout), "status", "--porcelain"):
            raise ValueError("fixture checkout is dirty")
        for name in members:
            source_dir(checkout, name)
        if not members:
            source_dir(checkout)
        os.replace(checkout, destination)


def acquire(destination: Path, *, upstream_url=UPSTREAM_URL, upstream_rev=UPSTREAM_REV,
            community_url=COMMUNITY_URL, community_rev=COMMUNITY_REV) -> dict:
    if destination.exists():
        raise FileExistsError(destination)
    destination.mkdir(parents=True)
    try:
        acquire_one(upstream_url, upstream_rev, destination / "builtins", members=BUILTIN_THEMES)
        acquire_one(community_url, community_rev, destination / "community")
        return {"dark": inspect(destination / "builtins", BUILTIN_THEMES[0]),
                "light": inspect(destination / "builtins", BUILTIN_THEMES[1]),
                "community": inspect(destination / "community")}
    except Exception:
        shutil.rmtree(destination)
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="action", required=True)
    get = sub.add_parser("acquire")
    get.add_argument("destination", type=Path)
    get.add_argument("--upstream-url", default=UPSTREAM_URL)
    get.add_argument("--upstream-rev", default=UPSTREAM_REV)
    get.add_argument("--community-url", default=COMMUNITY_URL)
    get.add_argument("--community-rev", default=COMMUNITY_REV)
    view = sub.add_parser("inspect")
    view.add_argument("source", type=Path)
    view.add_argument("--member")
    args = parser.parse_args()
    result = (acquire(args.destination, upstream_url=args.upstream_url,
                      upstream_rev=args.upstream_rev, community_url=args.community_url,
                      community_rev=args.community_rev)
              if args.action == "acquire" else inspect(args.source, args.member))
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
