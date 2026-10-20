#!/usr/bin/env python3
"""Repeat the pinned splash source audit without building or accessing a board."""

import hashlib
import json
from pathlib import Path
import subprocess


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    here = Path(__file__).resolve().parent
    root = here.parents[3]
    audit = json.loads((here / "source-audit.json").read_text())
    derivation = subprocess.check_output(
        ["nix-store", "--query", "--deriver", audit["kernel"]], text=True
    ).strip()
    if derivation != audit["kernel_derivation"]:
        raise SystemExit("FAIL: kernel derivation differs")
    result = json.loads(subprocess.check_output(
        ["nix", "derivation", "show", derivation], text=True
    ))
    entries = result.get("derivations", result)
    if len(entries) != 1:
        raise SystemExit("FAIL: expected one derivation")
    entry = next(iter(entries.values()))
    attrs = entry.get("structuredAttrs") or entry.get("env", {})
    if attrs.get("src") != audit["configured_kernel_source"]:
        raise SystemExit("FAIL: configured source differs")
    for name, item in audit["source_matches"].items():
        if digest(root / item["repo_path"]) != item["repo_sha256"]:
            raise SystemExit(f"FAIL: repository source differs: {name}")
        if digest(Path(item["configured_kernel_path"])) != item["configured_sha256"]:
            raise SystemExit(f"FAIL: configured source differs: {name}")
        if item["repo_sha256"] != item["configured_sha256"]:
            raise SystemExit(f"FAIL: recorded source pair differs: {name}")
    if digest(here / "current-boot-allowlist.log") != audit["allowlist_sha256"]:
        raise SystemExit("FAIL: journal allowlist differs")
    print("PASS: pinned derivation, four source pairs and journal allowlist hash")
    print("No new board observation, film, clock qualification or fix claimed.")


if __name__ == "__main__":
    main()
