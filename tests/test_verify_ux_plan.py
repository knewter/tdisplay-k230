#!/usr/bin/env python3
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VERIFY = ROOT / "tools/verify-ux-plan.py"
DOCS = ROOT / "docs/research/handheld-ux"


def call(*args):
    return subprocess.run([sys.executable, VERIFY, *map(str, args)], cwd=ROOT, text=True, capture_output=True)


def test_self_test_and_documents():
    result = call("--self-test")
    assert result.returncode == 0, result.stderr
    result = call(DOCS / "flow-matrix.md", DOCS / "issue-ledger.md", DOCS / "evidence-index.md", DOCS / "interaction-contract.md")
    assert result.returncode == 0, result.stderr


def test_rejects_missing_owner_and_citation():
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "issue-ledger.md"
        path.write_text("| Finding | Severity | Owner | Dependency | Evidence class | Citation | Acceptance | Open gate |\n| --- | --- | --- | --- | --- | --- | --- | --- |\n| x | P1 |  | y | native | docs/evidence/nope.md |  | z |\n")
        result = call(path)
    assert result.returncode == 1
    assert "missing owner" in result.stderr
    assert "citation is absent" in result.stderr


if __name__ == "__main__":
    test_self_test_and_documents()
    test_rejects_missing_owner_and_citation()
    print("test_verify_ux_plan: ok")
