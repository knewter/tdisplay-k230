#!/usr/bin/env python3
"""Capture one named board feature from a host V4L2 camera with FFmpeg.

The manifest records what the operator says the interaction source was. It is
provenance, not proof that a real finger activated anything in the footage.
"""

import argparse
import datetime as dt
import json
import pathlib
import re
import subprocess
import sys


def feature_name(value: str) -> str:
    name = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    if not name:
        raise argparse.ArgumentTypeError("feature name needs a letter or number")
    return name


def command(args: argparse.Namespace, output: pathlib.Path) -> list[str]:
    cmd = [
        "ffmpeg", "-hide_banner", "-loglevel", "warning", "-f", "v4l2",
        "-input_format", args.input_format, "-video_size", args.video_size,
        "-framerate", str(args.framerate), "-i", args.device,
    ]
    filters = []
    if args.rotate180:
        # Two clockwise transposes are a presentation transform. Leaving this
        # out preserves the camera's raw orientation.
        filters.append("transpose=2,transpose=2")
    if args.still:
        if filters:
            cmd += ["-vf", ",".join(filters)]
        return cmd + ["-frames:v", "1", "-q:v", "2", "-y", str(output)]
    # MJPEG cameras supply full-range pixels. Convert the range as well as
    # the pixel format so the H.264 output is ordinary limited-range yuv420p.
    filters.append("scale=out_range=tv")
    cmd += ["-vf", ",".join(filters)]
    return cmd + [
        "-t", str(args.duration), "-an", "-c:v", "libx264", "-pix_fmt",
        "yuv420p", "-color_range", "tv", "-preset", "veryfast", "-crf", "23",
        "-threads", "2", "-movflags", "+faststart", "-y", str(output),
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("feature", type=feature_name,
                        help="short feature name, e.g. keyboard-show")
    parser.add_argument("--device", default="/dev/video0", help="V4L2 camera device")
    parser.add_argument("--output-dir", type=pathlib.Path,
                        default=pathlib.Path("docs/evidence/video"))
    parser.add_argument("--duration", type=float, default=15,
                        help="clip duration in seconds (default: 15)")
    parser.add_argument("--still", action="store_true",
                        help="capture one JPEG instead of an MP4 clip")
    parser.add_argument("--rotate180", action="store_true",
                        help="rotate only the recorded presentation by 180 degrees")
    parser.add_argument("--input-format", default="mjpeg")
    parser.add_argument("--video-size", default="1280x720")
    parser.add_argument("--framerate", type=int, default=30)
    parser.add_argument("--provenance", choices=["real-touch", "injected", "unknown"],
                        default="unknown",
                        help="operator-declared interaction source; not proof")
    parser.add_argument("--description", required=True,
                        help="what the operator intends this recording to show")
    parser.add_argument("--dry-run", action="store_true",
                        help="write the manifest and print FFmpeg without opening the camera")
    args = parser.parse_args()
    if args.duration <= 0:
        parser.error("--duration must be positive")

    timestamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    suffix = ".jpg" if args.still else ".mp4"
    args.output_dir.mkdir(parents=True, exist_ok=True)
    artifact = args.output_dir / f"{timestamp}-{args.feature}{suffix}"
    manifest = artifact.with_suffix(".json")
    ffmpeg = command(args, artifact)
    metadata = {
        "captured_at": timestamp,
        "feature": args.feature,
        "description": args.description,
        "capture_source": {"device": args.device, "input_format": args.input_format,
                           "video_size": args.video_size, "framerate": args.framerate},
        "interaction_provenance": args.provenance,
        "provenance_note": "Operator-declared metadata does not prove that footage shows a real touch.",
        "artifact": {"path": str(artifact), "kind": "jpeg" if args.still else "mp4",
                     "duration_seconds": None if args.still else args.duration,
                     "presentation_rotation": 180 if args.rotate180 else 0},
        "ffmpeg_command": ffmpeg,
        "dry_run": args.dry_run,
    }
    manifest.write_text(json.dumps(metadata, indent=2) + "\n")
    print(f"manifest: {manifest}")
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
