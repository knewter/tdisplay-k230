import copy
import gzip
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import re
import struct
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock
import zlib

SPEC = importlib.util.spec_from_file_location("shell_trial", Path(__file__).parents[1] / "tools/mainline-drm-initrd-shell-trial.py")
trial = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(trial)
SYSTEM = "/nix/store/" + "a" * 32 + "-candidate-system"
BASH = "/nix/store/" + "b" * 32 + "-bash-interactive-riscv64-unknown-linux-gnu-5.3p15/bin/bash"
SYSTEMD = "/nix/store/" + "c" * 32 + "-systemd-riscv64-unknown-linux-gnu-261.2/lib/systemd/systemd"
LOADER = "/nix/store/" + "d" * 32 + "-glibc/lib/ld-linux-riscv64-lp64d.so.1"
OLD = "00000000-0000-0000-0000-000000000001"
BOOT = "00000000-0000-0000-0000-000000000002"
RECOVERED = "00000000-0000-0000-0000-000000000003"
TOKEN = "a" * 32
ORIGINAL = ("bootargs=consoleblank=0 console=ttyS0,115200n8 root=fstab loglevel=4 "
            "lsm=landlock,yama,bpf loglevel=7 k230.boot_trace=1 k230.boot_trace_sbi_only=1 "
            f"init={SYSTEM}/init\n")


def comparison():
    return {"system": SYSTEM, "bash": BASH, "bootargs": trial.shell_pid1_bootargs(ORIGINAL, SYSTEM)}


def frame(token, phase, match=1, boot=BOOT, rc=0):
    return (f"K230_SHELL_PID1_BEGIN {token} {phase}\n"
            f"K230_SHELL_PID1_END {token} {phase} RC={rc} MATCH={match} BOOT={boot}\nsh-5.3# ").encode()


class Clock:
    def __init__(self): self.now = 0
    def __call__(self): self.now += 0.01; return self.now


class Session:
    pump = trial.PrivateSession.pump
    instances = []
    def __init__(self, serial=None, log=None):
        self.buffer = b""; self.chunks = []; self.writes = []; self.uploads = []
        self.log = log or io.BytesIO(); self.failure = None; self.guard_match = 1; self.renewed_boot = BOOT
        self.port = SimpleNamespace(read=lambda n: self.chunks.pop(0) if self.chunks else b"")
        type(self).instances.append(self)
    def write(self, data):
        self.writes.append(data)
        text = data.decode()
        m = re.search(r"K230_(?:RDINIT_RX|RDINIT_TRUE|RDINIT_MOUNT_BEGIN|RDINIT_UP_BEGIN|RDINIT_REBOOT|SHELL_PID1_BEGIN) ([0-9a-f]{32})", text)
        if not m: return
        token = m[1]
        if "SHELL_PID1_BEGIN" in text:
            phase = re.search(r"SHELL_PID1_BEGIN [0-9a-f]{32} (initial|renewed)", text)[1]
            response = frame(token, phase, self.guard_match, self.renewed_boot if phase == "renewed" else BOOT)
            if self.failure == phase: return
            if self.failure == phase + "-duplicate": response += response
            if self.failure == phase + "-truncated": response = response[:-3]
            if self.failure == phase + "-stale": response = frame("f" * 32, phase)
            self.chunks.append(response)
        elif "RDINIT_RX" in text: self.chunks.append(f"K230_RDINIT_RX {token}\n".encode())
        elif "RDINIT_TRUE" in text: self.chunks.append(f"K230_RDINIT_TRUE {token} RC=0\n".encode())
        elif "RDINIT_MOUNT_BEGIN" in text:
            self.chunks.append(f"K230_RDINIT_MOUNT_BEGIN {token}\nK230_RDINIT_MOUNT_END {token} MKDIR_RC=0 MOUNT_ATTEMPTED=1 MOUNT_RC=0\n".encode())
        elif "RDINIT_UP_BEGIN" in text:
            self.chunks.append(f"K230_RDINIT_UP_BEGIN {token}\n12.5 8.0\nK230_RDINIT_UP_END {token} RC=0\n".encode())
        elif "RDINIT_REBOOT" in text: self.chunks.append(f"K230_RDINIT_REBOOT {token}\n".encode())
    def line(self, text, interrupt=True):
        self.writes.append((text + "\r").encode())
        self.buffer = trial.PROMPT
        if text.startswith("bootm"):
            self.buffer = b""
            self.chunks.append(b"[    0.1] Linux version 7.3.0-rc5 candidate\n[    4.1] Run /bin/sh as init process\nsh-5.3# ")
    def wait_for(self, token, timeout):
        if token == b"Linux version 7.3.0-rc5": self.pump()
        return True
    def command(self, text, timeout):
        self.writes.append(text.encode())
        if text.startswith("ext4load"): return b"123 bytes read in 1 ms\nK230# "
        if text.startswith("crc32"): return b"CRC32 for 0 ... 1 ==> abcdef01\nK230# "
        if text == "printenv bootargs": return (comparison()["bootargs"] + "\nK230# ").encode()
        return trial.PROMPT
    def upload_text(self, path, content, token): self.uploads.append((path, content))
    def run_state(self, phase, token):
        n = normal()
        return {**n, "boot_files": {k: v["sha256"] for k, v in n["boot_files"].items()},
                "boot_id": OLD if phase == "preflight" else RECOVERED}
    def wait_for_normal_login(self, timeout): return "login"
    def close(self): self.closed = True


