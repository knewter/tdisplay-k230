//! Bounded, muted video frames for the existing inputless wallpaper layer.
//! The decoder is a child process of the Rust shell, never a Wayland app.

use crate::frame_bytes;
use serde_json::Value;
use std::{
    fs,
    io::Read,
    os::fd::AsRawFd,
    path::{Path, PathBuf},
    process::{Child, Command, Stdio},
    sync::{
        atomic::{AtomicBool, AtomicU64, Ordering},
        mpsc::{self, Receiver, SyncSender, TryRecvError},
        Arc, Mutex,
    },
    thread::{self, JoinHandle},
    time::{Duration, Instant},
};

const SOURCE_LIMIT: u64 = 128 * 1024 * 1024;
const SOURCE_PIXELS: u64 = 1920 * 1080;
const FIRST_FRAME_TIMEOUT: Duration = Duration::from_millis(1300);
const FRAME_BYTES_LIMIT: usize = 1024 * 2048 * 4;

#[derive(Clone, Debug, Eq, PartialEq)]
pub struct VideoKey {
    pub path: PathBuf,
    pub width: u32,
    pub height: u32,
}

#[derive(Debug)]
pub enum VideoEvent {
    Frame(Vec<u8>),
    Error(&'static str),
}

pub struct VideoWallpaper {
    stop: Arc<AtomicBool>,
    decoded: Arc<AtomicU64>,
    child_pid: Arc<AtomicU64>,
    failure: Arc<Mutex<Option<&'static str>>>,
    events: Receiver<VideoEvent>,
    worker: Option<JoinHandle<()>>,
    pub key: VideoKey,
    pub started: Instant,
}

fn local_video(path: &Path) -> Result<PathBuf, &'static str> {
    if !path.is_absolute()
        || !matches!(
            path.extension().and_then(|x| x.to_str()),
            Some("mp4" | "m4v" | "mov")
        )
    {
        return Err("unsupported-format");
    }
    let meta = fs::symlink_metadata(path).map_err(|_| "source-unavailable")?;
    if !meta.file_type().is_file()
        || meta.file_type().is_symlink()
        || meta.len() == 0
        || meta.len() > SOURCE_LIMIT
    {
        return Err("source-bound");
    }
    let canonical = path.canonicalize().map_err(|_| "source-unavailable")?;
    if canonical != path {
        return Err("source-path");
    }
    Ok(canonical)
}

fn probe(path: &Path, ffprobe: &Path) -> Result<(), &'static str> {
    let mut child = Command::new(ffprobe)
        .args([
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-show_entries",
            "stream=codec_name,width,height",
            "-of",
            "json",
        ])
        .arg(path)
        .stdin(Stdio::null())
        .stdout(Stdio::piped())
        .stderr(Stdio::null())
        .spawn()
        .map_err(|_| "probe-unavailable")?;
    let deadline = Instant::now() + Duration::from_millis(800);
    loop {
        if child.try_wait().map_err(|_| "probe-failed")?.is_some() {
            break;
        }
        if Instant::now() >= deadline {
            let _ = child.kill();
            let _ = child.wait();
            return Err("probe-timeout");
        }
        thread::sleep(Duration::from_millis(10));
    }
    let output = child.wait_with_output().map_err(|_| "probe-failed")?;
    if !output.status.success() || output.stdout.len() > 4096 {
        return Err("unsupported-codec");
    }
    let parsed: Value = serde_json::from_slice(&output.stdout).map_err(|_| "probe-invalid")?;
    let streams = parsed
        .get("streams")
        .and_then(Value::as_array)
        .ok_or("probe-invalid")?;
    let stream = streams.first().ok_or("unsupported-codec")?;
    let (width, height) = (
        stream
            .get("width")
            .and_then(Value::as_u64)
            .ok_or("probe-invalid")?,
        stream
            .get("height")
            .and_then(Value::as_u64)
            .ok_or("probe-invalid")?,
    );
    if stream.get("codec_name").and_then(Value::as_str) != Some("h264")
        || width == 0
        || height == 0
        || width > 1920
        || height > 1080
        || width * height > SOURCE_PIXELS
    {
        return Err("unsupported-codec");
    }
    Ok(())
}

