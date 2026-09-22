#!/usr/bin/env python3
"""Every binary is accounted for in docs/blob-inventory.md, or this exits 1.

    ./tools/blob-scan.py                 the committed tree, plus any vendor
                                         checkout that happens to be on disk
    ./tools/blob-scan.py --no-vendor     the committed tree only (what CI sees)
    ./tools/blob-scan.py --self-test     prove the failure modes fire
    ./tools/blob-scan.py -v              list every binary and what covers it

The check is "every binary has an inventory row", not "there are no
binaries". A row that says a blob is permanent is a passing state; a
photograph of the panel committed as evidence is a passing state once the
inventory has a row for it. What fails:

  * a binary file in the tree, or in a vendor checkout, with no row;
  * a file-backed row whose bytes no longer match the recorded sha256;
  * a `group:` row whose member count has moved -- a member appeared or
    vanished, and the inventory did not say so;
  * a source or release hash pinned in the stage-1 nix files with no row,
    because a blob fetched by URL is not a blob a filesystem walk will find.

What the walk covers. The committed tree is `git ls-files`, so build output,
result-* links and the gitignored firmware/stage1/*.bin are not walked -- but
every file-backed row IS checked against disk when the file is present, which
is how the gitignored stage-1 binaries and the untracked SDK tools get their
hashes verified. Vendor checkouts are walked by their own `git ls-files`
(untracked build output is not a vendor blob, it is our build's output).

The MANIFEST grammar this reads is the fenced block under `### MANIFEST` in
docs/blob-inventory.md: one row per line, `CLASS  HASH  PATH`, where

    HASH   64 hex digits | sha256-<base64> | md5:<hex> | group:<N>-file(s) | -
    PATH   repo-relative path            firmware/stage1/env.env
           (sdk)path   -> .build/k230_linux_sdk/path
           (lilygo)path -> repo/canmv_k230/path
           a glob with * ** and {a,b}   (sdk)buildroot-overlay/package/aic8800{,_sdio/src}/fw/**
           embedded:<file>@<off>+<len>  a byte range inside firmware/stage1/<file>
           src:<name>                   a source tarball or checkout a nix file pins
           release:<name> / dl:<name>   a binary fetched by URL
           (silicon) ...                not a file at all

Runs on stdlib alone.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import os
import random
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
INVENTORY = "docs/blob-inventory.md"

# Where the inventory's path prefixes point. The scanner walks whichever of
# these is present on disk unless --no-vendor; it says which it skipped.
VENDOR_ROOTS = {
    "(sdk)": ".build/k230_linux_sdk",
    "(lilygo)": "repo/canmv_k230",
}
# Walk roots for vendor checkouts (the git root, which may be above the
# prefix's directory -- the LilyGO clone keeps datasheets and shipped images
# beside canmv_k230/).
VENDOR_WALK = {
    "(sdk)": ".build/k230_linux_sdk",
    "(lilygo)": "repo",
}

# The nix files whose fetches are stage 1's inputs. A hash pinned in any of
# these must be classified by the inventory as source (`src:`) or as a
# fetched binary (`release:` / `dl:`). Deliberately not every .nix file:
# the kernel pin in nix/kernel-src.nix is a source fetch the kernel
# capability owns, and a bump there should not have to touch the inventory.
STAGE1_NIX = [
    "nix/stage1.nix",
    "nix/k230-sdk-src.nix",
    "nix/uboot-k230.nix",
    "nix/opensbi-k230.nix",
]

HEX64 = re.compile(r"^[0-9a-f]{64}$")
SRI = re.compile(r"^sha256-[A-Za-z0-9+/]{43}=$")
NIX_HASH = re.compile(r"""(?:hash|sha256|outputHash)\s*=\s*"([^"]+)"\s*;""")


# --------------------------------------------------------------------------
# Classification
# --------------------------------------------------------------------------

TEXT_CONTROL_OK = {0x09, 0x0A, 0x0D, 0x1B, 0x07, 0x08, 0x0C}


