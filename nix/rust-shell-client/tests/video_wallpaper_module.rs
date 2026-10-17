//! The video wallpaper decoder child, driven through its public API with
//! stand-in `ffprobe`/`ffmpeg` scripts so every failure category and the
//! stop/restart (pause/resume) lifecycle run the real `decode_loop`. This is
//! host proof of the process handling only: it decodes no real H.264 (the
//! fixture-gated test in `video_wallpaper.rs` and
//! `tests/test_handheld_theme_backgrounds.py --video` do that) and says nothing
//! about the board's CPU or frame budget.

use k230_shell_rust::video_wallpaper::{VideoEvent, VideoKey, VideoWallpaper};
use std::{
    fs,
    os::unix::fs::{symlink, PermissionsExt},
    path::{Path, PathBuf},
    thread,
    time::{Duration, Instant},
};

const W: u32 = 320;
const H: u32 = 300;

struct Dir(PathBuf);
impl Dir {
    fn new(tag: &str) -> Self {
        let path = std::env::temp_dir().join(format!("k230-vw-{tag}-{}", std::process::id()));
        let _ = fs::remove_dir_all(&path);
        fs::create_dir_all(&path).unwrap();
        Dir(path)
    }
    fn script(&self, name: &str, body: &str) -> PathBuf {
        let path = self.0.join(name);
        fs::write(&path, format!("#!/bin/sh\n{body}\n")).unwrap();
        fs::set_permissions(&path, fs::Permissions::from_mode(0o755)).unwrap();
        path
    }
    fn clip(&self, name: &str) -> PathBuf {
        let path = self.0.join(name);
        fs::write(&path, b"not a real clip; the stand-in probe never reads it").unwrap();
        path
    }
}
impl Drop for Dir {
    fn drop(&mut self) {
        let _ = fs::remove_dir_all(&self.0);
    }
}

fn probe_says(dir: &Dir, codec: &str, width: u32, height: u32) -> PathBuf {
    dir.script(
        "ffprobe",
        &format!(
            "echo '{{\"streams\":[{{\"codec_name\":\"{codec}\",\"width\":{width},\"height\":{height}}}]}}'"
        ),
    )
}

/// Emits distinct whole BGRA frames of the key's size until killed.
fn frames_forever(dir: &Dir) -> PathBuf {
    dir.script(
        "ffmpeg",
        &format!("while :; do head -c {} /dev/urandom; sleep 0.02; done", W * H * 4),
    )
}

fn start(clip: &Path, ffmpeg: &Path, ffprobe: &Path) -> VideoWallpaper {
    VideoWallpaper::start(
        VideoKey {
            path: clip.to_path_buf(),
            width: W,
            height: H,
        },
        ffmpeg.to_path_buf(),
        ffprobe.to_path_buf(),
    )
}

fn next(worker: &VideoWallpaper, within: Duration) -> Option<VideoEvent> {
    let deadline = Instant::now() + within;
    while Instant::now() < deadline {
        if let Some(event) = worker.try_recv() {
            return Some(event);
        }
        thread::sleep(Duration::from_millis(5));
    }
    None
}

fn error_of(worker: &VideoWallpaper, within: Duration) -> &'static str {
    match next(worker, within) {
        Some(VideoEvent::Error(category)) => {
            assert_eq!(worker.failure(), Some(category), "failure() must agree");
            category
        }
        other => panic!("expected an error event, got {other:?}"),
    }
}

#[test]
fn source_bounds_fail_by_name_before_any_decoder_runs() {
    let dir = Dir::new("source");
    let ffprobe = probe_says(&dir, "h264", 640, 480);
    // A decoder that would leave evidence if it were ever started.
    let marker = dir.0.join("decoder-ran");
    let ffmpeg = dir.script("ffmpeg", &format!("touch {}", marker.display()));
    let within = Duration::from_secs(2);

    let missing = dir.0.join("missing.mp4");
    assert_eq!(error_of(&start(&missing, &ffmpeg, &ffprobe), within), "source-unavailable");

    let empty = dir.0.join("empty.mp4");
    fs::write(&empty, b"").unwrap();
    assert_eq!(error_of(&start(&empty, &ffmpeg, &ffprobe), within), "source-bound");

    let real = dir.clip("real.mp4");
    let link = dir.0.join("link.mp4");
    symlink(&real, &link).unwrap();
    assert_eq!(error_of(&start(&link, &ffmpeg, &ffprobe), within), "source-bound");

    let webm = dir.clip("clip.webm");
    assert_eq!(error_of(&start(&webm, &ffmpeg, &ffprobe), within), "unsupported-format");
    let relative = PathBuf::from("relative.mp4");
    assert_eq!(error_of(&start(&relative, &ffmpeg, &ffprobe), within), "unsupported-format");

    assert!(!marker.exists(), "no decoder may start for a rejected source");
}

