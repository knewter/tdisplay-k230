#!/usr/bin/env python3
"""Run one bounded rdinit=/bin/sh trial from the exact mainline DRM bundle.

Raw serial output can contain private machine details. The controller writes
it only to a newly-created mode-0600 log outside the repository and never
prints it to stdout.
"""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import importlib.util
import json
import os
import re
import shlex
import struct
import subprocess
import sys
import time
import uuid
import zlib
from datetime import datetime, timezone
from pathlib import Path


BUNDLE = Path(
    "/nix/store/gf3aqks2dg0z3ksz33ysfprnlbk83vw3-"
    "k230-mainline-drm-trial-boot-files"
)
SYSTEM = "/nix/store/k9f4r2i9k9qj58z8z4l2kssy9rpwxxm1-nixos-system-nixos-26.11.20260919.20b1ddd"
NORMAL_REPORT = Path("/home/jadams/tmp/k230-coherent-boot-board/received/after.json")
NORMAL_BASELINE = Path(__file__).resolve().parents[1] / "docs/evidence/boot-verification/coherent-ordinary-boot/postboot.json"
# The protected stage-one wrapper's CRC in the committed physical trial manifest.
NORMAL_WRAPPER_CRC32 = "99b89787"
STORE_ROOT = Path("/nix/store")
NORMAL_HELPER = Path(__file__).with_name("mainline-drm-normal-state.py")
NORMAL_STAGE = "/var/lib/k230-mainline-drm-trial"
BOARD_PYTHON = "/nix/store/v189xydz6qkcd4cbkixcmv91w8hbc560-python3-riscv64-unknown-linux-gnu-3.14.7/bin/python3"
MANIFEST_DEFAULT = Path("/home/jadams/tmp/k230-coordination/mainline-boot-manifest.json")
PRIVATE_LOG_DIR = Path("/home/jadams/tmp/k230-coordination/mainline-initrd-private")
LOCK_PATH = Path("/tmp/k230-board.lock")
SERIAL_DEVICE = "/dev/ttyACM0"
PROMPT = b"K230# "
RECEPTION_MAX_ATTEMPTS = 8
RECEPTION_ATTEMPT_TIMEOUT = 1.0
INITRD_READY_TIMEOUT = 90.0
RUNTIME_TRACE_TIMEOUT = 20.0
RUNTIME_TRACE_PARAMETER = "/sys/module/kernel/parameters/initcall_debug"
RUNTIME_TRACE_STAGES = ("sys-mkdir", "sys-mount", "permissions", "prior", "write", "readback")
SHELL_CONTROLS = ("fsck.mode=skip", "systemd.mask=k230-root-growth.service",
                  "systemd.mask=register-nix-paths.service", "initramfs_async=0")
SHELL_TRACE_FLAGS = ("k230.boot_trace=1", "k230.boot_trace_sbi_only=1")
UART_PROGRESS_FLAG = "k230.uart_progress=1"
UART_PROGRESS_POST_SAMPLE_FLAG = "k230.uart_progress_post_sample=1"
UART_PROGRESS_POST_SAMPLE = (b"K230_UPP1 point=after-n1-write\n", b"K230_UPP1 point=third-post-sleep\n")
UART_POST_SAMPLE_SOURCE_SHA256 = "aee68aaec5c5c0e2b23919901eb99189265fd2b4787a0e50bc11159afd81ef9b"
UART_PROGRESS_BREADCRUMBS_FLAG = "k230.uart_progress_breadcrumbs=1"
UART_PROGRESS_BREADCRUMBS = (b"K230_UPB1 point=worker-entry\n", b"K230_UPB1 point=first-post-sleep\n")
UART_BREADCRUMB_SOURCE_SHA256 = "7207dcae9462694a07bd4f7d37d1d9ea43a536496f1b96dd94fed3dfa78c6a22"
UART_PROGRESS_FIELDS = ("j", "t", "u", "ti", "ui", "tc", "rx", "tx", "fe", "pe", "oe", "be", "ie", "rm", "im", "hz")
UART_PROGRESS_UART_FIELDS = ("u", "ui", "rx", "tx", "fe", "pe", "oe", "be", "ie", "rm", "im", "hz")
BOOT_ID_PATTERN = r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"
_PROTOCOL_SPEC = importlib.util.spec_from_file_location(
    "rvv_board_boot", Path(__file__).with_name("rvv-board-boot.py")
)
_PROTOCOL = importlib.util.module_from_spec(_PROTOCOL_SPEC)
_PROTOCOL_SPEC.loader.exec_module(_PROTOCOL)
LOADS = (
    ("bootargs.txt", "1:2", "0x7000000", "/var/lib/k230-mainline-drm-trial/bootargs.txt"),
    ("fw_jump_add_uboot_head.bin", "1:1", "0x8000000", "/fw_jump_add_uboot_head.bin"),
    ("Image-mainline-drm", "1:2", "0x200000", "/var/lib/k230-mainline-drm-trial/Image-mainline-drm"),
    ("k230-tdisplay-mainline-drm.dtb", "1:2", "0x8400000", "/var/lib/k230-mainline-drm-trial/k230-tdisplay-mainline-drm.dtb"),
    ("initrd.uimg", "1:2", "0x9000000", "/var/lib/k230-mainline-drm-trial/initrd.uimg"),
)
PROBE_DATA = (
    "_k230_probe_rc=0; _k230_block_count=0; _k230_label_ok=0; _k230_nixos_sd=0; "
    "mkdir -p /proc /sys /dev; _k230_mkdir_rc=$?; "
    "printf 'K230_RDINIT_STAGE K230_STAGE_TOKEN mkdir-done\\n'; "
    "test $_k230_mkdir_rc -eq 0 || _k230_probe_rc=1; "
    "mount -t proc proc /proc 2>/dev/null || test -r /proc/mounts || _k230_probe_rc=1; "
    "printf 'K230_RDINIT_STAGE K230_STAGE_TOKEN proc-mount-check\\n'; "
    "_k230_have_sys=0; _k230_have_dev=0; "
    "while read _src _mnt _fs _rest; do "
    "test \"$_mnt\" = /sys && test \"$_fs\" = sysfs && _k230_have_sys=1; "
    "test \"$_mnt\" = /dev && test \"$_fs\" = devtmpfs && _k230_have_dev=1; "
    "done < /proc/mounts; "
    "test $_k230_have_sys -eq 1 || mount -t sysfs sysfs /sys || _k230_probe_rc=1; "
    "printf 'K230_RDINIT_STAGE K230_STAGE_TOKEN sys-mount-check\\n'; "
    "test $_k230_have_dev -eq 1 || mount -t devtmpfs devtmpfs /dev || _k230_probe_rc=1; "
    "printf 'K230_RDINIT_STAGE K230_STAGE_TOKEN dev-mount-check\\n'; "
    "_k230_have_proc=0; _k230_have_sys=0; _k230_have_dev=0; "
    "while read _src _mnt _fs _rest; do "
    "test \"$_mnt\" = /proc && test \"$_fs\" = proc && _k230_have_proc=1; "
    "test \"$_mnt\" = /sys && test \"$_fs\" = sysfs && _k230_have_sys=1; "
    "test \"$_mnt\" = /dev && test \"$_fs\" = devtmpfs && _k230_have_dev=1; "
    "done < /proc/mounts; "
    "test $_k230_have_proc -eq 1 && test $_k230_have_sys -eq 1 && "
    "test $_k230_have_dev -eq 1 || _k230_probe_rc=1; "
    "test -r /proc/partitions || _k230_probe_rc=1; "
    "test -r /proc/interrupts || _k230_probe_rc=1; "
    "test -d /sys/block || _k230_probe_rc=1; "
    "echo K230_PROC; printf 'K230_RDINIT_STAGE K230_STAGE_TOKEN proc-read-start\\n'; "
    "cat /proc/uptime /proc/interrupts /proc/cmdline /proc/partitions /proc/mounts; "
    "_k230_proc_read_rc=$?; printf 'K230_RDINIT_STAGE K230_STAGE_TOKEN proc-read-done\\n'; "
    "test $_k230_proc_read_rc -eq 0 || _k230_probe_rc=1; "
    "echo K230_SYS_BLOCK; ls -l /sys/block; "
    "printf 'K230_RDINIT_STAGE K230_STAGE_TOKEN sys-block-read-done\\n'; "
    "echo K230_DEV_BLOCK; ls -l /dev/mmcblk* 2>&1; "
    "printf 'K230_RDINIT_STAGE K230_STAGE_TOKEN dev-block-read-done\\n'; "
    "echo K230_UDEV_LABEL_LINKS; ls -l /dev/disk/by-label; "
    "for dev in /dev/mmcblk*p*; do "
    "if test -b \"$dev\"; then _k230_block_count=$((_k230_block_count+1)); "
    "if _k230_label=$(e2label \"$dev\" 2>&1); then _k230_label_ok=1; "
    "else _k230_label=unreadable; fi; "
    "printf 'K230_EXT4_LABEL %s %s\\n' \"$dev\" \"$_k230_label\"; "
    "test \"$_k230_label\" = NIXOS_SD && _k230_nixos_sd=1; fi; done; "
    "test $_k230_block_count -gt 0 || _k230_probe_rc=1; "
    "printf 'K230_RDINIT_STAGE K230_STAGE_TOKEN labels-read-done\\n'; "
    "test $_k230_label_ok -eq 1 || _k230_probe_rc=1; "
    "printf 'K230_LABEL_NIXOS_SD=%s\\n' \"$_k230_nixos_sd\""
)


def trial_bootargs(
    original: str, system: str = SYSTEM, *, ignore_unused_clocks: bool = False,
    debug_shutdown: bool = False,
    runtime_shutdown_trace: bool = False,
) -> str:
    """Add diagnostic arguments and require the matching NixOS init."""
    args = original.strip()
    params = args.removeprefix("bootargs=").split()
    init_args = [arg for arg in params if arg.startswith("init=")]
    if init_args != [f"init={system}/init"]:
        raise ValueError("bootargs do not select the matching trial system")
    if any(arg.startswith("rdinit=") for arg in params):
        raise ValueError("original bootargs already contain rdinit")
    if any(ord(char) < 32 for char in args):
        raise ValueError("bootargs must be a single line")
    if ignore_unused_clocks and any(arg.split("=", 1)[0] == "clk_ignore_unused" for arg in params):
        raise ValueError("original bootargs already contain clk_ignore_unused")
    if runtime_shutdown_trace and debug_shutdown:
        raise ValueError("runtime shutdown trace cannot be combined with boot debug")
    if debug_shutdown or runtime_shutdown_trace:
        if debug_shutdown and ignore_unused_clocks:
            raise ValueError("shutdown debug and clock diagnostics cannot be combined")
        for arg in params:
            name, _, value = arg.partition("=")
            if (name in {"initcall_debug", "ignore_loglevel", "quiet", "debug", "dyndbg"}
                    or name.endswith(".dyndbg")
                    or (name == "loglevel" and value not in tuple(str(n) for n in range(8)))):
                raise ValueError("original bootargs contain conflicting shutdown debug arguments")
    extra = " clk_ignore_unused" if ignore_unused_clocks else ""
    if debug_shutdown:
        # The bundle's existing loglevel=4/7 is preserved; the final 8 wins.
        extra = " initcall_debug loglevel=8"
    return f"{args} rdinit=/bin/sh" + extra


def volatile_bootargs_command(ignore_unused_clocks: bool = False, *, debug_shutdown: bool = False) -> str:
    if ignore_unused_clocks and debug_shutdown:
        raise ValueError("shutdown debug and clock diagnostics cannot be combined")
    extra = " clk_ignore_unused" if ignore_unused_clocks else ""
    if debug_shutdown:
        extra = " initcall_debug loglevel=8"
    return 'setenv bootargs "${bootargs} rdinit=/bin/sh' + extra + '"'


def validate_shell_selector(selector, mode, ignore_unused_clocks=False, debug_shutdown=False,
                            runtime_shutdown_trace=False):
    if type(selector) is not bool:
        raise ValueError("shell PID1 selector must be boolean")
    if selector and (mode != "minimal" or ignore_unused_clocks or debug_shutdown or runtime_shutdown_trace):
        raise ValueError("--same-image-shell-pid1 requires minimal mode without other diagnostic flags")


def shell_pid1_bootargs(original: str, system: str) -> str:
    """Qualify the original artifact before changing only its volatile arguments."""
    expected = ["consoleblank=0", "console=ttyS0,115200n8", "root=fstab", "loglevel=4",
                "lsm=landlock,yama,bpf", "loglevel=7", *SHELL_TRACE_FLAGS, f"init={system}/init"]
    if original != "bootargs=" + " ".join(expected) + "\n":
        raise ValueError("shell comparison requires exact original SBI-only artifact arguments")
    params = [p for p in expected if p not in SHELL_TRACE_FLAGS]
    return "bootargs=" + " ".join([*params, *SHELL_CONTROLS, "rdinit=/bin/sh"])


def shell_pid1_transport(args: str, system: str, *, uart_progress=False, uart_progress_breadcrumbs=False, uart_progress_post_sample=False) -> str:
    # Reconstruct the qualified transform instead of accepting arbitrary literal args.
    original = ("bootargs=consoleblank=0 console=ttyS0,115200n8 root=fstab loglevel=4 "
                "lsm=landlock,yama,bpf loglevel=7 " + " ".join(SHELL_TRACE_FLAGS) +
                f" init={system}/init\n")
    expected = shell_pid1_bootargs(original, system) + (" " + UART_PROGRESS_FLAG if uart_progress else "")
    if uart_progress_breadcrumbs:
        if not uart_progress:
            raise ValueError("breadcrumb transport requires reporter selection")
        expected += " " + UART_PROGRESS_BREADCRUMBS_FLAG
    if uart_progress_post_sample:
        if not uart_progress_breadcrumbs:
            raise ValueError("post-sample transport requires breadcrumbs")
        expected += " " + UART_PROGRESS_POST_SAMPLE_FLAG
    if args != expected:
        raise ValueError("unexpected shell comparison arguments")
    value = args.removeprefix("bootargs=")
    if not re.fullmatch(r"[A-Za-z0-9_./:=,+@% \-]+", value):
        raise ValueError("unsafe shell comparison transport")
    command = 'setenv bootargs "' + value + '"'
    if len(command.encode()) >= 512:
        raise ValueError("shell comparison exceeds U-Boot input bound")
    return command


