//! Opt-in layer-shell/SHM client. Live app pixels stay with Sway.
//! The layer/event plumbing began from the pinned Rust probe, which follows
//! Smithay Client Toolkit's MIT-licensed v0.20.0 simple_layer example.
use gio::prelude::*;
use k230_shell_rust::{
    appearance::{AppearanceEvent, AppearancePhase, AppearanceReceiver, AppearanceSnapshot},
    background_decode::{BackgroundCache, FitMode},
    catalog::{installed_apps, AppEntry},
    configure_size, frame_bytes,
    navigation::{DrawerAction, DrawerNavigation},
    protocol::{Phase, RevealMessage, RevealState, MAX_LINE},
    released_slot,
    render::{export_png, RenderParams, RendererCache},
    service_data::{ServiceReply, ServiceRequest, ServiceResponse, ServiceWorker},
    service_ui::{
        action_message, notification_max_scroll, notification_swipe_hit, notification_swipe_offset,
        notification_swipe_release, notification_swipe_start, notification_swipe_valid,
        panel_intent, Confirmation, NotificationCoast, NotificationSwipeSettle, PanelIntent,
        ServiceView, SWIPE_VERTICAL_CANCEL,
    },
    theme_carousel::{Carousel, CarouselOutcome, BACKGROUND_GEOMETRY, THEME_GEOMETRY},
    theme_catalog::{ThemeReply, ThemeRequest, ThemeWorker},
    theme_ui::{
        ThemeIntent, ThemePage, ThemeView, BACKGROUND_CAROUSEL_TOP, THEME_CAROUSEL_TOP,
    },
    video_status::{self, VideoStatus},
    video_visibility,
    video_wallpaper::{VideoEvent, VideoKey, VideoWallpaper},
    wifi_settings::{Kind as WifiKind, WifiRequest, WifiResult, WifiWorker},
    wifi_ui::{self, Intent as WifiIntent, Page as WifiPage, WifiView},
    Route, TouchTrace,
};
use smithay_client_toolkit::{
    compositor::{CompositorHandler, CompositorState, Region},
    delegate_compositor, delegate_layer, delegate_output, delegate_registry, delegate_seat,
    delegate_shm, delegate_touch,
    output::{OutputHandler, OutputState},
    registry::{ProvidesRegistryState, RegistryState},
    registry_handlers,
    seat::{touch::TouchHandler, Capability, SeatHandler, SeatState},
    shell::{
        wlr_layer::{
            Anchor, KeyboardInteractivity, Layer, LayerShell, LayerShellHandler, LayerSurface,
            LayerSurfaceConfigure,
        },
        WaylandSurface,
    },
    shm::{
        slot::{Buffer, SlotPool},
        Shm, ShmHandler,
    },
};
use std::{
    fs::{self, File, OpenOptions},
    io::{Read, Write},
    os::{
        fd::{AsFd, AsRawFd, FromRawFd},
        unix::{
            ffi::OsStrExt,
            fs::{FileTypeExt, MetadataExt, PermissionsExt},
            net::{UnixListener, UnixStream},
        },
    },
    path::PathBuf,
    process::{Command, Stdio},
    sync::mpsc::{self, Receiver, Sender},
    thread,
    time::{Duration, Instant},
};
use wayland_client::{
    globals::registry_queue_init,
    protocol::{wl_output, wl_seat, wl_shm, wl_surface, wl_touch},
    Connection, QueueHandle,
};

const SOCKET_NAME: &str = "k230-shell-rust.sock";
const APPEARANCE_SOCKET_NAME: &str = "k230-shell-rust-appearance.sock";
const MAX_PENDING_BYTES: usize = 4096;
const PEER_IDLE_TIMEOUT: Duration = Duration::from_secs(5);
/// How often the theme chooser's loading-spinner pulse is allowed to force
/// a redraw while something real is still in flight (a thumbnail decode, a
/// still-preview decode, a pending Activate). This is the *only* thing that
/// keeps the render loop busy while the chooser is otherwise at rest --
/// deliberately coarse (well under the panel's own ~15fps compositor
/// cadence, not a vsync-rate animation), because this redraw exists purely
/// to advance a decorative spinner, not to reflect anything that changed
/// visually more than a few times a second. Replaces a previous unconditional
/// per-event-loop-iteration `dirty = true` that ran at whatever rate the
/// loop happened to wake up (effectively the panel's own frame rate),
/// burning single-core CPU that competed with the very decode work a
/// pending thumbnail or preview was waiting on -- see
/// `RendererCache::theme_thumbnails_pending`'s doc for the full story.
const THEME_PULSE_INTERVAL: Duration = Duration::from_millis(160);

fn panel_input_rect(
    route: Route,
    width: u32,
    height: u32,
    ready: bool,
) -> Option<(i32, i32, i32, i32)> {
    if !ready {
        return None;
    }
    let top = if route == Route::Drawer {
        (f64::from(height) * 0.19) as i32
    } else {
        0
    };
    let bottom = if route == Route::Shade {
        (f64::from(height) * 0.65) as i32
    } else {
        height as i32
    };
    Some((0, top, width as i32, bottom - top))
}

fn socket_path() -> Result<PathBuf, String> {
    let runtime = std::env::var_os("XDG_RUNTIME_DIR").ok_or("XDG_RUNTIME_DIR is unset")?;
    Ok(PathBuf::from(runtime).join(SOCKET_NAME))
}

fn appearance_socket_path() -> Result<PathBuf, String> {
    let runtime = std::env::var_os("XDG_RUNTIME_DIR").ok_or("XDG_RUNTIME_DIR is unset")?;
    Ok(PathBuf::from(runtime).join(APPEARANCE_SOCKET_NAME))
}

fn appearance_renderable(
    snapshot: Option<&AppearanceSnapshot>,
    cache: &mut BackgroundCache,
    geometry: Option<(u32, u32)>,
) -> Result<(), String> {
    let Some(snapshot) = snapshot else {
        return Ok(());
    };
    let Some(_) = snapshot.selected_background.as_ref() else {
        return Ok(());
    };
    let Some(still) = snapshot.background.as_ref() else {
        return Err("video background is not supported".into());
    };
    let (width, height) = geometry.ok_or("wallpaper output is not configured")?;
    cache
        .render(still, Some(snapshot.path.as_path()), width, height, FitMode::Crop)
        .map(|_| ())
}

fn selected_video(snapshot: Option<&AppearanceSnapshot>, geometry: (u32, u32)) -> Option<VideoKey> {
    let snapshot = snapshot?;
    let choice = snapshot
        .backgrounds
        .iter()
        .find(|choice| choice.selected && choice.is_video)?;
    Some(VideoKey {
        path: choice.staged_path.clone(),
        width: geometry.0,
        height: geometry.1,
    })
}

fn fallback_still(snapshot: Option<&AppearanceSnapshot>) -> Option<PathBuf> {
    snapshot.and_then(|snapshot| {
        snapshot.background.clone().or_else(|| {
            snapshot
                .backgrounds
                .iter()
                .find(|choice| !choice.is_video)
                .map(|choice| choice.staged_path.clone())
        })
    })
}

/// Which retained decoder slot, if any, already matches the display key.
/// `Previous` is what a rollback needs: a transaction can settle onto a
/// generation whose decoder was demoted (but kept paused, with its last
/// frame) when the newer generation was committed, so restoring it does not
/// need to wait for another decode.
#[derive(Debug, Eq, PartialEq)]
enum VideoSlot {
    Active,
    Candidate,
    Previous,
    None,
}

fn resolve_video_slot(
    display: Option<&VideoKey>,
    active: Option<&VideoKey>,
    candidate: Option<&VideoKey>,
    previous: Option<&VideoKey>,
) -> VideoSlot {
    let Some(display) = display else {
        return VideoSlot::None;
    };
    if active == Some(display) {
        VideoSlot::Active
    } else if candidate == Some(display) {
        VideoSlot::Candidate
    } else if previous == Some(display) {
        VideoSlot::Previous
    } else {
        VideoSlot::None
    }
}

fn video_identity(snapshot: Option<&AppearanceSnapshot>) -> (Option<String>, Option<String>) {
    let Some(snapshot) = snapshot else {
        return (None, None);
    };
    let relative = snapshot
        .backgrounds
        .iter()
        .find(|choice| choice.selected && choice.is_video)
        .map(|choice| choice.relative.clone());
    (Some(snapshot.generation.clone()), relative)
}

struct VideoPlayback {
    decoder: VideoWallpaper,
    frame: Option<Vec<u8>>,
    error: Option<&'static str>,
    paused: bool,
    decoded_before_pause: u64,
}

impl VideoPlayback {
    fn new(key: VideoKey, ffmpeg: &std::path::Path, ffprobe: &std::path::Path) -> Self {
        Self {
            decoder: VideoWallpaper::start(key, ffmpeg.to_path_buf(), ffprobe.to_path_buf()),
            frame: None,
            error: None,
            paused: false,
            decoded_before_pause: 0,
        }
    }
    fn pause(&mut self) {
        if !self.paused {
            self.decoded_before_pause = self
                .decoded_before_pause
                .saturating_add(self.decoder.decoded());
            self.decoder.stop();
            self.paused = true;
        }
    }
    fn resume(&mut self, ffmpeg: &std::path::Path, ffprobe: &std::path::Path) {
        if self.paused {
            self.decoder = VideoWallpaper::start(
                self.decoder.key.clone(),
                ffmpeg.to_path_buf(),
                ffprobe.to_path_buf(),
            );
            self.paused = false;
        }
    }
    fn decoded(&self) -> u64 {
        self.decoded_before_pause
            .saturating_add(self.decoder.decoded())
    }
    fn poll(&mut self) -> bool {
        let mut changed = false;
        while let Some(event) = self.decoder.try_recv() {
            match event {
                VideoEvent::Frame(frame) => {
                    self.frame = Some(frame);
                    changed = true;
                }
                VideoEvent::Error(category) => {
                    self.error = Some(category);
                    changed = true;
                }
            }
        }
        if self.error.is_none() {
            self.error = self.decoder.failure();
            changed |= self.error.is_some();
        }
        changed
    }
}

fn poll_until(fd: i32, events: i16, deadline: Instant) -> Result<(), String> {
    let remaining = deadline.saturating_duration_since(Instant::now());
    if remaining.is_zero() {
        return Err("route timed out".into());
    }
    let millis = remaining.as_millis().min(i32::MAX as u128) as i32;
    let mut event = libc::pollfd {
        fd,
        events,
        revents: 0,
    };
    let result = unsafe { libc::poll(&mut event, 1, millis) };
    if result <= 0 || event.revents & events == 0 {
        return Err("route timed out".into());
    }
    Ok(())
}

fn connect_bounded(path: &std::path::Path, deadline: Instant) -> Result<UnixStream, String> {
    let bytes = path.as_os_str().as_bytes();
    let mut address: libc::sockaddr_un = unsafe { std::mem::zeroed() };
    if bytes.is_empty() || bytes.len() >= address.sun_path.len() {
        return Err("route path too long".into());
    }
    address.sun_family = libc::AF_UNIX as libc::sa_family_t;
    for (target, source) in address.sun_path.iter_mut().zip(bytes.iter()) {
        *target = *source as libc::c_char;
    }
    let fd = unsafe {
        libc::socket(
            libc::AF_UNIX,
            libc::SOCK_STREAM | libc::SOCK_NONBLOCK | libc::SOCK_CLOEXEC,
            0,
        )
    };
    if fd < 0 {
        return Err(std::io::Error::last_os_error().to_string());
    }
    let stream = unsafe { UnixStream::from_raw_fd(fd) };
    let status = unsafe {
        libc::connect(
            fd,
            &address as *const _ as *const libc::sockaddr,
            std::mem::size_of::<libc::sockaddr_un>() as libc::socklen_t,
        )
    };
    if status < 0 {
        if std::io::Error::last_os_error().raw_os_error() != Some(libc::EINPROGRESS) {
            return Err(std::io::Error::last_os_error().to_string());
        }
        poll_until(fd, libc::POLLOUT, deadline)?;
        let mut error = 0i32;
        let mut length = std::mem::size_of::<i32>() as libc::socklen_t;
        if unsafe {
            libc::getsockopt(
                fd,
                libc::SOL_SOCKET,
                libc::SO_ERROR,
                &mut error as *mut _ as *mut libc::c_void,
                &mut length,
            )
        } < 0
            || error != 0
        {
            return Err("route connect failed".into());
        }
    }
    Ok(stream)
}

fn request(route: &str) -> Result<(), String> {
    let path = socket_path()?;
    let bytes = format!("{route}\n");
    if Route::parse(bytes.as_bytes()).is_none() {
        return Err("unsupported route".into());
    }
    let deadline = Instant::now() + Duration::from_millis(500);
    let mut stream = connect_bounded(&path, deadline)?;
    let mut sent = 0;
    while sent < bytes.len() {
        poll_until(stream.as_raw_fd(), libc::POLLOUT, deadline)?;
        match stream.write(&bytes.as_bytes()[sent..]) {
            Ok(0) => return Err("route socket closed".into()),
            Ok(count) => sent += count,
            Err(e) if e.kind() == std::io::ErrorKind::WouldBlock => continue,
            Err(e) => return Err(e.to_string()),
        }
    }
    let mut reply = [0u8; 3];
    let mut received = 0;
    while received < reply.len() {
        poll_until(stream.as_raw_fd(), libc::POLLIN, deadline)?;
        match stream.read(&mut reply[received..]) {
            Ok(0) => return Err("route socket closed".into()),
            Ok(count) => received += count,
            Err(e) if e.kind() == std::io::ErrorKind::WouldBlock => continue,
            Err(e) => return Err(e.to_string()),
        }
    }
    if &reply == b"OK\n" {
        Ok(())
    } else {
        Err("route was not accepted".into())
    }
}

struct Peer {
    stream: UnixStream,
    bytes: Vec<u8>,
    deadline: Instant,
    progress_stream: bool,
}

enum Received {
    Route(Route, UnixStream),
    Reveal(RevealMessage),
    Abort,
}

/// Consume a ready burst without one poll timeout per line. Only contiguous
/// updates for the same gesture are replaced; begin/terminal ordering stays
/// intact. A hard batch limit returns control to Wayland event dispatch.
fn drain_routes(mut receive: impl FnMut() -> Option<Received>, mut emit: impl FnMut(Received)) {
    let mut latest: Option<RevealMessage> = None;
    for _ in 0..64 {
        let Some(record) = receive() else { break };
        if let Received::Reveal(message) = &record {
            if message.phase == Phase::Update {
                if latest.is_some_and(|previous| {
                    previous.seq != message.seq || previous.surface != message.surface
                }) {
                    emit(Received::Reveal(latest.take().expect("pending update")));
                }
                latest = Some(*message);
                continue;
            }
        }
        if let Some(message) = latest.take() {
            emit(Received::Reveal(message));
        }
        emit(record);
    }
    if let Some(message) = latest {
        emit(Received::Reveal(message));
    }
}