fn stop_child(child: &mut Child) {
    let _ = child.kill();
    let _ = child.wait();
}

fn decode_loop(
    key: VideoKey,
    ffmpeg: PathBuf,
    ffprobe: PathBuf,
    stop: Arc<AtomicBool>,
    decoded: Arc<AtomicU64>,
    child_pid: Arc<AtomicU64>,
    failure: Arc<Mutex<Option<&'static str>>>,
    events: SyncSender<VideoEvent>,
) {
    let result = (|| -> Result<(), &'static str> {
        let path = local_video(&key.path)?;
        probe(&path, &ffprobe)?;
        let expected = frame_bytes(key.width, key.height).ok_or("output-bound")?;
        if expected > FRAME_BYTES_LIMIT {
            return Err("output-bound");
        }
        let filter = format!(
            "fps=8,scale={}:{}:force_original_aspect_ratio=increase,crop={}:{}",
            key.width, key.height, key.width, key.height
        );
        let mut child = Command::new(ffmpeg)
            .args([
                "-nostdin",
                "-hide_banner",
                "-loglevel",
                "error",
                "-threads",
                "1",
                "-readrate",
                "1",
                "-stream_loop",
                "-1",
                "-i",
            ])
            .arg(path)
            .args([
                "-map", "0:v:0", "-an", "-sn", "-dn", "-vf", &filter, "-c:v", "rawvideo",
                "-pix_fmt", "bgra", "-f", "rawvideo", "pipe:1",
            ])
            .stdin(Stdio::null())
            .stdout(Stdio::piped())
            .stderr(Stdio::null())
            .spawn()
            .map_err(|_| "decoder-unavailable")?;
        child_pid.store(u64::from(child.id()), Ordering::Relaxed);
        let mut stdout = child.stdout.take().ok_or("decoder-pipe")?;
        let fd = stdout.as_raw_fd();
        let flags = unsafe { libc::fcntl(fd, libc::F_GETFL) };
        if flags < 0 || unsafe { libc::fcntl(fd, libc::F_SETFL, flags | libc::O_NONBLOCK) } < 0 {
            stop_child(&mut child);
            return Err("decoder-pipe");
        }
        let deadline = Instant::now() + FIRST_FRAME_TIMEOUT;
        let mut frame = vec![0u8; expected];
        let mut used = 0;
        loop {
            if stop.load(Ordering::Relaxed) {
                stop_child(&mut child);
                return Ok(());
            }
            if decoded.load(Ordering::Relaxed) == 0 && Instant::now() >= deadline {
                stop_child(&mut child);
                return Err("first-frame-timeout");
            }
            let mut pollfd = libc::pollfd {
                fd,
                events: libc::POLLIN,
                revents: 0,
            };
            let ready = unsafe { libc::poll(&mut pollfd, 1, 40) };
            if ready < 0 {
                stop_child(&mut child);
                return Err("decoder-pipe");
            }
            if ready == 0 {
                continue;
            }
            match stdout.read(&mut frame[used..]) {
                Ok(0) => {
                    stop_child(&mut child);
                    return Err("decoder-ended");
                }
                Ok(count) => used += count,
                Err(error) if error.kind() == std::io::ErrorKind::WouldBlock => continue,
                Err(_) => {
                    stop_child(&mut child);
                    return Err("decoder-pipe");
                }
            }
            if used == expected {
                decoded.fetch_add(1, Ordering::Relaxed);
                let _ = events.try_send(VideoEvent::Frame(std::mem::replace(
                    &mut frame,
                    vec![0u8; expected],
                )));
                used = 0;
            }
        }
    })();
    child_pid.store(0, Ordering::Relaxed);
    if let Err(category) = result {
        *failure.lock().expect("video failure mutex") = Some(category);
        let _ = events.try_send(VideoEvent::Error(category));
    }
}