def is_binary(path: Path, sample: int = 65536) -> bool:
    """Text is UTF-8 with (almost) no control bytes. Everything else is binary.

    A serial capture may carry a stray NUL -- docs/rtsmart-boot-log.txt holds
    two in 4.7 KB -- so a NUL alone does not make a file binary; a control
    byte ratio over two percent does. An ELF, an archive, a JPEG or a kmodel
    is not valid UTF-8 at all, which is the usual exit.
    """
    try:
        with path.open("rb") as fh:
            head = fh.read(sample)
    except OSError:
        return False
    if not head:
        return False
    decoded = False
    for encoding in ("utf-8", "gbk", "cp1252"):
        # Canaan's and LilyGO's trees carry C files with GBK comments, and
        # upstream MicroPython and RT-Thread each carry one with Windows-1252
        # quotes; none of those are blobs. Random binary data almost never
        # forms valid GBK or CP1252 (both reject some byte values), and what
        # does is caught by the control-byte ratio below.
        try:
            head.decode(encoding)
            decoded = True
            break
        except UnicodeDecodeError:
            continue
    if not decoded:
        return True
    control = sum(1 for b in head if b < 0x20 and b not in TEXT_CONTROL_OK)
    return control / len(head) > 0.02


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def to_hex(hash_spec: str) -> str | None:
    """Normalise a sha256 written as hex, SRI, or `sha256:<hex>` to hex."""
    spec = hash_spec.strip()
    if HEX64.match(spec):
        return spec
    if spec.startswith("sha256:") and HEX64.match(spec[7:]):
        return spec[7:]
    if SRI.match(spec):
        return base64.b64decode(spec[len("sha256-"):]).hex()
    return None


# --------------------------------------------------------------------------
# The MANIFEST
# --------------------------------------------------------------------------


@dataclass
class Row:
    cls: str
    hash_spec: str
    path: str
    line: int
    # Derived
    kind: str = ""          # file | group | embedded | pin | virtual
    rel: str = ""           # repo-relative path or glob
    sha256: str | None = None
    count: int | None = None
    members: list[str] = field(default_factory=list)


def expand_prefix(path: str) -> str:
    for prefix, root in VENDOR_ROOTS.items():
        if path.startswith(prefix):
            return root + "/" + path[len(prefix):]
    return path


def parse_manifest(text: str) -> list[Row]:
    m = re.search(r"^### MANIFEST\s*$", text, re.M)
    if not m:
        raise SystemExit(f"error: {INVENTORY} has no `### MANIFEST` section")
    fence = re.search(r"^```\s*\n(.*?)^```", text[m.end():], re.S | re.M)
    if not fence:
        raise SystemExit(f"error: {INVENTORY}: no fenced block under `### MANIFEST`")
    base_line = text[: m.end() + fence.start(1)].count("\n") + 1
    rows: list[Row] = []
    for i, raw in enumerate(fence.group(1).splitlines()):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        if len(parts) < 3:
            raise SystemExit(f"error: {INVENTORY}:{base_line + i}: cannot read row {raw!r}")
        cls, hash_spec, path = parts[0], parts[1], parts[2]
        row = Row(cls, hash_spec, path, base_line + i)
        if path.startswith("(silicon)"):
            row.kind = "virtual"
        elif path.startswith("embedded:"):
            row.kind = "embedded"
            row.sha256 = to_hex(hash_spec)
        elif path.startswith(("src:", "release:", "dl:")):
            row.kind = "pin"
            row.sha256 = to_hex(hash_spec)
        elif hash_spec.startswith("group:"):
            row.kind = "group"
            n = re.match(r"group:(\d+)-files?$", hash_spec)
            if not n:
                raise SystemExit(f"error: {INVENTORY}:{row.line}: bad group spec {hash_spec!r}")
            row.count = int(n.group(1))
            row.rel = expand_prefix(path)
        elif hash_spec.startswith("md5:") or hash_spec == "-":
            # Recorded, but not something this scanner can check on disk.
            row.kind = "virtual"
        else:
            row.kind = "file"
            row.sha256 = to_hex(hash_spec)
            row.rel = expand_prefix(path)
            if row.sha256 is None:
                raise SystemExit(f"error: {INVENTORY}:{row.line}: unreadable sha256 {hash_spec!r}")
        rows.append(row)
    return rows


# --------------------------------------------------------------------------
# Globs: * ** and {a,b}
# --------------------------------------------------------------------------


