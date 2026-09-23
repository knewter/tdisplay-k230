#!/usr/bin/env python3
"""Summarize CPU-side launcher transition metrics; never presentation timing."""

import argparse
import math
import statistics
import tempfile
from dataclasses import dataclass
from pathlib import Path

REQUIRED = {
    "render_wall_ms", "release_to_submit_wall_ms", "release_to_submit_cpu_ms",
    "extra_bytes", "buffers", "settled", "page", "overview", "direction",
}
CPU_FIELD = "release_to_submit_cpu_ms"


@dataclass(frozen=True)
class Record:
    values: dict[str, int | float]


def parse(path: Path) -> tuple[list[Record], list[str]]:
    records: list[Record] = []
    errors: list[str] = []
    for number, line in enumerate(path.read_text().splitlines(), 1):
        if not line.startswith("transition "):
            if line.strip():
                errors.append(f"{number}: not a transition record")
            continue
        values: dict[str, int | float] = {}
        try:
            for field in line.split()[1:]:
                key, value = field.split("=", 1)
                values[key] = float(value) if key == CPU_FIELD else int(value)
            missing = REQUIRED - values.keys()
            if missing:
                raise ValueError("missing " + ",".join(sorted(missing)))
            cpu = values[CPU_FIELD]
            if not math.isfinite(cpu) or cpu < 0:
                raise ValueError("release_to_submit_cpu_ms must be finite and non-negative")
            for key in REQUIRED - {CPU_FIELD}:
                if values[key] < 0:
                    raise ValueError(f"{key} must be non-negative")
            if values["settled"] not in (0, 1) or values["overview"] not in (0, 1):
                raise ValueError("settled and overview must be 0 or 1")
            if values["direction"] not in (0, 1, 2, 3):
                raise ValueError("direction must be 0, 1, 2, or 3")
        except (ValueError, TypeError) as error:
            errors.append(f"{number}: {error}")
            continue
        records.append(Record(values))
    return records, errors


def percentile(values: list[int | float], fraction: float) -> int | float:
    return sorted(values)[max(0, math.ceil(len(values) * fraction) - 1)]


def metric_summary(label: str, values: list[int | float]) -> str:
    return (f"{label}: median={statistics.median(values):g}ms "
            f"p95={percentile(values, .95):g}ms max={max(values):g}ms")


def alternating_error(records: list[Record], expected: int) -> str | None:
    apps = [record for record in records if record.values["settled"] == 1 and record.values["overview"] == 0]
    if len(apps) != expected * 2:
        return f"expected {expected * 2} settled Apps transitions, found {len(apps)}"
    for index in range(expected):
        left, right = apps[index * 2:index * 2 + 2]
        actual = (left.values["direction"], left.values["page"], right.values["direction"], right.values["page"])
        if actual != (0, 1, 1, 0):
            return f"pair {index + 1} is direction/page {actual[0]}/{actual[1]} then {actual[2]}/{actual[3]}, expected 0/1 then 1/0"
    return None


def report(records: list[Record], expect_alternating: int | None) -> tuple[str, int]:
    if not records:
        return "no valid transition metrics\n", 1
    settled = [record for record in records if record.values["settled"] == 1]
    if not settled:
        return f"records={len(records)} settled=0: FAIL: no completed transition\n", 1
    wall = [record.values["release_to_submit_wall_ms"] for record in settled]
    cpu = [record.values[CPU_FIELD] for record in settled]
    overview = sum(record.values["overview"] == 1 for record in settled)
    over_budget = sum(value > 200 for value in wall)
    text = [
        "Launcher transition metrics (CPU-side instrumentation; not scanout or presentation timing)",
        f"records={len(records)} settled={len(settled)} overview_settled={overview}",
        metric_summary("release-to-submit wall", wall),
        metric_summary("release-to-submit CPU", cpu),
        f"max_buffers={max(record.values['buffers'] for record in records)} "
        f"max_extra_bytes={max(record.values['extra_bytes'] for record in records)} "
        f"release_wall_over_200ms={over_budget}",
    ]
    status = 0
    if expect_alternating is not None:
        error = alternating_error(records, expect_alternating)
        if error:
            text.append("Apps alternation: FAIL: " + error)
            status = 1
        else:
            text.append(f"Apps alternation: PASS: {expect_alternating} left/page1 then right/page0 pairs")
        if over_budget:
            text.append("Budget: FAIL: at least one settled transition exceeded 200ms")
            status = 1
    return "\n".join(text) + "\n", status


def self_test() -> int:
    def line(direction: int, page: int, *, overview: int = 0, wall: int = 80, cpu: float = 7.125,
             settled: int = 1, buffers: int = 3, extra: int = 5600000) -> str:
        return ("transition render_wall_ms=4 release_to_submit_wall_ms=%d extra_bytes=%d "
                "settled=%d release_to_submit_cpu_ms=%.3f buffers=%d page=%d overview=%d direction=%d\n"
                % (wall, extra, settled, cpu, buffers, page, overview, direction))
    with tempfile.TemporaryDirectory() as temp:
        path = Path(temp) / "metrics.txt"
        path.write_text(line(0, 1, buffers=5, extra=7000000, settled=0) + line(0, 1) + line(1, 0) + line(2, 0, overview=1))
        records, errors = parse(path)
        text, status = report(records, 1)
        assert not errors and status == 0 and "median=7.125ms" in text
        assert "max_buffers=5 max_extra_bytes=7000000" in text
        path.write_text(line(0, 1) + line(1, 0, wall=201))
        records, errors = parse(path)
        assert not errors and report(records, 1)[1] == 1  # over budget fails checked acceptance
        path.write_text(line(0, 1) + line(0, 1))
        records, _ = parse(path)
        assert report(records, 1)[1] == 1  # duplicate left, no matching right
        path.write_text(line(0, 1, settled=0))
        records, _ = parse(path)
        assert report(records, None)[1] == 1  # intermediate frames are not completion
        path.write_text(line(0, 1) + "transition settled=1\n")
        records, errors = parse(path)
        assert len(records) == 1 and errors
    print("launcher transition analyzer synthetic fixtures: ok")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("metrics", type=Path, nargs="?", help="K230_LAUNCHER_METRICS text file")
    parser.add_argument("--expect-alternating", type=int, metavar="N",
                        help="require exactly N settled Apps left/page1 then right/page0 pairs")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        return self_test()
    if not args.metrics:
        parser.error("metrics is required unless --self-test is used")
    if args.expect_alternating is not None and args.expect_alternating < 0:
        parser.error("--expect-alternating must be non-negative")
    records, errors = parse(args.metrics)
    text, status = report(records, args.expect_alternating)
    print(text, end="")
    for message in errors:
        print("invalid: " + message)
    return 1 if errors else status


if __name__ == "__main__":
    raise SystemExit(main())