fn reduced_motion_enabled(value: Option<&str>) -> bool {
    value == Some("1")
}

struct RouteServer {
    listener: UnixListener,
    peer: Option<Peer>,
    path: PathBuf,
    _lock: File,
}

impl RouteServer {
    fn new(path: PathBuf) -> Result<Self, String> {
        let runtime = path.parent().ok_or("runtime path has no parent")?;
        let runtime_meta = fs::metadata(runtime).map_err(|e| e.to_string())?;
        if !runtime_meta.is_dir()
            || runtime_meta.uid() != unsafe { libc::geteuid() }
            || runtime_meta.permissions().mode() & 0o077 != 0
        {
            return Err("runtime directory must be private and owned by session user".into());
        }
        let lock_path = path.with_extension("lock");
        let lock = OpenOptions::new()
            .read(true)
            .write(true)
            .create(true)
            .truncate(false)
            .open(lock_path)
            .map_err(|e| e.to_string())?;
        if unsafe { libc::flock(lock.as_raw_fd(), libc::LOCK_EX | libc::LOCK_NB) } != 0 {
            return Err("shell client is already running".into());
        }
        if let Ok(metadata) = fs::symlink_metadata(&path) {
            if !metadata.file_type().is_socket() || metadata.uid() != unsafe { libc::geteuid() } {
                return Err("unsafe route socket exists".into());
            }
            fs::remove_file(&path).map_err(|e| e.to_string())?;
        }
        let old_mask = unsafe { libc::umask(0o077) };
        let bound = UnixListener::bind(&path);
        unsafe { libc::umask(old_mask) };
        let listener = bound.map_err(|e| e.to_string())?;
        fs::set_permissions(&path, fs::Permissions::from_mode(0o600)).map_err(|e| e.to_string())?;
        listener.set_nonblocking(true).map_err(|e| e.to_string())?;
        Ok(Self {
            listener,
            peer: None,
            path,
            _lock: lock,
        })
    }

    fn accept(&mut self) {
        if let Ok((stream, _)) = self.listener.accept() {
            if self.peer.is_some() {
                return;
            }
            if stream.set_nonblocking(true).is_err() {
                return;
            }
            self.peer = Some(Peer {
                stream,
                bytes: Vec::new(),
                deadline: Instant::now() + PEER_IDLE_TIMEOUT,
                progress_stream: false,
            });
        }
    }

    fn has_line(&self) -> bool {
        self.peer
            .as_ref()
            .is_some_and(|peer| peer.bytes.contains(&b'\n'))
    }

    fn receive(&mut self) -> Option<Received> {
        let peer = self.peer.as_mut()?;
        if Instant::now() >= peer.deadline {
            let abort = peer.progress_stream;
            self.peer = None;
            return abort.then_some(Received::Abort);
        }
        if !peer.bytes.contains(&b'\n') {
            let mut part = [0u8; 512];
            match peer.stream.read(&mut part) {
                Ok(0) => {
                    let abort = peer.progress_stream;
                    self.peer = None;
                    return abort.then_some(Received::Abort);
                }
                Ok(count) if peer.bytes.len() + count <= MAX_PENDING_BYTES => {
                    peer.bytes.extend_from_slice(&part[..count]);
                }
                Ok(_) => {
                    let abort = peer.progress_stream;
                    self.peer = None;
                    return abort.then_some(Received::Abort);
                }
                Err(e) if e.kind() == std::io::ErrorKind::WouldBlock => return None,
                Err(_) => {
                    let abort = peer.progress_stream;
                    self.peer = None;
                    return abort.then_some(Received::Abort);
                }
            }
        }
        let Some(end) = peer.bytes.iter().position(|byte| *byte == b'\n') else {
            if peer.bytes.len() > MAX_LINE {
                let abort = peer.progress_stream;
                self.peer = None;
                return abort.then_some(Received::Abort);
            }
            return None;
        };
        if end + 1 > MAX_LINE {
            let abort = peer.progress_stream;
            self.peer = None;
            return abort.then_some(Received::Abort);
        }
        let line: Vec<u8> = peer.bytes.drain(..=end).collect();
        peer.deadline = Instant::now() + PEER_IDLE_TIMEOUT;
        if let Some(route) = Route::parse(&line) {
            let peer = self.peer.take().expect("in-flight peer");
            return Some(Received::Route(route, peer.stream));
        }
        if let Some(message) = RevealMessage::parse(&line) {
            peer.progress_stream = true;
            if matches!(message.phase, Phase::Finish | Phase::Cancel) {
                self.peer = None; // complete terminal line; EOF is normal
            }
            return Some(Received::Reveal(message));
        }
        let abort = peer.progress_stream;
        self.peer = None;
        abort.then_some(Received::Abort)
    }
}

impl Drop for RouteServer {
    fn drop(&mut self) {
        let _ = fs::remove_file(&self.path);
    }
}

fn swaymsg_back(swaymsg: &std::path::Path) -> Result<(), String> {
    if !swaymsg.is_absolute() || !swaymsg.is_file() {
        return Err("K230_SWAYMSG must name an absolute executable".into());
    }
    let mut child = Command::new(swaymsg)
        .args(["card_shell", "back"])
        .stdin(Stdio::null())
        .stdout(Stdio::null())
        .stderr(Stdio::null())
        .spawn()
        .map_err(|error| error.to_string())?;
    let deadline = Instant::now() + Duration::from_secs(2);
    loop {
        match child.try_wait() {
            Ok(Some(status)) if status.success() => return Ok(()),
            Ok(Some(_)) => return Err("card_shell back failed".into()),
            Ok(None) if Instant::now() < deadline => thread::sleep(Duration::from_millis(10)),
            Ok(None) => {
                let _ = child.kill();
                let _ = child.wait();
                return Err("card_shell back timed out".into());
            }
            Err(error) => return Err(error.to_string()),
        }
    }
}

fn launch_selected(id: &str, swaymsg: &std::path::Path) -> Result<(), String> {
    swaymsg_back(swaymsg)?;
    let app = gio::DesktopAppInfo::new(id).ok_or("installed app disappeared")?;
    if !app.should_show() {
        return Err("installed app is no longer visible".into());
    }
    app.launch(&[], None::<&gio::AppLaunchContext>)
        .map_err(|error| error.to_string())
}

fn shade_close_swipe(start: (f64, f64), end: (f64, f64)) -> bool {
    let dx = end.0 - start.0;
    let dy = end.1 - start.1;
    dy <= -80.0 && dx.abs() <= 80.0
}

fn shade_release_closes(start: (f64, f64), end: (f64, f64), has_rows: bool, height: u32) -> bool {
    let list_bottom = f64::from(height) * 0.65 - 24.0;
    let in_list = start.1 >= k230_shell_rust::service_ui::NOTIFICATION_TOP && start.1 < list_bottom;
    (!has_rows || !in_list) && shade_close_swipe(start, end)
}

struct ShellClient {
    compositor: CompositorState,
    layer_shell: LayerShell,
    registry_state: RegistryState,
    seat_state: SeatState,
    output_state: OutputState,
    shm: Shm,
    pool: SlotPool,
    buffers: Vec<Buffer>,
    layer: Option<LayerSurface>,
    wallpaper: WallpaperState,
    background_cache: BackgroundCache,
    wallpaper_path: Option<PathBuf>,
    wallpaper_generation_root: Option<PathBuf>,
    video_source: Option<PathBuf>,
    video_active: Option<VideoPlayback>,
    video_candidate: Option<VideoPlayback>,
    video_previous: Option<VideoPlayback>,
    video_display: Option<VideoKey>,
    video_ffmpeg: Option<PathBuf>,
    video_ffprobe: Option<PathBuf>,
    video_start_attempted: bool,
    video_generation: Option<String>,
    video_relative: Option<String>,
    video_error: Option<&'static str>,
    video_submitted: u64,
    video_callbacks: u64,
    video_last_decoded_ms: Option<u64>,
    video_last_submitted_ms: Option<u64>,
    video_last_callback_ms: Option<u64>,
    video_status_last: Instant,
    video_status_runtime: PathBuf,
    video_cover_path: Option<PathBuf>,
    video_cover_last: Instant,
    video_covered: bool,
    touch_device: Option<wl_touch::WlTouch>,
    route: Route,
    touch: TouchTrace,
    width: u32,
    height: u32,
    configured: bool,
    dirty: bool,
    frame_pending: bool,
    started: Instant,
    apps: Vec<AppEntry>,
    nav: DrawerNavigation,
    nav_tick: Instant,
    launch_sender: Sender<(u64, Result<(), String>)>,
    launch_results: Receiver<(u64, Result<(), String>)>,
    launching: bool,
    launch_in_flight: bool,
    launch_seq: u64,
    launch_started: Option<Instant>,
    swaymsg: Option<PathBuf>,
    renderer: RendererCache,
    services: ServiceWorker,
    service_view: ServiceView,
    wifi_worker: WifiWorker,
    wifi_view: WifiView,
    wifi_origin_scroll: f64,
    wifi_dragged: bool,
    themes: ThemeWorker,
    theme_view: ThemeView,
    theme_carousel: Carousel,
    background_carousel: Carousel,
    panel_start: Option<(i32, (f64, f64))>,
    panel_origin_scroll: f64,
    panel_scrolled: bool,
    panel_scroll_dragged: bool,
    panel_scroll_sample: Option<(f64, u32)>,
    panel_scroll_velocity: f64,
    notification_coast: NotificationCoast,
    panel_swipe_owned: bool,
    panel_swipe_cancelled: bool,
    panel_swipe_moved: bool,
    panel_swipe_base: f64,
    notification_settle: Option<NotificationSwipeSettle>,
    notification_wait: Option<Instant>,
    appearance_pending: bool,
    reveal: RevealState,
    input_ready: bool,
    input_region_key: Option<(Route, u32, u32, bool)>,
    reduced_motion: bool,
    /// Last time the theme chooser's loading-spinner pulse actually
    /// advanced and forced a redraw. See `THEME_PULSE_INTERVAL`'s own doc:
    /// this is the bounded replacement for the old unconditional
    /// per-iteration `dirty = true` that redrew an unchanged frame at rest
    /// while thumbnails were still decoding.
    theme_pulse_at: Instant,
}

#[derive(Default)]
struct WallpaperState {
    layer: Option<LayerSurface>,
    buffers: Vec<Buffer>,
    width: u32,
    height: u32,
    configured: bool,
    frame_pending: bool,
    dirty: bool,
    recreate_after: Option<Instant>,
    map_started: Option<Instant>,
}

impl ShellClient {
    fn start_video(&self, key: VideoKey) -> Result<VideoPlayback, String> {
        let ffmpeg = self
            .video_ffmpeg
            .as_deref()
            .ok_or("video decoder unavailable")?;
        let ffprobe = self
            .video_ffprobe
            .as_deref()
            .ok_or("video probe unavailable")?;
        if !ffmpeg.is_absolute() || !ffprobe.is_absolute() {
            return Err("video tools must be absolute".into());
        }
        Ok(VideoPlayback::new(key, ffmpeg, ffprobe))
    }
    fn wifi_dirty(&mut self) {
        self.service_view.wifi = Some(self.wifi_view.public());
        self.renderer.set_services(self.service_view.clone());
        self.dirty = true;
    }

    fn submit_wifi(&mut self, request: WifiRequest) {
        let kind = request.kind();
        match self.wifi_worker.try_submit(request) {
            Ok(id) => self.wifi_view.submitted(id, kind),
            Err(error) => self.wifi_view.submit_failed(error),
        }
        self.wifi_dirty();
    }

    fn wifi_action(&mut self, intent: WifiIntent) {
        match intent {
            WifiIntent::Back => {
                if self.wifi_view.page == WifiPage::Connecting {
                    return;
                }
                if !self.wifi_view.back() {
                    self.service_view.wifi = None;
                    self.renderer.set_services(self.service_view.clone());
                    self.dirty = true;
                } else {
                    self.wifi_dirty();
                }
            }
            WifiIntent::Refresh => {
                if self.wifi_view.pending.is_none() {
                    self.submit_wifi(WifiRequest::Scan);
                }
            }
            WifiIntent::Select(index) => {
                self.wifi_view.select(index);
                self.wifi_dirty();
            }
            WifiIntent::Key(_)
            | WifiIntent::Backspace
            | WifiIntent::Symbols
            | WifiIntent::Shift
            | WifiIntent::Space => {
                self.wifi_view.key(intent);
                self.wifi_dirty();
            }
            WifiIntent::Connect => {
                if let Some(request) = self.wifi_view.connect_request() {
                    self.submit_wifi(request);
                }
            }
            WifiIntent::EditPassword => {
                self.wifi_view.edit_password();
                self.wifi_dirty();
            }
            WifiIntent::Forget => {
                if self.wifi_view.selected.as_ref().is_some_and(|selected| {
                    self.wifi_view.snapshot.as_ref().is_some_and(|snapshot| {
                        snapshot
                            .saved
                            .iter()
                            .any(|saved| saved.ssid == selected.ssid)
                    })
                }) {
                    self.wifi_view.page = WifiPage::ForgetConfirm;
                    self.wifi_dirty();
                }
            }
            WifiIntent::ForgetConfirm => {
                if let Some(request) = self.wifi_view.forget_request() {
                    self.submit_wifi(request);
                }
            }
            WifiIntent::ForgetCancel => {
                self.wifi_view.page = WifiPage::Entry;
                self.wifi_dirty();
            }
            WifiIntent::CancelPending => {
                if let Some((id, WifiKind::Connect | WifiKind::ConnectSaved)) =
                    self.wifi_view.pending
                {
                    self.wifi_worker.cancel(id);
                    self.wifi_view.message = Some("Cancelling connection…".into());
                    self.wifi_dirty();
                }
            }
            WifiIntent::Scroll(delta) => {
                self.wifi_view.scroll(delta);
                self.wifi_dirty();
            }
        }
    }

    fn wifi_reply(&mut self, reply: k230_shell_rust::wifi_settings::WifiReply) {
        let saved = matches!(
            &reply.result,
            Ok(WifiResult::Saved | WifiResult::Selected | WifiResult::Forgotten)
        );
        if self.wifi_view.accept(reply) {
            self.wifi_dirty();
            if saved {
                self.submit_wifi(WifiRequest::Status);
            }
        }
    }