def brace_expand(pattern: str) -> list[str]:
    m = re.search(r"\{([^{}]*)\}", pattern)
    if not m:
        return [pattern]
    out: list[str] = []
    for alt in m.group(1).split(","):
        out.extend(brace_expand(pattern[: m.start()] + alt + pattern[m.end():]))
    return out


def glob_to_regex(pattern: str) -> re.Pattern[str]:
    out = "^"
    i = 0
    while i < len(pattern):
        c = pattern[i]
        if pattern.startswith("**/", i):
            out += "(?:.*/)?"
            i += 3
            continue
        if pattern.startswith("**", i):
            out += ".*"
            i += 2
            continue
        if c == "*":
            out += "[^/]*"
        elif c == "?":
            out += "[^/]"
        else:
            out += re.escape(c)
        i += 1
    return re.compile(out + "$")


def matcher(pattern: str):
    regexes = [glob_to_regex(p) for p in brace_expand(pattern)]
    return lambda rel: any(r.match(rel) for r in regexes)


# --------------------------------------------------------------------------
# Walking
# --------------------------------------------------------------------------


def git_files(root: Path) -> list[str] | None:
    try:
        out = subprocess.run(
            ["git", "-C", str(root), "ls-files", "-z"],
            check=True, capture_output=True,
        ).stdout
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None
    return [p for p in out.decode("utf-8", "surrogateescape").split("\0") if p]


def walk_files(root: Path, use_git: bool) -> list[str]:
    if use_git:
        files = git_files(root)
        if files is not None:
            return files
    out: list[str] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d != ".git"]
        for name in filenames:
            out.append(os.path.relpath(os.path.join(dirpath, name), root))
    return out


# --------------------------------------------------------------------------
# The scan
# --------------------------------------------------------------------------


@dataclass
class Result:
    failures: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    walked: int = 0
    binaries: int = 0
    covered_by_file: int = 0
    covered_by_group: int = 0
    rows_verified: int = 0
    rows_absent: int = 0
    pins_checked: int = 0