def inspect_shell_initrd(prepared: dict) -> dict:
    """Inspect archived executables, not host symlink substitutes; never extract."""
    system = Path(prepared["system"])
    kernel = (system / "kernel").resolve(strict=True)
    immutable_store_path(kernel.parent, "selected kernel")
    if kernel.name != "Image" or hashlib.sha256(kernel.read_bytes()).hexdigest() != prepared["manifest"]["files"]["Image-mainline-drm"]["sha256"]:
        raise ValueError("shell comparison kernel does not match selected system")
    initrd = (system / "initrd").resolve(strict=True)
    immutable_store_path(initrd.parent, "selected initrd")
    payload = initrd.read_bytes()
    wrapped = (prepared["bundle"] / "initrd.uimg").read_bytes()
    if len(wrapped) < 64:
        raise ValueError("truncated shell comparison ramdisk")
    magic, hcrc, _, size, _, _, dcrc, os_id, arch, image_type, compression, _ = struct.unpack(">7I4B32s", wrapped[:64])
    header = wrapped[:4] + bytes(4) + wrapped[8:64]
    if (magic != 0x27051956 or zlib.crc32(header) != hcrc or (os_id, arch, image_type, compression) != (5, 26, 3, 0)
            or size != len(payload) or wrapped[64:] != payload or zlib.crc32(payload) != dcrc):
        raise ValueError("shell comparison initrd wrapper does not match selected system")
    spec = importlib.util.spec_from_file_location("shell_archive", Path(__file__).with_name("mainline-drm-uart-observer-trial.py"))
    archive = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(archive)
    entries = archive.archive_entries(payload)
    executables = {}
    loaders = []
    for name in ("init", "bin/sh", "bin/readlink", "bin/true", "bin/mkdir", "bin/mount", "bin/cat", "bin/reboot"):
        path = archive.archive_resolve(entries, name)
        mode, body = entries[path]
        if not mode & 0o111 or mode & 0o170000 != 0o100000 or not archive.riscv_elf(body):
            raise ValueError("shell comparison lacks an archived RISC-V executable")
        if name == "bin/sh" and not re.fullmatch(r"nix/store/[0-9a-z]{32}-bash-interactive-riscv64-unknown-linux-gnu-5\.3p15/bin/bash", path):
            raise ValueError("shell comparison does not select the intended Bash")
        if name == "init" and not re.fullmatch(r"nix/store/[0-9a-z]{32}-systemd-riscv64-unknown-linux-gnu-261\.2/lib/systemd/systemd", path):
            raise ValueError("shell comparison does not contain the intended original PID1")
        executables[name] = {"path": "/" + path, "sha256": hashlib.sha256(body).hexdigest()}
        if name in ("init", "bin/sh"):
            phoff = struct.unpack_from("<Q", body, 32)[0]
            phsize, phnum = struct.unpack_from("<HH", body, 54)
            if phsize != 56 or not 0 < phnum <= 128 or phoff + phsize * phnum > len(body):
                raise ValueError("invalid archived ELF program headers")
            found = []
            for i in range(phnum):
                base = phoff + i * phsize
                if struct.unpack_from("<I", body, base)[0] == 3:
                    start, length = struct.unpack_from("<Q", body, base + 8)[0], struct.unpack_from("<Q", body, base + 32)[0]
                    if not 1 < length <= 4096 or start + length > len(body) or body[start + length - 1] != 0:
                        raise ValueError("invalid archived ELF interpreter")
                    found.append(body[start:start + length - 1].decode("ascii"))
            if len(found) != 1:
                raise ValueError("missing or duplicate archived ELF interpreter")
            loaders.append(archive.archive_resolve(entries, found[0]))
    if loaders[0] != loaders[1]:
        raise ValueError("shell comparison programs do not share the archived loader")
    mode, loader = entries[loaders[0]]
    if not mode & 0o111 or not archive.riscv_elf(loader):
        raise ValueError("shell comparison common loader is not executable RISC-V")
    archive.archive_resolve(entries, "etc/initrd-release")
    return {"bash": executables["bin/sh"]["path"], "executables": executables,
            "loader": "/" + loaders[0], "loader_sha256": hashlib.sha256(loader).hexdigest(),
            "initrd_sha256": hashlib.sha256(payload).hexdigest()}


def prepare_shell_comparison(prepared: dict) -> dict:
    p = dict(prepared)
    p["bootargs"] = shell_pid1_bootargs((p["bundle"] / "bootargs.txt").read_text(), p["system"])
    p["transport"] = shell_pid1_transport(p["bootargs"], p["system"])
    p["shell_comparison"] = {**inspect_shell_initrd(p), "bootargs": p["bootargs"], "system": p["system"]}
    # Actually execute this assertion in both uploaded protected phase helpers.
    p["helper_text"] = ("from pathlib import Path\nassert not Path('/nix-path-registration').exists() and not Path('/nix-path-registration').is_symlink(), 'registration marker present'\n" + p["helper_text"])
    shell_guard_command("a" * 32, "initial", p["shell_comparison"], p["normal"])
    shell_guard_command("b" * 32, "renewed", p["shell_comparison"], p["normal"], "00000000-0000-0000-0000-000000000002")
    return p


def validate_uart_progress_selector(selector, same_image_shell_pid1, mode,
                                    ignore_unused_clocks=False, debug_shutdown=False,
                                    runtime_shutdown_trace=False):
    if type(selector) is not bool:
        raise ValueError("UART progress selector must be boolean")
    if selector and (not same_image_shell_pid1 or mode != "minimal" or
                     ignore_unused_clocks or debug_shutdown or runtime_shutdown_trace):
        raise ValueError("--uart-progress requires minimal --same-image-shell-pid1 without other diagnostics")


def validate_uart_breadcrumb_selector(selector, uart_progress, same_image_shell_pid1, mode):
    if type(selector) is not bool:
        raise ValueError("UART breadcrumb selector must be boolean")
    if selector and (uart_progress is not True or same_image_shell_pid1 is not True or mode != "minimal"):
        raise ValueError("--uart-progress-breadcrumbs requires minimal --same-image-shell-pid1 --uart-progress")


def validate_uart_post_sample_selector(selector, breadcrumbs, uart_progress, same_image_shell_pid1, mode):
    if type(selector) is not bool:
        raise ValueError("UART post-sample selector must be boolean")
    if selector and (breadcrumbs is not True or uart_progress is not True or
                     same_image_shell_pid1 is not True or mode != "minimal"):
        raise ValueError("--uart-progress-post-sample requires minimal --same-image-shell-pid1 --uart-progress --uart-progress-breadcrumbs")


def inspect_uart_progress_kernel(prepared):
    """Require a realized dev config from the very same kernel derivation."""
    kernel = (Path(prepared["system"]) / "kernel").resolve(strict=True).parent
    def query(*args):
        return subprocess.check_output(["nix-store", "--query", *args], text=True,
                                       timeout=20).splitlines()
    derivations = query("--deriver", str(kernel))
    if len(derivations) != 1 or not re.fullmatch(r"/nix/store/[0-9a-z]{32}-[^/]+\.drv", derivations[0]):
        raise ValueError("selected progress kernel derivation is unavailable")
    outputs = query("--outputs", derivations[0])
    if str(kernel) not in outputs:
        raise ValueError("selected kernel is not a reported derivation output")
    configs = []
    for output in outputs:
        if not output.endswith("-dev"):
            continue
        dev = immutable_store_path(Path(output), "selected kernel dev")
        config = dev / "lib/modules/7.3.0-rc5/build/.config"
        if config.is_file():
            configs.append(config)
    if len(configs) != 1:
        raise ValueError("realize the matching progress kernel dev output before UART access")
    content = configs[0].read_bytes()
    for name in ("K230_UART_PROGRESS", "RISCV_SBI", "RISCV_TIMER", "SERIAL_8250", "SERIAL_8250_DW", "OF"):
        if re.findall(rb"^CONFIG_" + name.encode() + rb"=(.*)$", content, re.M) != [b"y"]:
            raise ValueError("matching kernel config lacks required built-in " + name)
    return {"kernel": str(kernel), "derivation": derivations[0], "config": str(configs[0]),
            "config_sha256": hashlib.sha256(content).hexdigest()}


def inspect_uart_breadcrumb_kernel(prepared, *, uart_progress_post_sample=False):
    """Prove selected variant source and linked bytes, not just CONFIG=y."""
    proof = prepared["uart_progress_kernel"]
    description = json.loads(subprocess.check_output(
        ["nix", "--offline", "--extra-experimental-features", "nix-command", "derivation", "show", proof["derivation"]],
        text=True, timeout=20))
    if set(description) == {"derivations", "version"} and description["version"] == 4:
        description = description["derivations"]
        key = Path(proof["derivation"]).name
    else:
        key = proof["derivation"]
    if not isinstance(description, dict) or set(description) != {key}:
        raise ValueError("selected breadcrumb kernel derivation description is unknown")
    derivation = description[key]
    source_value = derivation.get("env", {}).get("src")
    if source_value is None:
        source_value = derivation.get("structuredAttrs", {}).get("src")
    if not isinstance(source_value, str):
        raise ValueError("selected kernel derivation lacks its source identity")
    source = immutable_store_path(Path(source_value), "selected breadcrumb source")
    worker = source / "drivers/soc/canaan/k230-uart-progress.c"
    content = worker.read_bytes()
    # Freeze to the reviewed layered worker once its source proof is available.
    expected_sha = UART_POST_SAMPLE_SOURCE_SHA256 if uart_progress_post_sample else UART_BREADCRUMB_SOURCE_SHA256
    if hashlib.sha256(content).hexdigest() != expected_sha:
        raise ValueError("selected worker is not the reviewed breadcrumb variant")
    image = (Path(proof["kernel"]) / "Image").read_bytes()
    offsets = {}
    markers = UART_PROGRESS_BREADCRUMBS + (UART_PROGRESS_POST_SAMPLE if uart_progress_post_sample else ())
    for marker in markers:
        literal = b"\n" + marker + b"\0"
        if image.count(literal) != 1:
            raise ValueError("selected Image lacks a unique compiled breadcrumb string")
        offsets[marker.decode().strip()] = image.index(literal)
    if image.count(b"k230.uart_progress_breadcrumbs=\0") != 1:
        raise ValueError("selected Image lacks its exact breadcrumb setup gate")
    if uart_progress_post_sample and image.count(b"k230.uart_progress_post_sample=\0") != 1:
        raise ValueError("selected Image lacks its exact post-sample setup gate")
    return {"source": str(source), "worker_sha256": hashlib.sha256(content).hexdigest(),
            "image_sha256": hashlib.sha256(image).hexdigest(), "marker_offsets": offsets}


def prepare_uart_progress(prepared, *, uart_progress_breadcrumbs=False, uart_progress_post_sample=False):
    validate_uart_post_sample_selector(uart_progress_post_sample, uart_progress_breadcrumbs, True, True, "minimal")
    p = prepare_shell_comparison(prepared)
    p["uart_progress_kernel"] = inspect_uart_progress_kernel(p)
    p["bootargs"] += " " + UART_PROGRESS_FLAG
    if uart_progress_breadcrumbs:
        p["uart_progress_breadcrumb_kernel"] = inspect_uart_breadcrumb_kernel(
            p, **({"uart_progress_post_sample": True} if uart_progress_post_sample else {}))
        p["bootargs"] += " " + UART_PROGRESS_BREADCRUMBS_FLAG
    if uart_progress_post_sample:
        p["uart_progress_post_sample_kernel"] = p["uart_progress_breadcrumb_kernel"]
        p["bootargs"] += " " + UART_PROGRESS_POST_SAMPLE_FLAG
    p["transport"] = shell_pid1_transport(p["bootargs"], p["system"], uart_progress=True,
                                          uart_progress_breadcrumbs=uart_progress_breadcrumbs,
                                          uart_progress_post_sample=uart_progress_post_sample)
    return p


def uart_progress_record(line):
    """Only exact complete public records; no printk insertion repair."""
    pattern = rb"K230_UP1 n=([0-5]) s=([0-5])" + b"".join(
        b" " + key.encode() + rb"=([0-9a-f]{" + str(16 if key in ("j", "t") else 8).encode() + rb"})"
        for key in UART_PROGRESS_FIELDS) + rb"\n"
    match = re.fullmatch(pattern, line)
    if not match or len(line) >= 256:
        return None
    result = {"n": int(match[1]), "s": int(match[2]),
              **{key: int(value, 16) for key, value in zip(UART_PROGRESS_FIELDS, match.groups()[2:])}}
    if ((result["s"] and any(result[key] for key in UART_PROGRESS_UART_FIELDS)) or
            (not result["s"] and not result["u"]) or (not result["ti"] and result["tc"])):
        return None
    return result


def uart_progress_breadcrumb(line):
    if line in UART_PROGRESS_BREADCRUMBS:
        return line.split(b"=", 1)[1].strip().decode("ascii")
    return None


def uart_progress_post_sample_record(line):
    if line in UART_PROGRESS_POST_SAMPLE:
        return line.split(b"=", 1)[1].strip().decode("ascii")
    return None