    fn theme_dirty(&mut self) {
        self.renderer.set_theme_view(self.theme_view.clone());
        self.dirty = true;
    }

    /// Mirrors `theme_carousel`'s own live "pressed" state (see
    /// `Carousel::pressed`) into `theme_view` so the renderer's next `draw`
    /// -- which only ever sees this cloned snapshot, never the live carousel
    /// -- shows the same-frame highlight goal 1 asks for. Called after
    /// every touch event that can change either carousel's contact (down,
    /// motion, up, cancel); a no-op (no redraw) when nothing changed.
    fn sync_theme_pressed(&mut self) {
        let center_x = f64::from(self.width) / 2.0;
        let want = (self.theme_view.page == ThemePage::List)
            .then(|| {
                let count = self.theme_view.list.as_ref().map_or(0, |l| l.themes.len());
                self.theme_carousel.pressed(count, center_x, THEME_CAROUSEL_TOP)
            })
            .flatten();
        if self.theme_view.theme_pressed != want {
            self.theme_view.theme_pressed = want;
            self.theme_dirty();
        }
    }

    /// Same as `sync_theme_pressed`, for the Preview page's background
    /// carousel.
    fn sync_background_pressed(&mut self) {
        let center_x = f64::from(self.width) / 2.0;
        let want = (self.theme_view.page == ThemePage::Preview)
            .then(|| {
                let count = self
                    .theme_view
                    .preview
                    .as_ref()
                    .map_or(0, |p| p.backgrounds.len());
                self.background_carousel
                    .pressed(count, center_x, BACKGROUND_CAROUSEL_TOP)
            })
            .flatten();
        if self.theme_view.background_pressed != want {
            self.theme_view.background_pressed = want;
            self.theme_dirty();
        }
    }

    fn submit_theme(&mut self, request: ThemeRequest) {
        match self.themes.try_submit(request.clone()) {
            Ok(id) => self.theme_view.submitted(request, id),
            Err(error) => {
                if matches!(
                    request,
                    ThemeRequest::Preview {
                        background_id: Some(_),
                        ..
                    }
                ) {
                    self.theme_view.selection_failed(error);
                } else {
                    self.theme_view.failed_to_submit(error);
                }
            }
        }
        self.theme_dirty();
    }

    fn theme_reply(&mut self, reply: ThemeReply) {
        if self.theme_view.accept(reply) {
            // `ThemeView::accept` just centered `theme_position`/
            // `background_position` on the freshly-loaded active theme or
            // selected background; jump the matching physics carousel
            // there too, with no animation (a fresh list/preview is not a
            // browsing gesture). Only the carousel for the page just
            // loaded is touched, so an in-flight drag on the *other*
            // carousel (e.g. background_carousel while a stray List reply
            // for an unrelated re-open lands) is never interrupted.
            match self.theme_view.page {
                ThemePage::List => self
                    .theme_carousel
                    .set_index(self.theme_view.theme_position.max(0.0).round() as usize),
                ThemePage::Preview => self
                    .background_carousel
                    .set_index(self.theme_view.background_position.max(0.0).round() as usize),
                ThemePage::Controls => {}
            }
            self.theme_dirty();
        }
    }

    fn theme_action(&mut self, intent: ThemeIntent) {
        match intent {
            ThemeIntent::Open => {
                let request = self.theme_view.open();
                self.submit_theme(request);
            }
            ThemeIntent::Back => {
                if let Some(request) = self.theme_view.back() {
                    self.submit_theme(request);
                } else {
                    self.theme_dirty();
                }
            }
            ThemeIntent::Close => self.hide(),
            ThemeIntent::Theme(index) => {
                if let Some(request) = self.theme_view.preview_request(index) {
                    self.submit_theme(request);
                }
            }
            ThemeIntent::Background(index) => match self.theme_view.background_request(index) {
                Ok(request) => self.submit_theme(request),
                Err(error) => {
                    self.theme_view.selection_failed(error);
                    self.theme_dirty();
                }
            },
            ThemeIntent::Apply => match self.theme_view.apply_request() {
                Ok(request) => self.submit_theme(request),
                Err(error) => {
                    self.theme_view.failed_to_submit(error);
                    self.theme_dirty();
                }
            },
        }
    }

    fn refresh_route(&mut self, route: Route) {
        let request = match route {
            Route::Shade => ServiceRequest::RefreshNotifications,
            Route::Settings => ServiceRequest::RefreshSettings,
            _ => return,
        };
        if let Err(error) = self.services.try_submit(request) {
            self.service_view.message = Some(error.into());
            self.renderer.set_services(self.service_view.clone());
            self.dirty = true;
        }
    }

    fn submit_service(&mut self, request: ServiceRequest) -> bool {
        if let Err(error) = self.services.try_submit(request) {
            self.service_view.message = Some(error.into());
            self.renderer.set_services(self.service_view.clone());
            self.dirty = true;
            return false;
        }
        true
    }

    fn service_reply(&mut self, reply: ServiceReply) {
        let dismiss_id = if let ServiceRequest::NotificationDismiss(id) = &reply.request {
            Some(*id)
        } else {
            None
        };
        let dismiss_failed = dismiss_id.is_some()
            && !matches!(&reply.result, Ok(ServiceResponse::Action(outcome)) if outcome.state == "dismissed");
        let refreshed_history = matches!(reply.request, ServiceRequest::RefreshNotifications);
        match reply.result {
            Ok(ServiceResponse::Settings(settings)) => {
                self.service_view.settings = Some(settings);
                self.service_view.settings_error = None;
            }
            Ok(ServiceResponse::Notifications(notifications)) => {
                self.notification_coast.stop();
                self.service_view.notification_scroll =
                    self.service_view
                        .notification_scroll
                        .min(notification_max_scroll(
                            notifications.events.len(),
                            self.height,
                        ));
                self.service_view.notifications = Some(notifications);
                self.service_view.notification_error = None;
            }
            Ok(ServiceResponse::Action(outcome)) => {
                self.service_view.message = Some(action_message(&outcome));
                self.service_view.confirmation = if outcome.state == "confirmation" {
                    match (
                        outcome.token,
                        outcome.power_action,
                        outcome.expires_in_seconds,
                    ) {
                        (Some(token), Some(action), Some(seconds)) if seconds > 0 => {
                            Some(Confirmation {
                                token,
                                action,
                                label: outcome.label.unwrap_or("Confirm power action".into()),
                                expires_at: Instant::now()
                                    + Duration::from_secs(u64::from(seconds)),
                            })
                        }
                        _ => None,
                    }
                } else {
                    None
                };
                if let Some(brightness) = outcome.brightness {
                    if let Some(settings) = &mut self.service_view.settings {
                        settings.brightness = brightness;
                    }
                }
                match reply.request {
                    ServiceRequest::NotificationDismiss(_)
                    | ServiceRequest::NotificationDismissAll
                    | ServiceRequest::NotificationAction(_) => self.refresh_route(Route::Shade),
                    ServiceRequest::Brightness(_) | ServiceRequest::KeyboardToggle => {
                        self.refresh_route(Route::Settings)
                    }
                    _ => {}
                }
            }
            Err(error) => match reply.request {
                ServiceRequest::RefreshSettings => {
                    self.service_view.settings = None;
                    self.service_view.settings_error = Some(error);
                }
                ServiceRequest::RefreshNotifications => {
                    self.service_view.notifications = None;
                    self.service_view.notification_error = Some(error);
                }
                _ => {
                    self.service_view.confirmation = None;
                    self.service_view.message =
                        Some(format!("Service outcome unavailable: {error}"));
                }
            },
        }
        if self
            .service_view
            .notification_swipe
            .as_ref()
            .is_some_and(|swipe| !notification_swipe_valid(&self.service_view, swipe))
        {
            self.service_view.notification_swipe = None;
            self.notification_settle = None;
            self.notification_wait = None;
        } else if (dismiss_failed || (refreshed_history && self.notification_wait.is_some()))
            && self
                .service_view
                .notification_swipe
                .as_ref()
                .is_some_and(|swipe| dismiss_id.is_none_or(|id| id == swipe.event_id))
        {
            self.notification_wait = None;
            self.settle_notification(0.0, None);
        }
        self.renderer.set_services(self.service_view.clone());
        self.dirty = true;
    }

    fn panel_action(&mut self, qh: &QueueHandle<Self>, intent: PanelIntent) {
        match intent {
            PanelIntent::Hide => self.hide(),
            PanelIntent::OpenSettings => {
                self.show(qh, Route::Settings);
            }
            PanelIntent::OpenWifi => {
                let request = self.wifi_view.open();
                self.submit_wifi(request);
            }
            PanelIntent::Request(request) => {
                let accepted = self.submit_service(request.clone());
                if self.service_view.request_queued(&request, accepted) {
                    self.renderer.set_services(self.service_view.clone());
                    self.dirty = true;
                }
            }
            PanelIntent::ScrollNotifications(delta) => {
                let max = self
                    .service_view
                    .notifications
                    .as_ref()
                    .map_or(0.0, |snapshot| {
                        notification_max_scroll(snapshot.events.len(), self.height)
                    });
                self.service_view.notification_scroll =
                    (self.service_view.notification_scroll + delta).clamp(0.0, max);
                self.renderer.set_services(self.service_view.clone());
                self.dirty = true;
            }
        }
    }

    fn settle_notification(&mut self, target: f64, dismiss_id: Option<u64>) {
        if let Some(swipe) = &self.service_view.notification_swipe {
            self.notification_settle = Some(NotificationSwipeSettle::new(
                swipe.offset,
                target,
                dismiss_id,
                self.reduced_motion,
            ));
        }
    }

    fn tick_notifications(&mut self, elapsed_ms: u32) {
        if self.route != Route::Shade {
            self.notification_coast.stop();
            return;
        }
        let max = self
            .service_view
            .notifications
            .as_ref()
            .map_or(0.0, |snapshot| {
                notification_max_scroll(snapshot.events.len(), self.height)
            });
        let mut changed = self.notification_coast.tick(
            &mut self.service_view.notification_scroll,
            max,
            elapsed_ms,
        );
        if self
            .notification_wait
            .is_some_and(|when| when.elapsed() >= Duration::from_secs(1))
        {
            self.notification_wait = None;
            self.settle_notification(0.0, None);
        }
        if let Some(mut settle) = self.notification_settle.take() {
            if let Some(swipe) = &mut self.service_view.notification_swipe {
                changed |= settle.tick(&mut swipe.offset, elapsed_ms);
            }
            if settle.finished() {
                if let Some(id) = settle.dismiss_id {
                    let valid = self
                        .service_view
                        .notification_swipe
                        .as_ref()
                        .is_some_and(|swipe| notification_swipe_valid(&self.service_view, swipe));
                    if valid && self.submit_service(ServiceRequest::NotificationDismiss(id)) {
                        self.notification_wait = Some(Instant::now());
                    } else {
                        self.settle_notification(0.0, None);
                    }
                } else {
                    self.service_view.notification_swipe = None;
                    changed = true;
                }
            } else if self.service_view.notification_swipe.is_some() {
                self.notification_settle = Some(settle);
            }
        }
        if changed {
            self.renderer.set_services(self.service_view.clone());
            self.dirty = true;
        }
    }

    fn log(&self, event: &str) {
        eprintln!(
            "rust-shell {}ms {event}",
            self.started.elapsed().as_millis()
        );
    }

    fn ensure_wallpaper(&mut self, qh: &QueueHandle<Self>) -> bool {
        if self.wallpaper.layer.is_some() {
            return true;
        }
        let surface = self.compositor.create_surface(qh);
        let layer = self.layer_shell.create_layer_surface(
            qh,
            surface,
            Layer::Background,
            Some("k230-shell-wallpaper"),
            None,
        );
        layer.set_anchor(Anchor::TOP | Anchor::BOTTOM | Anchor::LEFT | Anchor::RIGHT);
        layer.set_size(0, 0);
        layer.set_exclusive_zone(0);
        layer.set_keyboard_interactivity(KeyboardInteractivity::None);
        let Ok(empty) = Region::new(&self.compositor) else {
            return false;
        };
        layer.wl_surface().set_input_region(Some(empty.wl_region()));
        layer.commit();
        self.wallpaper.layer = Some(layer);
        self.wallpaper.configured = false;
        self.wallpaper.dirty = true;
        self.wallpaper.map_started = Some(Instant::now());
        self.log("wallpaper-map-request");
        true
    }

    fn draw_wallpaper(&mut self, qh: &QueueHandle<Self>) -> bool {
        // Do not gate drawing on the wallpaper's own outstanding frame
        // callback. The wallpaper sits on the background layer, which an
        // ordinary maximized app (or the card deck's own backdrop) can fully
        // occlude; a compositor is free to stop sending frame-done events
        // for a surface nothing is compositing, so `frame_pending` can stay
        // true indefinitely with no client-visible damage. That used to
        // block every redraw here unconditionally, which starved a themed
        // commit/rollback of the free buffer slot the pool below already
        // tracks independently (up to two buffers, reused as soon as the
        // compositor releases one) -- the bounded 1400ms wait in the event
        // loop's deferred commit path then always expired with `ready`
        // false, silently rejecting the transaction. The buffer pool's own
        // released-slot/allocate-up-to-two-slots bookkeeping below is the
        // correct and sufficient gate for whether a redraw can proceed.
        if self.appearance_pending || !self.wallpaper.configured {
            return false;
        }
        let (width, height) = (self.wallpaper.width, self.wallpaper.height);
        if frame_bytes(width, height).is_none() {
            return false;
        }
        let stride = (width * 4) as i32;
        self.wallpaper
            .buffers
            .retain(|b| b.stride() == stride && b.height() == height as i32);
        let available: Vec<bool> = self
            .wallpaper
            .buffers
            .iter()
            .map(|b| b.canvas(&mut self.pool).is_some())
            .collect();
        let (index, canvas) = if let Some(index) = released_slot(&available) {
            (
                index,
                self.wallpaper.buffers[index]
                    .canvas(&mut self.pool)
                    .expect("released wallpaper slot"),
            )
        } else {
            if self.wallpaper.buffers.len() >= 2 {
                self.wallpaper.dirty = true;
                return false;
            }
            let Ok((buffer, canvas)) = self.pool.create_buffer(
                width as i32,
                height as i32,
                stride,
                wl_shm::Format::Argb8888,
            ) else {
                self.log("wallpaper-shm-allocate-failed");
                return false;
            };
            self.wallpaper.buffers.push(buffer);
            (self.wallpaper.buffers.len() - 1, canvas)
        };
        let video_pixels = self.video_display.as_ref().and_then(|key| {
            self.video_candidate
                .as_ref()
                .filter(|video| video.decoder.key == *key)
                .or_else(|| {
                    self.video_active
                        .as_ref()
                        .filter(|video| video.decoder.key == *key)
                })
                .or_else(|| {
                    self.video_previous
                        .as_ref()
                        .filter(|video| video.decoder.key == *key)
                })
                .and_then(|video| video.frame.as_deref())
        });
        let video_drawn = video_pixels.is_some();
        let rendered = if let Some(pixels) = video_pixels {
            if pixels.len() != canvas.len() {
                Err("video frame size mismatch".into())
            } else {
                canvas.copy_from_slice(pixels);
                Ok(())
            }
        } else if let Some(path) = self.wallpaper_path.as_deref() {
            self.background_cache
                .render(
                    path,
                    self.wallpaper_generation_root.as_deref(),
                    width,
                    height,
                    FitMode::Crop,
                )
                .and_then(|pixels| {
                    if pixels.len() != canvas.len() {
                        return Err("wallpaper pixel size mismatch".into());
                    }
                    canvas.copy_from_slice(pixels);
                    Ok(())
                })
        } else {
            self.renderer.draw_wallpaper(canvas, width, height)
        };
        if let Err(error) = rendered {
            self.wallpaper.dirty = false;
            self.log(&format!("wallpaper-render-failed {error}"));
            return false;
        }
        let Some(layer) = self.wallpaper.layer.as_ref() else {
            return false;
        };
        layer
            .wl_surface()
            .damage_buffer(0, 0, width as i32, height as i32);
        layer.wl_surface().frame(qh, layer.wl_surface().clone());
        if self.wallpaper.buffers[index]
            .attach_to(layer.wl_surface())
            .is_err()
        {
            self.log("wallpaper-attach-failed");
            return false;
        }
        layer.commit();
        self.wallpaper.frame_pending = true;
        self.wallpaper.dirty = false;
        if video_drawn {
            self.video_submitted = self.video_submitted.saturating_add(1);
            self.video_last_submitted_ms = Some(video_status::monotonic_ms());
        }
        self.log("wallpaper-commit");
        true
    }