def scan(repo: Path, vendor: list[str], use_git: bool, verbose: bool,
         stage1_dir: Path | None) -> Result:
    res = Result()
    inventory = repo / INVENTORY
    if not inventory.is_file():
        res.failures.append(f"{INVENTORY} is missing")
        return res
    rows = parse_manifest(inventory.read_text(encoding="utf-8"))

    file_rows = {r.rel: r for r in rows if r.kind == "file"}
    group_rows = [(r, matcher(r.rel)) for r in rows if r.kind == "group"]

    # 1. Walk: the committed tree, then each vendor checkout, as
    #    repo-relative paths.
    found: list[str] = []
    if not use_git or git_files(repo) is None:
        res.notes.append(
            "walking the filesystem, not `git ls-files`: build products and other "
            "gitignored files are included"
        )
    for rel in walk_files(repo, use_git):
        found.append(rel)
    for prefix in vendor:
        walk_root = repo / VENDOR_WALK[prefix]
        if not walk_root.is_dir():
            res.notes.append(f"vendor checkout {prefix} not present at {VENDOR_WALK[prefix]}/; skipped")
            continue
        n = 0
        for rel in walk_files(walk_root, True):
            found.append(VENDOR_WALK[prefix] + "/" + rel)
            n += 1
        res.notes.append(f"walked vendor checkout {prefix} at {VENDOR_WALK[prefix]}/: {n} files")
    res.walked = len(found)

    # 2. Every binary must be covered.
    unlisted: list[str] = []
    for rel in sorted(found):
        path = repo / rel
        if not path.is_file() or not is_binary(path):
            continue
        res.binaries += 1
        row = file_rows.get(rel)
        if row is not None:
            res.covered_by_file += 1
            if verbose:
                print(f"  binary  {rel}  <- row {row.line} ({row.cls})")
            continue
        hit = None
        for row, match in group_rows:
            if match(rel):
                hit = row
                row.members.append(rel)
                break
        if hit is not None:
            res.covered_by_group += 1
            if verbose:
                print(f"  binary  {rel}  <- group row {hit.line} ({hit.cls}) {hit.path}")
            continue
        unlisted.append(rel)
    for rel in unlisted:
        res.failures.append(f"binary with no inventory row: {rel}")

    # 3. Every file-backed row that is on disk must match its hash.
    for rel, row in file_rows.items():
        path = repo / rel
        if not path.is_file():
            res.rows_absent += 1
            if verbose:
                print(f"  absent  {rel}  (row {row.line}; not on this machine)")
            continue
        got = sha256_file(path)
        if got != row.sha256:
            res.failures.append(
                f"{rel}: sha256 is {got}, inventory row {row.line} records {row.sha256}"
            )
        else:
            res.rows_verified += 1

    # 4. Group rows: the member count is what the inventory recorded.
    for row, _ in group_rows:
        walked_root = any(
            (row.rel.startswith(VENDOR_WALK[p]) and (repo / VENDOR_WALK[p]).is_dir())
            for p in vendor
        ) or not any(row.rel.startswith(r + "/") for r in VENDOR_WALK.values())
        if not walked_root:
            res.rows_absent += 1
            continue
        n = len(row.members)
        if n != row.count:
            res.failures.append(
                f"group row {row.line} {row.path!r}: {n} binary member(s) found, inventory records {row.count}"
                + (": " + ", ".join(row.members[:6]) + (" ..." if n > 6 else "") if n else "")
            )
        else:
            res.rows_verified += 1

    # 5. Embedded byte ranges, checked inside a stage-1 file when one is here.
    for row in rows:
        if row.kind != "embedded":
            continue
        m = re.match(r"embedded:([^@]+)@(0x[0-9a-f]+)\+(0x[0-9a-f]+)$", row.path)
        if not m:
            res.failures.append(f"{INVENTORY}:{row.line}: unreadable embedded spec {row.path!r}")
            continue
        name, off, ln = m.group(1), int(m.group(2), 16), int(m.group(3), 16)
        candidates = [stage1_dir / name] if stage1_dir else []
        candidates.append(repo / "firmware" / "stage1" / name)
        target = next((c for c in candidates if c.is_file()), None)
        if target is None:
            res.rows_absent += 1
            continue
        with target.open("rb") as fh:
            fh.seek(off)
            got = hashlib.sha256(fh.read(ln)).hexdigest()
        if got != row.sha256:
            res.failures.append(
                f"{target.relative_to(repo) if target.is_relative_to(repo) else target}: bytes at {hex(off)}+{hex(ln)} hash to {got}, inventory row {row.line} records {row.sha256}"
            )
        else:
            res.rows_verified += 1

    # 6. Hashes pinned in the stage-1 nix files.
    pins = {r.sha256: r for r in rows if r.kind == "pin" and r.sha256}
    for nix_rel in STAGE1_NIX:
        nix_path = repo / nix_rel
        if not nix_path.is_file():
            continue
        text = "\n".join(
            re.sub(r"(^|\s)#.*$", "", ln) for ln in nix_path.read_text(encoding="utf-8").splitlines()
        )
        for spec in NIX_HASH.findall(text):
            res.pins_checked += 1
            hx = to_hex(spec)
            if hx is None:
                res.failures.append(f"{nix_rel}: cannot read pinned hash {spec!r}")
                continue
            row = pins.get(hx)
            if row is None:
                res.failures.append(
                    f"{nix_rel} pins {spec}, which the inventory does not list. "
                    f"Add a `src:` row if it is source, a `release:` or `dl:` row if it is a binary"
                )
            elif verbose:
                print(f"  pin     {nix_rel}: {spec}  <- row {row.line} ({row.cls}) {row.path}")
    return res


def report(res: Result, vendor_desc: str) -> None:
    print(f"blob-scan: {vendor_desc}")
    for note in res.notes:
        print(f"  {note}")
    print(
        f"  walked {res.walked} files: {res.binaries} binary "
        f"({res.covered_by_file} by file row, {res.covered_by_group} by group row); "
        f"{res.rows_verified} inventory rows verified on disk, {res.rows_absent} not present here; "
        f"{res.pins_checked} nix pins checked"
    )
    if res.failures:
        print("")
        for f in res.failures:
            print(f"error: {f}", file=sys.stderr)
        print(f"blob-scan: FAIL ({len(res.failures)} problem(s))", file=sys.stderr)
    else:
        print("blob-scan: ok -- every binary is accounted for")


# --------------------------------------------------------------------------
# Self-test: the failure modes actually fire
# --------------------------------------------------------------------------