def observe_uart_progress(session, token, expected_args, *, timeout=180, readiness_timeout=90,
                          clock=time.monotonic, uart_progress_breadcrumbs=False, uart_progress_post_sample=False):
    """One fresh stimulus, then read only, including on unknown completion."""
    _validate_token(token)
    validate_uart_post_sample_selector(uart_progress_post_sample, uart_progress_breadcrumbs, True, True, "minimal")
    if not 0 < timeout <= 180 or not 0 < readiness_timeout <= min(timeout, 90):
        raise ValueError("invalid bounded UART observation deadline")
    started = clock()
    expected_cmdline = expected_args.removeprefix("bootargs=")
    text = b""
    records, errors = [], []
    breadcrumbs = []
    post_sample = []
    banner = entry = ready = sent = False
    normal_ready = False
    candidate_start = init_end = None
    parsed_lines = 0
    receipt_count = 0
    args_status = "UNKNOWN"
    prompt_seen = False
    overflow = False
    normal_tail = b""
    normal_stage = 0
    total = 0
    while clock() - started < timeout:
        try:
            chunk = session.pump()
        except Exception:
            errors.append("transport-read-unknown")
            break
        total += len(chunk)
        normal_tail = (normal_tail + chunk)[-131072:]
        normal_text = _PROTOCOL.uart_text(normal_tail)
        # Recovery is independent of candidate banner/protocol success.
        normal_patterns = (rb"^U-Boot SPL 2022\.10[^\n]*\n",
                           rb"^\[\s*[0-9]+\.[0-9]+\]\s+Linux version 6\.6\.36(?:[ \t][^\n]*)?\n",
                           rb"^nixos login:(?:[ \t]|$)", rb"^root@nixos:[^\n]*# ")
        while normal_stage < 4:
            found = re.search(normal_patterns[normal_stage], normal_text, re.M)
            if not found:
                break
            normal_text = normal_text[found.end():]
            normal_tail = normal_text
            normal_stage += 1
        normal_ready = normal_stage == 4
        if not overflow:
            if total > 1048576:
                overflow = True
                errors.append("capture-byte-bound")
            else:
                text += chunk
        if not overflow:
            normalized = _PROTOCOL.uart_text(text)
            if candidate_start is None:
                found = re.search(rb"^\[\s*[0-9]+\.[0-9]+\]\s+Linux version 7\.3\.0-rc5(?:[ \t][^\n]*)?\n", normalized, re.M)
                if found:
                    candidate_start = found.end()
                    banner = True
            if banner:
                phase = normalized[candidate_start:]
                received_args = re.findall(rb"^\[\s*[0-9]+\.[0-9]+\]\s+Kernel command line: ([^\n]*)\n", phase, re.M)
                args_status = ("DUPLICATE" if len(received_args) > 1 else
                               "MATCHED" if received_args == [expected_cmdline.encode()] else
                               "MISMATCH" if received_args else "UNKNOWN")
                if args_status in ("DUPLICATE", "MISMATCH") and "kernel-command-line-" + args_status.lower() not in errors:
                    errors.append("kernel-command-line-" + args_status.lower())
                # Fixed SBI records permit CRLF framing, never embedded-CR repair.
                record_phase = text.replace(b"\r\n", b"\n") if uart_progress_breadcrumbs else phase
                complete = record_phase.split(b"\n")[:-1] if not uart_progress_breadcrumbs or args_status == "MATCHED" else []
                for line in complete[parsed_lines:]:
                    if uart_progress_post_sample and b"K230_UPP" in line:
                        point = uart_progress_post_sample_record(line + b"\n")
                        if point is None:
                            errors.append("malformed-post-sample")
                        elif any(b["point"] == point for b in post_sample):
                            errors.append("duplicate-post-sample")
                        elif point == "after-n1-write" and post_sample:
                            errors.append("post-sample-order")
                        else:
                            post_sample.append({"point": point, "observed_after_stimulus": sent})
                    elif uart_progress_breadcrumbs and b"K230_UPB" in line:
                        point = uart_progress_breadcrumb(line + b"\n")
                        if point is None:
                            errors.append("malformed-breadcrumb")
                        elif any(b["point"] == point for b in breadcrumbs):
                            errors.append("duplicate-breadcrumb")
                        elif point == "worker-entry" and breadcrumbs:
                            errors.append("breadcrumb-order")
                        elif records:
                            errors.append("breadcrumb-after-sample")
                        else:
                            breadcrumbs.append({"point": point, "observed_after_stimulus": sent})
                    elif b"K230_UP" in line:
                        record = uart_progress_record(line + b"\n")
                        if record is None:
                            errors.append("malformed-record")
                        elif any(r["n"] == record["n"] for r in records):
                            errors.append("duplicate-record")
                        elif records and (record["n"] < records[-1]["n"] or record["j"] < records[-1]["j"] or record["t"] < records[-1]["t"]):
                            errors.append("record-order")
                        else:
                            records.append({**record, "observed_after_stimulus": sent})
                parsed_lines = len(complete)
                if init_end is None:
                    found = re.search(rb"^\[\s*[0-9]+\.[0-9]+\]\s+Run /bin/sh as init process\n", phase, re.M)
                    if found:
                        init_end = found.end()
                        entry = True
                if entry and not sent and clock() - started <= readiness_timeout:
                    prompt = re.search(rb"^sh-5\.3# (?=\n|\Z)", phase[init_end:], re.M)
                    if prompt:
                        suffix = phase[init_end:][prompt.end():]
                        # Only newlines and complete qualified direct records may
                        # follow the primary prompt in the same pump batch.
                        trailing = suffix.splitlines(keepends=True)
                        prompt_seen = all(line == b"\n" or uart_progress_record(line) is not None or
                                          (uart_progress_breadcrumbs and uart_progress_breadcrumb(line) is not None) or
                                          (uart_progress_post_sample and uart_progress_post_sample_record(line) is not None)
                                          for line in trailing)
                    ready = prompt_seen and args_status == "MATCHED"
                receipt_count = len(re.findall(rb"^K230_RDINIT_RX " + token.encode() + rb"\n", phase, re.M)) if sent else 0
                if receipt_count > 1 and "duplicate-receipt" not in errors:
                    errors.append("duplicate-receipt")
        if normal_ready:
            break
        if ready and not sent and not errors and not overflow:
            # No line()/Ctrl-U, no retry, no guard/proc/reboot command follows.
            sent = True
            try:
                session.write((reception_command(token) + "\r").encode())
            except Exception:
                errors.append("stimulus-write-unknown")
                break
    if banner and not overflow:
        record_phase = text.replace(b"\r\n", b"\n") if uart_progress_breadcrumbs else _PROTOCOL.uart_text(text)[candidate_start:]
        final = record_phase.split(b"\n")[-1]
        if uart_progress_post_sample and b"K230_UPP" in final:
            errors.append("truncated-post-sample")
        elif uart_progress_breadcrumbs and b"K230_UPB" in final:
            errors.append("truncated-breadcrumb")
        elif b"K230_UP" in final:
            errors.append("truncated-record")
    complete = [r["n"] for r in records] == list(range(6)) and not errors
    result = {"schema": "k230-uart-progress-observation-v1", "candidate_banner": banner,
            "init_entry": entry, "primary_prompt_observed": prompt_seen,
            "kernel_args_verified": args_status == "MATCHED", "kernel_args_status": args_status,
            "readiness_observed": ready, "stimulus_attempts": int(sent),
            "receipt_observed": receipt_count == 1 and "duplicate-receipt" not in errors,
            "receipt_status": "MATCHED" if receipt_count == 1 else "UNKNOWN",
            "records": records, "records_complete": complete, "protocol_errors": errors,
            "samples_observed_after_stimulus": sum(r["observed_after_stimulus"] for r in records),
            "normal_prompt_observed": normal_ready, "capture_timeout_seconds": timeout,
            "capture_seconds": max(0, clock() - started),
            "reboot_requested": False, "pid1_identity": "UNVERIFIED", "usable_root": "UNVERIFIED", "touch": "UNVERIFIED"}
    if uart_progress_breadcrumbs:
        result.update(uart_progress_breadcrumbs=True, breadcrumbs=breadcrumbs,
                      breadcrumbs_complete=[b["point"] for b in breadcrumbs] == ["worker-entry", "first-post-sleep"] and not errors)
    if uart_progress_post_sample:
        result.update(uart_progress_post_sample=True, post_sample=post_sample,
                      post_sample_complete=[b["point"] for b in post_sample] == ["after-n1-write", "third-post-sleep"] and not errors)
    return result


def shell_guard_command(token, phase, comparison, normal, boot_id=None):
    _validate_token(token)
    if phase not in ("initial", "renewed") or (phase == "renewed") != (boot_id is not None):
        raise ValueError("invalid shell guard phase")
    old = normal.get("trial_from_boot_id", normal.get("boot_id"))
    baseline = normal.get("boot_id")
    if not all(isinstance(v, str) and re.fullmatch(BOOT_ID_PATTERN, v) for v in (old, baseline)):
        raise ValueError("invalid protected normal boot identity")
    if boot_id is not None and not re.fullmatch(BOOT_ID_PATTERN, boot_id):
        raise ValueError("invalid candidate boot identity")
    bash = comparison["bash"]
    if not re.fullmatch(r"/nix/store/[0-9a-z]{32}-bash-interactive-riscv64-unknown-linux-gnu-5\.3p15/bin/bash", bash):
        raise ValueError("unsafe Bash identity")
    shell_pid1_transport(comparison["bootargs"], comparison["system"])
    cmdline = comparison["bootargs"].removeprefix("bootargs=")
    payload = (
        "_k230_ok=1; _k230_pid=$$; "
        'test "$_k230_pid" = 1 && test "$PPID" = 0 && test "$EUID" = 0 || _k230_ok=0; '
        'case $BASH_VERSION in 5.3.*) :;; *) _k230_ok=0;; esac; '
        f'_k230_exe=$(/bin/readlink /proc/1/exe 2>/dev/null); test "$?" = 0 && test "$_k230_exe" = {shlex.quote(bash)} || _k230_ok=0; '
        'IFS= read -r _k230_release 2>/dev/null < /proc/sys/kernel/osrelease; test "$?" = 0 && test "$_k230_release" = 7.3.0-rc5 || _k230_ok=0; '
        f'IFS= read -r _k230_cmdline 2>/dev/null < /proc/cmdline; test "$?" = 0 && test "$_k230_cmdline" = {shlex.quote(cmdline)} || _k230_ok=0; '
        'IFS= read -r _k230_boot 2>/dev/null < /proc/sys/kernel/random/boot_id; test "$?" = 0 || _k230_ok=0; '
        'case $_k230_boot in *[!0-9a-f-]*|\'\') _k230_boot=none; _k230_ok=0;; esac; '
        f'test "$_k230_boot" != {old} && test "$_k230_boot" != {baseline} || _k230_ok=0; '
        + (f'test "$_k230_boot" = {boot_id} || _k230_ok=0; ' if boot_id else "") +
        'test -r /etc/initrd-release && test ! -e /sysroot/nix/store || _k230_ok=0; '
        '_k230_root=0; while read -r _src _mnt _fs _rest; do '
        'if test "$_mnt" = /; then case $_fs in rootfs|ramfs|tmpfs) _k230_root=1;; *) _k230_ok=0;; esac; fi; '
        'case $_mnt in /sysroot|/sysroot/*) _k230_ok=0;; esac; :; '
        'done 2>/dev/null < /proc/mounts; test "$?" = 0 && test "$_k230_root" = 1 || _k230_ok=0; '
    )
    command = (f"printf 'K230_SHELL_PID1_BEGIN {token} {phase}\\n'; " + payload +
               f"printf 'K230_SHELL_PID1_END {token} {phase} RC=0 MATCH=%s BOOT=%s\\n' \"$_k230_ok\" \"$_k230_boot\"")
    if len(command.encode()) >= 3072:
        raise ValueError("shell guard exceeds bounded input length")
    return command


def shell_guard_result(output, token, phase):
    _validate_token(token)
    if phase not in ("initial", "renewed"):
        raise ValueError("invalid shell guard phase")
    text = _PROTOCOL.uart_text(output)
    scoped = list(re.finditer(rb"^K230_SHELL_PID1_(?:BEGIN|END) " + token.encode() + rb"[^\n]*\n", text, re.M))
    starts = list(re.finditer(rb"^K230_SHELL_PID1_BEGIN " + token.encode() + b" " + phase.encode() + rb"\n", text, re.M))
    ends = list(re.finditer(rb"^K230_SHELL_PID1_END " + token.encode() + b" " + phase.encode() +
                          rb" RC=([01]) MATCH=([01]) BOOT=(none|" + BOOT_ID_PATTERN.encode() + rb")\n", text, re.M))
    if len(scoped) != 2 or len(starts) != 1 or len(ends) != 1 or starts[0].end() != ends[0].start():
        return None
    if not re.fullmatch(rb"sh-5\.3# ", text[ends[0].end():]):
        return None
    rc, match, boot = ends[0].groups()
    return {"rc": int(rc), "match": match == b"1", "boot_id": boot.decode()}


def immutable_store_path(path: Path, description: str) -> Path:
    """Require a direct, existing, read-only store directory, not an alias."""
    if path.parent != STORE_ROOT or not re.fullmatch(r"[0-9abcdfghijklmnpqrsvwxyz]{32}-[A-Za-z0-9+._?=-]+", path.name):
        raise ValueError(f"{description} must be a direct immutable /nix/store path")
    if path.resolve(strict=True) != path or not path.is_dir() or path.stat().st_mode & 0o222:
        raise ValueError(f"{description} must be an immutable store directory")
    return path


def validate_file_record(info: object, name: str) -> None:
    if not isinstance(info, dict) or type(info.get("bytes")) is not int or info["bytes"] <= 0:
        raise ValueError(f"invalid positive artifact size: {name}")
    if not isinstance(info.get("sha256"), str) or not re.fullmatch(r"[0-9a-fA-F]{64}", info["sha256"]):
        raise ValueError(f"invalid artifact SHA-256: {name}")


def validate_load_ranges(files: dict[str, object]) -> None:
    """Check actual verified payload sizes at the exact U-Boot load addresses."""
    intervals = []
    for name, _, address, _ in LOADS:
        validate_file_record(files[name], name)
        start = int(address, 16)
        end = start + files[name]["bytes"]
        if not 0 <= start < end <= 0x40000000:
            raise ValueError(f"artifact load exceeds the board's 1 GiB RAM: {name}")
        intervals.append((start, end, name))
    intervals.sort()
    for left, right in zip(intervals, intervals[1:]):
        if left[1] > right[0]:
            raise ValueError(f"artifact load overlap: {left[2]} and {right[2]}")


def verified_bootargs(reply: bytes | None, expected: str) -> bool:
    if reply is None:
        return False
    matches = re.findall(rb"^bootargs=([^\n]*)\n", _PROTOCOL.uart_text(reply), re.M)
    return matches == [expected.removeprefix("bootargs=").encode()]


