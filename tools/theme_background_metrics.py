"""Bounded shell/decoder resource sampler for the private theme board trial.

The two named systemd cgroups include Sway and the Rust shell; a decoder
spawned by the Rust shell stays in shell-ui.service. These are process and
cgroup measurements, not a presentation or panel-photon measurement.
"""
from __future__ import annotations

from pathlib import Path
import time


UNITS = ("shell.service", "shell-ui.service")
MAX_PIDS = 64


def _bounded_text(path: Path, limit: int) -> str:
    with path.open("rb") as stream:
        data = stream.read(limit + 1)
    if len(data) > limit:
        raise ValueError("oversized resource counter")
    return data.decode("ascii")


def _integer(path: Path) -> int:
    text = _bounded_text(path, 64)
    value = int(text.strip())
    if value < 0:
        raise ValueError("negative cgroup counter")
    return value


def _cpu_usec(path: Path) -> int:
    rows = dict(line.split(None, 1) for line in _bounded_text(path / "cpu.stat", 4096).splitlines())
    value = int(rows["usage_usec"])
    if value < 0:
        raise ValueError("negative CPU counter")
    return value


def _rss_bytes(proc: Path, pids: set[int]) -> tuple[int, bool]:
    total = 0
    complete = True
    for pid in pids:
        try:
            status = _bounded_text(proc / str(pid) / "status", 65536)
            value = next(line.split()[1] for line in status.splitlines() if line.startswith("VmRSS:"))
            total += int(value) * 1024
        except (OSError, StopIteration, ValueError):
            complete = False  # A process may exit between cgroup and /proc reads.
    return total, complete


def snapshot(cgroup_root: Path = Path("/sys/fs/cgroup/system.slice"),
             proc_root: Path = Path("/proc")) -> dict:
    cpu = memory = 0
    pids: set[int] = set()
    units: dict[str, tuple[int, int, int]] = {}
    for unit in UNITS:
        group = cgroup_root / unit
        identity = group.stat()
        unit_cpu = _cpu_usec(group)
        units[unit] = (identity.st_dev, identity.st_ino, unit_cpu)
        cpu += unit_cpu
        memory += _integer(group / "memory.current")
        listed = [int(value) for value in _bounded_text(group / "cgroup.procs", 1024).split()]
        if len(listed) > MAX_PIDS or any(pid <= 0 for pid in listed):
            raise ValueError("unexpected cgroup process count")
        final_identity = group.stat()
        if (identity.st_dev, identity.st_ino) != (final_identity.st_dev, final_identity.st_ino):
            raise ValueError(f"{unit} cgroup was recreated during resource snapshot")
        pids.update(listed)
    if not pids or len(pids) > MAX_PIDS:
        raise ValueError("shell cgroups have no bounded process set")
    rss, complete = _rss_bytes(proc_root, pids)
    return {"cpu_usage_usec": cpu, "cgroup_memory_bytes": memory,
            "process_rss_bytes": rss, "rss_complete": complete,
            "process_count": len(pids), "unit_counters": units}


def measure(duration_s: float = 8.0, interval_s: float = 0.25, *,
            cgroup_root: Path = Path("/sys/fs/cgroup/system.slice"),
            proc_root: Path = Path("/proc"), clock=time.monotonic,
            sleep=time.sleep) -> dict:
    if not (2.0 <= duration_s <= 60.0 and 0.1 <= interval_s <= 1.0):
        raise ValueError("background sample duration or interval exceeds bound")
    began = clock()
    samples = [snapshot(cgroup_root, proc_root)]
    while clock() - began < duration_s:
        sleep(min(interval_s, max(0.0, duration_s - (clock() - began))))
        samples.append(snapshot(cgroup_root, proc_root))
    elapsed = clock() - began
    for previous, current in zip(samples, samples[1:]):
        for unit in UNITS:
            old_dev, old_ino, old_cpu = previous["unit_counters"][unit]
            new_dev, new_ino, new_cpu = current["unit_counters"][unit]
            if (old_dev, old_ino) != (new_dev, new_ino):
                raise ValueError(f"{unit} cgroup was recreated during background sample")
            if new_cpu < old_cpu:
                raise ValueError(f"{unit} CPU counter regressed during background sample")
    delta = samples[-1]["cpu_usage_usec"] - samples[0]["cpu_usage_usec"]
    if elapsed <= 0 or delta < 0:
        raise ValueError("background sample clock or CPU counter regressed")
    if not all(s["rss_complete"] for s in samples):
        raise ValueError("background RSS process sample was incomplete")
    return {"units": list(UNITS), "elapsed_s": round(elapsed, 6),
            "sample_count": len(samples), "cpu_usage_usec": delta,
            "mean_cpu_cores": round(delta / 1_000_000 / elapsed, 4),
            "process_rss_peak_bytes": max(s["process_rss_bytes"] for s in samples),
            "rss_complete": all(s["rss_complete"] for s in samples),
            "cgroup_memory_peak_bytes": max(s["cgroup_memory_bytes"] for s in samples),
            "process_count_peak": max(s["process_count"] for s in samples),
            "limitations": "Sampled peaks can miss spikes; cgroup memory includes caches. "
                           "These counters do not prove decoded or presented frames."}