    fn launch_app(&mut self, index: usize) {
        if self.launch_in_flight || self.route != Route::Drawer {
            if self.launch_in_flight {
                self.log("app-launch-worker-still-running");
            }
            return;
        }
        let Some(app) = self.apps.get(index) else {
            return;
        };
        let id = app.id.clone();
        let swaymsg = self.swaymsg.clone();
        let sender = self.launch_sender.clone();
        self.launch_seq = self.launch_seq.wrapping_add(1);
        let attempt = self.launch_seq;
        self.hide(); // existing live deck remains beneath this overlay
        self.launching = true;
        self.launch_in_flight = true;
        self.launch_started = Some(Instant::now());
        thread::spawn(move || {
            let result = swaymsg
                .as_deref()
                .ok_or_else(|| "K230_SWAYMSG is unavailable".into())
                .and_then(|path| launch_selected(&id, path));
            let _ = sender.send((attempt, result));
        });
    }

    fn ensure_layer(&mut self, qh: &QueueHandle<Self>) -> bool {
        if self.layer.is_none() {
            let surface = self.compositor.create_surface(qh);
            let layer = self.layer_shell.create_layer_surface(
                qh,
                surface,
                Layer::Overlay,
                Some("k230-shell-drawer"),
                None,
            );
            layer.set_anchor(Anchor::TOP | Anchor::BOTTOM | Anchor::LEFT | Anchor::RIGHT);
            layer.set_size(0, 0);
            layer.set_exclusive_zone(0);
            layer.set_keyboard_interactivity(KeyboardInteractivity::None);
            let Ok(empty) = Region::new(&self.compositor) else {
                self.log("input-region-unavailable");
                return false;
            };
            layer.wl_surface().set_input_region(Some(empty.wl_region()));
            layer.commit();
            self.layer = Some(layer);
            self.configured = false;
            self.input_ready = false;
            self.input_region_key = None;
            self.log("map-request");
        }
        true
    }

    fn show(&mut self, qh: &QueueHandle<Self>, route: Route) -> bool {
        if route == Route::Hide {
            self.hide();
            return true;
        }
        self.reveal.clear();
        if route != Route::Settings && self.wifi_view.page != WifiPage::Closed {
            if let Some((id, WifiKind::Connect | WifiKind::ConnectSaved)) = self.wifi_view.pending {
                self.wifi_worker.cancel(id);
            }
            self.wifi_view.close();
            self.service_view.wifi = None;
            self.renderer.set_services(self.service_view.clone());
        }
        if self.route != route {
            self.nav = DrawerNavigation::default();
            self.renderer.set_drawer_pressed(None);
            self.panel_start = None;
            self.panel_swipe_owned = false;
            self.notification_coast.stop();
            self.notification_settle = None;
            self.notification_wait = None;
            self.service_view.notification_swipe = None;
            self.renderer.set_services(self.service_view.clone());
        }
        self.route = route;
        self.refresh_route(route);
        if !self.ensure_layer(qh) {
            return false;
        }
        self.dirty = true;
        self.draw(qh);
        true
    }

    fn reveal_message(&mut self, qh: &QueueHandle<Self>, message: RevealMessage) {
        let now = self.started.elapsed().as_millis() as u64;
        if !self.reveal.apply(message, now, self.reduced_motion) {
            self.log("reveal-rejected");
            return;
        }
        if message.surface != Route::Settings && self.wifi_view.page != WifiPage::Closed {
            if let Some((id, WifiKind::Connect | WifiKind::ConnectSaved)) = self.wifi_view.pending {
                self.wifi_worker.cancel(id);
            }
            self.wifi_view.close();
            self.service_view.wifi = None;
            self.renderer.set_services(self.service_view.clone());
        }
        if self.route != message.surface {
            self.panel_start = None;
            self.panel_swipe_owned = false;
            self.notification_coast.stop();
            self.notification_settle = None;
            self.notification_wait = None;
            self.service_view.notification_swipe = None;
            self.renderer.set_services(self.service_view.clone());
        }
        self.route = message.surface;
        if message.phase == Phase::Begin {
            self.refresh_route(message.surface);
        }
        if !self.ensure_layer(qh) {
            self.reveal.clear();
            return;
        }
        if message.phase == Phase::Begin {
            // Drop overlay hit targets before the compositor-owned finger
            // stream can see this layer; do not wait for a frame callback.
            self.input_region();
            if let Some(layer) = self.layer.as_ref() {
                layer.commit();
            }
        }
        self.dirty = true;
    }

    fn input_region(&mut self) {
        let ready = self.reveal.surface().is_none() || self.reveal.input_ready();
        let key = (self.route, self.width, self.height, ready);
        if self.input_region_key == Some(key) {
            return;
        }
        let Some(layer) = self.layer.as_ref() else {
            return;
        };
        let Ok(region) = Region::new(&self.compositor) else {
            return;
        };
        if let Some((x, y, width, height)) =
            panel_input_rect(self.route, self.width, self.height, ready)
        {
            region.add(x, y, width, height);
        }
        layer
            .wl_surface()
            .set_input_region(Some(region.wl_region()));
        self.input_ready = ready;
        self.input_region_key = Some(key);
    }

    fn hide(&mut self) {
        self.touch.cancel();
        self.panel_start = None;
        self.service_view.notification_swipe = None;
        self.panel_swipe_owned = false;
        self.notification_coast.stop();
        self.notification_settle = None;
        self.notification_wait = None;
        if let Some((id, WifiKind::Connect | WifiKind::ConnectSaved)) = self.wifi_view.pending {
            self.wifi_worker.cancel(id);
        }
        self.wifi_view.close();
        self.service_view.wifi = None;
        self.renderer.set_services(self.service_view.clone());
        self.theme_view = ThemeView::default();
        self.renderer.set_theme_view(self.theme_view.clone());
        self.nav = DrawerNavigation::default();
        self.renderer.set_drawer_pressed(None);
        self.reveal.clear();
        self.layer.take();
        self.configured = false;
        self.frame_pending = false;
        self.dirty = false;
        self.buffers.clear();
        self.input_ready = false;
        self.input_region_key = None;
        self.log("unmap");
    }

    fn draw(&mut self, qh: &QueueHandle<Self>) -> bool {
        if self.appearance_pending || !self.configured || self.frame_pending || self.layer.is_none()
        {
            return false;
        }
        let Some(size) = frame_bytes(self.width, self.height) else {
            self.log("invalid-geometry");
            return false;
        };
        let stride = (self.width * 4) as i32;
        self.buffers
            .retain(|b| b.stride() == stride && b.height() == self.height as i32);
        let available: Vec<bool> = self
            .buffers
            .iter()
            .map(|b| b.canvas(&mut self.pool).is_some())
            .collect();
        let reusable = released_slot(&available);
        let (index, canvas) = if let Some(index) = reusable {
            (
                index,
                self.buffers[index]
                    .canvas(&mut self.pool)
                    .expect("released slot"),
            )
        } else {
            if self.buffers.len() >= 3 {
                self.dirty = true;
                return false;
            }
            let Ok((buffer, canvas)) = self.pool.create_buffer(
                self.width as i32,
                self.height as i32,
                stride,
                wl_shm::Format::Argb8888,
            ) else {
                self.log("shm-allocate-failed");
                return false;
            };
            if canvas.len() != size {
                self.log("shm-size-mismatch");
                return false;
            }
            self.buffers.push(buffer);
            (self.buffers.len() - 1, canvas)
        };
        let progress = if self.reveal.surface().is_some() {
            self.reveal.progress()
        } else {
            1.0
        };
        if let Err(error) = self.renderer.draw(
            canvas,
            RenderParams {
                width: self.width,
                height: self.height,
                route: self.route,
                progress,
                scroll: if self.route == Route::Drawer {
                    self.nav.scroll
                } else {
                    0.0
                },
            },
            &self.apps,
        ) {
            self.log(&format!("render-failed {error}"));
            return false;
        }
        self.input_region();
        let layer = self.layer.as_ref().expect("mapped");
        layer
            .wl_surface()
            .damage_buffer(0, 0, self.width as i32, self.height as i32);
        layer.wl_surface().frame(qh, layer.wl_surface().clone());
        if self.buffers[index].attach_to(layer.wl_surface()).is_err() {
            self.log("shm-attach-failed");
            return false;
        }
        layer.commit();
        self.frame_pending = true;
        self.dirty = false;
        self.log("commit");
        true
    }
}

impl CompositorHandler for ShellClient {
    fn scale_factor_changed(
        &mut self,
        _: &Connection,
        _: &QueueHandle<Self>,
        _: &wl_surface::WlSurface,
        _: i32,
    ) {
    }
    fn transform_changed(
        &mut self,
        _: &Connection,
        _: &QueueHandle<Self>,
        _: &wl_surface::WlSurface,
        _: wl_output::Transform,
    ) {
    }
    fn frame(
        &mut self,
        _: &Connection,
        qh: &QueueHandle<Self>,
        surface: &wl_surface::WlSurface,
        _: u32,
    ) {
        if self
            .wallpaper
            .layer
            .as_ref()
            .is_some_and(|l| l.wl_surface() == surface)
        {
            self.wallpaper.frame_pending = false;
            if self.video_display.is_some() {
                self.video_callbacks = self.video_callbacks.saturating_add(1);
                self.video_last_callback_ms = Some(video_status::monotonic_ms());
            }
            if self.wallpaper.dirty && !self.appearance_pending {
                self.draw_wallpaper(qh);
            }
            return;
        }
        if !self
            .layer
            .as_ref()
            .is_some_and(|l| l.wl_surface() == surface)
        {
            return;
        }
        self.frame_pending = false;
        self.log("frame-done");
        if self.dirty && !self.appearance_pending {
            self.draw(qh);
        }
    }
    fn surface_enter(
        &mut self,
        _: &Connection,
        _: &QueueHandle<Self>,
        _: &wl_surface::WlSurface,
        _: &wl_output::WlOutput,
    ) {
    }
    fn surface_leave(
        &mut self,
        _: &Connection,
        _: &QueueHandle<Self>,
        _: &wl_surface::WlSurface,
        _: &wl_output::WlOutput,
    ) {
    }
}

impl OutputHandler for ShellClient {
    fn output_state(&mut self) -> &mut OutputState {
        &mut self.output_state
    }
    fn new_output(&mut self, _: &Connection, _: &QueueHandle<Self>, _: wl_output::WlOutput) {}
    fn update_output(&mut self, _: &Connection, _: &QueueHandle<Self>, _: wl_output::WlOutput) {}
    fn output_destroyed(&mut self, _: &Connection, _: &QueueHandle<Self>, _: wl_output::WlOutput) {}
}

impl LayerShellHandler for ShellClient {
    fn closed(&mut self, _: &Connection, _: &QueueHandle<Self>, layer: &LayerSurface) {
        if self
            .wallpaper
            .layer
            .as_ref()
            .is_some_and(|wallpaper| wallpaper.wl_surface() == layer.wl_surface())
        {
            self.wallpaper = WallpaperState {
                recreate_after: Some(Instant::now() + Duration::from_millis(500)),
                ..WallpaperState::default()
            };
            self.log("wallpaper-closed");
            return;
        }
        self.hide();
    }
    fn configure(
        &mut self,
        _: &Connection,
        qh: &QueueHandle<Self>,
        layer: &LayerSurface,
        configure: LayerSurfaceConfigure,
        _: u32,
    ) {
        let (width, height) = configure.new_size;
        if self
            .wallpaper
            .layer
            .as_ref()
            .is_some_and(|wallpaper| wallpaper.wl_surface() == layer.wl_surface())
        {
            let mut geometry = (self.wallpaper.width, self.wallpaper.height);
            if configure_size(&mut geometry, width, height).is_none() {
                self.log("wallpaper-configure-rejected");
                return;
            }
            if (self.wallpaper.width, self.wallpaper.height) != geometry {
                self.video_active = None;
                self.video_candidate = None;
                self.video_previous = None;
                self.video_display = None;
                self.video_start_attempted = false;
            }
            (self.wallpaper.width, self.wallpaper.height) = geometry;
            self.wallpaper.configured = true;
            self.wallpaper.dirty = true;
            self.wallpaper.map_started = None;
            self.log(&format!("wallpaper-configure {width}x{height}"));
            self.draw_wallpaper(qh);
            return;
        }
        let mut geometry = (self.width, self.height);
        if configure_size(&mut geometry, width, height).is_none() {
            self.log("configure-rejected");
            return;
        }
        (self.width, self.height) = geometry;
        self.configured = true;
        self.dirty = true;
        self.log(&format!("configure {width}x{height}"));
        self.draw(qh);
    }
}

