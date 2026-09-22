#!/usr/bin/env python3
"""Encode sampled Grim PNG frames with host FFmpeg without inventing a frame rate."""

import argparse
import csv
import datetime as dt
import json
import pathlib
import re
import subprocess
import sys


def read_frames(sample_dir: pathlib.Path) -> list[dict[str, object]]:
    sample_dir = sample_dir.resolve()
    table = sample_dir / "frames.tsv"
    try:
        rows = list(csv.DictReader(table.open(newline=""), delimiter="\t"))
    except FileNotFoundError as error:
        raise ValueError(f"missing {table}") from error
    required = {"index", "start_monotonic_seconds", "end_monotonic_seconds", "file"}
    if not rows or set(rows[0]) != required:
        raise ValueError("frames.tsv must contain the sampler's four-column header and a frame")

    frames: list[dict[str, object]] = []
    previous_start = None
    for expected_index, row in enumerate(rows, start=1):
        try:
            index = int(row["index"])
            start = float(row["start_monotonic_seconds"])
            end = float(row["end_monotonic_seconds"])
        except ValueError as error:
            raise ValueError(f"invalid timestamp in frame {expected_index}") from error
        name = row["file"]
        path = sample_dir / name
        if (index != expected_index or pathlib.PurePath(name).name != name
                or not re.fullmatch(r"[A-Za-z0-9._-]+[.]png", name)):
            raise ValueError(f"invalid frame entry {expected_index}")
        if not path.is_file() or end < start or (previous_start is not None and start <= previous_start):
            raise ValueError(f"invalid frame timing or missing PNG for frame {expected_index}")
        frames.append({"index": index, "start": start, "end": end, "name": name, "path": path})
        previous_start = start
    return frames


def display_durations(frames: list[dict[str, object]]) -> list[float]:
    durations = []
    for current, following in zip(frames, frames[1:]):
        durations.append(round(float(following["start"]) - float(current["start"]), 6))
    # The last usable interval is the measured duration of its grim invocation.
    durations.append(round(float(frames[-1]["end"]) - float(frames[-1]["start"]), 6))
    return durations


def concat_text(frames: list[dict[str, object]], durations: list[float]) -> str:
    def quote(path: pathlib.Path) -> str:
        # ffconcat accepts backslash escapes inside single-quoted file names.
        return str(path).replace("\\", "\\\\").replace("'", "'\\''")

    lines = []
    for frame, duration in zip(frames, durations):
        lines.append(f"file '{quote(frame['path'])}'")
        # /proc/uptime records centiseconds. Without this image2 option, the
        # concat demuxer assumes 25 fps and rounds every timestamp to 40 ms.
        lines.append("option framerate 100")
        lines.append(f"duration {duration:.6f}")
    # ffmpeg's concat demuxer otherwise ignores the final duration.
    lines.append(f"file '{quote(frames[-1]['path'])}'")
    lines.append("option framerate 100")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("sample_dir", type=pathlib.Path)
    parser.add_argument("--output", type=pathlib.Path, required=True)
    parser.add_argument("--description", required=True)
    parser.add_argument("--provenance", choices=["real-touch", "injected", "unknown"], default="unknown")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    try:
        frames = read_frames(args.sample_dir)
    except ValueError as error:
        parser.error(str(error))
    durations = display_durations(frames)
    if any(duration <= 0 for duration in durations):
        parser.error("every rendered frame duration must be positive")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    concat = args.output.with_suffix(".concat.txt")
    concat.write_text(concat_text(frames, durations))
    ffmpeg = [
        "ffmpeg", "-hide_banner", "-loglevel", "warning", "-f", "concat", "-safe", "0",
        "-i", str(concat), "-fps_mode", "vfr", "-an", "-c:v", "libx264", "-pix_fmt",
        "yuv420p", "-movflags", "+faststart", "-y", str(args.output),
    ]
    captured_at = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    manifest = {
        "created_at": captured_at,
        "description": args.description,
        "artifact": {"path": str(args.output), "kind": "mp4-h264-yuv420p", "portrait_source": True},
        "capture_source": {
            "kind": "sampled-wayland-screencopy-png",
            "sample_directory": str(args.sample_dir),
            "frame_count": len(frames),
            "timestamps": "board /proc/uptime boot-relative monotonic seconds",
            "rendered_duration_seconds": sum(durations),
            "final_frame_codec_duration_note": (
                "The concat input repeats the final PNG so FFmpeg honors its measured "
                "duration. At its 100 fps input timebase, the MP4 may extend by 0.01 "
                "seconds beyond the measured display duration."
            ),
        },
        "frames": [
            {"index": frame["index"], "file": frame["name"],
             "capture_start_monotonic_seconds": frame["start"],
             "capture_end_monotonic_seconds": frame["end"],
             "display_duration_seconds": duration}
            for frame, duration in zip(frames, durations)
        ],
        "interaction_provenance": args.provenance,
        "evidence_note": "This is sampled Wayland screencopy. It does not demonstrate smoothness, frame rate, compositor performance, or prove real touch.",
        "ffmpeg_command": ffmpeg,
        "dry_run": args.dry_run,
    }
    manifest_path = args.output.with_suffix(".json")
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"concat: {concat}")
    print(f"manifest: {manifest_path}")
    print("command:", " ".join(ffmpeg))
    if args.dry_run:
        return 0
    try:
        subprocess.run(ffmpeg, check=True)
    except FileNotFoundError:
        print("ffmpeg was not found on PATH", file=sys.stderr)
        return 127
    except subprocess.CalledProcessError as error:
        return error.returncode
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