def normal():
    return {"system": "/normal", "profile": "/normal", "kernel": "/normal/Image", "uname": "6.6.36",
            "init": "init=/normal/init", "boot_id": OLD, "services": ["active"] * 3,
            "boot_files": {"Image": {"sha256": "d" * 64}}}


def elf(interpreter=None):
    body = bytearray(512)
    body[:7] = b"\x7fELF\x02\x01\x01"
    struct.pack_into("<H", body, 18, 243)
    struct.pack_into("<Q", body, 32, 64)
    struct.pack_into("<HH", body, 54, 56, 1)
    if interpreter:
        value = interpreter.encode() + b"\0"
        struct.pack_into("<I", body, 64, 3)
        struct.pack_into("<Q", body, 72, 128)
        struct.pack_into("<Q", body, 96, len(value))
        body[128:128 + len(value)] = value
    return bytes(body)


def archive_fixture(entries):
    raw = bytearray()
    for name, (mode, content) in [*entries.items(), ("TRAILER!!!", (0, b""))]:
        fields = [0, mode, 0, 0, 1, 0, len(content), 0, 0, 0, 0, len(name.encode()) + 1, 0]
        raw += b"070701" + "".join(f"{v:08x}" for v in fields).encode() + name.encode() + b"\0"
        raw += bytes((-len(raw)) % 4); raw += content; raw += bytes((-len(raw)) % 4)
    return gzip.compress(raw)