impl SeatHandler for ShellClient {
    fn seat_state(&mut self) -> &mut SeatState {
        &mut self.seat_state
    }
    fn new_seat(&mut self, _: &Connection, _: &QueueHandle<Self>, _: wl_seat::WlSeat) {}
    fn new_capability(
        &mut self,
        _: &Connection,
        qh: &QueueHandle<Self>,
        seat: wl_seat::WlSeat,
        cap: Capability,
    ) {
        if cap == Capability::Touch && self.touch_device.is_none() {
            self.touch_device = self.seat_state.get_touch(qh, &seat).ok();
            self.log("touch-capability");
        }
    }
    fn remove_capability(
        &mut self,
        _: &Connection,
        _: &QueueHandle<Self>,
        _: wl_seat::WlSeat,
        cap: Capability,
    ) {
        if cap == Capability::Touch {
            self.touch_device.take();
            self.touch.cancel();
            self.panel_start = None;
            self.panel_scrolled = false;
            self.panel_swipe_owned = false;
            self.notification_coast.stop();
            self.notification_settle = None;
            self.notification_wait = None;
            self.service_view.notification_swipe = None;
            self.renderer.set_services(self.service_view.clone());
            self.dirty = true;
            self.log("touch-capability-lost");
        }
    }
    fn remove_seat(&mut self, _: &Connection, _: &QueueHandle<Self>, _: wl_seat::WlSeat) {
        self.touch_device.take();
        self.touch.cancel();
        self.panel_start = None;
        self.panel_scrolled = false;
        self.panel_swipe_owned = false;
        self.notification_coast.stop();
        self.notification_settle = None;
        self.notification_wait = None;
        self.service_view.notification_swipe = None;
        self.renderer.set_services(self.service_view.clone());
        self.dirty = true;
    }
}

impl TouchHandler for ShellClient {
    fn down(
        &mut self,
        _: &Connection,
        qh: &QueueHandle<Self>,
        _: &wl_touch::WlTouch,
        _: u32,
        time_ms: u32,
        surface: wl_surface::WlSurface,
        id: i32,
        pos: (f64, f64),
    ) {
        if self
            .layer
            .as_ref()
            .is_some_and(|l| l.wl_surface() == &surface)
        {
            if self.touch.down(id, pos) {
                if self.wifi_view.page == WifiPage::Closed {
                    self.log(&format!("touch-down {id} {:.1} {:.1}", pos.0, pos.1));
                }
                if self.route == Route::Drawer && self.input_ready {
                    self.nav.down(id, pos, time_ms);
                    if self.renderer.set_drawer_pressed(self.nav.pressed(
                        self.width,
                        self.height,
                        self.apps.len(),
                    )) {
                        self.dirty = true;
                    }
                } else if matches!(self.route, Route::Shade | Route::Settings) && self.input_ready {
                    self.panel_start = Some((id, pos));
                    self.panel_origin_scroll = self.service_view.notification_scroll;
                    let stopped_coast = self.notification_coast.stop();
                    self.panel_scrolled = self.route == Route::Shade
                        && pos.1 >= k230_shell_rust::service_ui::NOTIFICATION_TOP
                        && stopped_coast;
                    self.panel_scroll_dragged = false;
                    self.panel_scroll_sample = Some((pos.1, time_ms));
                    self.panel_scroll_velocity = 0.0;
                    self.panel_swipe_owned = false;
                    self.panel_swipe_cancelled = false;
                    self.panel_swipe_moved = false;
                    if self.route == Route::Shade {
                        if let (Some(_), Some(swipe)) = (
                            self.notification_settle,
                            self.service_view.notification_swipe.as_ref(),
                        ) {
                            if notification_swipe_hit(
                                &self.service_view,
                                swipe,
                                pos,
                                self.width,
                                self.height,
                            ) {
                                self.panel_swipe_owned = true;
                                self.panel_swipe_base = swipe.offset;
                                self.notification_settle = None;
                            }
                        }
                    }
                    self.wifi_origin_scroll = self.wifi_view.scroll;
                    self.wifi_dragged = false;
                    if self.wifi_view.page == WifiPage::Closed {
                        // Arm the carousel only when the touch actually
                        // started inside its band, mirroring the old
                        // `valid_list` gate: an accidental down on the
                        // header/footer chrome must never later be
                        // mistaken for a carousel drag.
                        match self.theme_view.page {
                            ThemePage::List
                                if (THEME_CAROUSEL_TOP..THEME_CAROUSEL_TOP + THEME_GEOMETRY.expanded_h)
                                    .contains(&pos.1) =>
                            {
                                self.theme_carousel.down(id, pos, time_ms);
                                self.sync_theme_pressed();
                            }
                            ThemePage::Preview
                                if (BACKGROUND_CAROUSEL_TOP
                                    ..BACKGROUND_CAROUSEL_TOP + BACKGROUND_GEOMETRY.expanded_h)
                                    .contains(&pos.1) =>
                            {
                                self.background_carousel.down(id, pos, time_ms);
                                self.sync_background_pressed();
                            }
                            _ => {}
                        }
                    }
                }
            } else {
                self.log("touch-second-cancel");
                self.nav.cancel();
                if self.renderer.set_drawer_pressed(None) {
                    self.dirty = true;
                }
                self.panel_start = None;
                self.panel_scrolled = false;
                self.panel_swipe_owned = false;
                self.notification_coast.stop();
                if self.notification_wait.is_none() {
                    self.notification_settle = None;
                    self.settle_notification(0.0, None);
                }
                self.theme_carousel.cancel();
                self.background_carousel.cancel();
                self.sync_theme_pressed();
                self.sync_background_pressed();
                self.wifi_dragged = false;
            }
            if self.dirty {
                self.draw(qh);
            }
        }
    }
    fn up(
        &mut self,
        _: &Connection,
        qh: &QueueHandle<Self>,
        _: &wl_touch::WlTouch,
        _: u32,
        time_ms: u32,
        id: i32,
    ) {
        let point = self.touch.position;
        if self.touch.up(id) {
            if self.wifi_view.page == WifiPage::Closed {
                self.log(&format!("touch-up {id}"));
            }
            if self.route == Route::Drawer && self.input_ready {
                if self.renderer.set_drawer_pressed(None) {
                    self.dirty = true;
                }
                match self
                    .nav
                    .up(id, point, time_ms, self.width, self.height, self.apps.len())
                {
                    Some(DrawerAction::Launch(index)) => self.launch_app(index),
                    Some(DrawerAction::Close) => self.hide(),
                    None => {}
                }
            } else if self.input_ready {
                if let Some((start_id, start)) = self.panel_start.take() {
                    if start_id == id {
                        let swipe = self.service_view.notification_swipe.clone();
                        let list_has_rows = self
                            .service_view
                            .notifications
                            .as_ref()
                            .is_some_and(|snapshot| !snapshot.events.is_empty());
                        if self.panel_swipe_owned {
                            if let Some(swipe) = swipe {
                                let request = (!self.panel_swipe_cancelled
                                    && self.panel_swipe_moved)
                                    .then(|| {
                                        notification_swipe_release(
                                            &self.service_view,
                                            &swipe,
                                            point.1 - start.1,
                                        )
                                    })
                                    .flatten();
                                let target = if request.is_some() {
                                    swipe.offset.signum() * f64::from(self.width)
                                } else {
                                    0.0
                                };
                                self.settle_notification(target, request.map(|_| swipe.event_id));
                            }
                            self.panel_swipe_owned = false;
                            self.panel_swipe_cancelled = false;
                        } else if self.route == Route::Shade
                            && shade_release_closes(start, point, list_has_rows, self.height)
                        {
                            self.hide();
                        } else if self.route == Route::Settings {
                            if self.wifi_view.page != WifiPage::Closed {
                                if !self.wifi_dragged {
                                    if let Some(intent) = wifi_ui::hit(
                                        &self.wifi_view.public(),
                                        start,
                                        point,
                                        self.width,
                                        self.height,
                                    ) {
                                        self.wifi_action(intent);
                                    }
                                }
                            } else {
                                let center_x = f64::from(self.width) / 2.0;
                                let carousel_outcome = match self.theme_view.page {
                                    ThemePage::List => {
                                        let count = self
                                            .theme_view
                                            .list
                                            .as_ref()
                                            .map_or(0, |list| list.themes.len());
                                        self.theme_carousel.up(
                                            id,
                                            point,
                                            time_ms,
                                            count,
                                            center_x,
                                            THEME_CAROUSEL_TOP,
                                        )
                                    }
                                    ThemePage::Preview => {
                                        let count = self
                                            .theme_view
                                            .preview
                                            .as_ref()
                                            .map_or(0, |preview| preview.backgrounds.len());
                                        self.background_carousel.up(
                                            id,
                                            point,
                                            time_ms,
                                            count,
                                            center_x,
                                            BACKGROUND_CAROUSEL_TOP,
                                        )
                                    }
                                    ThemePage::Controls => None,
                                };
                                self.sync_theme_pressed();
                                self.sync_background_pressed();
                                match carousel_outcome {
                                    Some(CarouselOutcome::Confirm(index)) => {
                                        let intent = match self.theme_view.page {
                                            ThemePage::List => ThemeIntent::Theme(index),
                                            ThemePage::Preview => ThemeIntent::Background(index),
                                            ThemePage::Controls => unreachable!(
                                                "a carousel outcome only comes from List/Preview"
                                            ),
                                        };
                                        self.theme_action(intent);
                                    }
                                    Some(CarouselOutcome::Recenter(_) | CarouselOutcome::Consumed) => {
                                        // The carousel owns this touch (a tap that
                                        // missed every slice, or a drag release
                                        // that just armed momentum/settle);
                                        // `tick()` drives the rest, this just
                                        // repaints so it starts moving right away.
                                        self.theme_dirty();
                                    }
                                    None => {
                                        if let Some(intent) = self.theme_view.hit(
                                            start,
                                            point,
                                            self.width,
                                            self.height,
                                        ) {
                                            self.theme_action(intent);
                                        } else if self.theme_view.page == ThemePage::Controls {
                                            if let Some(intent) = panel_intent(
                                                self.route,
                                                start,
                                                point,
                                                self.width,
                                                self.height,
                                                &self.service_view,
                                            ) {
                                                self.panel_action(qh, intent);
                                            }
                                        }
                                    }
                                }
                            }
                        } else if self.panel_scroll_dragged {
                            let fresh = self.panel_scroll_sample.is_some_and(|(_, last_time)| {
                                time_ms.wrapping_sub(last_time) <= 120
                            });
                            self.notification_coast
                                .start(if fresh && !self.reduced_motion {
                                    self.panel_scroll_velocity
                                } else {
                                    0.0
                                });
                        } else if self.panel_scrolled {
                            // A down during coasting is a tap-to-stop, never an event action.
                        } else if let Some(intent) = panel_intent(
                            self.route,
                            start,
                            point,
                            self.width,
                            self.height,
                            &self.service_view,
                        ) {
                            if !(self.panel_scrolled
                                && matches!(intent, PanelIntent::ScrollNotifications(_)))
                            {
                                self.panel_action(qh, intent);
                            }
                        }
                    }
                }
            }
            if self.dirty {
                self.draw(qh);
            }
        }
    }
    fn motion(
        &mut self,
        _: &Connection,
        qh: &QueueHandle<Self>,
        _: &wl_touch::WlTouch,
        time_ms: u32,
        id: i32,
        pos: (f64, f64),
    ) {
        if self.touch.motion(id, pos) {
            if self.wifi_view.page == WifiPage::Closed {
                self.log(&format!("touch-move {id} {:.1} {:.1}", pos.0, pos.1));
            }
            if self.route == Route::Drawer && self.input_ready {
                if self
                    .nav
                    .motion(id, pos, time_ms, self.height, self.apps.len())
                {
                    self.dirty = true;
                }
                if self.renderer.set_drawer_pressed(self.nav.pressed(
                    self.width,
                    self.height,
                    self.apps.len(),
                )) {
                    self.dirty = true;
                }
            } else if self.route == Route::Shade && self.input_ready {
                if let Some((start_id, start)) = self.panel_start {
                    let dy = pos.1 - start.1;
                    if start_id == id
                        && self.panel_swipe_owned
                        && self.service_view.notification_swipe.is_some()
                    {
                        if dy.abs() > SWIPE_VERTICAL_CANCEL && !self.panel_swipe_cancelled {
                            self.panel_swipe_cancelled = true;
                            // The remaining contact is consumed, while the
                            // displaced row visibly returns without a jump.
                            self.settle_notification(0.0, None);
                        } else if !self.panel_swipe_cancelled {
                            if let Some(swipe) = &mut self.service_view.notification_swipe {
                                swipe.offset = (self.panel_swipe_base
                                    + notification_swipe_offset(start.0, pos.0))
                                .clamp(-f64::from(self.width), f64::from(self.width));
                            }
                            self.panel_swipe_moved = true;
                        }
                        self.renderer.set_services(self.service_view.clone());
                        self.dirty = true;
                    } else if start_id == id
                        && !self.panel_scrolled
                        && !self.panel_swipe_owned
                        && self.notification_settle.is_none()
                        && self.service_view.notification_swipe.is_none()
                    {
                        if let Some(swipe) = notification_swipe_start(
                            start,
                            pos,
                            self.width,
                            self.height,
                            &self.service_view,
                        ) {
                            self.service_view.notification_swipe = Some(swipe);
                            self.panel_swipe_owned = true;
                            self.panel_swipe_moved = true;
                            self.panel_swipe_base = 0.0;
                            self.renderer.set_services(self.service_view.clone());
                            self.dirty = true;
                        }
                    }
                    if start_id == id
                        && self.service_view.notification_swipe.is_none()
                        && !self.panel_swipe_owned
                        && start.1 >= k230_shell_rust::service_ui::NOTIFICATION_TOP
                        && dy.abs() > 22.0
                    {
                        let max = self
                            .service_view
                            .notifications
                            .as_ref()
                            .map_or(0.0, |snapshot| {
                                notification_max_scroll(snapshot.events.len(), self.height)
                            });
                        let next = (self.panel_origin_scroll - dy).clamp(0.0, max);
                        if (next - self.service_view.notification_scroll).abs() >= 1.0 {
                            self.service_view.notification_scroll = next;
                            self.renderer.set_services(self.service_view.clone());
                            self.dirty = true;
                        }
                        self.panel_scrolled = true;
                        self.panel_scroll_dragged = true;
                        if let Some((last_y, last_time)) = self.panel_scroll_sample {
                            let dt = time_ms.wrapping_sub(last_time);
                            if (1..=120).contains(&dt) {
                                self.panel_scroll_velocity =
                                    (-(pos.1 - last_y) / f64::from(dt)).clamp(-2.5, 2.5);
                            }
                        }
                        self.panel_scroll_sample = Some((pos.1, time_ms));
                    }
                }
            } else if self.route == Route::Settings
                && self.input_ready
                && self.wifi_view.page == WifiPage::List
            {
                if let Some((start_id, start)) = self.panel_start {
                    let scale_y = 1232.0 / f64::from(self.height.max(1));
                    let dy = (pos.1 - start.1) * scale_y;
                    if start_id == id && start.1 * scale_y >= 338.0 && dy.abs() > 18.0 {
                        self.wifi_dragged = true;
                        let previous = self.wifi_view.scroll;
                        self.wifi_view.scroll = self.wifi_origin_scroll;
                        self.wifi_view.scroll(-dy);
                        if (self.wifi_view.scroll - previous).abs() >= 1.0 {
                            self.wifi_dirty();
                        }
                    }
                }
            } else if self.route == Route::Settings
                && self.input_ready
                && self.theme_view.page != ThemePage::Controls
                && self.wifi_view.page == WifiPage::Closed
            {
                let count = match self.theme_view.page {
                    ThemePage::List => self.theme_view.list.as_ref().map_or(0, |l| l.themes.len()),
                    ThemePage::Preview => self
                        .theme_view
                        .preview
                        .as_ref()
                        .map_or(0, |p| p.backgrounds.len()),
                    ThemePage::Controls => 0,
                };
                let moved = match self.theme_view.page {
                    ThemePage::List => self.theme_carousel.motion(id, pos, time_ms, count),
                    ThemePage::Preview => self.background_carousel.motion(id, pos, time_ms, count),
                    ThemePage::Controls => false,
                };
                if moved {
                    match self.theme_view.page {
                        ThemePage::List => {
                            self.theme_view.theme_position = self.theme_carousel.position();
                        }
                        ThemePage::Preview => {
                            self.theme_view.background_position = self.background_carousel.position();
                        }
                        ThemePage::Controls => {}
                    }
                    self.theme_dirty();
                }
                match self.theme_view.page {
                    ThemePage::List => self.sync_theme_pressed(),
                    ThemePage::Preview => self.sync_background_pressed(),
                    ThemePage::Controls => {}
                }
            }
            if self.dirty {
                self.draw(qh);
            }
        }
    }
    fn shape(
        &mut self,
        _: &Connection,
        _: &QueueHandle<Self>,
        _: &wl_touch::WlTouch,
        _: i32,
        _: f64,
        _: f64,
    ) {
    }
    fn orientation(
        &mut self,
        _: &Connection,
        _: &QueueHandle<Self>,
        _: &wl_touch::WlTouch,
        _: i32,
        _: f64,
    ) {
    }
    fn cancel(&mut self, _: &Connection, qh: &QueueHandle<Self>, _: &wl_touch::WlTouch) {
        self.touch.cancel();
        self.nav.cancel();
        self.renderer.set_drawer_pressed(None);
        self.panel_start = None;
        self.panel_scrolled = false;
        self.panel_swipe_owned = false;
        self.notification_coast.stop();
        self.notification_wait = None;
        self.settle_notification(0.0, None);
        self.renderer.set_services(self.service_view.clone());
        self.theme_carousel.cancel();
        self.background_carousel.cancel();
        self.sync_theme_pressed();
        self.sync_background_pressed();
        self.log("touch-cancel");
        self.dirty = true;
        self.draw(qh);
    }
}

