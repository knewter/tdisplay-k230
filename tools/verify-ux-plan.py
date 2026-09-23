#!/usr/bin/env python3
"""Check the structural evidence fields in the handheld UX planning documents."""
from __future__ import annotations

import argparse
import os
import re
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TABLE_RULES = {
    "flow-matrix.md": {"flow", "user goal", "expected visible result", "escape / recovery", "accessibility check", "owner", "dependency", "evidence class", "citation", "open gate"},
    "issue-ledger.md": {"finding", "severity", "owner", "dependency", "evidence class", "citation", "acceptance", "open gate"},
    "evidence-index.md": {"task", "visible result", "severity", "owner", "dependency", "evidence class", "citation", "acceptance", "open gate"},
}
REQUIRED_CONTRACT = ("Visual tokens", "Navigation ownership", "Motion and accessibility acceptance", "Measurable review checks", "native", "real-finger", "UNVERIFIED")
REQUIRED_SHEETS = ("apps-comparison.svg", "keyboard-comparison.svg", "live-card-overview.svg")
PATH_RE = re.compile(r"(?:docs|openspec|tests|tools)/[A-Za-z0-9_./-]+")


def tables(text: str):
    lines = text.splitlines()
    index = 0
    while index + 1 < len(lines):
        if lines[index].startswith("|") and lines[index + 1].startswith("|") and set(lines[index + 1]) <= set("| -:"):
            headers = [cell.strip().lower() for cell in lines[index].strip("|").split("|")]
            rows = []
            index += 2
            while index < len(lines) and lines[index].startswith("|"):
                rows.append([cell.strip() for cell in lines[index].strip("|").split("|")])
                index += 1
            yield headers, rows
        else:
            index += 1


def existing_citation(value: str) -> bool:
    if "UNVERIFIED" in value:
        return True
    paths = PATH_RE.findall(value)
    return bool(paths) and all((ROOT / item.rstrip(".,;:)")).exists() for item in paths)


def check_table(path: Path, required: set[str]) -> list[str]:
    errors: list[str] = []
    matched = False
    for headers, rows in tables(path.read_text()):
        header_set = set(headers)
        if required <= header_set:
            matched = True
            for number, row in enumerate(rows, 1):
                values = dict(zip(headers, row))
                for field in required:
                    if not values.get(field, "").strip():
                        errors.append(f"{path}: row {number}: missing {field}")
                if values.get("severity") and values["severity"] not in {"P0", "P1", "P2", "Deferred"}:
                    errors.append(f"{path}: row {number}: invalid severity {values['severity']!r}")
                evidence = values.get("evidence class", "")
                if evidence and not all(item.strip() in {"host", "native", "injected", "camera", "real-finger", "serial", "UNVERIFIED"} for item in evidence.split(",")):
                    errors.append(f"{path}: row {number}: invalid evidence class {evidence!r}")
                if not existing_citation(values.get("citation", "")):
                    errors.append(f"{path}: row {number}: citation is absent or does not exist")
    if not matched:
        errors.append(f"{path}: required table headings not found")
    return errors


def check_contract(path: Path) -> list[str]:
    text = path.read_text()
    errors = [f"{path}: missing contract term {term!r}" for term in REQUIRED_CONTRACT if term not in text]
    if sum(1 for _ in tables(text)) < 3:
        errors.append(f"{path}: expected visual, navigation, and motion tables")
    for item in PATH_RE.findall(text):
        if not (ROOT / item.rstrip(".,;:)")).exists():
            errors.append(f"{path}: citation path does not exist: {item}")
    for sheet in REQUIRED_SHEETS:
        sheet_path = path.parent / sheet
        if not sheet_path.exists() or "568" not in sheet_path.read_text():
            errors.append(f"{path}: missing target-geometry SVG sheet: {sheet}")
    return errors


def run(paths: list[Path]) -> int:
    errors: list[str] = []
    for path in paths:
        if not path.exists():
            errors.append(f"missing file: {path}")
            continue
        if path.name == "interaction-contract.md":
            errors.extend(check_contract(path))
        elif path.name in TABLE_RULES:
            errors.extend(check_table(path, TABLE_RULES[path.name]))
        else:
            errors.append(f"unsupported UX-plan document: {path}")
    if errors:
        print("UX plan verification failed:", file=sys.stderr)
        print("\n".join(f"- {error}" for error in errors), file=sys.stderr)
        return 1
    print(f"UX plan verification passed for {len(paths)} document(s).")
    return 0


def self_test() -> int:
    docs = ROOT / "docs/research/handheld-ux"
    expected = [docs / name for name in (*TABLE_RULES, "interaction-contract.md")]
    if run(expected):
        return 1
    with tempfile.TemporaryDirectory() as directory:
        bad = Path(directory) / "issue-ledger.md"
        bad.write_text("| Finding | Severity | Owner | Dependency | Evidence class | Citation | Acceptance | Open gate |\n| --- | --- | --- | --- | --- | --- | --- | --- |\n| missing owner | P9 |  | x | made-up | no-file |  | x |\n")
        if run([bad]) == 0:
            print("self-test expected invalid ledger to fail", file=sys.stderr)
            return 1
    print("UX plan verifier self-test passed.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("paths", nargs="*", type=Path)
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        return self_test()
    if not args.paths:
        parser.error("supply UX-plan documents or --self-test")
    return run(args.paths)


if __name__ == "__main__":
    raise SystemExit(main())