impl VideoWallpaper {
    pub fn start(key: VideoKey, ffmpeg: PathBuf, ffprobe: PathBuf) -> Self {
        let stop = Arc::new(AtomicBool::new(false));
        let decoded = Arc::new(AtomicU64::new(0));
        let child_pid = Arc::new(AtomicU64::new(0));
        let failure = Arc::new(Mutex::new(None));
        let (sender, events) = mpsc::sync_channel(1);
        let worker = thread::spawn({
            let (stop, decoded, child_pid, failure, key) = (
                stop.clone(),
                decoded.clone(),
                child_pid.clone(),
                failure.clone(),
                key.clone(),
            );
            move || {
                decode_loop(
                    key, ffmpeg, ffprobe, stop, decoded, child_pid, failure, sender,
                )
            }
        });
        Self {
            stop,
            decoded,
            child_pid,
            failure,
            events,
            worker: Some(worker),
            key,
            started: Instant::now(),
        }
    }
    pub fn try_recv(&self) -> Option<VideoEvent> {
        match self.events.try_recv() {
            Ok(event) => Some(event),
            Err(TryRecvError::Empty | TryRecvError::Disconnected) => None,
        }
    }
    pub fn decoded(&self) -> u64 {
        self.decoded.load(Ordering::Relaxed)
    }
    pub fn failure(&self) -> Option<&'static str> {
        *self.failure.lock().expect("video failure mutex")
    }
    pub fn decoder_pid(&self) -> Option<u64> {
        match self.child_pid.load(Ordering::Relaxed) {
            0 => None,
            pid => Some(pid),
        }
    }
    pub fn stop(&mut self) {
        self.stop.store(true, Ordering::Relaxed);
        if let Some(worker) = self.worker.take() {
            let _ = worker.join();
        }
    }
}
impl Drop for VideoWallpaper {
    fn drop(&mut self) {
        self.stop();
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn source_and_output_bounds_precede_decoder() {
        assert_eq!(
            local_video(Path::new("relative.mp4")),
            Err("unsupported-format")
        );
        assert_eq!(
            local_video(Path::new("/tmp/x.webm")),
            Err("unsupported-format")
        );
        assert!(frame_bytes(568, 1232).unwrap() <= FRAME_BYTES_LIMIT);
        assert!(frame_bytes(2048, 4096).is_none());
    }

    #[test]
    fn bounded_real_decoder_emits_distinct_muted_frames_when_fixture_supplied() {
        let (Some(path), Some(ffmpeg), Some(ffprobe)) = (
            std::env::var_os("K230_VIDEO_TEST_CLIP"),
            std::env::var_os("K230_VIDEO_TEST_FFMPEG"),
            std::env::var_os("K230_VIDEO_TEST_FFPROBE"),
        ) else {
            return;
        };
        let mut worker = VideoWallpaper::start(
            VideoKey {
                path: PathBuf::from(path),
                width: 320,
                height: 600,
            },
            PathBuf::from(ffmpeg),
            PathBuf::from(ffprobe),
        );
        let deadline = Instant::now() + Duration::from_secs(3);
        let mut first = None;
        let mut distinct = false;
        while Instant::now() < deadline && !distinct {
            match worker.try_recv() {
                Some(VideoEvent::Frame(frame)) => {
                    if let Some(previous) = &first {
                        distinct = *previous != frame;
                    } else {
                        first = Some(frame);
                    }
                }
                Some(VideoEvent::Error(error)) => panic!("decoder failed: {error}"),
                None => thread::sleep(Duration::from_millis(10)),
            }
        }
        assert!(distinct, "video worker did not emit distinct frames");
        assert!(worker.decoded() >= 2);
        worker.stop();
        assert!(worker.decoder_pid().is_none());
    }
}