impl ShmHandler for ShellClient {
    fn shm_state(&mut self) -> &mut Shm {
        &mut self.shm
    }
}
delegate_compositor!(ShellClient);
delegate_output!(ShellClient);
delegate_shm!(ShellClient);
delegate_seat!(ShellClient);
delegate_touch!(ShellClient);
delegate_layer!(ShellClient);
delegate_registry!(ShellClient);
impl ProvidesRegistryState for ShellClient {
    fn registry(&mut self) -> &mut RegistryState {
        &mut self.registry_state
    }
    registry_handlers![OutputState, SeatState];
}

fn serve() -> Result<(), String> {
    // Catalog discovery runs before connecting Wayland. A slow XDG scan never
    // stalls an owned touch stream or a route acknowledgement.
    let apps = installed_apps();
    let mut routes = RouteServer::new(socket_path()?)?;
    let mut appearance = AppearanceReceiver::bind(
        appearance_socket_path()?,
        std::env::var_os("K230_THEME_DEFAULT_GENERATION").map(PathBuf::from),
    )?;
    let mut pending_appearance: Option<(AppearanceEvent, Instant, Option<AppearanceSnapshot>)> =
        None;
    let mut pending_video_prepare: Option<(AppearanceEvent, Instant, VideoKey)> = None;
    let conn = Connection::connect_to_env().map_err(|e| e.to_string())?;
    let (globals, mut queue) = registry_queue_init(&conn).map_err(|e| e.to_string())?;
    let qh = queue.handle();
    let compositor = CompositorState::bind(&globals, &qh).map_err(|e| e.to_string())?;
    let layer_shell = LayerShell::bind(&globals, &qh).map_err(|e| e.to_string())?;
    let shm = Shm::bind(&globals, &qh).map_err(|e| e.to_string())?;
    let pool = SlotPool::new(568 * 1232 * 4 * 5, &shm).map_err(|e| e.to_string())?;
    let (launch_sender, launch_results) = mpsc::channel();
    let settings_command = std::env::var_os("K230_SETTINGS")
        .map(PathBuf::from)
        .unwrap_or_default();
    let notification_socket = std::env::var_os("K230_NOTIFICATION_SOCKET")
        .map(PathBuf::from)
        .unwrap_or_default();
    let services = ServiceWorker::spawn(settings_command, notification_socket);
    let wifi_socket = std::env::var_os("K230_WIFI_SOCKET")
        .map(PathBuf::from)
        .unwrap_or_else(|| PathBuf::from("/run/k230-wifi-settings/broker.sock"));
    let wifi_worker = WifiWorker::spawn(wifi_socket);
    let theme_command = std::env::var_os("K230_THEME_COMMAND")
        .map(PathBuf::from)
        .unwrap_or_default();
    let themes = ThemeWorker::spawn(theme_command);
    let mut state = ShellClient {
        compositor,
        layer_shell,
        registry_state: RegistryState::new(&globals),
        seat_state: SeatState::new(&globals, &qh),
        output_state: OutputState::new(&globals, &qh),
        shm,
        pool,
        buffers: Vec::new(),
        layer: None,
        wallpaper: WallpaperState::default(),
        background_cache: BackgroundCache::new(),
        wallpaper_path: fallback_still(appearance.active()),
        wallpaper_generation_root: appearance.active().map(|snapshot| snapshot.path.clone()),
        video_source: appearance.active().and_then(|snapshot| {
            snapshot
                .backgrounds
                .iter()
                .find(|choice| choice.selected && choice.is_video)
                .map(|choice| choice.staged_path.clone())
        }),
        video_active: None,
        video_candidate: None,
        video_previous: None,
        video_display: None,
        video_ffmpeg: std::env::var_os("K230_WALLPAPER_FFMPEG").map(PathBuf::from),
        video_ffprobe: std::env::var_os("K230_WALLPAPER_FFPROBE").map(PathBuf::from),
        video_start_attempted: false,
        video_generation: video_identity(appearance.active()).0,
        video_relative: video_identity(appearance.active()).1,
        video_error: None,
        video_submitted: 0,
        video_callbacks: 0,
        video_last_decoded_ms: None,
        video_last_submitted_ms: None,
        video_last_callback_ms: None,
        video_status_last: Instant::now() - Duration::from_secs(2),
        video_status_runtime: std::env::var_os("XDG_RUNTIME_DIR")
            .map(PathBuf::from)
            .unwrap_or_default(),
        video_cover_path: std::env::var_os("K230_WALLPAPER_COVER_PATH").map(PathBuf::from),
        video_cover_last: Instant::now() - Duration::from_secs(2),
        video_covered: false,
        touch_device: None,
        route: Route::Drawer,
        touch: TouchTrace::default(),
        width: 568,
        height: 1232,
        configured: false,
        dirty: false,
        frame_pending: false,
        started: Instant::now(),
        apps,
        nav: DrawerNavigation::default(),
        nav_tick: Instant::now(),
        launch_sender,
        launch_results,
        launching: false,
        launch_in_flight: false,
        launch_seq: 0,
        launch_started: None,
        swaymsg: std::env::var_os("K230_SWAYMSG").map(PathBuf::from),
        renderer: RendererCache::default(),
        services,
        service_view: ServiceView::default(),
        wifi_worker,
        wifi_view: WifiView::default(),
        wifi_origin_scroll: 0.0,
        wifi_dragged: false,
        themes,
        theme_view: ThemeView::default(),
        theme_carousel: Carousel::new(THEME_GEOMETRY),
        background_carousel: Carousel::new(BACKGROUND_GEOMETRY),
        panel_start: None,
        panel_origin_scroll: 0.0,
        panel_scrolled: false,
        panel_scroll_dragged: false,
        panel_scroll_sample: None,
        panel_scroll_velocity: 0.0,
        notification_coast: NotificationCoast::default(),
        panel_swipe_owned: false,
        panel_swipe_cancelled: false,
        panel_swipe_moved: false,
        panel_swipe_base: 0.0,
        notification_settle: None,
        notification_wait: None,
        appearance_pending: false,
        reveal: RevealState::default(),
        input_ready: false,
        input_region_key: None,
        reduced_motion: reduced_motion_enabled(
            std::env::var("K230_SETTINGS_REDUCED_MOTION")
                .ok()
                .as_deref(),
        ),
        theme_pulse_at: Instant::now(),
    };
    state.service_view.keyboard_gesture_hint =
        std::env::var("K230_KEYBOARD_TOUCH_GESTURES").as_deref() == Ok("1");
    state.renderer.set_appearance(appearance.active().cloned());
    state.renderer.set_services(state.service_view.clone());
    state.renderer.set_theme_view(state.theme_view.clone());
    if !state.ensure_wallpaper(&qh) {
        return Err("wallpaper layer unavailable".into());
    }
    state.log("ready-idle");
    loop {
        queue
            .dispatch_pending(&mut state)
            .map_err(|e| e.to_string())?;
        for _ in 0..8 {
            let Some(reply) = state.services.try_recv() else {
                break;
            };
            state.service_reply(reply);
        }
        for _ in 0..4 {
            let Some(reply) = state.wifi_worker.try_recv() else {
                break;
            };
            state.wifi_reply(reply);
        }
        for _ in 0..4 {
            let Some(reply) = state.themes.try_recv() else {
                break;
            };
            state.theme_reply(reply);
        }
        if state.renderer.poll_theme_image(state.width, state.height) {
            state.dirty = true;
        }
        // Each theme/background row thumbnail decodes independently of the
        // single live wallpaper preview above; without this, a completed
        // decode would sit undrained until some unrelated event happened to
        // mark the frame dirty, and later rows would never even get
        // requested past the worker's bounded queue depth.
        if state.renderer.poll_theme_thumbnails() {
            state.dirty = true;
        }
        if state
            .service_view
            .confirmation
            .as_ref()
            .is_some_and(|confirmation| Instant::now() >= confirmation.expires_at)
        {
            state.service_view.confirmation = None;
            state.service_view.message = Some("Confirmation expired; request again".into());
            state.renderer.set_services(state.service_view.clone());
            state.dirty = true;
        }
        if state.wallpaper.layer.is_none()
            && state
                .wallpaper
                .recreate_after
                .is_some_and(|when| Instant::now() >= when)
        {
            if state.ensure_wallpaper(&qh) {
                state.wallpaper.recreate_after = None;
            } else {
                state.wallpaper.recreate_after = Some(Instant::now() + Duration::from_secs(1));
                state.log("wallpaper-remap-deferred");
            }
        }
        if state.wallpaper.layer.is_some()
            && !state.wallpaper.configured
            && state
                .wallpaper
                .map_started
                .is_some_and(|when| when.elapsed() >= Duration::from_secs(3))
        {
            state.wallpaper = WallpaperState {
                recreate_after: Some(Instant::now() + Duration::from_secs(1)),
                ..WallpaperState::default()
            };
            state.log("wallpaper-configure-timeout");
        }
        if state.video_cover_last.elapsed() >= Duration::from_millis(500) {
            state.video_cover_last = Instant::now();
            state.video_covered = state.video_cover_path.as_deref().is_some_and(|path| {
                video_visibility::certified(
                    path,
                    state.wallpaper.width,
                    state.wallpaper.height,
                    video_status::monotonic_ms(),
                )
            });
        }
        if state.wallpaper.configured && !state.video_start_attempted {
            if let Some(path) = state.video_source.clone() {
                let key = VideoKey {
                    path,
                    width: state.wallpaper.width,
                    height: state.wallpaper.height,
                };
                state.video_start_attempted = true;
                state.video_display = Some(key.clone());
                if !state.reduced_motion && !state.video_covered {
                    match state.start_video(key) {
                        Ok(video) => state.video_active = Some(video),
                        Err(error) => {
                            state.video_error = Some("decoder-unavailable");
                            state.log(&format!("wallpaper-video-fallback {error}"));
                        }
                    }
                }
            }
        }
        if state.wallpaper.configured
            && !state.video_covered
            && !state.reduced_motion
            && state.video_start_attempted
            && state.video_active.is_none()
            && state.video_error.is_none()
        {
            if let Some(key) = state.video_display.clone() {
                match state.start_video(key) {
                    Ok(video) => state.video_active = Some(video),
                    Err(error) => {
                        state.video_error = Some("decoder-unavailable");
                        state.log(&format!("wallpaper-video-fallback {error}"));
                    }
                }
            }
        }
        if let Some(video) = state.video_active.as_mut() {
            if state.video_covered || state.reduced_motion {
                video.pause();
            } else if video.paused {
                if let (Some(ffmpeg), Some(ffprobe)) = (&state.video_ffmpeg, &state.video_ffprobe) {
                    video.resume(ffmpeg, ffprobe);
                }
            }
        }
        let active_changed = state.video_active.as_mut().is_some_and(VideoPlayback::poll);
        let candidate_changed = state
            .video_candidate
            .as_mut()
            .is_some_and(VideoPlayback::poll);
        if active_changed || candidate_changed {
            if active_changed {
                state.video_last_decoded_ms = Some(video_status::monotonic_ms());
            }
            if state
                .video_active
                .as_ref()
                .is_some_and(|video| video.error.is_some())
            {
                state.video_error = state.video_active.as_ref().and_then(|video| video.error);
                state.log("wallpaper-video-fallback decoder-error");
                state.video_active = None;
                state.video_display = None;
            }
            if state.video_display.is_some() {
                state.wallpaper.dirty = true;
            }
        }
        if let Some((event, started, key)) = pending_video_prepare.take() {
            let ready = state.video_candidate.as_ref().is_some_and(|video| {
                video.decoder.key == key && video.frame.is_some() && video.error.is_none()
            });
            let error = state
                .video_candidate
                .as_ref()
                .is_some_and(|video| video.error.is_some());
            if ready || error || started.elapsed() >= Duration::from_millis(1450) {
                if !ready {
                    state.video_candidate = None;
                } else if state.video_covered || state.reduced_motion {
                    if let Some(video) = state.video_candidate.as_mut() {
                        video.pause();
                    }
                }
                if let Err(error) = appearance.respond(event, ready) {
                    state.log(&format!("wallpaper-video-prepare-ack-failed {error}"));
                }
            } else {
                pending_video_prepare = Some((event, started, key));
            }
        }
        match appearance.receive() {
            Ok(Some(event)) => {
                match event.phase {
                    AppearancePhase::Prepare => {
                        let geometry = state
                            .wallpaper
                            .configured
                            .then_some((state.wallpaper.width, state.wallpaper.height));
                        if let Some(key) =
                            geometry.and_then(|size| selected_video(event.snapshot.as_ref(), size))
                        {
                            if state.video_active.as_ref().is_some_and(|video| {
                                video.decoder.key == key && video.frame.is_some()
                            }) {
                                let _ = appearance.respond(event, true);
                            } else {
                                match state.start_video(key.clone()) {
                                    Ok(video) => {
                                        state.video_candidate = Some(video);
                                        pending_video_prepare = Some((event, Instant::now(), key));
                                    }
                                    Err(error) => {
                                        state.log(&format!(
                                            "appearance-video-prepare-rejected {error}"
                                        ));
                                        let _ = appearance.respond(event, false);
                                    }
                                }
                            }
                            continue;
                        }
                        let result = appearance_renderable(
                            event.snapshot.as_ref(),
                            &mut state.background_cache,
                            geometry,
                        );
                        let accepted = result.is_ok();
                        if let Err(error) = result {
                            state.log(&format!("appearance-prepare-rejected {error}"));
                        }
                        if let Err(error) = appearance.respond(event, accepted) {
                            state.log(&format!("appearance-prepare-ack-failed {error}"));
                        }
                    }
                    AppearancePhase::Commit | AppearancePhase::Rollback => {
                        let previous = appearance.active().cloned();
                        let geometry = state
                            .wallpaper
                            .configured
                            .then_some((state.wallpaper.width, state.wallpaper.height));
                        let video_key =
                            geometry.and_then(|size| selected_video(event.snapshot.as_ref(), size));
                        let video_ready = video_key.as_ref().is_none_or(|key| {
                            state.video_candidate.as_ref().is_some_and(|video| {
                                &video.decoder.key == key
                                    && video.frame.is_some()
                                    && video.error.is_none()
                            }) || state.video_active.as_ref().is_some_and(|video| {
                                &video.decoder.key == key
                                    && video.frame.is_some()
                                    && video.error.is_none()
                            }) || state.video_previous.as_ref().is_some_and(|video| {
                                &video.decoder.key == key && video.frame.is_some()
                            })
                        });
                        let renderable = if !video_ready {
                            Err("video frame unavailable".into())
                        } else if video_key.is_some() {
                            Ok(())
                        } else {
                            appearance_renderable(
                                event.snapshot.as_ref(),
                                &mut state.background_cache,
                                geometry,
                            )
                        };
                        if let Err(error) = renderable {
                            state.log(&format!("appearance-commit-rejected {error}"));
                            let _ = appearance.respond(event, false);
                        } else {
                            state.wallpaper_path = fallback_still(event.snapshot.as_ref());
                            state.wallpaper_generation_root =
                                event.snapshot.as_ref().map(|snapshot| snapshot.path.clone());
                            state.video_display = video_key;
                            state.renderer.set_appearance(event.snapshot.clone());
                            state.appearance_pending = true;
                            state.dirty = true;
                            state.wallpaper.dirty = true;
                            pending_appearance = Some((event, Instant::now(), previous));
                        }
                    }
                }
            }
            Ok(None) => {}
            Err(error) => state.log(&format!("appearance-receive-failed {error}")),
        }
        for _ in 0..4 {
            let Ok((attempt, result)) = state.launch_results.try_recv() else {
                break;
            };
            if attempt == state.launch_seq {
                state.launch_in_flight = false;
                if state.launching {
                    state.launching = false;
                    state.launch_started = None;
                    if let Err(error) = result {
                        state.log(&format!("app-launch-failed {error}"));
                        state.show(&qh, Route::Drawer);
                    } else {
                        state.log("app-launch-requested");
                    }
                } else {
                    state.log("late-app-launch-result");
                }
            } else {
                state.log("stale-app-launch-result");
            }
        }
        if state.launching
            && state
                .launch_started
                .is_some_and(|started| started.elapsed() >= Duration::from_secs(3))
        {
            state.launching = false;
            state.launch_started = None;
            state.log("app-launch-timeout");
            state.show(&qh, Route::Drawer);
        }
        let now = Instant::now();
        let elapsed = now
            .duration_since(state.nav_tick)
            .as_millis()
            .min(u128::from(u32::MAX)) as u32;
        state.nav_tick = now;
        if state.route == Route::Drawer && state.nav.tick(elapsed, state.height, state.apps.len()) {
            state.dirty = true;
        }
        state.tick_notifications(elapsed);
        if state.route == Route::Settings {
            let count = match state.theme_view.page {
                ThemePage::List => state.theme_view.list.as_ref().map_or(0, |l| l.themes.len()),
                ThemePage::Preview => state
                    .theme_view
                    .preview
                    .as_ref()
                    .map_or(0, |p| p.backgrounds.len()),
                ThemePage::Controls => 0,
            };
            let moved = match state.theme_view.page {
                ThemePage::List => state.theme_carousel.tick(elapsed, count),
                ThemePage::Preview => state.background_carousel.tick(elapsed, count),
                ThemePage::Controls => false,
            };
            if moved {
                match state.theme_view.page {
                    ThemePage::List => {
                        state.theme_view.theme_position = state.theme_carousel.position();
                    }
                    ThemePage::Preview => {
                        state.theme_view.background_position = state.background_carousel.position();
                    }
                    ThemePage::Controls => {}
                }
                state.theme_dirty();
            }
            // Idle-redraw fix: this used to unconditionally set `dirty =
            // true` every single iteration while any thumbnail was pending,
            // regardless of whether anything actually changed that
            // iteration. `poll_theme_thumbnails`/`poll_theme_image` (called
            // unconditionally near the top of this loop, every iteration,
            // independent of `dirty` or this block) already retry dropped
            // requests and already set `dirty` themselves the moment a
            // decode actually completes -- so forcing it here too bought
            // nothing but a full scene render + Wayland commit at whatever
            // rate the loop happened to wake (effectively the panel's own
            // ~15fps), burning single-core CPU that competed with the very
            // decode work a pending thumbnail, still preview, or activation
            // was waiting on. The one legitimate reason left to redraw
            // without anything having changed is to advance the loading
            // spinner itself, and that only needs a few frames a second --
            // see `THEME_PULSE_INTERVAL`'s own doc.
            let waiting_on_background_work = state.renderer.theme_thumbnails_pending()
                || state.renderer.theme_preview_image_pending()
                || matches!(state.theme_view.pending, Some(ThemeRequest::Activate { .. }));
            if waiting_on_background_work
                && now.duration_since(state.theme_pulse_at) >= THEME_PULSE_INTERVAL
            {
                state.theme_pulse_at = now;
                state.theme_view.pulse_phase = (state.theme_view.pulse_phase + 0.12) % 1.0;
                state.theme_dirty();
            }
        }
        if state
            .reveal
            .tick(state.started.elapsed().as_millis() as u64)
        {
            if state.reveal.surface().is_none() {
                state.hide();
            } else {
                state.dirty = true;
            }
        }
        // A release can arrive after all bounded slots were busy. Retry from
        // the event loop so the deferred touch frame is eventually submitted.
        if let Some((event, started, previous)) = pending_appearance.take() {
            let overlay_ready = state.layer.is_none() || (state.configured && !state.frame_pending);
            // `draw_wallpaper()` no longer requires its own outstanding frame
            // callback to have fired (see its comment): the background layer
            // can be fully occluded by an ordinary maximized app or the card
            // deck's backdrop, and a compositor may then never send that
            // callback at all. Mirror the same relaxed condition here so this
            // readiness check does not itself keep the transaction pending
            // forever waiting on a signal that will never arrive.
            let ready = state.wallpaper.configured && overlay_ready;
            if !ready && started.elapsed() < Duration::from_millis(1400) {
                pending_appearance = Some((event, started, previous));
            } else {
                let accepted = if ready {
                    state.appearance_pending = false;
                    let background = state.draw_wallpaper(&qh);
                    if !background {
                        state.log("appearance-commit-rejected draw-wallpaper-failed");
                    }
                    let foreground = state.layer.is_none() || state.draw(&qh);
                    if background && !foreground {
                        state.log("appearance-commit-rejected draw-failed");
                    }
                    state.appearance_pending = true;
                    let flushed = queue.flush().is_ok();
                    if background && foreground && !flushed {
                        state.log("appearance-commit-rejected flush-failed");
                    }
                    background && foreground && flushed
                } else {
                    state.log(&format!(
                        "appearance-commit-rejected ready-timeout \
                         wallpaper-configured={} wallpaper-frame-pending={} \
                         overlay-layer-present={} overlay-configured={} overlay-frame-pending={}",
                        state.wallpaper.configured,
                        state.wallpaper.frame_pending,
                        state.layer.is_some(),
                        state.configured,
                        state.frame_pending,
                    ));
                    false
                };
                if !accepted {
                    state.wallpaper_path = fallback_still(previous.as_ref());
                    state.wallpaper_generation_root =
                        previous.as_ref().map(|snapshot| snapshot.path.clone());
                    state.video_display = selected_video(
                        previous.as_ref(),
                        (state.wallpaper.width, state.wallpaper.height),
                    );
                    state.renderer.set_appearance(previous);
                    state.dirty = true;
                    state.wallpaper.dirty = true;
                    state.video_candidate = None;
                } else {
                    state.video_source = state.video_display.as_ref().map(|key| key.path.clone());
                    state.video_start_attempted = state.video_source.is_some();
                    let identity = video_identity(event.snapshot.as_ref());
                    state.video_generation = identity.0;
                    state.video_relative = identity.1;
                    state.video_error = None;
                    state.video_submitted = 0;
                    state.video_callbacks = 0;
                    state.video_last_decoded_ms = None;
                    state.video_last_submitted_ms = None;
                    state.video_last_callback_ms = None;
                    let slot = resolve_video_slot(
                        state.video_display.as_ref(),
                        state.video_active.as_ref().map(|video| &video.decoder.key),
                        state
                            .video_candidate
                            .as_ref()
                            .map(|video| &video.decoder.key),
                        state
                            .video_previous
                            .as_ref()
                            .map(|video| &video.decoder.key),
                    );
                    if slot != VideoSlot::Active {
                        let mut former = state.video_active.take();
                        if let Some(video) = former.as_mut() {
                            video.pause();
                        }
                        state.video_active = match slot {
                            VideoSlot::Candidate => state.video_candidate.take(),
                            VideoSlot::Previous => state.video_previous.take(),
                            VideoSlot::Active | VideoSlot::None => None,
                        };
                        state.video_previous = former;
                    }
                    if let Some(video) = state.video_active.as_mut() {
                        if state.video_covered || state.reduced_motion {
                            video.pause();
                        }
                    }
                    state.video_candidate = None;
                }
                state.appearance_pending = false;
                if let Err(error) = appearance.respond(event, accepted) {
                    state.log(&format!("appearance-ack-failed {error}"));
                }
            }
        }
        if state.dirty && !state.frame_pending && pending_appearance.is_none() {
            state.draw(&qh);
        }
        if state.wallpaper.dirty && !state.wallpaper.frame_pending && pending_appearance.is_none() {
            state.draw_wallpaper(&qh);
        }
        if state.video_status_last.elapsed() >= Duration::from_secs(1) {
            state.video_status_last = Instant::now();
            let selected = state.video_relative.as_deref();
            let playback = state.video_active.as_ref();
            let status =
                VideoStatus {
                    schema: 1,
                    generation: state.video_generation.as_deref(),
                    background_fingerprint: state.video_generation.as_deref().zip(selected).map(
                        |(generation, relative)| video_status::fingerprint(generation, relative),
                    ),
                    decoder_pid: playback.and_then(|video| video.decoder.decoder_pid()),
                    state: if selected.is_none() {
                        "still"
                    } else if state.reduced_motion {
                        "paused-reduced-motion"
                    } else if state.video_covered {
                        "paused-covered"
                    } else if state.video_error.is_some() {
                        "error"
                    } else if playback.is_some_and(|video| video.frame.is_some()) {
                        "playing"
                    } else {
                        "unsupported"
                    },
                    error_category: state.video_error,
                    frames_decoded: playback.map_or(0, VideoPlayback::decoded),
                    frames_submitted: state.video_submitted,
                    frame_callbacks: state.video_callbacks,
                    last_decoded_monotonic_ms: state.video_last_decoded_ms,
                    last_submitted_monotonic_ms: state.video_last_submitted_ms,
                    last_callback_monotonic_ms: state.video_last_callback_ms,
                };
            if let Err(error) = video_status::write_private(&state.video_status_runtime, &status) {
                state.log(&format!("wallpaper-status-unavailable {error}"));
            }
        }
        queue.flush().map_err(|e| e.to_string())?;
        let Some(read_guard) = queue.prepare_read() else {
            continue;
        };
        let peer_fd = routes.peer.as_ref().map_or(-1, |p| p.stream.as_raw_fd());
        let appearance_peer_fd = appearance.peer_fd().unwrap_or(-1);
        let mut fds = [
            libc::pollfd {
                fd: queue.as_fd().as_raw_fd(),
                events: libc::POLLIN,
                revents: 0,
            },
            libc::pollfd {
                fd: routes.listener.as_raw_fd(),
                events: libc::POLLIN,
                revents: 0,
            },
            libc::pollfd {
                fd: peer_fd,
                events: libc::POLLIN,
                revents: 0,
            },
            libc::pollfd {
                fd: appearance.listener_fd(),
                events: libc::POLLIN,
                revents: 0,
            },
            libc::pollfd {
                fd: appearance_peer_fd,
                events: libc::POLLIN,
                revents: 0,
            },
        ];
        let timeout = if state.reveal.settling()
            || state.nav.coasting()
            || state.notification_coast.moving()
            || state.notification_settle.is_some()
            || state.notification_wait.is_some()
            || routes.has_line()
            || pending_appearance.is_some()
            || (state.route == Route::Settings
                && (state.theme_carousel.is_animating()
                    || state.background_carousel.is_animating()
                    || state.renderer.theme_thumbnails_pending()
                    || state.renderer.theme_preview_image_pending()
                    || matches!(state.theme_view.pending, Some(ThemeRequest::Activate { .. }))))
        {
            16
        } else {
            100
        };
        let polled = unsafe { libc::poll(fds.as_mut_ptr(), fds.len() as libc::nfds_t, timeout) };
        if polled < 0 {
            if std::io::Error::last_os_error().kind() == std::io::ErrorKind::Interrupted {
                continue;
            }
            return Err(std::io::Error::last_os_error().to_string());
        }
        if fds[0].revents & libc::POLLIN != 0 {
            read_guard.read().map_err(|e| e.to_string())?;
        } else {
            drop(read_guard);
        }
        if fds[1].revents & libc::POLLIN != 0 {
            routes.accept();
        }
        if fds[3].revents & libc::POLLIN != 0 {
            if let Err(error) = appearance.accept() {
                state.log(&format!("appearance-accept-failed {error}"));
            }
        }
        if routes.has_line()
            || fds[2].revents & (libc::POLLIN | libc::POLLHUP) != 0
            || routes
                .peer
                .as_ref()
                .is_some_and(|p| Instant::now() >= p.deadline)
        {
            drain_routes(
                || routes.receive(),
                |record| match record {
                    Received::Route(route, mut peer) => {
                        let mapped = state.show(&qh, route);
                        let reply: &[u8] = if mapped && queue.flush().is_ok() {
                            b"OK\n"
                        } else {
                            b"ERR\n"
                        };
                        let _ = peer.write_all(reply);
                    }
                    Received::Reveal(message) => state.reveal_message(&qh, message),
                    Received::Abort => {
                        state.reveal.eof(
                            state.started.elapsed().as_millis() as u64,
                            state.reduced_motion,
                        );
                        state.dirty = true;
                    }
                },
            );
            if state.dirty && !state.frame_pending {
                state.draw(&qh);
            }
        }
    }
}