def verified_load(reply: bytes | None, expected: dict[str, object]) -> bool:
    """Use the shared strict parser for complete, non-echoed U-Boot reports."""
    try:
        _PROTOCOL.verify_load(reply, int(expected["bytes"]))
    except (RuntimeError, TypeError, ValueError):
        return False
    return True


def verified_crc(reply: bytes | None, expected: dict[str, object]) -> bool:
    try:
        _PROTOCOL.verify_crc(reply, str(expected["crc32"]).lower())
    except (RuntimeError, TypeError, ValueError):
        return False
    return True


PROBE_STAGE_NAMES = (
    "shell-start", "mkdir-done", "proc-mount-check", "sys-mount-check",
    "dev-mount-check", "proc-read-start", "proc-read-done",
    "sys-block-read-done", "dev-block-read-done", "labels-read-done",
)


def _validate_token(token: str) -> None:
    if not re.fullmatch(r"[0-9a-f]{32}", token):
        raise ValueError("probe token must be a 32-character lowercase UUID")


def reception_command(token: str) -> str:
    _validate_token(token)
    return f"PATH=/bin:/sbin; export PATH; printf 'K230_RDINIT_RX {token}\\n'"


def true_command(token: str) -> str:
    _validate_token(token)
    return f"/bin/true; printf 'K230_RDINIT_TRUE {token} RC=%s\\n' \"$?\""


def uptime_command(token: str) -> str:
    _validate_token(token)
    return (
        f"printf 'K230_RDINIT_UP_BEGIN {token}\\n'; /bin/cat /proc/uptime; "
        f"printf 'K230_RDINIT_UP_END {token} RC=%s\\n' \"$?\""
    )


def proc_mount_command(token: str) -> str:
    _validate_token(token)
    return (
        f"printf 'K230_RDINIT_MOUNT_BEGIN {token}\\n'; "
        "/bin/mkdir -p /proc; _k230_mkdir_rc=$?; _k230_mount_attempted=0; _k230_mount_rc=255; "
        "if test $_k230_mkdir_rc -eq 0; then _k230_mount_attempted=1; "
        "/bin/mount -t proc proc /proc; _k230_mount_rc=$?; fi; "
        f"printf 'K230_RDINIT_MOUNT_END {token} MKDIR_RC=%s MOUNT_ATTEMPTED=%s MOUNT_RC=%s\\n' "
        "\"$_k230_mkdir_rc\" \"$_k230_mount_attempted\" \"$_k230_mount_rc\""
    )


def reboot_command(token: str) -> str:
    _validate_token(token)
    return f"printf 'K230_RDINIT_REBOOT {token}\\n'; /bin/reboot -ff"


def label_setup_command(token: str, stage: str) -> str:
    _validate_token(token)
    commands = {
        "dev-mkdir": "/bin/mkdir -p /dev 2>/dev/null; _k230_rc=$?",
        "dev-mount": (
            "_k230_have_dev=0; while read _src _mnt _fs _rest; do "
            "if test \"$_mnt\" = /dev && test \"$_fs\" = devtmpfs; then _k230_have_dev=1; fi; "
            "done < /proc/mounts; _k230_rc=$?; "
            "if test $_k230_rc -eq 0 && test $_k230_have_dev -eq 0; then "
            "/bin/mount -t devtmpfs devtmpfs /dev 2>/dev/null; _k230_rc=$?; fi"
        ),
        "node": "test -b /dev/mmcblk1p2; _k230_rc=$?",
    }
    if stage not in commands:
        raise ValueError("unknown label setup stage")
    return (
        f"printf 'K230_RDINIT_LABEL_SETUP_BEGIN {token} STAGE={stage}\\n'; "
        f"{commands[stage]}; "
        f"printf 'K230_RDINIT_LABEL_SETUP_END {token} STAGE={stage} RC=%s\\n' \"$_k230_rc\""
    )


def label_command(token: str) -> str:
    _validate_token(token)
    return (
        f"printf 'K230_RDINIT_LABEL_BEGIN {token}\\n'; "
        "_k230_label=$(/bin/e2label /dev/mmcblk1p2 2>/dev/null); _k230_rc=$?; _k230_match=0; "
        "if test $_k230_rc -eq 0 && test \"$_k230_label\" = NIXOS_SD; then _k230_match=1; fi; "
        f"printf 'K230_RDINIT_LABEL_END {token} RC=%s MATCH=%s\\n' \"$_k230_rc\" \"$_k230_match\""
    )


def label_result(output: bytes, token: str, stage: str = "label") -> dict[str, int | bool] | None:
    _validate_token(token)
    if stage not in ("dev-mkdir", "dev-mount", "node", "label"):
        raise ValueError("unknown label stage")
    prefix = b"K230_RDINIT_LABEL" + (b"_SETUP" if stage != "label" else b"")
    suffix = b" STAGE=" + stage.encode() if stage != "label" else b""
    text = _PROTOCOL.uart_text(output)
    starts = list(re.finditer(rb"^" + prefix + b"_BEGIN " + token.encode() + suffix + rb"\n", text, re.M))
    ends = list(re.finditer(
        rb"^" + prefix + b"_END " + token.encode() + suffix +
        rb" RC=([0-9]{1,3})" + (rb" MATCH=([01])" if stage == "label" else b"") + rb"\n",
        text, re.M,
    ))
    if len(starts) != 1 or len(ends) != 1 or starts[0].end() > ends[0].start():
        return None
    rc = int(ends[0].group(1))
    if rc > 255:
        return None
    result = {"rc": rc}
    if stage == "label":
        match = ends[0].group(2) == b"1"
        if rc != 0 and match:
            return None
        result["match"] = match
    return result


def root_stage_command(token: str, stage: str, system: str = SYSTEM) -> str:
    _validate_token(token)
    scan = (
        "_k230_count=0; _k230_valid=0; while read _src _mnt _fs _opts _rest; do "
        "if test \"$_mnt\" = /sysroot; then _k230_count=$((_k230_count+1)); "
        "_ro=0; _noload=0; case \",$_opts,\" in *,ro,*) _ro=1;; esac; "
        "case \",$_opts,\" in *,noload,*|*,norecovery,*) _noload=1;; esac; "
        "if test \"$_src\" = /dev/mmcblk1p2 && test \"$_fs\" = ext4 && "
        "test $_ro -eq 1 && test $_noload -eq 1; then _k230_valid=$((_k230_valid+1)); fi; fi; "
        "done < /proc/mounts; _k230_rc=$?; _k230_mounted=0; "
        "if test $_k230_count -gt 0; then _k230_mounted=1; fi; "
    )
    commands = {
        "unmounted": scan + "if test $_k230_rc -eq 0 && test $_k230_count -ne 0; then _k230_rc=1; fi",
        "flags": scan + "if test $_k230_rc -eq 0; then "
                 "if test $_k230_count -ne 1 || test $_k230_valid -ne 1; then _k230_rc=1; fi; fi",
        "mkdir": "/bin/mkdir -p /sysroot 2>/dev/null; _k230_rc=$?",
        "empty": "_k230_rc=0; test -d /sysroot || _k230_rc=1; "
                 "for _path in /sysroot/* /sysroot/.[!.]* /sysroot/..?*; do "
                 "if test -e \"$_path\" || test -L \"$_path\"; then _k230_rc=1; fi; done",
        "mount": "/bin/mount -t ext4 -o ro,noload /dev/mmcblk1p2 /sysroot 2>/dev/null; _k230_rc=$?",
        "init": f"test -x {shlex.quote('/sysroot' + system + '/init')}; _k230_rc=$?",
        "prepare-root": f"test -x {shlex.quote('/sysroot' + system + '/prepare-root')}; _k230_rc=$?",
        "umount": "/bin/umount /sysroot 2>/dev/null; _k230_rc=$?",
    }
    commands["after-umount"] = commands["unmounted"]
    if stage not in commands:
        raise ValueError("unknown root mount stage")
    mounted = " MOUNTED=%s" if stage in ("unmounted", "after-umount", "flags") else ""
    values = ' "$_k230_rc"' + (' "$_k230_mounted"' if mounted else "")
    return (
        f"printf 'K230_RDINIT_ROOT_BEGIN {token} STAGE={stage}\\n'; "
        f"{commands[stage]}; "
        f"printf 'K230_RDINIT_ROOT_END {token} STAGE={stage} RC=%s{mounted}\\n'{values}"
    )


def _root_mount_marker_text(text: bytes, token: str) -> bytes:
    """Rejoin only the captured EXT4 mount-info insertion inside a fresh nonce.

    This changes a parser view, never the UART log. No other printk, marker
    field or incomplete line is removed; the normal uniqueness/RC gates still
    apply to the resulting complete marker.
    """
    uuid = rb"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"
    insertion = (
        rb"\[ {0,8}[0-9]{1,10}\.[0-9]{6}\] EXT4-fs \(mmcblk1p2\): mounted filesystem "
        + uuid + rb" ro without journal\. Quota mode: disabled\.\n"
    )
    split_end = re.compile(
        rb"^K230_RDINIT_ROOT_END ([0-9a-f]{1,31})" + insertion
        + rb"([0-9a-f]{1,31})( STAGE=mount RC=[0-9]{1,3}\n)", re.M,
    )

    def rejoin(match):
        if match.group(1) + match.group(2) != token.encode():
            return match.group(0)
        return b"K230_RDINIT_ROOT_END " + token.encode() + match.group(3)

    return split_end.sub(rejoin, text)


def root_stage_result(output: bytes, token: str, stage: str) -> dict[str, int | bool] | None:
    _validate_token(token)
    if stage not in ("unmounted", "after-umount", "flags", "mkdir", "empty", "mount", "init", "prepare-root", "umount"):
        raise ValueError("unknown root mount stage")
    text = _PROTOCOL.uart_text(output)
    if stage == "mount":
        text = _root_mount_marker_text(text, token)
    scope = token.encode() + b" STAGE=" + stage.encode()
    starts = list(re.finditer(rb"^K230_RDINIT_ROOT_BEGIN " + scope + rb"\n", text, re.M))
    has_mounted = stage in ("unmounted", "after-umount", "flags")
    ends = list(re.finditer(
        rb"^K230_RDINIT_ROOT_END " + scope + rb" RC=([0-9]{1,3})" +
        (rb" MOUNTED=([01])" if has_mounted else b"") + rb"\n", text, re.M,
    ))
    if len(starts) != 1 or len(ends) != 1 or starts[0].end() > ends[0].start():
        return None
    rc = int(ends[0].group(1))
    if rc > 255:
        return None
    result = {"rc": rc}
    if has_mounted:
        result["mounted"] = ends[0].group(2) == b"1"
        if rc == 0 and result["mounted"] != (stage == "flags"):
            return None
    return result


def run_root_mount_protocol(session, token: str, system: str, timeout: float, clock):
    def stage(name):
        session.write((root_stage_command(token, name, system) + "\r").encode())
        bound = 60.0 if name in ("mount", "init", "prepare-root", "umount") else timeout
        result = await_protocol_marker(
            session, lambda output, fresh: root_stage_result(output, fresh, name), token, bound, clock,
        )
        if result is None:
            raise ProbeProtocolError(f"root-mount {name}")
        return {"attempted": True, **result}

    outcome = {
        "mount": {"attempted": False}, "init": {"attempted": False},
        "prepare-root": {"attempted": False}, "umount": {"attempted": False},
    }
    for name in ("unmounted", "mkdir", "empty"):
        outcome[name] = stage(name)
        if outcome[name]["rc"] != 0:
            return outcome, False
    outcome["mount"] = stage("mount")
    outcome["flags"] = stage("flags")
    ok = outcome["mount"]["rc"] == 0 and outcome["flags"]["rc"] == 0
    if ok:
        for name in ("init", "prepare-root"):
            outcome[name] = stage(name)
            if outcome[name]["rc"] != 0:
                ok = False
                break
    if outcome["mount"]["rc"] == 0 or outcome["flags"]["mounted"]:
        outcome["umount"] = stage("umount")
        ok = ok and outcome["umount"]["rc"] == 0
        if outcome["umount"]["rc"] == 0:
            outcome["after-umount"] = stage("after-umount")
            ok = ok and outcome["after-umount"]["rc"] == 0
    return outcome, ok


def survey_command(token: str) -> str:
    _validate_token(token)
    data = PROBE_DATA.replace("K230_STAGE_TOKEN", token)
    return (
        "PATH=/bin:/sbin; export PATH; "
        f"{data}; "
        f"printf 'K230_RDINIT_SURVEY {token} RC=%s\\n' \"$_k230_probe_rc\""
    )


def probe_stage_markers(output: bytes, token: str) -> tuple[str, ...]:
    """Return only unique complete stage lines for this fresh probe token."""
    if not re.fullmatch(r"[0-9a-f]{32}", token):
        raise ValueError("probe token must be a 32-character lowercase UUID")
    text = _PROTOCOL.uart_text(output)
    matches = re.findall(
        rb"^K230_RDINIT_STAGE " + re.escape(token.encode()) + rb" ([a-z-]+)\n",
        text,
        re.M,
    )
    allowed = set(PROBE_STAGE_NAMES)
    if any(match.decode() not in allowed for match in matches):
        return ()
    if len(matches) != len(set(matches)):
        return ()
    return tuple(name for name in PROBE_STAGE_NAMES if name.encode() in matches)


class ProbeProtocolError(RuntimeError):
    def __init__(self, stage: str, diagnostic: dict[str, object] | None = None):
        super().__init__(f"initrd minimal protocol did not complete at {stage}; do not send more probe input")
        self.stage = stage
        self.diagnostic = diagnostic


def receive_marker(output: bytes, token: str) -> bool | None:
    _validate_token(token)
    text = _PROTOCOL.uart_text(output)
    matches = re.findall(rb"^K230_RDINIT_RX " + re.escape(token.encode()) + rb"\n", text, re.M)
    return True if len(matches) == 1 else None