#[test]
fn probe_failures_are_distinct_named_categories() {
    let dir = Dir::new("probe");
    let clip = dir.clip("clip.mp4");
    let ffmpeg = frames_forever(&dir);
    let within = Duration::from_secs(3);

    let cases: [(&str, String, &str); 5] = [
        ("hevc", "echo '{\"streams\":[{\"codec_name\":\"hevc\",\"width\":640,\"height\":480}]}'".into(), "unsupported-codec"),
        ("oversize", "echo '{\"streams\":[{\"codec_name\":\"h264\",\"width\":4000,\"height\":3000}]}'".into(), "unsupported-codec"),
        ("failed", "exit 1".into(), "unsupported-codec"),
        ("no-video-stream", "echo '{\"streams\":[]}'".into(), "unsupported-codec"),
        ("garbage", "echo 'not json'".into(), "probe-invalid"),
    ];
    for (name, body, expected) in cases {
        let ffprobe = dir.script(&format!("ffprobe-{name}"), &body);
        assert_eq!(error_of(&start(&clip, &ffmpeg, &ffprobe), within), expected, "{name}");
    }

    let absent = dir.0.join("no-such-ffprobe");
    assert_eq!(error_of(&start(&clip, &ffmpeg, &absent), within), "probe-unavailable");

    let hang = dir.script("ffprobe-hang", "sleep 5");
    let started = Instant::now();
    assert_eq!(error_of(&start(&clip, &ffmpeg, &hang), Duration::from_secs(3)), "probe-timeout");
    assert!(started.elapsed() < Duration::from_secs(3));
}

#[test]
fn decoder_failures_are_named_and_leave_no_child() {
    let dir = Dir::new("decoder");
    let clip = dir.clip("clip.mp4");
    let ffprobe = probe_says(&dir, "h264", 640, 480);

    let absent = dir.0.join("no-such-ffmpeg");
    let worker = start(&clip, &absent, &ffprobe);
    assert_eq!(error_of(&worker, Duration::from_secs(3)), "decoder-unavailable");

    let ends = dir.script("ffmpeg-ends", "exit 0");
    let worker = start(&clip, &ends, &ffprobe);
    assert_eq!(error_of(&worker, Duration::from_secs(3)), "decoder-ended");
    assert_eq!(worker.decoded(), 0);
    assert!(worker.decoder_pid().is_none());

    let silent = dir.script("ffmpeg-silent", "sleep 30");
    let worker = start(&clip, &silent, &ffprobe);
    assert_eq!(error_of(&worker, Duration::from_secs(4)), "first-frame-timeout");
    assert!(worker.decoder_pid().is_none(), "a timed-out decoder is reaped");
}

#[test]
fn stop_reaps_the_decoder_and_a_fresh_start_resumes_frames() {
    let dir = Dir::new("lifecycle");
    let clip = dir.clip("clip.mp4");
    let ffprobe = probe_says(&dir, "h264", 640, 480);
    let ffmpeg = frames_forever(&dir);

    let mut worker = start(&clip, &ffmpeg, &ffprobe);
    let mut frames = Vec::new();
    while frames.len() < 2 {
        match next(&worker, Duration::from_secs(3)) {
            Some(VideoEvent::Frame(frame)) => frames.push(frame),
            other => panic!("expected frames, got {other:?}"),
        }
    }
    assert!(frames.iter().all(|frame| frame.len() == (W * H * 4) as usize));
    assert_ne!(frames[0], frames[1], "stand-in frames are distinct");
    let pid = worker.decoder_pid().expect("a running decoder has a pid");
    assert!(Path::new(&format!("/proc/{pid}")).exists());
    assert!(worker.decoded() >= 2);

    // Pause: stopping joins the worker and kills and reaps the child.
    worker.stop();
    assert!(worker.decoder_pid().is_none());
    assert!(
        !Path::new(&format!("/proc/{pid}")).exists(),
        "the decoder child must be gone after stop"
    );
    let decoded_when_paused = worker.decoded();
    thread::sleep(Duration::from_millis(200));
    assert_eq!(worker.decoded(), decoded_when_paused, "no decoding while paused");

    // Resume: a new worker for the same key decodes again with a new child.
    let mut resumed = start(&clip, &ffmpeg, &ffprobe);
    match next(&resumed, Duration::from_secs(3)) {
        Some(VideoEvent::Frame(frame)) => assert_eq!(frame.len(), (W * H * 4) as usize),
        other => panic!("expected a frame after resume, got {other:?}"),
    }
    let new_pid = resumed.decoder_pid().expect("resumed decoder has a pid");
    assert_ne!(new_pid, pid);
    drop(worker);
    resumed.stop();
    assert!(resumed.decoder_pid().is_none());
}

#[test]
fn output_bound_is_named_before_the_decoder_starts() {
    let dir = Dir::new("output");
    let clip = dir.clip("clip.mp4");
    let ffprobe = probe_says(&dir, "h264", 640, 480);
    let marker = dir.0.join("decoder-ran");
    let ffmpeg = dir.script("ffmpeg", &format!("touch {}", marker.display()));
    let worker = VideoWallpaper::start(
        VideoKey {
            path: clip,
            width: 100,
            height: 100,
        },
        ffmpeg,
        ffprobe,
    );
    assert_eq!(error_of(&worker, Duration::from_secs(2)), "output-bound");
    assert!(!marker.exists());
}