fn main() {
    let args: Vec<String> = std::env::args().collect();
    let outcome = match args.as_slice() {
        [_, flag] if flag == "--serve" => serve(),
        [_, flag, route] if flag == "--surface" => request(route),
        [_, flag, route, output] if flag == "--render-fixture" => {
            let selected = Route::parse(format!("{route}\n").as_bytes())
                .ok_or("unsupported fixture route".to_string());
            selected.and_then(|selected| export_png(
                &PathBuf::from(output), 568, 1232, selected, &installed_apps()))
        }
        [_, flag, source, generation_root, width, height] if flag == "--write-wallpaper-cache" => {
            // Precompute a prepared theme generation's panel-sized wallpaper
            // decode so a later commit/restart/rollback can load it instead
            // of decoding the full-size source again (background_decode.rs).
            // Used both by `tools/theme_activate.py`'s `prepare()` at
            // runtime and by a native-arch build of this same binary at Nix
            // build time for the one pinned bundled generation
            // (nix/handheld-theme-default). Never touches Wayland.
            match (width.parse::<u32>(), height.parse::<u32>()) {
                (Ok(width), Ok(height)) => k230_shell_rust::background_decode::write_wallpaper_cache(
                    std::path::Path::new(source),
                    std::path::Path::new(generation_root),
                    width,
                    height,
                ),
                _ => Err("invalid wallpaper cache geometry".into()),
            }
        }
        [_, flag, source, dest_dir, variant, width, height] if flag == "--write-thumbnail-cache" => {
            // Precompute a build-time thumbnail for one of the bundled
            // built-in themes' `preview.png` or background images, at one
            // of `theme_carousel`'s two carousel geometries' two variant
            // sizes, keyed by `source`'s own content hash into `dest_dir` --
            // the read-only seed directory this package ships -- so the
            // chooser's very first view of a bundled theme never pays a
            // full source decode, whether it reads the pinned Nix store
            // path or a later byte-identical staged generation copy of it
            // (see `theme_thumbnails::write_builtin_thumbnail`'s own doc).
            // Used only by `nix/handheld-theme-default/default.nix`, via a
            // native-arch build of this same binary. Never touches Wayland.
            let parsed_variant = match variant.as_str() {
                "expanded" => Ok(k230_shell_rust::theme_thumbnails::Variant::Expanded),
                "slice" => Ok(k230_shell_rust::theme_thumbnails::Variant::Slice),
                _ => Err("invalid thumbnail cache variant".to_string()),
            };
            match (parsed_variant, width.parse::<u32>(), height.parse::<u32>()) {
                (Ok(variant), Ok(width), Ok(height)) => {
                    k230_shell_rust::theme_thumbnails::write_builtin_thumbnail(
                        std::path::Path::new(source),
                        std::path::Path::new(dest_dir),
                        variant,
                        width,
                        height,
                    )
                }
                _ => Err("invalid thumbnail cache geometry".into()),
            }
        }
        _ => Err(
            "usage: k230-shell-rust --serve | --surface drawer|shade|settings|hide | --render-fixture drawer|shade|settings OUTPUT.png | --write-wallpaper-cache SOURCE GENERATION_ROOT WIDTH HEIGHT | --write-thumbnail-cache SOURCE DEST_DIR expanded|slice WIDTH HEIGHT".into(),
        ),
    };
    if let Err(error) = outcome {
        eprintln!("k230-shell-rust: {error}");
        std::process::exit(1);
    }
}