def protocol_rc_marker(output: bytes, token: str, stage: str) -> int | None:
    _validate_token(token)
    tags = {"true": "K230_RDINIT_TRUE", "uptime": "K230_RDINIT_UP_END", "survey": "K230_RDINIT_SURVEY"}
    if stage not in tags:
        raise ValueError("unknown protocol RC stage")
    text = _PROTOCOL.uart_text(output)
    matches = re.findall(
        rb"^" + tags[stage].encode() + rb" " + re.escape(token.encode()) + rb" RC=([0-9]{1,3})\n",
        text,
        re.M,
    )
    if len(matches) != 1:
        return None
    value = int(matches[0])
    return value if value <= 255 else None


def uptime_result(output: bytes, token: str) -> dict[str, object] | None:
    _validate_token(token)
    text = _PROTOCOL.uart_text(output)
    starts = list(re.finditer(rb"^K230_RDINIT_UP_BEGIN " + re.escape(token.encode()) + rb"\n", text, re.M))
    ends = list(re.finditer(rb"^K230_RDINIT_UP_END " + re.escape(token.encode()) + rb" RC=([0-9]{1,3})\n", text, re.M))
    if len(starts) != 1 or len(ends) != 1 or starts[0].end() > ends[0].start():
        return None
    values = re.findall(rb"^([0-9]+\.[0-9]+) ([0-9]+\.[0-9]+)$", text[starts[0].end():ends[0].start()], re.M)
    rc = int(ends[0].group(1))
    if rc > 255:
        return None
    if rc == 0 and len(values) != 1:
        return None
    if len(values) > 1:
        return None
    uptime = None
    if values:
        uptime = [values[0][0].decode(), values[0][1].decode()]
    return {"rc": rc, "uptime": uptime}


def proc_mount_result(output: bytes, token: str) -> dict[str, int | bool] | None:
    _validate_token(token)
    text = _PROTOCOL.uart_text(output)
    starts = list(re.finditer(rb"^K230_RDINIT_MOUNT_BEGIN " + re.escape(token.encode()) + rb"\n", text, re.M))
    ends = list(re.finditer(
        rb"^K230_RDINIT_MOUNT_END " + re.escape(token.encode()) +
        rb" MKDIR_RC=([0-9]{1,3}) MOUNT_ATTEMPTED=([01]) MOUNT_RC=([0-9]{1,3})\n",
        text,
        re.M,
    ))
    if len(starts) != 1 or len(ends) != 1 or starts[0].end() > ends[0].start():
        return None
    mkdir_rc, attempted, mount_rc = (int(value) for value in ends[0].groups())
    if mkdir_rc > 255 or mount_rc > 255:
        return None
    if (mkdir_rc == 0) != (attempted == 1):
        return None
    if not attempted and mount_rc != 255:
        return None
    return {"mkdir_rc": mkdir_rc, "mount_attempted": bool(attempted), "mount_rc": mount_rc}


def survey_rc_marker(output: bytes, token: str) -> int | None:
    return protocol_rc_marker(output, token, "survey")


def reboot_marker(output: bytes, token: str) -> bool | None:
    _validate_token(token)
    text = _PROTOCOL.uart_text(output)
    matches = re.findall(rb"^K230_RDINIT_REBOOT " + re.escape(token.encode()) + rb"\n", text, re.M)
    return True if len(matches) == 1 else None


def reboot_chroot_refusal(output: bytes) -> bool:
    text = _PROTOCOL.uart_text(output)
    return len(re.findall(rb"^Running in chroot, ignoring request\.\n", text, re.M)) == 1


def await_protocol_marker(session, parser, token: str, timeout: float, clock=time.monotonic):
    deadline = clock() + timeout
    while clock() < deadline:
        session.pump()
        result = parser(session.buffer, token)
        if result is not None:
            return result
    return None


def await_reception(
    session,
    first_token: str,
    *,
    attempts: int = RECEPTION_MAX_ATTEMPTS,
    timeout: float = RECEPTION_ATTEMPT_TIMEOUT,
    token_factory=None,
    clock=time.monotonic,
):
    """Retry only the safe builtin receipt line until the console accepts one fresh token."""
    _validate_token(first_token)
    if not 1 <= attempts <= RECEPTION_MAX_ATTEMPTS:
        raise ValueError(f"reception attempts must be between 1 and {RECEPTION_MAX_ATTEMPTS}")
    if not 0 < timeout <= RECEPTION_ATTEMPT_TIMEOUT:
        raise ValueError(f"reception timeout must be positive and at most {RECEPTION_ATTEMPT_TIMEOUT}s")
    make_token = token_factory or (lambda: uuid.uuid4().hex)
    seen = {first_token}
    for attempt in range(attempts):
        token = first_token if attempt == 0 else make_token()
        _validate_token(token)
        if attempt and token in seen:
            raise ValueError("reception retry tokens must be fresh")
        seen.add(token)
        # Drain pending console bytes before each retry. Parser matching is scoped
        # to this fresh token, so an echo or delayed response from an older line
        # cannot make the current attempt ready.
        session.pump()
        session.write((reception_command(token) + "\r").encode())
        if await_protocol_marker(session, receive_marker, token, timeout, clock) is True:
            return token, attempt + 1
    return None


def await_initrd_ready(session, *, timeout=INITRD_READY_TIMEOUT, clock=time.monotonic) -> bool:
    """Read only: require candidate init entry, then its initial shell prompt."""
    if not 0 < timeout <= INITRD_READY_TIMEOUT:
        raise ValueError("initrd readiness timeout must be positive and at most 90s")
    banner = rb"^\[\s*[0-9]+\.[0-9]+\]\s+Linux version 7\.3\.0-rc5(?:[ \t][^\n]*)?\n"
    ready = rb"^\[\s*[0-9]+\.[0-9]+\]\s+Run /bin/sh as init process\n"
    prompt = rb"^sh-[0-9]+\.[0-9]+# \Z"
    candidate_seen = False
    init_seen = False
    deadline = clock() + timeout
    while True:
        output = _PROTOCOL.uart_text(session.buffer)
        if not candidate_seen:
            match = re.search(banner, output, re.M)
            if match:
                # Exclude stale normal/pretrial text; preserve candidate bytes
                # already read alongside its banner. The raw log is untouched.
                session.buffer = output[match.start():]
                output = session.buffer
                candidate_seen = True
        if candidate_seen and not init_seen:
            match = re.search(ready, output, re.M)
            if match:
                # Linux prints the entry checkpoint before kernel_execve.
                # A pre-entry prompt or a continuation prompt is not readiness.
                session.buffer = output[match.end():]
                output = session.buffer
                init_seen = True
        if init_seen and re.search(prompt, output, re.M):
            return True
        if clock() >= deadline:
            return False
        session.pump()


def runtime_trace_command(token: str, stage: str) -> str:
    _validate_token(token)
    if stage not in RUNTIME_TRACE_STAGES:
        raise ValueError("unknown runtime shutdown trace stage")
    parameter = RUNTIME_TRACE_PARAMETER
    match_rc = "if test $_k230_rc -eq 0; then _k230_match=1; fi; "
    scan = (
        "while read _src _mnt _fs _rest; do "
        "if test \"$_mnt\" = /sys; then _k230_total=$((_k230_total + 1)); "
        "if test \"$_fs\" = sysfs; then _k230_sysfs=$((_k230_sysfs + 1)); fi; fi; "
        "done 2>/dev/null < /proc/mounts; _k230_rc=$?; "
    )
    if stage == "sys-mkdir":
        body = "/bin/mkdir -p /sys 2>/dev/null; _k230_rc=$?; " + match_rc
    elif stage == "sys-mount":
        body = "_k230_total=0; _k230_sysfs=0; " + scan + (
            "if test $_k230_rc -eq 0 && test $_k230_total -eq 0; then "
            "/bin/mount -t sysfs -o nosuid,nodev,noexec sysfs /sys 2>/dev/null; _k230_rc=$?; fi; "
            "if test $_k230_rc -eq 0; then _k230_total=0; _k230_sysfs=0; "
        ) + scan + (
            "fi; if test $_k230_rc -eq 0 && test $_k230_total -eq 1 "
            "&& test $_k230_sysfs -eq 1; then _k230_match=1; fi; "
        )
    elif stage == "permissions":
        body = f"test -f {parameter} && test -r {parameter} && test -w {parameter}; _k230_rc=$?; " + match_rc
    elif stage in ("prior", "readback"):
        expected = "N" if stage == "prior" else "Y"
        body = (
            "_k230_value=''; _k230_extra=''; { IFS= read -r _k230_value; _k230_rc=$?; "
            "if IFS= read -r _k230_extra || test -n \"$_k230_extra\"; then _k230_rc=1; fi; "
            f"}} 2>/dev/null < {parameter}; _k230_group_rc=$?; "
            "if test $_k230_group_rc -ne 0; then _k230_rc=$_k230_group_rc; fi; "
            f"if test $_k230_rc -eq 0 && test \"$_k230_value\" = {expected}; then _k230_match=1; fi; "
        )
    else:
        body = f"{{ printf '1\\n' > {parameter}; }} 2>/dev/null; _k230_rc=$?; " + match_rc
    return (
        f"printf 'K230_RDINIT_TRACE_BEGIN {token} STAGE={stage}\\n'; "
        "_k230_rc=255; _k230_match=0; " + body +
        f"printf 'K230_RDINIT_TRACE_END {token} STAGE={stage} RC=%s MATCH=%s\\n' "
        "\"$_k230_rc\" \"$_k230_match\""
    )


def runtime_trace_result(output: bytes, token: str, stage: str) -> dict[str, object] | None:
    _validate_token(token)
    if stage not in RUNTIME_TRACE_STAGES:
        raise ValueError("unknown runtime shutdown trace stage")
    text = _PROTOCOL.uart_text(output)
    prefix = rb"K230_RDINIT_TRACE_"
    suffix = re.escape(f" {token} STAGE={stage}".encode())
    starts = list(re.finditer(rb"^" + prefix + rb"BEGIN" + suffix + rb"[^\n]*\n", text, re.M))
    ends = list(re.finditer(rb"^" + prefix + rb"END" + suffix + rb"[^\n]*\n", text, re.M))
    if len(starts) != 1 or len(ends) != 1 or starts[0].end() > ends[0].start():
        return None
    if starts[0].group() != b"K230_RDINIT_TRACE_BEGIN" + f" {token} STAGE={stage}\n".encode():
        return None
    result = re.fullmatch(prefix + rb"END" + suffix + rb" RC=([0-9]{1,3}) MATCH=([01])\n", ends[0].group())
    if result is None:
        return None
    rc, match = map(int, result.groups())
    if rc > 255 or (rc != 0 and match):
        return None
    return {"rc": rc, "match": bool(match)}


def run_runtime_shutdown_trace(session, token, *, timeout=RUNTIME_TRACE_TIMEOUT, clock=time.monotonic,
                               token_factory=None):
    if not 0 < timeout <= RUNTIME_TRACE_TIMEOUT:
        raise ValueError("runtime trace timeout must be positive, finite and at most 20s")
    trace = {"schema": "k230-runtime-shutdown-trace-v1", "attempted": True,
             "stages": {}, "enable_verified": False, "parameter_state": "UNVERIFIED"}
    make_token = token_factory or (lambda: uuid.uuid4().hex)
    seen = {token}
    for stage in RUNTIME_TRACE_STAGES:
        fresh = make_token()
        _validate_token(fresh)
        if fresh in seen:
            raise ValueError("runtime trace stage tokens must be fresh")
        seen.add(fresh)
        if stage == "write":
            trace["parameter_state"] = "UNVERIFIED"
        session.write((runtime_trace_command(fresh, stage) + "\r").encode())
        result = await_protocol_marker(
            session, lambda output, nonce: runtime_trace_result(output, nonce, stage),
            fresh, min(timeout, RUNTIME_TRACE_TIMEOUT), clock,
        )
        if result is None:
            trace.update(status="unknown", failed_stage=stage)
            raise ProbeProtocolError(f"runtime shutdown trace {stage}", trace)
        trace["stages"][stage] = result
        if result["rc"] != 0 or not result["match"]:
            trace.update(status="failed", failed_stage=stage)
            return trace, False
        if stage == "prior":
            trace["parameter_state"] = "N"
    trace.update(status="complete", enable_verified=True, parameter_state="Y")
    return trace, True


