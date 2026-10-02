#!/usr/bin/env python3
"""Fail-closed preflight and recovery identity check for the mainline trial."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys


def digest(path):
    h = hashlib.sha256()
    with open(path, "rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def run(mode, token):
    expected = json.loads(Path("/run/k230-mainline-expected.json").read_text())
    assert mode in ("preflight", "postflight")
    assert len(token) == 32 and all(c in "0123456789abcdef" for c in token)
    protected_names = {
        "Image", "initrd.uimg", "k230-tdisplay.dtb", "bootargs.txt",
        "fw_jump_add_uboot_head.bin", "force_dtb", "lcd_dtb", "hdmi_dtb",
    }
    assert set(expected["boot_files"]) == protected_names
    system = expected["system"]
    kernel = expected["kernel"]
    assert os.path.realpath("/run/current-system") == system
    assert os.path.realpath("/nix/var/nix/profiles/system") == expected["profile"]
    assert os.path.realpath("/run/booted-system/kernel") == kernel
    cmdline = Path("/proc/cmdline").read_text().split()
    assert [arg for arg in cmdline if arg.startswith("init=")] == ["init=" + system + "/init"]
    files = {}
    for name, info in expected["boot_files"].items():
        path = "/boot/" + name
        observed = digest(path)
        assert observed == info["sha256"], "protected boot hash mismatch: " + name
        files[name] = observed
    services = subprocess.check_output(
        ["systemctl", "is-active", "shell", "shell-ui", "theme-helper"], text=True
    ).splitlines()
    assert services == ["active"] * 3
    boot_id = Path("/proc/sys/kernel/random/boot_id").read_text().strip()
    if mode == "postflight":
        assert boot_id != expected["trial_from_boot_id"], "recovery did not create a new boot"
    observed = {
        "system": os.path.realpath("/run/current-system"),
        "profile": os.path.realpath("/nix/var/nix/profiles/system"),
        "kernel": os.path.realpath("/run/booted-system/kernel"),
        "init": "init=" + system + "/init",
        "uname": subprocess.check_output(["uname", "-r"], text=True).strip(),
        "boot_id": boot_id,
        "services": services,
        "boot_files": files,
    }
    assert observed["uname"] == expected["uname"]
    if mode == "preflight":
        stage = Path(expected["stage"])
        assert os.path.realpath(stage / "system") == expected["candidate_system"]
        assert set(expected["candidate_files"]) == {
            "Image-mainline-drm", "k230-tdisplay-mainline-drm.dtb", "initrd.uimg", "bootargs.txt"
        }
        assert set(expected["metadata_sha256"]) == {"registration", "store-paths", "SHA256SUMS"}
        for name, info in expected["candidate_files"].items():
            path = stage / name
            assert path.is_file() and path.stat().st_size == info["bytes"]
            assert digest(path) == info["sha256"], "staged candidate mismatch: " + name
        for name, sha in expected["metadata_sha256"].items():
            assert digest(stage / name) == sha, "staged metadata mismatch: " + name
        staged_paths = (stage / "store-paths").read_text().splitlines()
        closure = subprocess.check_output(
            ["nix-store", "-qR", expected["candidate_system"]], text=True
        ).splitlines()
        assert len(staged_paths) == len(set(staged_paths))
        assert set(closure) == set(staged_paths), "registered candidate closure differs from bundle"
        for start in range(0, len(staged_paths), 100):
            subprocess.run(
                ["nix-store", "--check-validity", *staged_paths[start : start + 100]],
                check=True,
                stdout=subprocess.DEVNULL,
            )
        args = (stage / "bootargs.txt").read_text().split()
        assert "init=" + expected["candidate_system"] + "/init" in args
        assert Path(expected["candidate_system"] + "/init").is_file()
    print("K230_MAINLINE_STATE " + token + " " + mode + " " + json.dumps(observed, sort_keys=True), flush=True)


if __name__ == "__main__":
    if os.geteuid() != 0 or len(sys.argv) != 3:
        raise SystemExit("root and mode/token arguments required")
    run(sys.argv[1], sys.argv[2])