class ShellPid1Tests(unittest.TestCase):
    def test_exact_transform_and_safe_literal_before_input(self):
        after = trial.shell_pid1_bootargs(ORIGINAL, SYSTEM)
        self.assertEqual(after.split(), [p for p in ORIGINAL.split() if p not in trial.SHELL_TRACE_FLAGS] + [*trial.SHELL_CONTROLS, "rdinit=/bin/sh"])
        command = trial.shell_pid1_transport(after, SYSTEM)
        self.assertEqual(command, 'setenv bootargs "' + after.removeprefix("bootargs=") + '"')
        self.assertLess(len(command), 512); self.assertNotIn("${", command); self.assertNotIn("saveenv", command)
        for suffix in (" ;saveenv", " $unsafe", "\n", " k230.boot_trace=0", " rdinit=/bin/sh", " filler=" + "a" * 512):
            with self.subTest(suffix=suffix), self.assertRaises(ValueError): trial.shell_pid1_transport(after + suffix, SYSTEM)

    def test_original_qualification_rejects_all_extra_missing_alternate_controls(self):
        bad = [ORIGINAL.rstrip(), ORIGINAL.replace(SYSTEM, "/wrong"), ORIGINAL.replace("console=ttyS0,115200n8", "console=tty0"),
               ORIGINAL.replace("k230.boot_trace=1", "k230.boot_trace=0"), ORIGINAL.replace("loglevel=7", "loglevel=0")]
        for arg in ("rdinit=/bin/sh", "initramfs_async=0", "fsck.mode=skip", "systemd.mask=other", "keep_bootcon=1", "earlycon=sbi", "clk_ignore_unused", "k230.boot_trace=1", "k230.boot_trace_sbi_only=0", "unknown=value"):
            bad.append(ORIGINAL.rstrip() + " " + arg + "\n")
        for value in bad:
            with self.subTest(value=value), self.assertRaises(ValueError): trial.shell_pid1_bootargs(value, SYSTEM)

    def test_selector_types_and_conflicts_fail_before_preparation_or_serial(self):
        for value, mode, flags in [(1, "minimal", {}), (None, "minimal", {}), ("false", "minimal", {}),
                                   *[(True, m, {}) for m in ("label", "root-mount", "survey")],
                                   *[(True, "minimal", {k: True}) for k in ("ignore_unused_clocks", "debug_shutdown", "runtime_shutdown_trace")]]:
            with mock.patch.object(trial, "prepare_trial") as prep, mock.patch.object(trial, "PrivateSession") as port:
                with self.assertRaises(ValueError): trial.run_trial(Path("/missing"), Path("/unused"), Path("/unused"), mode, same_image_shell_pid1=value, **flags)
                prep.assert_not_called(); port.assert_not_called()

    def test_cli_conflicts_and_default_do_not_change_old_invocations(self):
        for flags in (["--mode", "survey"], ["--debug-shutdown"], ["--runtime-shutdown-trace"], ["--ignore-unused-clocks"]):
            with mock.patch.object(sys, "argv", ["trial", "--same-image-shell-pid1", *flags]), mock.patch.object(trial, "run_trial") as run, mock.patch("sys.stderr"):
                with self.assertRaises(SystemExit): trial.main()
                run.assert_not_called()
        with mock.patch.object(sys, "argv", ["trial"]), mock.patch.object(trial, "run_trial", return_value=True) as run:
            self.assertEqual(trial.main(), 0); self.assertNotIn("same_image_shell_pid1", run.call_args.kwargs)
        with mock.patch.object(sys, "argv", ["trial", "--same-image-shell-pid1"]), mock.patch.object(trial, "run_trial", return_value=True) as run:
            self.assertEqual(trial.main(), 0); self.assertIs(run.call_args.kwargs["same_image_shell_pid1"], True)
        self.assertEqual(trial.trial_bootargs("init=" + trial.SYSTEM + "/init"), "init=" + trial.SYSTEM + "/init rdinit=/bin/sh")

    def test_fresh_guard_frames_reject_echo_stale_duplicates_truncation_and_insertion(self):
        good = frame(TOKEN, "initial")
        self.assertEqual(trial.shell_guard_result(good, TOKEN, "initial"), {"rc": 0, "match": True, "boot_id": BOOT})
        for bad in (good + good, good[:-1], good.removesuffix(b"sh-5.3# "),
                    frame("f" * 32, "initial"), b"printf '" + good + b"'",
                    good.replace(b"\nK230_SHELL_PID1_END", b"\n[    3.0] unrelated printk\nK230_SHELL_PID1_END"),
                    good.replace(b"RC=0", b"RC=2"),
                    f"K230_SHELL_PID1_END {TOKEN} renewed RC=malformed\n".encode() + good,
                    f"K230_SHELL_PID1_BEGIN {TOKEN} unknown\n".encode() + good,
                    good.replace(b"sh-5.3# ", b"> ")):
            with self.subTest(bad=bad): self.assertIsNone(trial.shell_guard_result(bad, TOKEN, "initial"))
        self.assertIsNone(trial.shell_guard_result(good, TOKEN, "renewed"))

    def protocol(self, session):
        return trial.run_probe_protocol(session, TOKEN, "minimal", timeout=0.1, clock=Clock(),
                                        token_factory=iter(("b" * 32, "c" * 32)).__next__,
                                        shell_comparison=comparison(), normal=normal())

    def test_real_pump_protocol_requires_both_guards_then_one_reboot(self):
        s = Session(); result = self.protocol(s)
        self.assertTrue(result["diagnostic_ok"]); self.assertTrue(result["reboot_marker"])
        self.assertEqual(result["diagnostic"]["schema"], "k230-initrd-shell-pid1-v1")
        self.assertEqual(list(result["diagnostic"]["shell_pid1"]), ["initial", "renewed"])
        self.assertEqual(sum(b"/bin/reboot -ff" in w for w in s.writes), 1)
        self.assertIn(b"K230_SHELL_PID1_BEGIN", s.writes[-2]); self.assertIn(b"renewed", s.writes[-2])
        self.assertEqual(len(s.writes), 7)

    def test_unknown_guards_stop_input_and_preserve_partial_facts(self):
        for phase in ("initial", "renewed"):
            for suffix in ("", "-duplicate", "-truncated", "-stale"):
                s = Session(); s.failure = phase + suffix
                with self.subTest(failure=s.failure), self.assertRaises(trial.ProbeProtocolError): self.protocol(s)
                self.assertIn(phase.encode(), s.writes[-1]); self.assertNotIn(b"/bin/reboot", b"\n".join(s.writes))
                self.assertFalse(any(w in (b"\x03", b"exit\r") for w in s.writes))

    def test_known_failed_or_changed_boot_guard_never_reboots(self):
        for match, boot in ((0, BOOT), (1, RECOVERED), (1, OLD)):
            s = Session(); s.guard_match = match; s.renewed_boot = boot
            result = self.protocol(s)
            self.assertTrue(result["recovery_required"]); self.assertFalse(result["reboot_marker"])
            self.assertFalse(any(b"/bin/reboot" in w for w in s.writes))

    def test_setup_failure_skips_guard_and_reboot_in_comparison(self):
        for stage in ("true", "proc"):
            class Failed(Session):
                def write(self, data):
                    super().write(data)
                    if stage == "true" and b"RDINIT_TRUE" in data:
                        self.chunks[-1] = self.chunks[-1].replace(b"RC=0", b"RC=1")
                    if stage == "proc" and b"RDINIT_MOUNT_BEGIN" in data:
                        self.chunks[-1] = self.chunks[-1].replace(b"MOUNT_RC=0", b"MOUNT_RC=1")
            s = Failed(); result = self.protocol(s)
            self.assertTrue(result["recovery_required"])
            self.assertFalse(any(b"SHELL_PID1_BEGIN" in w or b"/bin/reboot" in w for w in s.writes))

    def test_guard_payload_executes_against_isolated_mount_and_identity_fixtures(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            files = {"/proc/1/exe": ("exe", BASH), "/proc/sys/kernel/osrelease": ("release", "7.3.0-rc5"),
                     "/proc/cmdline": ("cmdline", comparison()["bootargs"].removeprefix("bootargs=")),
                     "/proc/sys/kernel/random/boot_id": ("boot", BOOT), "/etc/initrd-release": ("initrd-release", "fixture")}
            for _, (name, value) in files.items(): (root / name).write_text(value + "\n")
            command = trial.shell_guard_command(TOKEN, "initial", comparison(), normal())
            self.assertLess(len(command.encode()), 3072); self.assertNotIn("/proc/self", command)
            command = "BASH_VERSION=5.3.15; " + command.replace("_k230_pid=$$", "_k230_pid=1").replace('test "$PPID" = 0', 'test 0 = 0').replace('test "$EUID" = 0', 'test 0 = 0')
            command = command.replace("/bin/readlink /proc/1/exe", "/bin/cat " + str(root / "exe"))
            for path, (name, _) in files.items(): command = command.replace(path, str(root / name))
            command = command.replace("/sysroot/nix/store", str(root / "absent-store")).replace("/proc/mounts", str(root / "mounts"))
            for table, match in (("rootfs / rootfs rw 0 0\nproc /proc proc rw 0 0\n", True),
                                 ("rootfs / rootfs rw 0 0\ndevtmpfs /dev devtmpfs rw 0 0\nproc /proc proc rw 0 0\n", True),
                                 ("rootfs / rootfs rw 0 0\n/dev/mmcblk1p2 /sysroot ext4 ro 0 0\nproc /proc proc rw 0 0\n", False),
                                 ("/dev/mmcblk1p2 / ext4 ro 0 0\nproc /proc proc rw 0 0\n", False), (None, False)):
                if table is None: (root / "mounts").unlink()
                else: (root / "mounts").write_text(table)
                for shell in ("bash", "sh"):
                    done = subprocess.run([shell, "-c", command], capture_output=True, timeout=2)
                    result = trial.shell_guard_result(done.stdout + b"sh-5.3# ", TOKEN, "initial")
                    self.assertEqual(done.returncode, 0, done.stderr); self.assertEqual(result["match"], match)
            (root / "mounts").write_text("rootfs / rootfs rw 0 0\nproc /proc proc rw 0 0\n")
            for name, bad in (("exe", "/wrong/bash"), ("release", "6.6.36"), ("cmdline", "wrong"), ("cmdline", " " + comparison()["bootargs"].removeprefix("bootargs=")), ("boot", OLD)):
                file = root / name; original = file.read_text(); file.write_text(bad + "\n")
                done = subprocess.run(["bash", "-c", command], capture_output=True, timeout=2)
                self.assertFalse(trial.shell_guard_result(done.stdout + b"sh-5.3# ", TOKEN, "initial")["match"]); file.write_text(original)

    def initrd_fixture(self, root, *, different_loader=False):
        entries = {SYSTEMD.lstrip("/"): (0o100555, elf(LOADER)), BASH.lstrip("/"): (0o100555, elf(LOADER + ("-other" if different_loader else ""))),
                   LOADER.lstrip("/"): (0o100555, elf()), "init": (0o120777, SYSTEMD.encode()), "bin/sh": (0o120777, BASH.encode()),
                   "etc/initrd-release": (0o100444, b"fixture")}
        for name in ("readlink", "true", "mkdir", "mount", "cat", "reboot"): entries["bin/" + name] = (0o100555, elf())
        payload = archive_fixture(entries)
        header = struct.pack(">7I4B32s", 0x27051956, 0, 0, len(payload), 0, 0, zlib.crc32(payload), 5, 26, 3, 0, bytes(32))
        header = header[:4] + struct.pack(">I", zlib.crc32(header)) + header[8:]
        system = root / "system"; bundle = root / "bundle"; system.mkdir(); bundle.mkdir()
        (system / "kernel").write_bytes(b"kernel"); (system / "initrd").write_bytes(payload); (bundle / "initrd.uimg").write_bytes(header + payload)
        return {"system": str(system), "bundle": bundle, "manifest": {"files": {"Image-mainline-drm": {"sha256": hashlib.sha256(b"kernel").hexdigest()}}}}

    def test_actual_archive_parser_checks_executables_shared_loader_and_wrapper(self):
        with tempfile.TemporaryDirectory() as directory, mock.patch.object(trial, "immutable_store_path"):
            p = self.initrd_fixture(Path(directory))
            # Selected kernel is conventionally named Image, not a file called kernel.
            system = Path(p["system"]); (system / "kernel").rename(system / "Image"); (system / "kernel").symlink_to("Image")
            proof = trial.inspect_shell_initrd(p)
            self.assertEqual(proof["bash"], BASH); self.assertEqual(proof["loader"], LOADER)
            self.assertEqual(set(proof["executables"]), {"init", "bin/sh", "bin/readlink", "bin/true", "bin/mkdir", "bin/mount", "bin/cat", "bin/reboot"})
            for file in (system / "Image", Path(p["bundle"]) / "initrd.uimg"):
                original = file.read_bytes(); file.write_bytes(original + b"bad")
                with self.assertRaises(ValueError): trial.inspect_shell_initrd(p)
                file.write_bytes(original)
        with tempfile.TemporaryDirectory() as directory, mock.patch.object(trial, "immutable_store_path"):
            p = self.initrd_fixture(Path(directory), different_loader=True)
            system = Path(p["system"]); (system / "kernel").rename(system / "Image"); (system / "kernel").symlink_to("Image")
            with self.assertRaises(ValueError): trial.inspect_shell_initrd(p)

    def test_full_transport_reuses_protected_checks_and_records_only_shell_claim(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); bundle = root / "bundle"; bundle.mkdir(); (bundle / "bootargs.txt").write_text(ORIGINAL)
            p = {"system": SYSTEM, "bundle": bundle, "normal": normal(), "helper_text": "pass\n",
                 "manifest": {"files": {name: {"bytes": 123, "crc32": "abcdef01"} for name, _, _, _ in trial.LOADS}}}
            s = Session()
            with mock.patch.object(trial, "prepare_trial", return_value=p), mock.patch.object(trial, "inspect_shell_initrd", return_value={"bash": BASH}), \
                    mock.patch.object(trial, "LOCK_PATH", root / "lock"), mock.patch.object(trial, "PrivateSession", return_value=s), \
                    mock.patch.dict(sys.modules, {"serial": mock.Mock()}):
                self.assertTrue(trial.run_trial(root / "manifest", root / "log", root / "result", "minimal", bundle, root / "report", same_image_shell_pid1=True))
            literal = trial.shell_pid1_transport(comparison()["bootargs"], SYSTEM).encode()
            self.assertIn(literal, s.writes); self.assertFalse(any(b"${bootargs}" in w for w in s.writes))
            self.assertEqual(sum(w.startswith(b"ext4load") for w in s.writes), 5); self.assertEqual(sum(w.startswith(b"crc32") for w in s.writes), 5)
            helpers = [content for path, content in s.uploads if path.endswith(".py")]
            self.assertEqual(len(helpers), 2); self.assertTrue(all(".is_symlink()" in value and "'/nix-path-registration'" in value for value in helpers))
            result = json.loads((root / "result").read_text()); self.assertTrue(result["same_image_shell_pid1"])
            self.assertEqual(result["ordinary_init"], "NOT_ATTEMPTED"); self.assertEqual(result["usable_root"], "UNVERIFIED")
            self.assertEqual(result["normal_recovery"]["boot_id"], RECOVERED)
            self.assertEqual(sum(b"/bin/reboot -ff" in w for w in s.writes), 1)

    def test_preparation_errors_leave_port_unopened_and_helper_registration_assertion_is_real(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); (root / "bootargs.txt").write_text(ORIGINAL.rstrip() + " extra=bad\n")
            p = {"bundle": root, "system": SYSTEM}
            with mock.patch.object(trial, "prepare_trial", return_value=p), mock.patch.object(trial, "PrivateSession") as port:
                with self.assertRaises(ValueError): trial.run_trial(root / "m", root / "l", root / "r", "minimal", same_image_shell_pid1=True)
                port.assert_not_called(); self.assertFalse((root / "l").exists())
            marker = root / "registration"
            (root / "bootargs.txt").write_text(ORIGINAL)
            p.update(normal=normal(), helper_text="executed=True\n")
            with mock.patch.object(trial, "inspect_shell_initrd", return_value={"bash": BASH}):
                helper = trial.prepare_shell_comparison(p)["helper_text"]
            code = helper.replace("/nix-path-registration", str(marker))
            exec(code, {})
            marker.write_text("fixture")
            with self.assertRaises(AssertionError): exec(code, {})
            marker.unlink(); marker.symlink_to(root / "missing")
            with self.assertRaises(AssertionError): exec(code, {})

    def test_full_transport_unknown_readiness_or_guard_sends_no_further_input(self):
        for stage in ("readiness", "initial"):
            with tempfile.TemporaryDirectory() as directory:
                root = Path(directory); bundle = root / "bundle"; bundle.mkdir(); (bundle / "bootargs.txt").write_text(ORIGINAL)
                p = {"system": SYSTEM, "bundle": bundle, "normal": normal(), "helper_text": "pass\n",
                     "manifest": {"files": {name: {"bytes": 123, "crc32": "abcdef01"} for name, _, _, _ in trial.LOADS}}}
                s = Session(); s.failure = stage
                original_probe = trial.run_probe_protocol
                def fast_probe(active, token, mode, **kwargs):
                    return original_probe(active, token, mode, timeout=0.1, clock=Clock(), **kwargs)
                with mock.patch.object(trial, "prepare_trial", return_value=p), mock.patch.object(trial, "inspect_shell_initrd", return_value={"bash": BASH}), \
                        mock.patch.object(trial, "LOCK_PATH", root / "lock"), mock.patch.object(trial, "PrivateSession", return_value=s), \
                        mock.patch.object(trial, "await_initrd_ready", return_value=stage != "readiness"), \
                        mock.patch.object(trial, "run_probe_protocol", side_effect=fast_probe), \
                        mock.patch.dict(sys.modules, {"serial": mock.Mock()}), mock.patch("sys.stderr"):
                    self.assertFalse(trial.run_trial(root / "manifest", root / "log", root / "result", "minimal", bundle, root / "report", same_image_shell_pid1=True))
                result = json.loads((root / "result").read_text())
                self.assertEqual(result["status"], "recovery-required-unknown-no-reboot-requested")
                self.assertIsNone(result["normal_recovery"]); self.assertFalse(result["reboot_marker_observed"])
                self.assertNotIn(b"/bin/reboot", b"\n".join(s.writes))
                self.assertEqual(len([path for path, _ in s.uploads if path.endswith(".py")]), 1)
                if stage == "readiness": self.assertTrue(s.writes[-1].startswith(b"bootm"))
                else: self.assertIn(b"SHELL_PID1_BEGIN", s.writes[-1])


if __name__ == "__main__": unittest.main()