def run_probe_protocol(
    session,
    token: str,
    mode: str,
    *,
    timeout: float = 30.0,
    readiness_attempts: int = RECEPTION_MAX_ATTEMPTS,
    readiness_timeout: float = RECEPTION_ATTEMPT_TIMEOUT,
    token_factory=None,
    clock=time.monotonic,
    system: str = SYSTEM,
    runtime_shutdown_trace: bool = False,
    shell_comparison: dict | None = None,
    normal: dict | None = None,
):
    """Run sequential tests; label and survey require every minimal RC to be zero."""
    if mode not in ("minimal", "survey", "label", "root-mount"):
        raise ValueError("probe mode must be minimal, survey, label or root-mount")
    if runtime_shutdown_trace and mode != "minimal":
        raise ValueError("runtime shutdown trace requires minimal mode")
    if shell_comparison is not None:
        validate_shell_selector(True, mode, runtime_shutdown_trace=runtime_shutdown_trace)
        shell_guard_command("a" * 32, "initial", shell_comparison, normal)
    prerequisite_schema = (
        f"k230-initrd-{mode}-prerequisite-failure-v1" if mode in ("label", "root-mount")
        else "k230-initrd-prerequisite-failure-v1"
    )
    received = await_reception(
        session,
        token,
        attempts=readiness_attempts,
        timeout=readiness_timeout,
        token_factory=token_factory,
        clock=clock,
    )
    if received is None:
        raise ProbeProtocolError("reception")
    token, reception_attempts_used = received

    session.write((true_command(token) + "\r").encode())
    true_rc = await_protocol_marker(
        session, lambda output, fresh: protocol_rc_marker(output, fresh, "true"), token, timeout, clock
    )
    if true_rc is None:
        raise ProbeProtocolError("/bin/true")

    minimal = {
        "reception_marker": True,
        "reception_attempts": reception_attempts_used,
        "true_rc": true_rc,
    }
    if runtime_shutdown_trace:
        minimal["runtime_shutdown_trace"] = {"attempted": False, "stages": {}, "enable_verified": False,
                                             "parameter_state": "UNVERIFIED"}
    if true_rc != 0:
        diagnostic = {
            "schema": prerequisite_schema,
            "requested_mode": mode,
            **minimal,
            "proc_mount": {"attempted": False},
        }
        return {
            "diagnostic": diagnostic,
            "diagnostic_ok": False,
            "reboot_marker": False,
            "recovery_required": True,
            "recovery_reason": "true-command-nonzero",
        }

    session.write((proc_mount_command(token) + "\r").encode())
    mount_rc = await_protocol_marker(session, proc_mount_result, token, timeout, clock)
    if mount_rc is None:
        raise ProbeProtocolError("/bin/mkdir -p /proc and /bin/mount -t proc proc /proc")
    minimal["proc_mount"] = mount_rc
    if mount_rc["mkdir_rc"] != 0 or not mount_rc["mount_attempted"] or mount_rc["mount_rc"] != 0:
        diagnostic = {
            "schema": prerequisite_schema,
            "requested_mode": mode,
            **minimal,
            "uptime": {"attempted": False},
        }
        recovery_reason = (
            "proc-directory-setup-nonzero"
            if mount_rc["mkdir_rc"] != 0 or not mount_rc["mount_attempted"]
            else "proc-mount-nonzero"
        )
        return {
            "diagnostic": diagnostic,
            "diagnostic_ok": False,
            "reboot_marker": False,
            "recovery_required": True,
            "recovery_reason": recovery_reason,
        }

    session.write((uptime_command(token) + "\r").encode())
    uptime = await_protocol_marker(session, uptime_result, token, timeout, clock)
    if uptime is None:
        raise ProbeProtocolError("/bin/cat /proc/uptime")
    minimal["uptime_rc"] = uptime["rc"]
    minimal["uptime"] = uptime["uptime"]
    if uptime["rc"] != 0:
        diagnostic = {
            "schema": prerequisite_schema,
            "requested_mode": mode,
            **minimal,
        }
        return {
            "diagnostic": diagnostic,
            "diagnostic_ok": False,
            "reboot_marker": False,
            "recovery_required": True,
            "recovery_reason": "proc-uptime-nonzero",
        }
    minimal_ok = True
    shell_boot = None
    guard_tokens = {token}
    if shell_comparison is not None:
        minimal["shell_pid1"] = {}

        def guard(phase):
            fresh = token_factory() if token_factory else uuid.uuid4().hex
            if not isinstance(fresh, str) or not re.fullmatch(r"[0-9a-f]{32}", fresh) or fresh in guard_tokens:
                raise ProbeProtocolError("shell PID1 guard nonce")
            guard_tokens.add(fresh)
            session.buffer = b""  # Raw capture is unchanged; exclude the preceding prompt.
            session.write((shell_guard_command(fresh, phase, shell_comparison, normal, shell_boot) + "\r").encode())
            result = await_protocol_marker(
                session, lambda output, nonce: shell_guard_result(output, nonce, phase), fresh, timeout, clock
            )
            if result is None:
                raise ProbeProtocolError("shell PID1 " + phase + " guard", {
                    "schema": "k230-initrd-shell-pid1-unknown-v1", **minimal, "failed_stage": phase,
                })
            minimal["shell_pid1"][phase] = result
            return (result["rc"] == 0 and result["match"] and re.fullmatch(BOOT_ID_PATTERN, result["boot_id"])
                    and result["boot_id"] not in (normal["boot_id"], normal.get("trial_from_boot_id"))
                    and (phase == "initial" or result["boot_id"] == shell_boot))

        if not guard("initial"):
            return {"diagnostic": {"schema": "k230-initrd-shell-pid1-v1", **minimal},
                    "diagnostic_ok": False, "reboot_marker": False, "recovery_required": True,
                    "recovery_reason": "shell-pid1-initial-guard-failed"}
        shell_boot = minimal["shell_pid1"]["initial"]["boot_id"]
    if runtime_shutdown_trace:
        try:
            trace, trace_ok = run_runtime_shutdown_trace(
                session, token, timeout=min(timeout, RUNTIME_TRACE_TIMEOUT), clock=clock,
                token_factory=token_factory,
            )
        except ProbeProtocolError as exc:
            exc.diagnostic = {"schema": "k230-initrd-minimal-unknown-v1", **minimal,
                              "runtime_shutdown_trace": exc.diagnostic, "stage": exc.stage}
            raise
        minimal["runtime_shutdown_trace"] = trace
        if not trace_ok:
            return {"diagnostic": {"schema": "k230-initrd-minimal-v2", **minimal},
                    "diagnostic_ok": False, "reboot_marker": False, "recovery_required": True,
                    "recovery_reason": f"runtime-shutdown-trace-{trace['failed_stage']}-failed"}
    label = None
    label_setup = {}
    if mode in ("label", "root-mount"):
        for stage in ("dev-mkdir", "dev-mount", "node"):
            session.write((label_setup_command(token, stage) + "\r").encode())
            outcome = await_protocol_marker(
                session, lambda output, fresh: label_result(output, fresh, stage), token, timeout, clock,
            )
            if outcome is None:
                raise ProbeProtocolError(f"label {stage}")
            label_setup[stage] = outcome
            if outcome["rc"] != 0:
                return {
                    "diagnostic": {
                        "schema": f"k230-initrd-{mode}-v1", "minimal": minimal,
                        "setup": label_setup, "label": {"attempted": False},
                        **({"root": {"attempted": False}} if mode == "root-mount" else {}),
                    },
                    "diagnostic_ok": False, "reboot_marker": False,
                    "recovery_required": True, "recovery_reason": f"label-{stage}-nonzero",
                }
        session.write((label_command(token) + "\r").encode())
        label = await_protocol_marker(session, label_result, token, 60.0, clock)
        if label is None:
            raise ProbeProtocolError("label read")
    root = {"attempted": False}
    root_ok = False
    if mode == "root-mount" and label["rc"] == 0 and label["match"]:
        root, root_ok = run_root_mount_protocol(session, token, system, timeout, clock)
        root = {"attempted": True, **root}
    survey = None
    if mode == "survey" and minimal_ok:
        session.write((survey_command(token) + "\r").encode())
        survey_rc = await_protocol_marker(session, survey_rc_marker, token, max(timeout, 60.0), clock)
        if survey_rc is None:
            raise ProbeProtocolError("optional survey")
        survey = {"status": "complete", "rc": survey_rc, "nixos_sd_label_present": probe_nixos_label(session.buffer)}
    elif mode == "survey":
        survey = {"status": "skipped", "reason": "minimal-stage-rc-failure"}

    if shell_comparison is not None and not guard("renewed"):
        return {"diagnostic": {"schema": "k230-initrd-shell-pid1-v1", **minimal},
                "diagnostic_ok": False, "reboot_marker": False, "recovery_required": True,
                "recovery_reason": "shell-pid1-renewed-guard-failed"}
    # Start a fresh rolling buffer before the reboot request. A fixed offset
    # into the capped buffer stops seeing new bytes once verbose output fills
    # it; clearing also excludes pretrial login/refusal markers.
    session.buffer = b""
    session.write((reboot_command(token) + "\r").encode())
    reboot_seen = await_protocol_marker(session, reboot_marker, token, min(timeout, 5.0), clock)
    if mode == "root-mount":
        diagnostic = {
            "schema": "k230-initrd-root-mount-v1", "minimal": minimal,
            "setup": label_setup, "label": {"attempted": True, **label}, "root": root,
        }
        diagnostic_ok = root_ok
    elif mode == "label":
        diagnostic = {
            "schema": "k230-initrd-label-v1", "minimal": minimal,
            "setup": label_setup, "label": {"attempted": True, **label},
        }
        diagnostic_ok = label["rc"] == 0 and label["match"]
    elif mode == "minimal":
        diagnostic = {"schema": "k230-initrd-shell-pid1-v1" if shell_comparison is not None else "k230-initrd-minimal-v2", **minimal}
        diagnostic_ok = minimal_ok
    else:
        diagnostic = {"schema": "k230-initrd-survey-v2", "minimal": minimal, "survey": survey}
        diagnostic_ok = minimal_ok and (survey is None or survey.get("rc") == 0)
    return {
        "diagnostic": diagnostic,
        "diagnostic_ok": diagnostic_ok,
        "reboot_marker": reboot_seen is True,
    }


def probe_result(output: bytes, token: str) -> int | None:
    """Return only a full output line, after stripping the known UART prefix."""
    if not re.fullmatch(r"[0-9a-f]{32}", token):
        raise ValueError("probe token must be a 32-character lowercase UUID")
    text = _PROTOCOL.uart_text(output)
    matches = re.findall(
        rb"^K230_RDINIT_PROBE " + re.escape(token.encode()) + rb" RC=([0-9]{1,3})\n",
        text,
        re.M,
    )
    if len(matches) != 1:
        return None
    return int(matches[0])


def probe_nixos_label(output: bytes) -> bool | None:
    text = _PROTOCOL.uart_text(output)
    matches = re.findall(rb"^K230_LABEL_NIXOS_SD=([01])\n", text, re.M)
    if len(matches) != 1:
        return None
    return matches[0] == b"1"


def normal_expectation(
    report_path: Path, manifest: dict[str, object], bundle: Path = BUNDLE, system: str = SYSTEM,
) -> dict[str, object]:
    report = json.loads(report_path.read_text())
    baseline = json.loads(NORMAL_BASELINE.read_text())
    if report.get("system") != "/nix/store/p1a1hz9n8s4g8qyr55ffl3dzbnjgqwr8-nixos-system-nixos-26.11.20260919.20b1ddd":
        raise ValueError("protected normal system differs from the current installed baseline")
    if report.get("profile") != report["system"]:
        raise ValueError("protected normal profile does not select the current system")
    if report.get("services") != ["active"] * 3:
        raise ValueError("protected normal report does not show all shell services active")
    if set(report.get("boot_files", {})) != {
        "Image", "initrd.uimg", "k230-tdisplay.dtb", "bootargs.txt",
        "fw_jump_add_uboot_head.bin", "force_dtb", "lcd_dtb", "hdmi_dtb",
    }:
        raise ValueError("protected normal boot-file set is incomplete")
    if report.get("kernel") != baseline["kernel"] or report["boot_files"] != baseline["boot_files"]:
        raise ValueError("protected normal kernel or boot-file identities differ from the committed baseline")
    if not isinstance(report.get("boot_id"), str) or not re.fullmatch(
        r"[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}", report["boot_id"],
    ):
        raise ValueError("protected normal report lacks a valid boot ID")
    wrapper = manifest["files"]["fw_jump_add_uboot_head.bin"]
    protected_wrapper = report["boot_files"]["fw_jump_add_uboot_head.bin"]
    if wrapper["bytes"] != protected_wrapper["bytes"] or wrapper["sha256"].lower() != protected_wrapper["sha256"]:
        raise ValueError("manifest stage-one wrapper differs from the protected normal wrapper")
    if wrapper["crc32"].lower() != NORMAL_WRAPPER_CRC32:
        raise ValueError("manifest stage-one wrapper CRC differs from the protected normal wrapper")
    uname = "6.6.36"  # Fresh serial report and nix/kernel.nix modDirVersion.
    files = manifest["files"]
    candidate_files = {
        name: {"bytes": int(files[name]["bytes"]), "sha256": str(files[name]["sha256"]).lower()}
        for name in ("Image-mainline-drm", "k230-tdisplay-mainline-drm.dtb", "initrd.uimg", "bootargs.txt")
    }
    metadata = {}
    for name in ("registration", "store-paths", "SHA256SUMS"):
        path = bundle / name
        if not path.is_file() or path.is_symlink() or path.stat().st_size <= 0 or path.stat().st_mode & 0o222:
            raise FileNotFoundError(f"exact trial bundle metadata is missing or unsafe: {name}")
        metadata[name] = hashlib.sha256(path.read_bytes()).hexdigest()
    return {
        "system": report["system"], "profile": report["profile"], "kernel": report["kernel"],
        "uname": uname, "boot_id": report["boot_id"], "boot_files": report["boot_files"],
        "init": "init=" + report["system"] + "/init",
        "stage": NORMAL_STAGE, "candidate_system": system,
        "candidate_files": candidate_files, "metadata_sha256": metadata,
    }


def prepare_trial(manifest_path: Path, bundle: Path, report_path: Path) -> dict[str, object]:
    """Fail closed on selected host identities before any board/serial access."""
    bundle = immutable_store_path(bundle, "candidate bundle")
    if not (bundle / "system").is_symlink():
        raise ValueError("candidate bundle must contain its system symlink")
    system_path = immutable_store_path((bundle / "system").resolve(strict=True), "candidate system")
    system = str(system_path)
    if not (system_path / "init").is_file() or not os.access(system_path / "init", os.X_OK):
        raise FileNotFoundError("candidate system init is missing")
    manifest = json.loads(manifest_path.read_text())
    if manifest.get("system") != system:
        raise ValueError("manifest does not name the expected matching trial system")
    files = manifest.get("files", {})
    if not isinstance(files, dict) or set(files) != {name for name, _, _, _ in LOADS}:
        raise ValueError("manifest file set does not match the exact trial bundle")
    validate_load_ranges(files)
    for name, _, _, _ in LOADS:
        expected = files[name]
        if not isinstance(expected.get("crc32"), str) or not re.fullmatch(r"[0-9a-fA-F]{8}", expected["crc32"]):
            raise ValueError(f"invalid artifact CRC32: {name}")
        if name == "fw_jump_add_uboot_head.bin":
            continue  # Protected normal partition; anchored below, verified on board before boot.
        artifact = bundle / name
        if (artifact.is_symlink() or not artifact.is_file()
                or artifact.stat().st_mode & 0o222 or artifact.stat().st_size != expected["bytes"]):
            raise FileNotFoundError(f"exact trial bundle artifact is missing or has wrong size: {name}")
        content = artifact.read_bytes()
        if hashlib.sha256(content).hexdigest() != expected["sha256"].lower():
            raise ValueError(f"exact trial bundle artifact hash mismatch: {name}")
        if f"{zlib.crc32(content):08x}" != expected["crc32"].lower():
            raise ValueError(f"exact trial bundle artifact CRC mismatch: {name}")
    original_args = (bundle / "bootargs.txt").read_text()
    if not original_args.startswith("bootargs="):
        raise ValueError("bundle bootargs must be a U-Boot bootargs assignment")
    expected_args = trial_bootargs(original_args, system)
    normal = normal_expectation(report_path, manifest, bundle, system)
    return {
        "bundle": bundle, "system": system, "manifest": manifest,
        "bootargs": expected_args, "normal": normal, "helper_text": NORMAL_HELPER.read_text(),
    }


