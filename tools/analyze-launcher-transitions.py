#!/usr/bin/env python3
"""Summarize CPU-side launcher transition metrics; never presentation timing."""

import argparse
import math
import statistics
import tempfile
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Record:
    values: dict[str, int]


def parse(path: Path) -> tuple[list[Record], list[str]]:
    records: list[Record] = []
    ignored: list[str] = []
    for number, line in enumerate(path.read_text().splitlines(), 1):
        if not line.startswith("transition "):
            if line.strip():
                ignored.append(f"{number}: not a transition record")
            continue
        values: dict[str, int] = {}
        try:
            for field in line.split()[1:]:
                key, value = field.split("=", 1)
                values[key] = int(value)
            required = {"render_wall_ms", "release_to_submit_wall_ms", "release_to_submit_cpu_ms",
                        "extra_bytes", "buffers", "settled", "page", "overview", "direction"}
            if not required.issubset(values):
                raise ValueError("missing " + ",".join(sorted(required - values.keys())))
        except ValueError as error:
            ignored.append(f"{number}: {error}")
            continue
        records.append(Record(values))
    return records, ignored


def percentile(values: list[int], fraction: float) -> int:
    return sorted(values)[max(0, math.ceil(len(values) * fraction) - 1)]


def metric_summary(label: str, values: list[int]) -> str:
    return (f"{label}: median={statistics.median(values):g}ms "
            f"p95={percentile(values, .95)}ms max={max(values)}ms")


def alternating_error(records: list[Record], expected: int) -> str | None:
    apps = [record for record in records if record.values["settled"] == 1 and record.values["overview"] == 0]
    if len(apps) != expected * 2:
        return f"expected {expected * 2} settled Apps transitions, found {len(apps)}"
    for index in range(expected):
        left, right = apps[index * 2:index * 2 + 2]
        if (left.values["direction"], left.values["page"], right.values["direction"], right.values["page"]) != (0, 1, 1, 0):
            return (f"pair {index + 1} is direction/page "
                    f"{left.values['direction']}/{left.values['page']} then "
                    f"{right.values['direction']}/{right.values['page']}, expected 0/1 then 1/0")
    return None


def report(records: list[Record], expect_alternating: int | None) -> tuple[str, int]:
    if not records:
        return "no valid transition metrics\n", 1
    settled = [record for record in records if record.values["settled"] == 1]
    candidates = settled or records
    wall = [record.values["release_to_submit_wall_ms"] for record in candidates]
    cpu = [record.values["release_to_submit_cpu_ms"] for record in candidates]
    overview = sum(record.values["overview"] == 1 for record in candidates)
    over_budget = sum(value > 200 for value in wall)
    text = [
        "Launcher transition metrics (CPU-side instrumentation; not scanout or presentation timing)",
        f"records={len(records)} settled={len(settled)} overview_settled={overview}",
        metric_summary("release-to-submit wall", wall),
        metric_summary("release-to-submit CPU", cpu),
        f"max_buffers={max(record.values['buffers'] for record in candidates)} "
        f"max_extra_bytes={max(record.values['extra_bytes'] for record in candidates)} "
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
    return "\n".join(text) + "\n", status


def self_test() -> int:
    def line(direction: int, page: int, *, overview: int = 0, wall: int = 80, cpu: int = 7,
             settled: int = 1) -> str:
        return ("transition render_wall_ms=4 release_to_submit_wall_ms=%d extra_bytes=5600000 "
                "settled=%d release_to_submit_cpu_ms=%d buffers=3 page=%d overview=%d direction=%d\n"
                % (wall, settled, cpu, page, overview, direction))
    with tempfile.TemporaryDirectory() as temp:
        path = Path(temp) / "metrics.txt"
        path.write_text(line(0, 1) + line(1, 0, wall=201) + line(2, 0, overview=1))
        records, ignored = parse(path)
        text, status = report(records, 1)
        assert not ignored and status == 0 and "release_wall_over_200ms=1" in text
        path.write_text(line(0, 1) + line(0, 1))
        records, _ = parse(path)
        assert report(records, 1)[1] == 1  # duplicate left, no matching right
        path.write_text(line(0, 1) + "transition settled=1\n")
        records, ignored = parse(path)
        assert len(records) == 1 and ignored
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
    records, ignored = parse(args.metrics)
    text, status = report(records, args.expect_alternating)
    print(text, end="")
    for message in ignored:
        print("ignored: " + message)
    return status


if __name__ == "__main__":
    raise SystemExit(main())