def run_scan(root: Path, extra: list[str]) -> tuple[int, str]:
    proc = subprocess.run(
        [sys.executable, __file__, "--root", str(root), "--no-git", "--no-vendor", *extra],
        capture_output=True, text=True,
    )
    return proc.returncode, proc.stdout + proc.stderr


def self_test() -> int:
    rng = random.Random(230)
    ok = True

    def case(title: str, root: Path, expect_fail: bool, must_mention: str) -> None:
        nonlocal ok
        code, out = run_scan(root, [])
        fired = code != 0
        mentioned = must_mention in out
        good = (fired == expect_fail) and (mentioned or not expect_fail)
        ok = ok and good
        verdict = "as expected" if good else "WRONG"
        print(f"--- {title}")
        print(f"    scan exit status: {code}  ({'failed' if fired else 'passed'}, {verdict})")
        for ln in out.splitlines():
            if ln.startswith("error:") or ln.startswith("blob-scan:"):
                print(f"    {ln}")

    with tempfile.TemporaryDirectory(prefix="blob-scan-selftest-") as tmp:
        base = Path(tmp)
        # A minimal tree: the inventory, the stage-1 nix files, and every
        # binary the committed tree carries (the evidence photographs), so
        # that the baseline is the real tree's baseline and a group row
        # counts what it counts there.
        wanted = [INVENTORY, *STAGE1_NIX]
        wanted += [rel for rel in (git_files(REPO) or []) if is_binary(REPO / rel)]
        for rel in wanted:
            src = REPO / rel
            if src.is_file():
                (base / rel).parent.mkdir(parents=True, exist_ok=True)
                shutil.copy(src, base / rel)

        case("baseline: the inventory and the nix files alone", base, False, "")

        planted = base / "firmware" / "planted.bin"
        planted.parent.mkdir(parents=True, exist_ok=True)
        planted.write_bytes(bytes(rng.getrandbits(8) for _ in range(4096)))
        case("a binary with no inventory row is planted at firmware/planted.bin",
             base, True, "firmware/planted.bin")
        planted.unlink()

        stage1 = base / "nix" / "stage1.nix"
        original = stage1.read_text(encoding="utf-8") if stage1.is_file() else ""
        mutated = "sha256-" + base64.b64encode(bytes(rng.getrandbits(8) for _ in range(32))).decode()
        stage1.parent.mkdir(parents=True, exist_ok=True)
        stage1.write_text(
            original
            + '\n# self-test\nrelease = fetchurl {\n'
            '  url = "https://example.invalid/stage1.tar.gz";\n'
            f'  hash = "{mutated}";\n}};\n',
            encoding="utf-8",
        )
        case("nix/stage1.nix pins a release hash the inventory does not list",
             base, True, mutated)
        stage1.write_text(original, encoding="utf-8")

        env = base / "firmware" / "stage1" / "env.env"
        env.parent.mkdir(parents=True, exist_ok=True)
        env.write_bytes(bytes(rng.getrandbits(8) for _ in range(8192)))
        case("a listed blob (firmware/stage1/env.env) has different bytes than its row",
             base, True, "firmware/stage1/env.env")
        env.unlink()

    print("")
    print("self-test: " + ("ok -- every planted fault was reported" if ok else "FAILED"))
    return 0 if ok else 1


# --------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", default=None, help="repository root (default: this checkout)")
    parser.add_argument("--no-git", action="store_true",
                        help="walk the filesystem instead of `git ls-files`")
    parser.add_argument("--no-vendor", action="store_true",
                        help="do not walk vendor checkouts even when present")
    parser.add_argument("--stage1", default=None,
                        help="a built stage-1 directory to check `embedded:` rows against")
    parser.add_argument("-v", "--verbose", action="store_true")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args(argv)

    if args.self_test:
        return self_test()

    repo = Path(args.root).resolve() if args.root else REPO
    vendor = [] if args.no_vendor else list(VENDOR_ROOTS)
    res = scan(repo, vendor, not args.no_git, args.verbose,
               Path(args.stage1).resolve() if args.stage1 else None)
    desc = f"{repo}" + (" (committed tree only)" if args.no_vendor else "")
    report(res, desc)
    return 1 if res.failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