def state_marker(output: bytes, token: str, mode: str) -> dict[str, object] | None:
    text = _PROTOCOL.uart_text(output)
    matches = re.findall(
        rb"^K230_MAINLINE_STATE " + re.escape(token.encode()) + rb" " + mode.encode() + rb" (\{[^\n]+\})\n",
        text,
        re.M,
    )
    if len(matches) != 1:
        return None
    try:
        value = json.loads(matches[0])
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None
    return value if isinstance(value, dict) else None


def upload_marker(output: bytes, token: str) -> bool:
    text = _PROTOCOL.uart_text(output)
    lines = re.findall(
        rb"^K230_UPLOAD_" + re.escape(token.encode()) + rb"\n", text, re.M
    )
    return len(lines) == 1


class PrivateSession:
    def __init__(self, serial, log_file):
        self.port = serial.Serial(SERIAL_DEVICE, 115200, timeout=0.1, exclusive=True)
        self.log = log_file
        self.buffer = b""

    def write(self, data: bytes) -> None:
        self.port.write(data)
        self.port.flush()

    def line(self, command: str, *, interrupt: bool = True) -> None:
        if interrupt:
            self.write(b"\x15")
            time.sleep(0.05)
        self.log.write((f"\n--- command: {command} ---\n").encode())
        self.buffer = b""
        self.write(command.encode() + b"\r")

    def upload_text(self, destination: str, content: str, token: str) -> None:
        if not re.fullmatch(r"/run/k230-mainline-[a-z-]+\.(?:py|json)", destination):
            raise ValueError("unexpected in-memory helper destination")
        self.buffer = b""
        self.write(f"cat > {destination} <<'K230_EOF'\r".encode())
        time.sleep(0.1)
        for line in content.splitlines():
            if len(line.encode()) > 2000:
                raise ValueError("helper transfer line exceeds serial shell limit")
            self.write(line.encode() + b"\r")
            time.sleep(0.002)
        self.write(b"K230_EOF\r")
        self.write(f"printf 'K230_UPLOAD_{token}\\n'\r".encode())
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            self.pump()
            if upload_marker(self.buffer, token):
                return
        raise RuntimeError("in-memory diagnostic helper transfer did not complete")

    def run_state(self, mode: str, token: str) -> dict[str, object]:
        if mode not in ("preflight", "postflight"):
            raise ValueError("unknown state mode")
        self.line(f"{BOARD_PYTHON} -I /run/k230-mainline-normal-state.py {mode} {token}", interrupt=False)
        deadline = time.monotonic() + (180 if mode == "preflight" else 90)
        while time.monotonic() < deadline:
            self.pump()
            state = state_marker(self.buffer, token, mode)
            if state is not None:
                return state
        raise RuntimeError(f"protected normal {mode} did not return a complete identity marker")

    def pump(self) -> bytes:
        chunk = self.port.read(65536)
        if chunk:
            self.log.write(chunk)
            self.buffer = (self.buffer + chunk)[-131072:]
        return chunk

    def wait_for(self, token: bytes, timeout: float) -> bool:
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            self.pump()
            if token in self.buffer:
                return True
        return False

    def wait_for_normal_login(self, timeout: float) -> str | None:
        """Inspect only the rolling phase started before the reboot request."""
        end = time.monotonic() + timeout
        while True:
            if re.search(rb"^nixos login:(?:[ \t]|$)", _PROTOCOL.uart_text(self.buffer), re.M):
                return "login"
            if reboot_chroot_refusal(self.buffer):
                return "chroot-refusal"
            if time.monotonic() >= end:
                return None
            self.pump()

    def command(self, command: str, timeout: float = 30) -> bytes | None:
        self.line(command)
        if not self.wait_for(PROMPT, timeout):
            return None
        return self.buffer

    def close(self) -> None:
        self.port.close()


def safe_log_path(path: Path) -> Path:
    resolved = path.expanduser().resolve()
    repo = Path(__file__).resolve().parents[1]
    if resolved == repo or repo in resolved.parents:
        raise ValueError("raw serial log must be outside the repository")
    if resolved.exists():
        raise FileExistsError("private log already exists; choose a new path")
    if resolved.parent == PRIVATE_LOG_DIR:
        resolved.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        os.chmod(resolved.parent, 0o700)
    elif not resolved.parent.is_dir():
        raise FileNotFoundError("custom private log directory must already exist")
    if resolved.parent.stat().st_mode & 0o077:
        raise PermissionError("private log directory must not be accessible to group/other")
    return resolved


def write_private_result(path: Path, value: dict[str, object]) -> None:
    result_fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(result_fd, "w") as result_file:
        json.dump(value, result_file, indent=2, sort_keys=True)
        result_file.write("\n")


def finish_uart_progress(session, token, prepared, before, log_path, result_path):
    post_sample_mode = "uart_progress_post_sample_kernel" in prepared
    breadcrumb_mode = "uart_progress_breadcrumb_kernel" in prepared
    observation = observe_uart_progress(session, token, prepared["bootargs"],
                                        **({"uart_progress_breadcrumbs": True} if breadcrumb_mode else {}),
                                        **({"uart_progress_post_sample": True} if post_sample_mode else {}))
    after = None
    recovery_error = None
    if observation["normal_prompt_observed"]:
        try:
            post_token = uuid.uuid4().hex
            session.upload_text("/run/k230-mainline-normal-state.py", prepared["helper_text"], post_token)
            session.upload_text("/run/k230-mainline-expected.json", json.dumps(prepared["normal"], indent=2), post_token)
            candidate = session.run_state("postflight", post_token)
            normal = prepared["normal"]
            for key in ("system", "profile", "kernel", "uname", "init"):
                if candidate.get(key) != normal[key]:
                    raise ValueError("normal postflight identity mismatch")
            if (candidate.get("boot_files") != {name: info["sha256"] for name, info in normal["boot_files"].items()}
                    or candidate.get("services") != ["active"] * 3
                    or not re.fullmatch(BOOT_ID_PATTERN, candidate.get("boot_id", ""))
                    or candidate["boot_id"] in (normal["boot_id"], normal["trial_from_boot_id"])):
                raise ValueError("normal postflight files/services/fresh boot mismatch")
            after = candidate
        except Exception:
            # Preserve observation even if renewed normal guards fail/timeout.
            recovery_error = "protected-normal-postflight-unverified"
    diagnostic_ok = (observation["records_complete"] and observation["receipt_observed"] and
                     all(r["s"] == 0 and r["ti"] > 0 for r in observation["records"]))
    if breadcrumb_mode:
        diagnostic_ok = diagnostic_ok and observation["breadcrumbs_complete"]
    if post_sample_mode:
        diagnostic_ok = diagnostic_ok and observation["post_sample_complete"]
    status = ("recovery-verified-diagnostic-observed" if diagnostic_ok else
              "recovery-verified-diagnostic-incomplete") if after else "recovery-required-observation-only"
    result = {
        "result_schema": "mainline-initrd-uart-progress-v1", "status": status,
        "uart_progress": True, "same_image_shell_pid1": True,
        "candidate_system": prepared["system"], "candidate_bundle": str(prepared["bundle"]),
        "expected_bootargs": prepared["bootargs"], "kernel_proof": prepared["uart_progress_kernel"],
        "normal_preflight": before, "probe": observation, "normal_recovery": after,
        "recovery_error": recovery_error, "diagnostic_ok": diagnostic_ok,
        "reboot_requested": False, "persistent_boot_selection_changed": False,
        "ordinary_init": "NOT_ATTEMPTED", "usable_root": "UNVERIFIED", "touch": "UNVERIFIED",
        "raw_serial_log_path": str(log_path),
    }
    if breadcrumb_mode:
        result.update(uart_progress_breadcrumbs=True,
                      breadcrumb_kernel_proof=prepared["uart_progress_breadcrumb_kernel"])
    if post_sample_mode:
        result.update(uart_progress_post_sample=True,
                      post_sample_kernel_proof=prepared["uart_progress_post_sample_kernel"])
    write_private_result(result_path, result)
    print("Finite UART observation saved; no candidate reboot or retry was sent. " +
          ("Protected normal postflight verified." if after else "Protected normal recovery remains required."))
    return bool(after and diagnostic_ok)


