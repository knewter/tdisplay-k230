#!/usr/bin/env python3
"""Build the spec site: the data pass, then Astro, then the budgets.

    ./scripts/build_site.py            # site/dist/
    ./scripts/build_site.py --local    # no /tdisplay-k230/ base prefix

This is the one command. It fails, loudly and with a non-zero exit, when

  * a requirement declares neither an `<!-- UNVERIFIED -->` marker nor a
    `*Grounding: ...*` citation -- the renderer will not call it grounded;
  * a requirement cites evidence under `docs/` that is not committed;
  * a binary file exists that `docs/blob-inventory.md` does not account for
    (`tools/blob-scan.py`);
  * the build takes longer or produces more than its recorded budget;
  * the built site fails its own assertions (a count that is not first, a
    dead link, an in-flight proposal in the accepted-spec ledger).

The site is still written when a requirement is at fault, and shows the fault.
A defect nobody can see is one nobody fixes. Budget and assertion failures
leave whatever Astro produced in place; the exit code is what CI reads.

Budgets -- measured 2026-09-20 on `solomon`, an AMD Ryzen 9 5950X (32 threads),
Node 26.7.0, Astro 5.18.2, over one capability and five requirements. The
measurements and their headroom are recorded in
docs/evidence/spec-site-build.txt.
"""

from __future__ import annotations

import argparse
import importlib.util
import os
import subprocess
import sys
import time
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

# Set high on purpose. A cold CI runner installing nothing still pays Node
# start-up and a Vite build, and the taxonomy allows fifteen capabilities
# where this tree has a handful. A breach should mean something changed, not
# that the numbers were always tight.
MAX_BUILD_SECONDS = 120.0
MAX_OUTPUT_BYTES = 8 * 1024 * 1024


def load_render_specs():
    spec = importlib.util.spec_from_file_location(
        "render_specs", REPO / "scripts" / "render_specs.py"
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules["render_specs"] = module
    spec.loader.exec_module(module)
    return module


def tree_bytes(root: Path) -> int:
    return sum(p.stat().st_size for p in root.rglob("*") if p.is_file())


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--local",
        action="store_true",
        help="build without the GitHub Pages base prefix, for a local preview",
    )
    parser.add_argument(
        "--max-seconds", type=float, default=MAX_BUILD_SECONDS
    )
    parser.add_argument("--max-bytes", type=int, default=MAX_OUTPUT_BYTES)
    parser.add_argument(
        "--skip-assertions",
        action="store_true",
        help="skip the checks on the built output (they need the build to exist)",
    )
    args = parser.parse_args(argv)

    site = REPO / "site"
    if not (site / "node_modules").is_dir():
        print(
            f"error: {site}/node_modules is missing. Run `npm install --prefix site` "
            "once; the build itself needs no network.",
            file=sys.stderr,
        )
        return 1

    links = subprocess.run(["node", str(REPO / "tests" / "test_work_markdown_links.mjs")], cwd=REPO)
    if links.returncode != 0:
        print("error: work Markdown link checks failed", file=sys.stderr)
        return links.returncode

    started = time.monotonic()
    failures: list[str] = []

    # The separate work page reads committed OpenSpec state. A dirty checkout
    # still builds an explicitly dated HEAD snapshot, never private worktree
    # activity or an accidental mixture of staged and unstaged task files.
    print("\n$ ./scripts/render_work_board.py")
    work = subprocess.run([sys.executable, str(REPO / "scripts" / "render_work_board.py")], cwd=REPO)
    if work.returncode != 0:
        print("error: work board data pass failed", file=sys.stderr)
        return work.returncode

    # 1. The data pass: parse, classify, check evidence, write specs.json.
    render_specs = load_render_specs()
    data_status = render_specs.main(["--repo", str(REPO)])
    if data_status != 0:
        failures.append(
            "the specs carry defects; they are listed above and shown on the site"
        )

    # 1b. Every binary is accounted for in docs/blob-inventory.md, or the
    #     build fails here, beside the evidence check, for the same reason:
    #     a site that publishes the inventory must not publish a stale one.
    #     The scan walks the committed tree and whichever vendor checkouts
    #     are on this machine; it says which. See tools/blob-scan.py.
    print("\n$ ./tools/blob-scan.py")
    scan = subprocess.run([sys.executable, str(REPO / "tools" / "blob-scan.py")], cwd=REPO)
    if scan.returncode != 0:
        failures.append(
            "a binary is not accounted for in docs/blob-inventory.md (tools/blob-scan.py)"
        )

    # 2. Astro.
    script = "build:local" if args.local else "build"
    print(f"\n$ npm run {script} --prefix site")
    build = subprocess.run(
        ["npm", "run", script, "--silent"],
        cwd=site,
        env={**os.environ, "CI": "1"},
    )
    if build.returncode != 0:
        print("error: astro build failed", file=sys.stderr)
        return build.returncode

    seconds = time.monotonic() - started
    dist = site / "dist"
    size = tree_bytes(dist)
    pages = sum(1 for _ in dist.rglob("index.html"))

    print(
        f"\n{dist}: {pages} pages, {size} bytes, {seconds:.2f} s"
        f"  (budgets: {args.max_bytes} bytes, {args.max_seconds:.1f} s)"
    )

    # 3. Budgets.
    if seconds > args.max_seconds:
        failures.append(
            f"build took {seconds:.2f} s against a budget of "
            f"{args.max_seconds:.2f} s"
        )
    if size > args.max_bytes:
        failures.append(
            f"output is {size} bytes against a budget of {args.max_bytes} bytes"
        )

    # 4. What the built site must be true of, checked against the built site.
    if not args.skip_assertions:
        loader = unittest.TestLoader()
        suite = loader.discover(
            str(REPO / "tests"), pattern="test_site_output.py", top_level_dir=str(REPO / "tests")
        )
        result = unittest.TextTestRunner(verbosity=1).run(suite)
        if not result.wasSuccessful():
            failures.append(
                f"{len(result.failures) + len(result.errors)} assertion(s) failed "
                "against the built site"
            )

    if failures:
        print("", file=sys.stderr)
        for failure in failures:
            print(f"error: {failure}", file=sys.stderr)
        return 2
    print("ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
