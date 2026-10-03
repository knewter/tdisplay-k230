import hashlib
import gzip
import importlib.util
import io
import json
from pathlib import Path
import struct
import shutil
import shlex
import subprocess
import sys
import tempfile
from contextlib import contextmanager
from types import SimpleNamespace
import unittest
from unittest import mock
import zlib

try:
    from compression import zstd as host_zstd
except ImportError:
    host_zstd = None

SPEC = importlib.util.spec_from_file_location("uart_observer", Path(__file__).parents[1] / "tools/mainline-drm-uart-observer-trial.py")
t = importlib.util.module_from_spec(SPEC); SPEC.loader.exec_module(t)
NONCE = "a" * 32
FROM = "11111111-1111-1111-1111-111111111111"
BOOT = "22222222-2222-2222-2222-222222222222"
SELECTED = "/nix/store/" + "a" * 32 + "-candidate"
ARGS = "bootargs=console=ttyS0,115200n8 root=fstab loglevel=4 loglevel=7 init=" + SELECTED + "/init\n"
DUAL_ARGS = ARGS.replace("console=ttyS0,115200n8", "console=tty0 consoleblank=0 console=ttyS0,115200n8")
BANNER = b"[    0.0] Linux version 7.3.0-rc5 test\nsystemd 261.2 running\n"
PROMPT = b"\x1b[?2004hsh-5.3# "
NORMAL = b"\nU-Boot SPL 2022.10\n[    0.0] Linux version 6.6.36 vendor\nnixos login: root\nroot@nixos:~# "


class Clock:
    def __init__(self, step=.1): self.n = 0; self.step = step
    def __call__(self): self.n += self.step; return self.n


def properties(stage):
    if stage == "ready": return dict(boot_id=BOOT, shell_pid="55", guards="1", window_ms="12000")
    if stage == "return": return dict(boot_id=BOOT, shell_pid="55", guards="1", reboot="1")
    if stage == "failed": return dict(phase="renew", reason="guard")
    return {k: stage if k == "sample" else "active" if k == "runtime" else "00000000" if k.endswith("flag") else "0" for k in sorted(t.SAMPLE_FIELDS)}


def frame(stage, *, seq=None, nonce=NONCE, fields=None, timestamp=True):
    seq = t.STAGES.index(stage) if seq is None else seq
    raw = "".join(k + "=" + v + "\n" for k, v in (fields or properties(stage)).items()).encode()
    prefix = b"[    4.250000] " if timestamp else b""
    return prefix + f"K230_UOBS_V1 {nonce} {seq} {stage} {len(raw)} {zlib.crc32(raw):08x} ".encode() + raw.hex().encode() + b"\n"


def ready(): return BANNER + frame("ready") + frame("before") + PROMPT


class Session:
    pump = t.rd.PrivateSession.pump
    def __init__(self, chunks, *, ack=True, return_output=None):
        self.chunks = list(chunks); self.buffer = b""; self.log = io.BytesIO(); self.writes = []; self.closed = False
        self.ack = ack
        self.return_output = return_output if return_output is not None else b"\n" + frame("after") + frame("return") + NORMAL
        self.port = SimpleNamespace(read=self.read)
    def read(self, n): return self.chunks.pop(0) if self.chunks else b""
    def write(self, value):
        self.writes.append(value)
        if value == t.receipt_command(NONCE):
            ack = f"\nK230_UOBS_RX {NONCE}\n".encode() if self.ack else b""
            self.chunks += [ack + self.return_output]
    def close(self): self.closed = True