def run_trial(
    manifest_path: Path, log_path: Path, result_path: Path, mode: str,
    bundle: Path = BUNDLE, normal_report: Path = NORMAL_REPORT,
    ignore_unused_clocks: bool = False,
    debug_shutdown: bool = False,
    runtime_shutdown_trace: bool = False,
    same_image_shell_pid1: bool = False,
    uart_progress: bool = False,
    uart_progress_breadcrumbs: bool = False,
    uart_progress_post_sample: bool = False,
) -> bool:
    validate_shell_selector(same_image_shell_pid1, mode, ignore_unused_clocks, debug_shutdown, runtime_shutdown_trace)
    validate_uart_progress_selector(uart_progress, same_image_shell_pid1, mode,
                                    ignore_unused_clocks, debug_shutdown, runtime_shutdown_trace)
    validate_uart_breadcrumb_selector(uart_progress_breadcrumbs, uart_progress, same_image_shell_pid1, mode)
    validate_uart_post_sample_selector(uart_progress_post_sample, uart_progress_breadcrumbs, uart_progress, same_image_shell_pid1, mode)
    if mode not in ("minimal", "survey", "label", "root-mount"):
        raise ValueError("probe mode must be minimal, survey, label or root-mount")
    if ignore_unused_clocks and not (mode == "label" or (mode == "minimal" and runtime_shutdown_trace)):
        raise ValueError("--ignore-unused-clocks requires --mode label or --mode minimal --runtime-shutdown-trace")
    if debug_shutdown and mode != "minimal":
        raise ValueError("--debug-shutdown requires --mode minimal")
    if runtime_shutdown_trace and mode != "minimal":
        raise ValueError("--runtime-shutdown-trace requires --mode minimal")
    if runtime_shutdown_trace and debug_shutdown:
        raise ValueError("--runtime-shutdown-trace cannot be combined with --debug-shutdown")
    prepared = prepare_trial(manifest_path, bundle, normal_report)
    if uart_progress:
        prepared = prepare_uart_progress(prepared,
                                         **({"uart_progress_breadcrumbs": True} if uart_progress_breadcrumbs else {}),
                                         **({"uart_progress_post_sample": True} if uart_progress_post_sample else {}))
    elif same_image_shell_pid1:
        prepared = prepare_shell_comparison(prepared)
    manifest = prepared["manifest"]
    system = prepared["system"]
    files = manifest["files"]
    expected_args = prepared["bootargs"]
    if ignore_unused_clocks or debug_shutdown or runtime_shutdown_trace:
        expected_args = trial_bootargs(
            (bundle / "bootargs.txt").read_text(), system,
            ignore_unused_clocks=ignore_unused_clocks, debug_shutdown=debug_shutdown,
            runtime_shutdown_trace=runtime_shutdown_trace,
        )
    normal = prepared["normal"]
    helper_text = prepared["helper_text"]
    selection = {"ignore_unused_clocks": ignore_unused_clocks} if mode == "label" or runtime_shutdown_trace else {}
    if same_image_shell_pid1:
        selection.update(same_image_shell_pid1=True, ordinary_init="NOT_ATTEMPTED",
                         usable_root="UNVERIFIED", touch="UNVERIFIED",
                         shell_artifacts={key: value for key, value in prepared["shell_comparison"].items()
                                          if key not in ("bootargs", "system")})
    if debug_shutdown:
        selection["debug_shutdown"] = True
    if runtime_shutdown_trace:
        selection["runtime_shutdown_trace"] = True
    try:
        import serial
    except ImportError as exc:
        raise RuntimeError("pyserial is required; use nix shell nixpkgs#python3Packages.pyserial") from exc

    log_path = safe_log_path(log_path)
    result_path = safe_log_path(result_path)
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    fd = os.open(log_path, flags, 0o600)
    os.fchmod(fd, 0o600)
    with os.fdopen(fd, "wb", buffering=0) as log_file:
        lock_fd = os.open(LOCK_PATH, os.O_CREAT | os.O_RDWR, 0o600)
        try:
            fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise RuntimeError("board lock is held; no serial device was opened") from exc
        session = None
        boot_started = False
        in_uboot = False
        recovery_login_seen = False
        recovery_identity_verified = False
        probe_outcome = None
        try:
            session = PrivateSession(serial, log_file)
            session.write(b"\x03\r")
            if not session.wait_for(b"root@nixos", 15):
                raise RuntimeError("root serial shell not observed; no reboot or file access attempted")

            preflight_token = uuid.uuid4().hex
            session.upload_text("/run/k230-mainline-normal-state.py", helper_text, preflight_token)
            session.upload_text(
                "/run/k230-mainline-expected.json",
                json.dumps(normal, indent=2),
                preflight_token,
            )
            observed_before = session.run_state("preflight", preflight_token)
            if (
                observed_before.get("system") != normal["system"]
                or observed_before.get("profile") != normal["profile"]
                or observed_before.get("kernel") != normal["kernel"]
                or observed_before.get("uname") != normal["uname"]
                or observed_before.get("init") != normal["init"]
                or observed_before.get("boot_files") != {
                    name: info["sha256"] for name, info in normal["boot_files"].items()
                }
            ):
                raise RuntimeError("preflight identity differs from the fresh protected normal report")
            normal["trial_from_boot_id"] = observed_before["boot_id"]

            session.line("reboot", interrupt=False)
            deadline = time.monotonic() + 35
            while time.monotonic() < deadline:
                session.pump()
                if b"Hit any key to stop autoboot" in session.buffer:
                    session.write(b" ")
                if PROMPT in session.buffer:
                    break
            else:
                raise RuntimeError("U-Boot prompt not reached; no files were loaded")
            in_uboot = True

            for command in ("mmc list", "ext4ls mmc 1:1 /", "printenv bootcmd", "printenv blinux"):
                if session.command(command, 30) is None:
                    raise RuntimeError("U-Boot preflight did not return to its prompt")

            for name, partition, address, source_path in LOADS:
                expected = files[name]
                load = session.command(
                    f"ext4load mmc {partition} {address} {source_path}", 90
                )
                crc = session.command(f"crc32 {address} {hex(int(expected['bytes']))}", 40)
                if not verified_load(load, expected):
                    raise RuntimeError(f"strict load report failed for {name}; no candidate boot was issued")
                if not verified_crc(crc, expected):
                    raise RuntimeError(f"count/CRC mismatch for {name}; no candidate boot was issued")

            args = session.command(
                f"env import -t 0x7000000 {hex(int(files['bootargs.txt']['bytes']))}", 15
            )
            if args is None:
                raise RuntimeError("could not import the matching volatile bootargs")
            # U-Boot imports the complete exact bootargs file above. Expand its
            # saved value only inside volatile RAM, then append diagnostic arguments.
            command = prepared["transport"] if same_image_shell_pid1 else volatile_bootargs_command(
                ignore_unused_clocks, **({"debug_shutdown": True} if debug_shutdown else {}),
            )
            if session.command(command, 15) is None:
                raise RuntimeError("could not set volatile rdinit bootargs")
            printed = session.command("printenv bootargs", 15)
            if not verified_bootargs(printed, expected_args):
                raise RuntimeError("volatile bootargs do not contain both matching init paths")
            if "rdinit=/bin/sh" not in expected_args:
                raise AssertionError("pure bootargs validation disagreed with U-Boot check")

            session.line("bootm 0x8000000 0x9000000 0x8400000", interrupt=False)
            boot_started = True
            in_uboot = False
            if uart_progress:
                return finish_uart_progress(session, uuid.uuid4().hex, prepared, observed_before,
                                            log_path, result_path)
            if not session.wait_for(b"Linux version 7.3.0-rc5", 45):
                raise RuntimeError("Linux version banner not observed; reset may be required")
            token = uuid.uuid4().hex
            try:
                selection["initrd_readiness_observed"] = await_initrd_ready(session)
                if not selection["initrd_readiness_observed"]:
                    raise ProbeProtocolError("initrd readiness")
                probe_outcome = run_probe_protocol(
                    session, token, mode, system=system,
                    **({"runtime_shutdown_trace": True} if runtime_shutdown_trace else {}),
                    **({"shell_comparison": prepared["shell_comparison"], "normal": normal}
                       if same_image_shell_pid1 else {}),
                )
            except ProbeProtocolError as exc:
                write_private_result(result_path, {
                    "result_schema": f"mainline-initrd-{mode}-unknown-v1",
                    "status": "recovery-required-unknown-no-reboot-requested",
                    "mode": f"volatile-rdinit-{mode}", **selection,
                    "candidate_system": system, "candidate_bundle": str(prepared["bundle"]),
                    "normal_preflight": observed_before,
                    "probe": exc.diagnostic or {
                        "schema": f"k230-initrd-{mode}-unknown-v1", "stage": exc.stage,
                        **({"runtime_shutdown_trace": {"attempted": False, "stages": {}, "enable_verified": False,
                                                       "parameter_state": "UNVERIFIED"}}
                           if runtime_shutdown_trace else {}),
                    },
                    "reboot_marker_observed": False, "normal_recovery": None,
                    "persistent_boot_selection_changed": False, "raw_serial_log_path": str(log_path),
                })
                print(f"{mode} protocol incomplete at {exc.stage}; no further probe or recovery input was sent. "
                      "Protected normal recovery is required and unverified.", file=sys.stderr)
                return False
            if probe_outcome.get("recovery_required"):
                reason = str(probe_outcome["recovery_reason"])
                write_private_result(result_path, {
                    "result_schema": "mainline-initrd-diagnostic-v3",
                    **selection,
                    "status": "recovery-required-no-reboot-requested",
                    "mode": f"volatile-rdinit-{mode}",
                    "candidate_system": system,
                    "candidate_bundle": str(prepared["bundle"]),
                    "normal_preflight": observed_before,
                    "probe": probe_outcome["diagnostic"],
                    "reboot_marker_observed": False,
                    "normal_recovery": None,
                    "recovery_reason": reason,
                    "persistent_boot_selection_changed": False,
                    "raw_serial_log_path": str(log_path),
                })
                print(
                    f"Diagnostic stopped at {reason}; no reboot was requested because safe reset prerequisites failed. "
                    f"Protected normal recovery is not yet verified; private serial log: {log_path}",
                    file=sys.stderr,
                )
                return False

            login_state = session.wait_for_normal_login(180)
            if login_state == "chroot-refusal":
                write_private_result(result_path, {
                    "result_schema": "mainline-initrd-diagnostic-v3",
                    **selection,
                    "status": "recovery-required-systemctl-chroot-refusal",
                    "mode": f"volatile-rdinit-{mode}",
                    "candidate_system": system,
                    "candidate_bundle": str(prepared["bundle"]),
                    "normal_preflight": observed_before,
                    "probe": probe_outcome["diagnostic"],
                    "reboot_marker_observed": probe_outcome["reboot_marker"],
                    "normal_recovery": None,
                    "recovery_reason": "systemctl-reboot-alias-refused-in-chroot",
                    "persistent_boot_selection_changed": False,
                    "raw_serial_log_path": str(log_path),
                })
                print(
                    "systemctl refused the reboot as a chroot; no retry was sent. "
                    f"Protected normal recovery is not verified; private serial log: {log_path}",
                    file=sys.stderr,
                )
                return False
            if login_state != "login":
                write_private_result(result_path, {
                    "result_schema": "mainline-initrd-diagnostic-v3", **selection,
                    "status": "recovery-required-normal-return-timeout",
                    "mode": f"volatile-rdinit-{mode}",
                    "candidate_system": system,
                    "candidate_bundle": str(prepared["bundle"]),
                    "normal_preflight": observed_before,
                    "probe": probe_outcome["diagnostic"],
                    "reboot_marker_observed": probe_outcome["reboot_marker"],
                    "normal_recovery": None,
                    "recovery_reason": "normal-login-not-observed-after-initrd-reboot",
                    "normal_return_timeout_seconds": 180,
                    "persistent_boot_selection_changed": False,
                    "raw_serial_log_path": str(log_path),
                })
                print("Normal login not observed within 180s after the initrd reboot request; "
                      "received probe facts were preserved. No further input was sent; "
                      "protected normal recovery remains unverified.", file=sys.stderr)
                return False
            recovery_login_seen = True
            if not session.wait_for(b"root@nixos", 30):
                raise RuntimeError("recovered root shell not observed; preserved recovery identities remain unchecked")
            post_token = uuid.uuid4().hex
            session.upload_text("/run/k230-mainline-normal-state.py", helper_text, post_token)
            session.upload_text(
                "/run/k230-mainline-expected.json",
                json.dumps(normal, indent=2),
                post_token,
            )
            observed_after = session.run_state("postflight", post_token)
            if (
                observed_after.get("system") != normal["system"]
                or observed_after.get("profile") != normal["profile"]
                or observed_after.get("kernel") != normal["kernel"]
                or observed_after.get("uname") != normal["uname"]
                or observed_after.get("init") != normal["init"]
                or observed_after.get("boot_files") != {
                    name: info["sha256"] for name, info in normal["boot_files"].items()
                }
                or observed_after.get("services") != ["active"] * 3
            ):
                raise RuntimeError("recovered system/kernel/profile/services/protected files differ from baseline")
            recovery_identity_verified = True
            diagnostic_ok = bool(probe_outcome["diagnostic_ok"])
            status = (
                "recovery-verified-diagnostic-passed"
                if diagnostic_ok else "recovery-verified-diagnostic-failed"
            )
            print(f"Protected normal recovery identities verified; private serial log: {log_path}")
            print("Recovered system, kernel, profile, services, boot ID, and eight protected boot-file hashes verified.")
            print(f"Diagnostic mode: {mode}; result: {status}; reboot marker: {probe_outcome['reboot_marker']}.")
            safe_result = {
                "result_schema": "mainline-initrd-diagnostic-v3",
                **selection,
                "status": status,
                "mode": f"volatile-rdinit-{mode}",
                "candidate_system": system,
                "candidate_bundle": str(prepared["bundle"]),
                "normal_preflight": observed_before,
                "probe": probe_outcome["diagnostic"],
                "reboot_marker_observed": probe_outcome["reboot_marker"],
                "normal_recovery": observed_after,
                "persistent_boot_selection_changed": False,
                "raw_serial_log_path": str(log_path),
            }
            write_private_result(result_path, safe_result)
            return diagnostic_ok
        except Exception:
            if session is not None and in_uboot and not boot_started:
                # All pre-boot failures leave Linux/normal boot files intact.
                session.line("reset", interrupt=False)
                print("Pre-boot failure: reset requested; normal boot selection is unchanged.", file=sys.stderr)
            elif boot_started:
                if recovery_identity_verified:
                    print(
                        "Protected normal recovery identities were verified; the diagnostic probe "
                        "failed its required mount/block-label checks. Keep the physical gate open.",
                        file=sys.stderr,
                    )
                elif recovery_login_seen:
                    print(
                        "Normal login returned but recovered identities were not verified. "
                        "Do not declare recovery or change boot files; preserve the board for inspection.",
                        file=sys.stderr,
                    )
                else:
                    print(
                        "Linux started; PID 1 may still be the diagnostic shell. Do not send exit. "
                        "Keep the reservation and use the agreed physical power-cycle recovery only "
                        "if automatic reboot did not return to normal login.",
                        file=sys.stderr,
                    )
            raise
        finally:
            if session is not None:
                session.close()
            os.close(lock_fd)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=MANIFEST_DEFAULT)
    parser.add_argument("--bundle", type=Path, default=BUNDLE,
                        help="exact immutable candidate boot bundle; system is derived from its system symlink")
    parser.add_argument("--normal-report", type=Path, default=NORMAL_REPORT,
                        help="protected normal identity report matching the committed baseline")
    parser.add_argument(
        "--mode", choices=("minimal", "survey", "label", "root-mount"), default="minimal",
        help="minimal by default; label, read-only root mount and full survey require explicit modes",
    )
    parser.add_argument("--ignore-unused-clocks", action="store_true",
                        help="label, or minimal with runtime tracing: add volatile clk_ignore_unused")
    parser.add_argument("--same-image-shell-pid1", action="store_true",
                        help="minimal only: exact SBI-only image, markers off, async=0, qualified controls and Bash PID1")
    parser.add_argument("--uart-progress", action="store_true",
                        help="minimal shell comparison only: matching configured kernel; one receipt then passive capture, no candidate reboot; requires host nix-store and matching realized kernel.dev")
    parser.add_argument("--uart-progress-breadcrumbs", action="store_true",
                        help="requires minimal same-image shell plus UART progress: exact reviewed source/compiled markers; two fixed worker points, no candidate reboot")
    parser.add_argument("--uart-progress-post-sample", action="store_true",
                        help="requires all minimal shell/progress/breadcrumb selectors: reviewed PostSample kernel; two fixed return/sleep points, no candidate reboot")
    shutdown_flags = parser.add_mutually_exclusive_group()
    shutdown_flags.add_argument("--debug-shutdown", action="store_true",
                        help="minimal mode only: add volatile initcall_debug loglevel=8 shutdown tracing")
    shutdown_flags.add_argument("--runtime-shutdown-trace", action="store_true",
                        help="minimal mode only: enable shutdown tracing after verified sysfs and parameter gates")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    parser.add_argument(
        "--log", type=Path,
        default=PRIVATE_LOG_DIR / f"mainline-initrd-shell-{stamp}.private.log",
    )
    parser.add_argument(
        "--result", type=Path,
        default=PRIVATE_LOG_DIR / f"mainline-initrd-shell-{stamp}.result.json",
    )
    args = parser.parse_args()
    try:
        validate_shell_selector(args.same_image_shell_pid1, args.mode, args.ignore_unused_clocks,
                                args.debug_shutdown, args.runtime_shutdown_trace)
        validate_uart_progress_selector(args.uart_progress, args.same_image_shell_pid1, args.mode,
                                        args.ignore_unused_clocks, args.debug_shutdown, args.runtime_shutdown_trace)
        validate_uart_breadcrumb_selector(args.uart_progress_breadcrumbs, args.uart_progress,
                                         args.same_image_shell_pid1, args.mode)
        validate_uart_post_sample_selector(args.uart_progress_post_sample, args.uart_progress_breadcrumbs,
                                          args.uart_progress, args.same_image_shell_pid1, args.mode)
    except ValueError as exc:
        parser.error(str(exc))
    if args.ignore_unused_clocks and not (args.mode == "label" or (args.mode == "minimal" and args.runtime_shutdown_trace)):
        parser.error("--ignore-unused-clocks requires --mode label or --mode minimal --runtime-shutdown-trace")
    if args.debug_shutdown and args.mode != "minimal":
        parser.error("--debug-shutdown requires --mode minimal")
    if args.runtime_shutdown_trace and args.mode != "minimal":
        parser.error("--runtime-shutdown-trace requires --mode minimal")
    try:
        diagnostic_ok = run_trial(
            args.manifest, args.log, args.result, args.mode, args.bundle, args.normal_report,
            **({"ignore_unused_clocks": True} if args.ignore_unused_clocks else {}),
            **({"debug_shutdown": True} if args.debug_shutdown else {}),
            **({"runtime_shutdown_trace": True} if args.runtime_shutdown_trace else {}),
            **({"same_image_shell_pid1": True} if args.same_image_shell_pid1 else {}),
            **({"uart_progress": True} if args.uart_progress else {}),
            **({"uart_progress_breadcrumbs": True} if args.uart_progress_breadcrumbs else {}),
            **({"uart_progress_post_sample": True} if args.uart_progress_post_sample else {}),
        )
    except Exception as exc:
        print(f"Trial stopped: {exc}", file=sys.stderr)
        return 1
    return 0 if diagnostic_ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