#[cfg(test)]
mod route_tests {
    use super::*;
    use std::os::unix::fs::DirBuilderExt;

    #[test]
    fn shade_upward_contact_closes_only_after_valid_release() {
        let mut touch = TouchTrace::default();
        assert!(touch.down(3, (282.0, 580.0)));
        assert!(touch.motion(3, (280.0, 440.0)));
        assert!(touch.up(3));
        assert!(shade_close_swipe((282.0, 580.0), touch.position));
        assert!(!shade_close_swipe((282.0, 580.0), (282.0, 540.0)));
        assert!(!shade_close_swipe((282.0, 580.0), (420.0, 440.0)));
        assert!(touch.down(4, (280.0, 580.0)));
        touch.cancel();
        assert!(!touch.up(4));
        assert!(shade_release_closes(
            (280.0, 580.0),
            (280.0, 300.0),
            false,
            1232
        ));
        assert!(shade_release_closes(
            (280.0, 170.0),
            (280.0, 80.0),
            true,
            1232
        ));
        assert!(!shade_release_closes(
            (280.0, 580.0),
            (280.0, 300.0),
            true,
            1232
        ));
    }

    #[test]
    fn shade_to_settings_expands_mapped_input_region() {
        assert_eq!(
            panel_input_rect(Route::Shade, 568, 1232, true),
            Some((0, 0, 568, 800))
        );
        assert_eq!(
            panel_input_rect(Route::Settings, 568, 1232, true),
            Some((0, 0, 568, 1232))
        );
        assert_eq!(panel_input_rect(Route::Shade, 568, 1232, false), None);
        assert_eq!(
            panel_input_rect(Route::Shade, 600, 1200, true),
            Some((0, 0, 600, 780))
        );
    }

    /// A rollback transaction can settle on a generation whose decoder was
    /// demoted to `video_previous` (kept paused, with its last frame) when a
    /// newer generation was committed. The resolved slot must be `Previous`
    /// so that generation is restored immediately rather than waiting for a
    /// fresh decode, and a display key matching nothing must resolve to
    /// `None` rather than fabricating a match.
    #[test]
    fn rollback_resolves_to_retained_previous_decoder_without_new_decode() {
        let generation_a = VideoKey {
            path: PathBuf::from("/tmp/a.mp4"),
            width: 568,
            height: 1232,
        };
        let generation_b = VideoKey {
            path: PathBuf::from("/tmp/b.mp4"),
            width: 568,
            height: 1232,
        };
        let unrelated = VideoKey {
            path: PathBuf::from("/tmp/c.mp4"),
            width: 568,
            height: 1232,
        };

        // Committed generation B is active; A was demoted to `previous`
        // (paused, with its last frame retained) rather than dropped.
        let active = Some(&generation_b);
        let candidate = None;
        let previous = Some(&generation_a);

        // A rollback now targets generation A: it must resolve to the
        // retained previous slot, not `None` (which would force a fresh
        // decode and stall restoration) and not `Active` (B is not A).
        assert_eq!(
            resolve_video_slot(Some(&generation_a), active, candidate, previous),
            VideoSlot::Previous
        );

        // Re-committing the already-active generation keeps it in place.
        assert_eq!(
            resolve_video_slot(Some(&generation_b), active, candidate, previous),
            VideoSlot::Active
        );

        // A generation matching none of the retained slots has nothing to
        // restore from.
        assert_eq!(
            resolve_video_slot(Some(&unrelated), active, candidate, previous),
            VideoSlot::None
        );

        // No selected video at all resolves to `None`.
        assert_eq!(
            resolve_video_slot(None, active, candidate, previous),
            VideoSlot::None
        );

        // A prepared candidate takes priority over a stale previous slot
        // when both happen to name the same generation.
        assert_eq!(
            resolve_video_slot(
                Some(&generation_a),
                active,
                Some(&generation_a),
                previous
            ),
            VideoSlot::Candidate
        );
    }

    #[test]
    fn appearance_media_requires_a_configured_still_decoder() {
        let mut snapshot = AppearanceSnapshot {
            generation: "0123456789abcdef01234567".into(),
            path: "/tmp/fixture-generation".into(),
            icon_theme: None,
            background: None,
            selected_background: None,
            backgrounds: vec![],
            palette: Default::default(),
            sections: Default::default(),
            applied: vec![],
            unavailable: vec![],
            unknown: vec![],
        };
        let mut cache = BackgroundCache::new();
        assert!(appearance_renderable(Some(&snapshot), &mut cache, None).is_ok());
        snapshot.selected_background = Some("/tmp/fixture.webm".into());
        assert!(appearance_renderable(Some(&snapshot), &mut cache, Some((568, 1232))).is_err());
        snapshot.background = Some("/tmp/fixture.png".into());
        assert!(appearance_renderable(Some(&snapshot), &mut cache, None).is_err());
    }

    #[test]
    fn sway_back_failure_blocks_launch_handoff() {
        let script = std::env::temp_dir().join(format!(
            "k230-sway-back-{}-{}",
            std::process::id(),
            std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .unwrap()
                .as_nanos()
        ));
        fs::write(&script, "#!/bin/sh\nexit 2\n").unwrap();
        fs::set_permissions(&script, fs::Permissions::from_mode(0o700)).unwrap();
        assert!(swaymsg_back(&script).is_err());
        fs::write(&script, "#!/bin/sh\nexit 0\n").unwrap();
        assert!(swaymsg_back(&script).is_ok());
        fs::remove_file(script).unwrap();
    }

    #[test]
    fn split_stream_finish_and_premature_eof() {
        let runtime = std::env::temp_dir().join(format!(
            "k230-shell-route-{}-{}",
            std::process::id(),
            std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .unwrap()
                .as_nanos()
        ));
        fs::DirBuilder::new().mode(0o700).create(&runtime).unwrap();
        let path = runtime.join(SOCKET_NAME);
        let mut server = RouteServer::new(path.clone()).unwrap();
        let mut client = UnixStream::connect(&path).unwrap();
        server.accept();
        let begin = b"{\"v\":1,\"kind\":\"reveal\",\"surface\":\"drawer\",\"phase\":\"begin\",\"seq\":19,\"progress\":0}\n";
        client.write_all(&begin[..12]).unwrap();
        assert!(server.receive().is_none());
        client.write_all(&begin[12..]).unwrap();
        let Some(Received::Reveal(message)) = server.receive() else {
            panic!("missing begin");
        };
        assert_eq!(message.phase, Phase::Begin);
        client.shutdown(std::net::Shutdown::Both).unwrap();
        drop(client);
        let mut aborted = false;
        for _ in 0..10 {
            if matches!(server.receive(), Some(Received::Abort)) {
                aborted = true;
                break;
            }
            thread::sleep(Duration::from_millis(10));
        }
        assert!(aborted);

        let mut client = UnixStream::connect(&path).unwrap();
        server.accept();
        client.write_all(begin).unwrap();
        assert!(matches!(server.receive(), Some(Received::Reveal(_))));
        let finish = b"{\"v\":1,\"kind\":\"reveal\",\"surface\":\"drawer\",\"phase\":\"finish\",\"seq\":19,\"progress\":1000}\n";
        client.write_all(finish).unwrap();
        let Some(Received::Reveal(message)) = server.receive() else {
            panic!("missing finish");
        };
        assert_eq!(message.phase, Phase::Finish);
        drop(client);
        assert!(server.peer.is_none());
        drop(server);
        fs::remove_dir_all(runtime).unwrap();
    }

    #[test]
    fn buffered_progress_burst_coalesces_before_next_poll() {
        let runtime = std::env::temp_dir().join(format!(
            "k230-shell-burst-{}-{}",
            std::process::id(),
            std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .unwrap()
                .as_nanos()
        ));
        fs::DirBuilder::new().mode(0o700).create(&runtime).unwrap();
        let path = runtime.join(SOCKET_NAME);
        let mut server = RouteServer::new(path.clone()).unwrap();
        let mut client = UnixStream::connect(&path).unwrap();
        server.accept();
        let mut lines = String::new();
        for (phase, progress) in std::iter::once(("begin", 0))
            .chain((1..=20).map(|index| ("update", index * 40)))
            .chain(std::iter::once(("finish", 1000)))
        {
            lines.push_str(&format!("{{\"v\":1,\"kind\":\"reveal\",\"surface\":\"drawer\",\"phase\":\"{phase}\",\"seq\":22,\"progress\":{progress}}}\n"));
        }
        client.write_all(lines.as_bytes()).unwrap();
        let mut collected = Vec::new();
        drain_routes(
            || server.receive(),
            |record| {
                if let Received::Reveal(message) = record {
                    collected.push((message.phase, message.progress));
                }
            },
        );
        assert_eq!(
            collected,
            vec![
                (Phase::Begin, 0),
                (Phase::Update, 800),
                (Phase::Finish, 1000)
            ]
        );
        assert!(server.peer.is_none());
        assert!(reduced_motion_enabled(Some("1")));
        assert!(!reduced_motion_enabled(Some("0")));
        assert!(!reduced_motion_enabled(None));
        drop(client);
        drop(server);
        fs::remove_dir_all(runtime).unwrap();
    }
}