class ProtocolTests(unittest.TestCase):
    def test_complete_real_pump_split_frames_one_receipt_and_normal(self):
        wire = ready()
        s = Session([wire[:53], wire[53:300], wire[300:]])
        facts = t.monitor(s, NONCE, FROM, clock=Clock())
        self.assertTrue(facts["passed"])
        self.assertEqual(s.writes, [t.receipt_command(NONCE)])
        self.assertEqual([p["stage"] for p in facts["frames"]], list(t.STAGES))
        self.assertTrue(facts["normal_prompt_observed"])
        self.assertIn(b"K230_UOBS_V1", s.log.getvalue())
        self.assertNotIn("reboot", b"".join(s.writes).decode())

    def test_missing_receipt_preserves_observer_and_recovered_failure(self):
        s = Session([ready()], ack=False)
        facts = t.monitor(s, NONCE, FROM, clock=Clock())
        self.assertFalse(facts["passed"])
        self.assertTrue(facts["observer_complete"])
        self.assertTrue(facts["normal_prompt_observed"])
        self.assertFalse(facts["receipt_acknowledged"])
        self.assertEqual(len(s.writes), 1)

    def test_stale_echo_duplicate_and_premature_receipt_cannot_pass(self):
        stale = b"\nK230_UOBS_RX " + b"b" * 32 + b"\n"
        echoed = t.receipt_command(NONCE) + b"\n"
        duplicate = f"\nK230_UOBS_RX {NONCE}\nK230_UOBS_RX {NONCE}\n".encode()
        for output in (stale, echoed, duplicate):
            s = Session([ready()], ack=False, return_output=output + frame("after") + frame("return") + NORMAL)
            facts = t.monitor(s,NONCE,FROM,clock=Clock())
            self.assertFalse(facts["passed"]); self.assertTrue(facts["normal_prompt_observed"]); self.assertEqual(len(s.writes),1)
        s = Session([BANNER + frame("ready") + frame("before") + f"K230_UOBS_RX {NONCE}\n".encode() + PROMPT + NORMAL])
        self.assertFalse(t.monitor(s,NONCE,FROM,clock=Clock())["passed"]); self.assertEqual(s.writes,[])

    def test_primary_prompt_after_observer_window_never_receives_input(self):
        s = Session([BANNER + frame("ready") + frame("before")] + [b""] * 8 + [PROMPT + b"\n" + frame("after") + frame("return") + NORMAL])
        facts = t.monitor(s,NONCE,FROM,clock=Clock(step=1))
        self.assertFalse(facts["passed"]); self.assertTrue(facts["normal_prompt_observed"]); self.assertEqual(s.writes,[])

    def test_no_ready_or_prompt_never_sends_and_retains_early_return(self):
        for wire in (NORMAL, b"Linux version garbled\n" + NORMAL, BANNER + NORMAL, BANNER + frame("ready") + frame("before") + NORMAL,
                     BANNER + frame("ready") + PROMPT + NORMAL):
            s = Session([wire])
            with self.subTest(wire=wire[:30]):
                facts = t.monitor(s, NONCE, FROM, clock=Clock())
                self.assertFalse(facts["passed"])
                self.assertTrue(facts["normal_prompt_observed"])
                self.assertEqual(s.writes, [])

    def test_no_input_before_before_or_premanager_prompt(self):
        for prefix in (PROMPT + BANNER, b"Linux version 7.3.0-rc5 test\n" + PROMPT + b"\nsystemd 261.2\n",
                       b"Linux version 7.3.0-rc5 test\nsystemd 261.20\n" + PROMPT):
            s = Session([prefix + frame("ready") + frame("before") + NORMAL])
            facts = t.monitor(s, NONCE, FROM, clock=Clock())
            self.assertFalse(facts["readiness_observed"]); self.assertEqual(s.writes, [])

    def test_boot_status_after_prompt_still_receives_once(self):
        s = Session([ready() + b"[    5.1] boot status\n"])
        self.assertTrue(t.monitor(s, NONCE, FROM, clock=Clock())["passed"])
        self.assertEqual(len(s.writes), 1)

    def test_duplicate_stale_out_of_order_and_failed_frames_never_enable_input(self):
        for records in (frame("ready") * 2 + frame("before"), frame("ready", nonce="b" * 32) + frame("before"),
                        frame("before") + frame("ready"), frame("failed", seq=0)):
            s = Session([BANNER + records + PROMPT + NORMAL])
            facts = t.monitor(s, NONCE, FROM, clock=Clock())
            self.assertFalse(facts["passed"]); self.assertEqual(s.writes, [])

    def test_malformed_length_crc_and_interleaving_fail_closed(self):
        original = frame("ready")
        parts = original.split(b" ")
        for wire in (original[:-2] + b"f\n", original.replace(b" ready ", b" ready 999"),
                     original[:-15] + b"[    5.0] printk\n" + original[-15:],
                     original.replace(b"K230_UOBS_V1", b"K230_UOBS_V1garbled")):
            s = Session([BANNER + wire + frame("before") + PROMPT + NORMAL])
            self.assertFalse(t.monitor(s, NONCE, FROM, clock=Clock())["passed"])
            self.assertEqual(s.writes, [])
        with self.assertRaises(t.Invalid): t.decode_frame(original.replace(parts[-2], b"ffffffff", 1), NONCE)

    def test_changed_identity_and_invalid_sample_fields_stop_one_input(self):
        for stage, key, value in (("ready", "boot_id", FROM), ("ready", "guards", "0"), ("ready", "shell_pid", "1"),
                                  ("before", "rx", "-1"), ("before", "cflag", "FFFFFFFF"), ("before", "irq_total", "1")):
            fields = properties(stage); fields[key] = value
            wire = BANNER + (frame("ready", fields=fields) if stage == "ready" else frame("ready") + frame("before", fields=fields)) + PROMPT + NORMAL
            s = Session([wire]); self.assertFalse(t.monitor(s, NONCE, FROM, clock=Clock())["passed"])
            self.assertEqual(s.writes, [])
        fields = properties("return"); fields["shell_pid"] = "56"
        s = Session([ready()], return_output=b"\n" + frame("after") + frame("return", fields=fields) + NORMAL)
        self.assertFalse(t.monitor(s, NONCE, FROM, clock=Clock())["passed"]); self.assertEqual(len(s.writes), 1)

    def test_missing_return_timeout_and_transport_failure_preserve_partial_facts(self):
        s = Session([ready()], return_output=b"\n" + frame("after"))
        facts = t.monitor(s, NONCE, FROM, clock=Clock(step=1))
        self.assertFalse(facts["normal_prompt_observed"])
        self.assertEqual(len(facts["frames"]), 3); self.assertEqual(len(s.writes), 1)
        s = Session([ready()]); s.return_output = b""
        original = s.read
        def read(n):
            if s.writes: raise OSError("disconnect")
            return original(n)
        s.port.read = read
        facts = t.monitor(s, NONCE, FROM, clock=Clock())
        self.assertEqual(len(facts["frames"]), 2)
        self.assertIn("transport failed", facts["failure"])

    def test_overflow_rolling_buffer_and_incomplete_line_fail_without_reboot(self):
        for chunks in ([BANNER, b"x\n" * (t.STREAM_LIMIT // 2), frame("ready") + frame("before") + PROMPT + NORMAL],
                       [BANNER, b"x" * 1200 + b"\n", frame("ready") + frame("before") + PROMPT + NORMAL]):
            s = Session(chunks); facts = t.monitor(s, NONCE, FROM, clock=Clock())
            self.assertFalse(facts["passed"]); self.assertEqual(s.writes, [])
        s = Session([BANNER, b"unrelated printk\n" * 9000, frame("ready") + frame("before") + PROMPT])
        facts = t.monitor(s, NONCE, FROM, clock=Clock())
        # A rolling transport buffer must not lose the observed candidate phase.
        self.assertTrue(facts["passed"]); self.assertEqual(len(s.writes), 1)

    def test_normal_requires_order_and_record_before_recovery(self):
        for wire in (b"Linux version 6.6.36 vendor\nnixos login: root\nroot@nixos:~# ",
                     b"Linux version 6.6.36 vendor\nU-Boot SPL 2022.10\nnixos login: root\nroot@nixos:~# "):
            s = Session([ready()], return_output=b"\n" + frame("after") + frame("return") + wire)
            self.assertFalse(t.monitor(s, NONCE, FROM, clock=Clock(step=1))["normal_prompt_observed"])
        s = Session([BANNER + b"U-Boot SPL 2022.10\n" + frame("ready") + frame("before") + PROMPT + NORMAL])
        self.assertFalse(t.monitor(s, NONCE, FROM, clock=Clock())["passed"]); self.assertEqual(s.writes, [])

    def test_invalid_timeouts_and_bootarg_conflicts_before_input(self):
        for timeout in (0, -1, float("nan"), float("inf"), 181):
            s = Session([])
            with self.assertRaises(ValueError): t.monitor(s, NONCE, FROM, ready_timeout=timeout)
            self.assertEqual(s.writes, [])
        for arg in ("rdinit=/bin/sh", "clk_ignore_unused", "initcall_debug", "rd.systemd.unit=basic.target", "k230.uobs.nonce=" + NONCE):
            with self.assertRaises(ValueError): t.bootargs(ARGS.rstrip() + " " + arg, SELECTED, NONCE, FROM)
        expected = t.bootargs(ARGS, SELECTED, NONCE, FROM)
        self.assertNotIn("rdinit=", expected); self.assertEqual(expected.count("k230.uobs.nonce="), 1)


class RunTests(unittest.TestCase):
    def run_fixture(self, *, ack=True, recovered=True, prepare_failure=False, serial_console_only=False, sbi_boot_console=False):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); root.chmod(0o700)
            args = SimpleNamespace(bundle=Path(SELECTED), manifest=root / "manifest", normal_report=root / "normal", blkid_result=root / "blkid", log=root / "wire", result=root / "result",serial_console_only=serial_console_only,sbi_boot_console=sbi_boot_console)
            s = Session([ready()], ack=ack, return_output=None if recovered else b"\n" + frame("after"))
            s.chunks.insert(0, b"root@nixos:~# ")
            p = {"bundle": args.bundle, "system": SELECTED, "observer": {}, "initrd_inspection": {}, "normal": {"boot_id": FROM}, "original_bootargs": DUAL_ARGS if serial_console_only else ARGS, "helper_text": ""}
            factory = mock.Mock(side_effect=lambda serial, log: setattr(s, "log", log) or s)
            def checks(session, prepared, normal, mode): return {"boot_id": FROM if mode == "preflight" else "33333333-3333-3333-3333-333333333333"}
            with mock.patch.object(t, "prepare", side_effect=ValueError("bad manifest") if prepare_failure else lambda *a, **kw: p), mock.patch.object(t.rd, "PrivateSession", factory), mock.patch.object(t.rd, "LOCK_PATH", str(root / "lock")), mock.patch.object(t, "boot"), mock.patch.object(t.system, "normal_check", side_effect=checks) as check, mock.patch.object(t.uuid, "uuid4", return_value=SimpleNamespace(hex=NONCE)), mock.patch.dict(sys.modules, {"serial": SimpleNamespace()}), mock.patch.object(t, "monitor", wraps=lambda session, nonce, before: original_monitor(session, nonce, before, clock=Clock(step=1))):
                passed = t.run(args)
            value = json.loads(args.result.read_text())
            self.assertEqual(args.result.stat().st_mode & 0o777, 0o600)
            if not prepare_failure: self.assertEqual(args.log.stat().st_mode & 0o777, 0o600)
            return passed, value, s.writes, factory.call_count, [c.args[3] for c in check.call_args_list]

    def test_run_success_uses_protected_postflight_after_single_receipt(self):
        passed, value, writes, opened, checks = self.run_fixture()
        self.assertTrue(passed); self.assertEqual(value["status"], "recovery-verified-diagnostic-passed")
        self.assertEqual(writes, [b"\r", t.receipt_command(NONCE)]); self.assertEqual(checks, ["preflight", "postflight"])

    def test_run_comparison_records_selector_and_exact_fresh_argument_selection(self):
        passed,value,writes,opened,checks=self.run_fixture(serial_console_only=True)
        self.assertTrue(passed);self.assertTrue(value["serial_console_only"])
        self.assertEqual(value["expected_bootargs"],t.bootargs(DUAL_ARGS,SELECTED,NONCE,FROM,serial_console_only=True))
        self.assertNotIn("console=tty0",value["expected_bootargs"])
        self.assertEqual(writes,[b"\r",t.receipt_command(NONCE)])

    def test_run_missing_receipt_recovers_but_does_not_pass(self):
        passed, value, writes, opened, checks = self.run_fixture(ack=False)
        self.assertFalse(passed); self.assertEqual(value["status"], "recovery-verified-diagnostic-failed")
        self.assertEqual(checks, ["preflight", "postflight"]); self.assertEqual(len(writes), 2)

    def test_run_sbi_comparison_records_both_selectors_and_fresh_arguments(self):
        passed,value,writes,opened,checks=self.run_fixture(serial_console_only=True,sbi_boot_console=True)
        self.assertTrue(passed);self.assertTrue(value["serial_console_only"]);self.assertTrue(value["sbi_boot_console"])
        self.assertEqual(value["expected_bootargs"],t.bootargs(DUAL_ARGS,SELECTED,NONCE,FROM,serial_console_only=True,sbi_boot_console=True))
        self.assertEqual(writes,[b"\r",t.receipt_command(NONCE)])

    def test_run_unknown_return_never_postflight_or_additional_input(self):
        passed, value, writes, opened, checks = self.run_fixture(recovered=False)
        self.assertFalse(passed); self.assertEqual(value["status"], "recovery-required-unknown")
        self.assertEqual(checks, ["preflight"]); self.assertEqual(len(writes), 2)
        self.assertEqual(len(value["diagnostic"]["frames"]), 3)

    def test_prepare_failure_never_opens_serial(self):
        passed, value, writes, opened, checks = self.run_fixture(prepare_failure=True)
        self.assertFalse(passed); self.assertEqual(opened, 0); self.assertEqual(writes, [])
        self.assertEqual(value["status"], "not-started-no-serial-opened")


original_monitor = t.monitor


@unittest.skipUnless(shutil.which("dtc") and shutil.which("fdtput"), "host lacks dtc/fdtput; no actual DT proof")
class DtbTests(unittest.TestCase):
    def test_actual_host_dtb_only_bootarg_change_and_hardware_rejection(self):
        with tempfile.TemporaryDirectory(dir=Path.home() / "tmp") as directory:
            root = Path(directory)
            def compile(name, bootarg, reg):
                src = root / (name + ".dts"); dst = root / (name + ".dtb")
                src.write_text('/dts-v1/; / { chosen { bootargs="' + bootarg + '"; }; test { value=<' + str(reg) + '>; }; };')
                subprocess.run(["dtc", "-I", "dts", "-O", "dtb", "-o", str(dst), str(src)], check=True, capture_output=True)
                return dst
            base = compile("base", "base", 1); candidate = compile("candidate", "candidate", 1); bad = compile("bad", "candidate", 2)
            original = base.read_bytes(), candidate.read_bytes()
            self.assertTrue(t.dt_hardware_equal(base, candidate)); self.assertFalse(t.dt_hardware_equal(base, bad))
            self.assertEqual(original, (base.read_bytes(), candidate.read_bytes()))


def elf(machine=243, bits=2, endian=1):
    raw = bytearray(64); raw[:7] = b"\x7fELF" + bytes([bits, endian, 1]); raw[18:20] = machine.to_bytes(2, "little")
    return bytes(raw)


def cpio(records):
    archive = bytearray()
    for name, mode, body in records + [("TRAILER!!!", 0, b"")]:
        name = name.encode() + b"\0"
        fields = [0, mode, 0, 0, 1, 0, len(body), 0, 0, 0, 0, len(name), 0]
        archive += b"070701" + b"".join(f"{n:08x}".encode() for n in fields) + name
        archive += bytes(-len(archive) % 4); archive += body; archive += bytes(-len(archive) % 4)
    return gzip.compress(archive)


HELPER_PATH = "/nix/store/" + "a" * 32 + "-observer/bin/k230-uart-observer"
UNIT = b"[Service]\nExecStart=/bin/sh\nStandardInput=tty\nTTYReset=yes\nTTYVHangup=yes\nRestart=always\n"
ENV = 'Environment="LOCALE_ARCHIVE=/nix/store/' + 'b' * 32 + '-glibc-locales/lib/locale/locale-archive" "TZDIR=/nix/store/' + 'c' * 32 + '-tzdata/share/zoneinfo"\n'


def initrd_records(helper=HELPER_PATH, executable=None):
    dropin = "[Unit]\nConditionKernelCommandLine=k230.uobs.nonce\n\n[Service]\n" + ENV + "ExecStart=\nExecStart=" + helper + "\nRestart=no\n"
    return [("etc/systemd/system", 0o120777, b"/nix/store/units"),
            ("nix/store/units", 0o040755, b""),
            ("nix/store/units/debug-shell.service", 0o120777, b"/nix/store/systemd/debug-shell.service"),
            ("nix/store/systemd/debug-shell.service", 0o100444, UNIT),
            ("nix/store/units/debug-shell.service.d/overrides.conf", 0o120777, b"/nix/store/dropin/overrides.conf"),
            ("nix/store/dropin/overrides.conf", 0o100444, dropin.encode()),
            (helper.lstrip("/"), 0o100555, elf() if executable is None else executable),
            ("etc/k230-uobs-version", 0o100444, b"1\n")]


class InitrdTests(unittest.TestCase):
    @unittest.skipIf(host_zstd is None, "host Python lacks compression.zstd; no native Zstandard proof")
    def test_actual_zstd_archive_format_and_bound(self):
        wire = host_zstd.compress(gzip.decompress(cpio(initrd_records())))
        with mock.patch.object(t,"BASE_DEBUG_UNIT_SHA",hashlib.sha256(UNIT).hexdigest()):
            self.assertEqual(t.inspect_initrd(wire,HELPER_PATH,elf())["initrd_sha256"],hashlib.sha256(wire).hexdigest())
        with mock.patch.object(t,"ARCHIVE_LIMIT",100),self.assertRaises(ValueError): t.archive_entries(wire)

    def test_actual_newc_symlink_resolution_exact_helper_unit_and_dropin(self):
        compressed = cpio(initrd_records())
        with mock.patch.object(t, "BASE_DEBUG_UNIT_SHA", hashlib.sha256(UNIT).hexdigest()):
            result = t.inspect_initrd(compressed, HELPER_PATH, elf())
        self.assertEqual(result["helper_sha256"], hashlib.sha256(elf()).hexdigest())
        self.assertEqual(result["initrd_sha256"], hashlib.sha256(compressed).hexdigest())

    def test_missing_helper_bad_architecture_unit_or_dropin_rejected(self):
        for kind in ("missing", "elf32", "x86", "endian", "unit", "restart", "exec", "tty", "extra", "environment"):
            records = initrd_records()
            if kind == "missing": records = [r for r in records if r[0] != HELPER_PATH.lstrip("/")]
            elif kind in ("elf32", "x86", "endian"):
                bad = elf(bits=1) if kind == "elf32" else elf(machine=62) if kind == "x86" else elf(endian=2)
                records = [(n, m, bad if n == HELPER_PATH.lstrip("/") else b) for n, m, b in records]
            elif kind == "unit": records = [(n,m,b.replace(b"TTYVHangup=yes",b"TTYVHangup=no")) for n,m,b in records]
            else:
                change = {"restart": (b"Restart=no", b"Restart=always"), "exec": (b"ExecStart=\n", b""), "tty": (b"Restart=no", b"Restart=no\nTTYReset=no"), "extra": (b"Restart=no", b"Restart=no\nExecStart=/bin/sh"), "environment": (b"TZDIR=", b"BASH_ENV=")}[kind]
                records = [(n,m,b.replace(*change) if n.endswith("overrides.conf") else b) for n,m,b in records]
            with self.subTest(kind=kind), mock.patch.object(t, "BASE_DEBUG_UNIT_SHA", hashlib.sha256(UNIT).hexdigest()), self.assertRaises(ValueError):
                t.inspect_initrd(cpio(records), HELPER_PATH, elf())

    def test_duplicate_truncated_oversized_and_cyclic_archive_rejected(self):
        for wire in (cpio(initrd_records() + [initrd_records()[-1]]), gzip.compress(b"070701"), gzip.compress(b"bad")):
            with self.assertRaises(ValueError): t.archive_entries(wire)
        with mock.patch.object(t, "ARCHIVE_LIMIT", 100), self.assertRaises(ValueError): t.archive_entries(cpio(initrd_records()))
        entries = {"etc/systemd/system": (0o120777, b"/etc/systemd/system")}
        with self.assertRaises(ValueError): t.archive_resolve(entries, "/etc/systemd/system/debug-shell.service")


class BootTests(unittest.TestCase):
    def test_load_crc_and_printed_args_failure_never_boots_candidate(self):
        class BootSession:
            def __init__(self, fault): self.buffer=b""; self.writes=[]; self.commands=[]; self.fault=fault
            def line(self, cmd, interrupt=False): self.writes.append(cmd)
            def pump(self): self.buffer=t.rd.PROMPT; return self.buffer
            def write(self, data): self.writes.append(data)
            def command(self, cmd, timeout):
                self.commands.append(cmd)
                if cmd.startswith("ext4load"): return b"load"
                if cmd.startswith("crc32"): return b"crc"
                return b"args"
        p = {"manifest": {"files": {name: {"bytes":100,"crc32":"00000000"} for name, *rest in t.rd.LOADS}}, "original_bootargs": ARGS, "bootargs": t.bootargs(ARGS, SELECTED, NONCE, FROM)}
        for fault in ("load", "crc", "args", None):
            s=BootSession(fault)
            with mock.patch.object(t.rd, "verified_load", return_value=fault != "load"), mock.patch.object(t.rd, "verified_crc", return_value=fault != "crc"), mock.patch.object(t.rd, "verified_bootargs", return_value=fault != "args"):
                if fault:
                    with self.assertRaises(t.Invalid): t.boot(s,p,clock=Clock())
                    self.assertNotIn("bootm 0x8000000 0x9000000 0x8400000",s.writes)
                else:
                    t.boot(s,p,clock=Clock())
                    self.assertEqual(s.writes.count("bootm 0x8000000 0x9000000 0x8400000"),1)
                    self.assertEqual(sum(cmd.startswith("ext4load") for cmd in s.commands),5)
                    self.assertEqual(sum(cmd.startswith("crc32") for cmd in s.commands),5)


@contextmanager
def artifact_fixture(*, dual_console=False):
    with tempfile.TemporaryDirectory(dir=Path.home() / "tmp") as directory:
        root = Path(directory); store = root / "store"; store.mkdir()
        dirs = {name: store / (letter * 32 + "-" + name) for name, letter in (("observer","a"),("base-system","b"),("system","c"),("base","d"),("kernel","e"),("candidate","f"))}
        for d in dirs.values(): d.mkdir()
        helper = dirs["observer"] / "bin/k230-uart-observer"; helper.parent.mkdir(); helper.write_bytes(elf()); helper.chmod(0o555)
        source = root / "observer.c"; source.write_text("/* isolated reviewed fixture */\n")
        kernel = dirs["kernel"]; (kernel / "Image").write_bytes(b"proven-kernel")
        base, bundle, selected = dirs["base"], dirs["candidate"], dirs["system"]
        (base / "system").symlink_to(dirs["base-system"])
        (selected / "kernel").symlink_to(kernel / "Image")
        original = "bootargs=console=ttyS0,115200n8 root=fstab loglevel=4 loglevel=7 init=" + str(selected) + "/init\n"
        if dual_console:
            original=original.replace("console=ttyS0,115200n8","console=tty0 consoleblank=0 console=ttyS0,115200n8")
        (bundle / "bootargs.txt").write_text(original)
        for name, args in ((base,"base"),(bundle,original.removeprefix("bootargs=").rstrip())):
            src = root / (name.name + ".dts")
            src.write_text('/dts-v1/; / { chosen { bootargs="' + args + '"; }; test { value=<1>; }; };')
            subprocess.run(["dtc", "-I", "dts", "-O", "dtb", "-o", str(name / "k230-tdisplay-mainline-drm.dtb"), str(src)], check=True, capture_output=True)
            (name / "Image-mainline-drm").write_bytes(b"proven-kernel")
        compressed = cpio(initrd_records(str(helper), elf())); (selected / "initrd").write_bytes(compressed)
        header = bytearray(struct.pack(">7I4B32s",0x27051956,0,0,len(compressed),0,0,zlib.crc32(compressed),5,26,3,0,b"observer"))
        header[4:8] = zlib.crc32(header).to_bytes(4,"big"); (bundle / "initrd.uimg").write_bytes(header + compressed)
        (bundle / "store-paths").write_text("\n".join(map(str,(dirs["observer"],selected,kernel))) + "\n")
        sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
        metadata = {"schema":"k230-uart-observer-artifact-v1","protocol":"K230_UOBS_V1","helper":str(helper),"helper_sha256":sha(helper),"helper_source_sha256":sha(source),"system":str(selected),"init":str(selected)+"/init","kernel":str(kernel),"base_kernel":str(kernel),"base_bundle":str(base),"dtb_sha256":sha(bundle / "k230-tdisplay-mainline-drm.dtb"),"base_dtb_sha256":sha(base / "k230-tdisplay-mainline-drm.dtb"),"dtb_bootargs_only":True,"window_ms":12000,"payload_max":384}
        (bundle / "observer.json").write_text(json.dumps(metadata)); (bundle / "SHA256SUMS").write_text(sha(bundle / "observer.json") + "  observer.json\n")
        normal = {k:"normal-" + k for k in ("system","profile","kernel","uname","init")}; normal.update(boot_id=FROM,boot_files={"Image":{"sha256":"a"*64}})
        expected = {k:normal[k] for k in ("system","profile","kernel","uname","init")}; expected.update(services=["active"]*3,boot_files={"Image":"a"*64})
        prerequisite = {"schema":"mainline-initrd-blkid-v1","status":"recovery-verified-diagnostic-passed","candidate_bundle":str(base),"candidate_system":str(dirs["base-system"]),"diagnostic":{"passed":True,"retrieval":{"complete":True}},"reboot_marker_observed":True,"normal_recovery":dict(expected,boot_id=BOOT),"normal_preflight":{"boot_id":FROM}}
        p = {"bundle":bundle,"system":str(selected),"normal":normal,"helper_text":"_fixture_helper_reached=True\n","manifest":{"files":{"bootargs.txt":{"bytes":len(original.encode())}}}}
        for directory_path in (base, dirs["base-system"], dirs["observer"]): directory_path.chmod(0o555)
        (bundle / "observer.json").chmod(0o444)
        try:
            with mock.patch.object(t, "BASE_BUNDLE",base), mock.patch.object(t,"BASE_KERNEL",str(kernel)), mock.patch.object(t,"SOURCE_FILE",source), mock.patch.object(t,"BASE_DEBUG_UNIT_SHA",hashlib.sha256(UNIT).hexdigest()), mock.patch.object(t.rd,"STORE_ROOT",store), mock.patch.object(t.rd,"prepare_trial",side_effect=lambda *a: dict(p)), mock.patch.object(t.debug,"private_input",return_value=prerequisite):
                yield SimpleNamespace(root=root,bundle=bundle,helper=helper,source=source,selected=selected,prerequisite=prerequisite,metadata=metadata)
        finally:
            for d in dirs.values(): d.chmod(0o755)


@unittest.skipUnless(shutil.which("dtc") and shutil.which("fdtput") and shutil.which("fdtget"), "host lacks DT tools; no actual artifact preparation proof")
class PreparationTests(unittest.TestCase):
    def test_sbi_complete_preparation_retains_original_artifacts(self):
        with artifact_fixture(dual_console=True) as f:
            names=("bootargs.txt","k230-tdisplay-mainline-drm.dtb","initrd.uimg","Image-mainline-drm")
            before={name:(f.bundle/name).read_bytes() for name in names}
            p=t.prepare(f.bundle,f.root/"manifest",f.root/"normal",f.root/"blkid",NONCE,serial_console_only=True,sbi_boot_console=True)
            self.assertTrue(p["serial_console_only"]);self.assertTrue(p["sbi_boot_console"])
            self.assertTrue(p["bootargs"].endswith(" earlycon=sbi keep_bootcon"))
            self.assertNotIn("console=tty0",p["bootargs"])
            self.assertIn("initrd_inspection",p)
            self.assertEqual(before,{name:(f.bundle/name).read_bytes() for name in names})

    def test_complete_actual_preparation_proves_archive_elf_and_marker_guard(self):
        with artifact_fixture() as f:
            p = t.prepare(f.bundle,f.root / "manifest",f.root / "normal",f.root / "blkid",NONCE)
            self.assertIn("initrd_inspection",p); self.assertEqual(p["observer"]["helper_sha256"],hashlib.sha256(elf()).hexdigest())
            marker = f.root / "registration"
            code = p["helper_text"].replace("/nix-path-registration",str(marker))
            namespace={}; exec(code,namespace); self.assertTrue(namespace["_fixture_helper_reached"])
            marker.symlink_to(f.root / "missing")
            namespace={}
            with self.assertRaises(AssertionError): exec(code,namespace)
            self.assertNotIn("_fixture_helper_reached",namespace)

    def test_wrong_base_proof_source_binary_metadata_and_ramdisk_rejected(self):
        for fault in ("prerequisite","source","machine","metadata","checksum","ramdisk","closure"):
            with self.subTest(fault=fault), artifact_fixture() as f:
                if fault=="prerequisite": f.prerequisite["candidate_bundle"]=str(f.bundle)
                if fault=="source": f.source.write_text("different source")
                if fault=="machine": f.helper.chmod(0o755); f.helper.write_bytes(elf(machine=62)); f.helper.chmod(0o555)
                if fault=="metadata":
                    path=f.bundle / "observer.json"; path.chmod(0o644); changed=dict(f.metadata,payload_max=4096); path.write_text(json.dumps(changed)); path.chmod(0o444)
                if fault=="checksum": (f.bundle / "SHA256SUMS").write_text("0"*64 + "  observer.json\n")
                if fault=="ramdisk": (f.bundle / "initrd.uimg").write_bytes(b"truncated")
                if fault=="closure": (f.bundle / "store-paths").write_text(str(f.selected)+"\n")
                with self.assertRaises(ValueError): t.prepare(f.bundle,f.root / "manifest",f.root / "normal",f.root / "blkid",NONCE)


class SerialComparisonTests(unittest.TestCase):
    def prepared(self, comparison=False, sbi=False):
        return {"manifest":{"files":{name:{"bytes":100,"crc32":"00000000"} for name,*_ in t.rd.LOADS}}, "original_bootargs":DUAL_ARGS,
                "bootargs":t.bootargs(DUAL_ARGS,SELECTED,NONCE,FROM,serial_console_only=comparison,sbi_boot_console=sbi),"serial_console_only":comparison,"sbi_boot_console":sbi}

    def test_default_arguments_and_transport_remain_exactly_unchanged(self):
        expected = t.debug.bootargs(DUAL_ARGS,SELECTED) + f" k230.uobs.nonce={NONCE} k230.uobs.from={FROM} k230.uobs.init={SELECTED}/init"
        self.assertEqual(t.bootargs(DUAL_ARGS,SELECTED,NONCE,FROM),expected)
        extra=expected.removeprefix(DUAL_ARGS.rstrip()).lstrip()
        self.assertEqual(t.volatile_commands(self.prepared()),["env import -t 0x7000000 0x64",'setenv bootargs "${bootargs} '+extra+'"'])

    def test_comparison_deletes_only_one_token_and_preserves_all_controls(self):
        default=t.bootargs(DUAL_ARGS,SELECTED,NONCE,FROM)
        compared=t.bootargs(DUAL_ARGS,SELECTED,NONCE,FROM,serial_console_only=True)
        self.assertEqual(compared,default.replace("console=tty0 ","",1))
        tokens=compared.removeprefix("bootargs=").split()
        self.assertEqual([p for p in tokens if p.startswith("console=")],["console=ttyS0,115200n8"])
        self.assertIn("consoleblank=0",tokens)
        self.assertEqual(tokens.count("init="+SELECTED+"/init"),1)
        for control in t.debug.CONTROLS: self.assertEqual(tokens.count(control),1)
        for name in ("k230.uobs.nonce=","k230.uobs.from=","k230.uobs.init="):
            self.assertEqual(sum(p.startswith(name) for p in tokens),1)

    def test_missing_duplicate_or_other_console_forms_rejected(self):
        bad = (DUAL_ARGS.replace("console=tty0 ",""), DUAL_ARGS.replace("console=ttyS0,115200n8 ",""),
               DUAL_ARGS.replace("console=tty0","console=tty0 console=tty0"), DUAL_ARGS.replace("console=ttyS0,115200n8","console=ttyS0,115200n8 console=ttyS0,115200n8"),
               DUAL_ARGS.replace("console=tty0","console=tty1"), DUAL_ARGS.replace("console=ttyS0,115200n8","console=ttyS0,9600n8"),
               DUAL_ARGS.replace("console=tty0","console=tty0,115200"), DUAL_ARGS.replace("consoleblank=0","consoleblank=1"),
               DUAL_ARGS.replace("consoleblank=0","consoleblank=0 consoleblank=0"),DUAL_ARGS.replace("console=tty0","console"))
        for original in bad:
            with self.subTest(original=original),self.assertRaises(ValueError):
                t.bootargs(original,SELECTED,NONCE,FROM,serial_console_only=True)

    def test_sbi_adds_exact_two_tokens_to_serial_comparison(self):
        compared=t.bootargs(DUAL_ARGS,SELECTED,NONCE,FROM,serial_console_only=True)
        result=t.bootargs(DUAL_ARGS,SELECTED,NONCE,FROM,serial_console_only=True,sbi_boot_console=True)
        self.assertEqual(result,compared+" earlycon=sbi keep_bootcon")
        commands=t.volatile_commands(self.prepared(True,True))
        self.assertEqual(commands[:2],t.volatile_commands(self.prepared(True))[:2])
        self.assertEqual(commands[2],t.volatile_commands(self.prepared(True))[2][:-1]+" earlycon=sbi keep_bootcon\"")
        self.assertTrue(all(len(c.encode())<512 for c in commands))

    def test_sbi_requires_serial_only_before_artifact_or_serial_access(self):
        with self.assertRaises(ValueError):t.bootargs(DUAL_ARGS,SELECTED,NONCE,FROM,sbi_boot_console=True)
        with mock.patch.object(t.rd,"prepare_trial") as preparation,self.assertRaises(ValueError):
            t.prepare(Path(SELECTED),Path("manifest"),Path("normal"),Path("blkid"),NONCE,sbi_boot_console=True)
        preparation.assert_not_called()

    def test_sbi_rejects_preexisting_early_console_policy(self):
        for token in ("earlycon", "earlycon=sbi", "earlycon=uart8250,mmio32,0x91400000", "keep_bootcon", "keep_bootcon=0"):
            with self.subTest(token=token),self.assertRaises(ValueError):
                t.bootargs(DUAL_ARGS.rstrip()+" "+token,SELECTED,NONCE,FROM,serial_console_only=True,sbi_boot_console=True)

    def test_retained_console_duplicate_frames_still_send_zero_receipts(self):
        s=Session([BANNER+frame("ready")*2+frame("before")*2+PROMPT+NORMAL])
        facts=t.monitor(s,NONCE,FROM,clock=Clock())
        self.assertFalse(facts["passed"]);self.assertTrue(facts["normal_prompt_observed"])
        self.assertIn("duplicate",facts["failure"]);self.assertEqual(s.writes,[])

    def test_uboot_expansion_and_command_syntax_rejected_before_any_boot_input(self):
        for unsafe in ('"',"'","$x","${bootargs}","$(reboot)","`reboot`",";","\\", "\nreboot"):
            original=DUAL_ARGS.rstrip()+" unsafe="+unsafe
            with self.subTest(unsafe=unsafe),self.assertRaises(ValueError): t.bootargs(original,SELECTED,NONCE,FROM,serial_console_only=True)
        p=self.prepared(True);p["bootargs"]+=' $unsafe'
        s=SimpleNamespace(writes=[],line=lambda *a,**kw: self.fail("unsafe command sent"))
        with self.assertRaises(ValueError):t.boot(s,p,clock=Clock())

    def test_exact_comparison_transport_replacement_no_duplicate_and_print_gate(self):
        class UBoot:
            def __init__(self,mismatch=False):self.buffer=b"";self.writes=[];self.commands=[];self.args="";self.mismatch=mismatch
            def line(self,cmd,interrupt=False):self.writes.append(cmd)
            def write(self,data):self.writes.append(data)
            def pump(self):self.buffer=t.rd.PROMPT;return self.buffer
            def command(self,cmd,timeout):
                self.commands.append(cmd)
                if cmd.startswith("env import"):self.args=DUAL_ARGS.removeprefix("bootargs=").rstrip()
                elif cmd.startswith("setenv bootargs"):
                    parts=shlex.split(cmd);self.assert_parts=parts
                    self.args=parts[2].replace("${bootargs}",self.args)
                elif cmd=="printenv bootargs":return ("bootargs="+self.args+(" wrong=1" if self.mismatch else "")+"\nK230# ").encode()
                return t.rd.PROMPT
        for sbi,mismatch in ((False,False),(False,True),(True,False),(True,True)):
            p=self.prepared(True,sbi)
            s=UBoot(mismatch)
            with mock.patch.object(t.rd,"verified_load",return_value=True),mock.patch.object(t.rd,"verified_crc",return_value=True):
                if mismatch:
                    with self.assertRaises(t.Invalid):t.boot(s,p,clock=Clock())
                    self.assertNotIn("bootm 0x8000000 0x9000000 0x8400000",s.writes)
                else:
                    t.boot(s,p,clock=Clock());self.assertEqual(s.args,p["bootargs"].removeprefix("bootargs="))
                    self.assertEqual(s.writes.count("bootm 0x8000000 0x9000000 0x8400000"),1)
            expected=t.volatile_commands(p)
            self.assertEqual(s.commands[-4:],expected+["printenv bootargs"])
            self.assertTrue(all(len(c.encode())<512 for c in expected))


if __name__ == "__main__": unittest.main()
