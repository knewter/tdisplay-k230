//! Opt-in layer-shell/SHM client. Live app pixels stay with Sway.
//! The layer/event plumbing began from the pinned Rust probe, which follows
//! Smithay Client Toolkit's MIT-licensed v0.20.0 simple_layer example.
use gio::prelude::*;
use k230_shell_rust::{
    app_watch::CatalogWatcher,
    appearance::{AppearanceEvent, AppearancePhase, AppearanceReceiver, AppearanceSnapshot},
    background_decode::{BackgroundCache, FitMode},
    catalog::{applications_dirs, scan_apps, AppEntry},
    configure_preserves_aspect, configure_size, frame_bytes, runtime_trace,
    home_grid, home_state,
    home_screen::{HomeAction, HomeScreen},
    home_widgets,
    navigation::{self, DrawerAction, DrawerNavigation},
    pipewire_ipc,
    pointer_input::{self, PointerContact, POINTER_CONTACT_ID},
    protocol::{Phase, RevealMessage, RevealState, MAX_LINE},
    released_slot,
    render::{export_png, panel_travel_height, RenderParams, RendererCache, SplashParams},
    service_data::{ControlState, ControlValue, ServiceReply, ServiceRequest, ServiceResponse, ServiceWorker},
    service_ui::{
        action_message, backdrop_tap, close_drag_engaged, close_drag_progress,
        close_drag_release_target, close_drag_zone, drawer_close_candidate_after_scroll,
        drawer_close_drag_zone, filter_app_indices, shade_panel_close_zone,
        notification_max_scroll, notification_swipe_hit, notification_swipe_offset,
        notification_swipe_release, notification_swipe_start, notification_swipe_valid,
        panel_intent, settings_output_picker_hit, slider_band, volume_icon_tap_zone,
        volume_slider_band, Confirmation, DrawerSearch, NotificationCoast, NotificationSwipeSettle,
        PanelClose, PanelIntent, ServiceView, SWIPE_VERTICAL_CANCEL,
    },
    slider,
    volume,
    splash::{
        fade_alpha, should_auto_dismiss_failed, should_time_out, window_event_matches, Splash,
        SplashStatus, SplashTarget,
    },
    sway_ipc,
    theme_carousel::{Carousel, CarouselOutcome, BACKGROUND_GEOMETRY, THEME_GEOMETRY},
    theme_catalog::{ThemeReply, ThemeRequest, ThemeResponse, ThemeWorker},
    theme_ui::{
        ThemeIntent, ThemePage, ThemeView, BACKGROUND_CAROUSEL_TOP, THEME_CAROUSEL_TOP,
    },
    video_status::{self, VideoStatus},
    video_visibility,
    video_wallpaper::{VideoEvent, VideoKey, VideoWallpaper},
    wifi_settings::{Kind as WifiKind, WifiRequest, WifiResult, WifiWorker},
    wifi_ui::{self, key_event_intent, Intent as WifiIntent, Page as WifiPage, WifiView},
    Route, TouchTrace,
};
use smithay_client_toolkit::{
    compositor::{CompositorHandler, CompositorState, Region},
    delegate_compositor, delegate_keyboard, delegate_layer, delegate_output, delegate_registry,
    delegate_seat, delegate_shm, delegate_touch, delegate_pointer, delegate_presentation_time,
    presentation_time::{PresentationTimeState, PresentationTimeHandler, PresentTime},
    reexports::protocols::wp::presentation_time::client::wp_presentation_feedback,
    output::{OutputHandler, OutputState},
    registry::{ProvidesRegistryState, RegistryState},
    registry_handlers,
    seat::{
        keyboard::{KeyEvent, KeyboardHandler, Modifiers, RawModifiers},
        touch::TouchHandler,
        pointer::{PointerEvent, PointerEventKind, PointerHandler},
        Capability, SeatHandler, SeatState,
    },
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
    path::{Path, PathBuf},
    process::{Command, Stdio},
    sync::{
        atomic::{AtomicBool, Ordering},
        mpsc::{self, Receiver, Sender},
        Arc,
    },
    thread,
    time::{Duration, Instant},
};
use wayland_client::{
    globals::registry_queue_init,
    protocol::{wl_keyboard, wl_output, wl_seat, wl_shm, wl_surface, wl_touch, wl_pointer},
    Connection, QueueHandle, WEnum,
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

/// Rate limit for `K230_DRAWER_FRAME` (`draw`'s own doc): a scroll/fling
/// redraws far faster than any human reads a log line, so this samples at
/// roughly 2Hz instead of once per frame -- enough to see a sustained
/// board number without flooding the journal during a long scroll.
const DRAWER_FRAME_LOG_INTERVAL: Duration = Duration::from_millis(500);
/// Duration of the drawer long-press-drag's reveal animation (coordinator
/// follow-up: "slide down or fade out over about 180-220 ms with
/// ease-out"), the midpoint of that range.
const DRAWER_DRAG_REVEAL_MS: u64 = 200;

/// A plain pixel copy of the drawer's own last-rendered frame, taken once
/// at the instant a long-press-drag arms (`begin_drawer_home_drag`), and
/// animated (slide + fade, `RendererCache::draw_drawer_reveal`) for
/// `DRAWER_DRAG_REVEAL_MS` before this client switches to the steady-state
/// Cancel-band-only rendering (`RendererCache::draw_drawer_drag`).
struct DrawerDragReveal {
    started: Instant,
    snapshot: Vec<u8>,
}
/// How long after this shell's own volume/mute write a matching PipeWire
/// graph confirmation is still treated as an echo of that write, not a
/// fresh external change (`apply_pipewire_event`'s `volume_echo_until_ms`
/// check). Generous relative to a single `wpctl` round trip (process
/// spawn plus one PipeWire client connect/set/disconnect) so a slow tick
/// under load still lands inside it; short enough that a genuinely new
/// external change arriving shortly after still raises the HUD promptly.
const VOLUME_ECHO_GRACE_MS: u64 = 1_500;

fn panel_input_rect(
    // Every route now maps the same full-height input region (see below);
    // kept as a parameter, not dropped, so a future route that genuinely
    // needs its own offset again does not have to change every call site
    // to add it back.
    _route: Route,
    width: u32,
    height: u32,
    ready: bool,
) -> Option<(i32, i32, i32, i32)> {
    if !ready {
        return None;
    }
    // Drawer used to reserve a `height*0.19` band (about 234px at this
    // panel's reference size) above its own input region, matching a much
    // older design where the drawer sheet was bottom-anchored with a real
    // empty band above it. `docs/design/app-drawer-review.md`'s redesign
    // made the drawer "fill nearly the whole screen from the top inset,
    // with no black band above it" -- `navigation.rs`'s own `list_top`
    // (search field + first grid row) now starts at just 118px -- but this
    // function's own exclusion was never updated to match, silently
    // routing every touch between y=118 and y=234 (the search field and
    // the drawer's entire first row of tiles) to whatever surface sits
    // *below* the drawer instead of the drawer itself. Confirmed live: a
    // QEMU long-press-drag on a first-row drawer tile
    // (`K230_DEBUG_TOUCH`-instrumented) landed on Home's own surface, not
    // the drawer's, while developing task 1's drag contract. Drawer now
    // gets the same full-height input region Shade/Settings already have.
    let top = 0;
    // Shade used to map only its own 0.65h panel, leaving the dim backdrop
    // below it outside the surface's input region entirely -- a touch
    // starting there never reached this client at all. A close drag may
    // now start anywhere on that backdrop (`close_drag_zone`), so Shade
    // maps the full remaining height, the same as Settings already did;
    // its own dim scrim already visually blocks whatever is behind it, so
    // this also closes a pre-existing pass-through-touch inconsistency
    // between the two routes rather than opening a new one.
    Some((0, top, width as i32, height as i32 - top))
}

fn socket_path() -> Result<PathBuf, String> {
    let runtime = std::env::var_os("XDG_RUNTIME_DIR").ok_or("XDG_RUNTIME_DIR is unset")?;
    Ok(PathBuf::from(runtime).join(SOCKET_NAME))
}

fn appearance_socket_path() -> Result<PathBuf, String> {
    let runtime = std::env::var_os("XDG_RUNTIME_DIR").ok_or("XDG_RUNTIME_DIR is unset")?;
    Ok(PathBuf::from(runtime).join(APPEARANCE_SOCKET_NAME))
}

/// Whether `draw()` may even attempt a redraw, before it gets to the
/// buffer pool's own free-slot bookkeeping (`released_slot`/`buffers.len()`
/// in `draw()` itself), which is the correct and sufficient readiness gate
/// beyond this. Deliberately takes no outstanding-frame-callback flag to
/// gate on: cd36242b already found that a compositor may withhold
/// frame-done callbacks indefinitely for a surface nothing currently
/// composites (there, the background/wallpaper layer, fully occluded by a
/// maximized app or the card deck's own backdrop). The overlay/settings
/// surface this guards is exactly as occludable -- board evidence
/// (2026-09-27): Optimistic Apply's own tap-time check skipped with
/// `reason=not-ready-for-a-frame` while the theme chooser's own panel (the
/// very thing being drawn) still had an outstanding frame callback from an
/// earlier redraw the compositor had not yet acked, even though a free
/// buffer slot was sitting right there. Gating a redraw attempt on that
/// flag can therefore starve a redraw indefinitely for the same reason
/// `draw_wallpaper()`'s own entry guard was fixed to stop doing; this
/// function's signature is what makes that mistake impossible to repeat
/// here.
fn redraw_entry_ready(appearance_pending: bool, configured: bool, layer_present: bool) -> bool {
    !appearance_pending && configured && layer_present
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

/// The user's decision (2026-09-25 coordinator message: "theme swaps
/// should be instant"; they approved optimistic apply): when an Apply tap
/// targets a generation this receiver already holds `prepare`d -- staged
/// by task 3.2's browse-ahead, or by an identical repeat Apply -- the new
/// appearance may be shown on the very next frame, ahead of the durable
/// two-phase commit `request` (still submitted to `ThemeWorker`
/// unchanged, still running to completion asynchronously). A cold,
/// never-prepared generation is deliberately excluded: nothing here may
/// ever trigger preparing one early or shorten its own real decode/stage
/// cost, only skip *waiting* for a receiver's own already-finished
/// preparation. Pure and independent of `AppearanceSnapshot` so it is
/// trivially testable without a real receiver or filesystem fixture.
fn should_apply_optimistically(request: &ThemeRequest, prepared_generation: Option<&str>) -> bool {
    optimistic_apply_skip_reason(request, prepared_generation).is_none()
}

/// The same decision as `should_apply_optimistically`, but naming *why*
/// not when the answer is no -- `None` means "eligible, show it"; `Some`
/// carries a short, `journalctl`-greppable reason. Board evidence
/// (2026-09-26) needed this: a generation-mismatch skip that looked
/// identical to a plain cold-theme skip from the outside was actually a
/// second, unrelated warm-up's `prepare` overwriting the receiver's
/// single `prepared` slot after this Apply's own target had already
/// staged there -- see `ThemeView::poll_prepare_ahead`'s own fix for that
/// race. Logged verbatim as `optimistic-apply skipped reason=<this>` at
/// the one call site in `serve`'s loop.
fn optimistic_apply_skip_reason(
    request: &ThemeRequest,
    prepared_generation: Option<&str>,
) -> Option<&'static str> {
    let ThemeRequest::Activate { expected_generation, .. } = request else {
        return Some("not-an-activate-request");
    };
    match prepared_generation {
        None => Some("not-prepared"),
        Some(generation) if generation != expected_generation => Some("generation-mismatch"),
        Some(_) => None,
    }
}

/// Whether a fresh optimistic-apply attempt is due this tick: exactly once
/// per distinct `pending_id` (`ThemeWorker` hands out a fresh, higher id
/// for every request, including a repeat Activate of the same theme), and
/// never while nothing is pending. This is what makes a rapid double Apply
/// safe: the first Apply's own id (attempted, whether or not it actually
/// rendered) never suppresses a second, later Apply's own distinct id, and
/// a still-pending Apply is never re-attempted tick after tick.
fn optimistic_apply_due(already_attempted_for: Option<u64>, pending_id: Option<u64>) -> bool {
    pending_id.is_some() && already_attempted_for != pending_id
}

/// Whether a `Commit`/`Rollback` event's own redraw may be skipped
/// because Optimistic Apply already rendered and flushed the exact frame
/// this event would otherwise redraw. `phase` restricts this to `Commit`
/// only: a `Rollback`'s own target is, by definition, the *previous*
/// generation, never the one Optimistic Apply just showed, so it could
/// never legitimately match anyway -- checking `phase` here is belt and
/// braces, not load-bearing on its own, but makes that guarantee explicit
/// rather than incidental. `optimistic_active`/`event_generation` are
/// `None` whenever there is nothing to reuse (no optimistic show ran, or
/// this event carries no generation at all, e.g. a rollback to the
/// packaged default) -- `None == None` is deliberately never treated as a
/// match.
fn may_reuse_optimistic_frame(
    phase: AppearancePhase,
    optimistic_active: Option<&str>,
    event_generation: Option<&str>,
) -> bool {
    phase == AppearancePhase::Commit
        && optimistic_active.is_some()
        && optimistic_active == event_generation
}

const CARD_APPEARANCE_SOCKET_ENV: &str = "K230_CARD_APPEARANCE_SOCKET";

/// The card-shell compositor's own appearance socket, for the best-effort
/// "show" side channel only (never for the durable two-phase protocol,
/// which stays entirely in `tools/theme_transaction.py`). Matches
/// `SWAY_K230_CARD_APPEARANCE_SOCKET`'s own production default
/// (`nix/shell.nix`) so this works with no further wiring once the
/// compositor is listening there; an explicitly empty env var disables it,
/// the same convention `K230_THEME_HELPER_SOCKET`/`K230_THEME_COMMAND`
/// already use.
fn card_appearance_socket_path() -> Option<PathBuf> {
    match std::env::var_os(CARD_APPEARANCE_SOCKET_ENV) {
        Some(value) if value.is_empty() => None,
        Some(value) => Some(PathBuf::from(value)),
        None => Some(PathBuf::from("/run/shell/k230-card-appearance.sock")),
    }
}

/// Best-effort, fire-and-forget "show" message to the card-shell
/// compositor's own appearance socket (task: optimistic Apply). The
/// compositor only ever acts on this if it independently already holds
/// this exact generation `prepare`d (`card-shell/appearance.c`'s own
/// `service.prepared`/`candidate` check) -- this function cannot know
/// that from here, and does not need to: a rejected or ignored "show" can
/// only cost the one message, never correctness, because the real
/// two-phase commit this chooser is still driving settles the
/// compositor's actual state regardless of whether this ever arrives.
/// Never reads a reply -- a connected stream socket's already-queued
/// bytes are still delivered after this end closes, so there is nothing
/// to wait on -- and every failure (missing socket, refused connection, a
/// slow/unresponsive peer past its own short write deadline) is silently
/// ignored so this can never stall the caller beyond that bound.
fn show_appearance_optimistically(socket_path: &Path, generation: &str, path: &Path) {
    let Some(path_str) = path.to_str() else {
        return;
    };
    let message = serde_json::json!({
        "protocol": 1,
        "phase": "show",
        "generation": generation,
        "path": path_str,
    });
    let Ok(mut bytes) = serde_json::to_vec(&message) else {
        return;
    };
    bytes.push(b'\n');
    if let Ok(mut stream) = UnixStream::connect(socket_path) {
        if stream
            .set_write_timeout(Some(Duration::from_millis(50)))
            .is_ok()
        {
            let _ = stream.write_all(&bytes);
        }
    }
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

/// What a launch attempt actually did, distinguishing "focused an existing
/// window" (no splash is warranted -- see `launch_home_app`'s doc) from
/// "spawned a new process" (the splash stays up and waits for its window).
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
enum LaunchOutcome {
    Focused,
    /// The pid GIO's `AppLaunchContext` reported for the spawned process,
    /// if any -- see `launch_selected`'s own doc for when this is `None`.
    Spawned(Option<i32>),
}

/// What a splash's background watcher thread (`spawn_splash_watcher`)
/// reports back once it has something to say. Paired with the launch
/// attempt's `u64` sequence number in the channel itself, matching the
/// existing `launch_sender`/`launch_results` staleness pattern.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
enum SplashSignal {
    /// A sway `window` event matched this splash's target -- see
    /// `splash::window_event_matches`.
    Matched,
    /// The spawned process's pid no longer names a running process, and no
    /// matching window ever appeared first.
    ProcessExited,
}

/// Spawns the background thread that watches for `splash`'s window to map
/// (or its process to exit first) and reports back on `sender`, tagged
/// with `attempt` so a stale result from a superseded launch is ignored --
/// exactly like the existing `launch_sender`/`launch_results` pattern this
/// mirrors. Returns the `stop` flag the caller should set (and store as
/// `ShellClient::splash_watch_stop`) to end this thread early once its
/// splash no longer needs it.
///
/// Started only once `launch_selected`'s outcome is known (`target`,
/// `pid`), not at the tap itself: a spawned process needs to load, connect
/// to Wayland, and commit a first frame before any window could possibly
/// map, which always takes far longer than the sub-millisecond gap between
/// showing the splash and this thread subscribing -- so no `window` event
/// this splash needs to see can be missed by that gap. This keeps the
/// splash's own state (`SplashTarget`) fixed for its whole lifetime rather
/// than needing a `Mutex` a watcher thread and the main thread would both
/// have to touch.
fn spawn_splash_watcher(
    target: SplashTarget,
    pid: Option<i32>,
    attempt: u64,
    sender: Sender<(u64, SplashSignal)>,
) -> Arc<AtomicBool> {
    let stop = Arc::new(AtomicBool::new(false));
    let thread_stop = stop.clone();
    thread::spawn(move || {
        let Some(socket) = std::env::var_os("SWAYSOCK") else {
            return;
        };
        let socket_path = std::path::PathBuf::from(socket);
        let mut matched = false;
        let result = sway_ipc::watch_window_events(
            &socket_path,
            |event| {
                let hit = splash_window_event_matches(target, event);
                if hit {
                    matched = true;
                }
                hit
            },
            || {
                if thread_stop.load(Ordering::Relaxed) {
                    return true;
                }
                if let Some(pid) = pid {
                    if !sway_ipc::process_alive(pid) {
                        return true;
                    }
                }
                false
            },
        );
        if matched {
            let _ = sender.send((attempt, SplashSignal::Matched));
        } else if !thread_stop.load(Ordering::Relaxed) {
            // Either the process exited (checked again here since the
            // `should_stop` closure above may have returned true for that
            // reason specifically) or the watch itself ended some other
            // way (socket closed, IO error) with the process already gone.
            // Both cases mean this launch is never going to map a window.
            // No pid at all (a `SplashTarget::LaunchOrder` launch) means
            // there is nothing concrete to check here; deliberately send
            // nothing rather than guess, and let the splash's own
            // `SPLASH_TIMEOUT` be the fallback instead.
            match pid {
                Some(pid) if !sway_ipc::process_alive(pid) => {
                    let _ = sender.send((attempt, SplashSignal::ProcessExited));
                }
                _ => {
                    if let Err(error) = result {
                        eprintln!("rust-shell splash-watch-failed {error}");
                    }
                }
            }
        }
    });
    stop
}

/// Whether a live `sway_ipc::WindowEvent` matches `target`, using the real
/// `/proc` ancestry walk -- the thin, I/O-performing counterpart to the
/// pure, already-unit-tested `splash::window_event_matches`.
fn splash_window_event_matches(target: SplashTarget, event: &sway_ipc::WindowEvent) -> bool {
    window_event_matches(target, &event.change, event.pid, sway_ipc::parent_pid)
}

/// `path` is the exact `.desktop` file `catalog::scan_apps` most recently
/// found for this id -- re-parsed fresh here with
/// [`gio::DesktopAppInfo::from_filename`], never through GIO's own id-keyed
/// cache (`DesktopAppInfo::new`), so a launch always reflects the file that
/// is actually on disk right now, including one a live rescan only just
/// picked up.
///
/// Captures the spawned pid via `gio::AppLaunchContext`'s `launched` signal:
/// GIO emits it synchronously (a direct signal emission inside the same
/// `launch()` call, not scheduled through a `GMainContext`), so this needs
/// no glib main loop running on this thread to observe it, and works from
/// the plain `thread::spawn`ed worker `launch_app`/`launch_home_app` already
/// use. Its `platform_data` carries a `pid` key only since glib 2.72 and
/// only for a launch GIO itself spawned (never for a DBus-activated entry),
/// so `LaunchOutcome::Spawned(None)` is an expected, not a error, outcome --
/// the splash falls back to `SplashTarget::LaunchOrder` in that case (see
/// its own doc).
fn launch_selected(path: &std::path::Path, swaymsg: &std::path::Path) -> Result<LaunchOutcome, String> {
    swaymsg_back(swaymsg)?;
    let app = gio::DesktopAppInfo::from_filename(path).ok_or("installed app disappeared")?;
    // `should_show()` alone does not cover `Hidden` -- see
    // `catalog::parse_entry`'s own comment on the same gap.
    if !app.should_show() || app.is_hidden() {
        return Err("installed app is no longer visible".into());
    }
    let pid_cell = std::rc::Rc::new(std::cell::Cell::new(None::<i32>));
    let context = gio::AppLaunchContext::new();
    {
        let pid_cell = pid_cell.clone();
        context.connect_launched(move |_context, _app, platform_data| {
            if !platform_data.is_type(glib::VariantTy::VARDICT) {
                return;
            }
            let dict = glib::VariantDict::new(Some(platform_data));
            if let Some(pid) = dict
                .lookup_value("pid", Some(glib::VariantTy::INT32))
                .and_then(|value| value.get::<i32>())
            {
                pid_cell.set(Some(pid));
            }
        });
    }
    app.launch(&[], Some(&context))
        .map_err(|error| error.to_string())?;
    Ok(LaunchOutcome::Spawned(pid_cell.get()))
}

/// Home's tap behavior: focus an already-running instance when one can be
/// identified, otherwise fall back to the exact same launch path the drawer
/// already uses. The focus lookup is a best-effort heuristic (see
/// `home_screen::app_id_matches`'s own doc); any miss or IPC failure simply
/// falls through to `launch_selected` rather than doing nothing. `path` is
/// `None` when `id` is a Home pin whose `.desktop` file the catalog no
/// longer finds (an uninstalled app) -- focusing an already-running
/// instance can still work by id/exec-hint alone, but there is nothing left
/// to launch, so that case reports the same "installed app disappeared"
/// error a stale drawer tap always has.
fn focus_or_launch(id: &str, path: Option<&std::path::Path>, swaymsg: &std::path::Path) -> Result<LaunchOutcome, String> {
    if let Some(con_id) = running_con_id(id, path, swaymsg) {
        if focus_con(con_id, swaymsg).is_ok() {
            return Ok(LaunchOutcome::Focused);
        }
    }
    let path = path.ok_or("installed app disappeared")?;
    launch_selected(path, swaymsg)
}

/// Runs `swaymsg -r -t get_tree` (the same invocation
/// `tools/notification_center.py`'s `SwayActions.refresh` already uses) and
/// looks for a container matching `id`. `None` on any failure -- a timeout,
/// a missing binary, an oversized or unparsable reply -- so a lookup
/// problem always degrades to an ordinary launch, never a stuck tap.
fn running_con_id(id: &str, path: Option<&std::path::Path>, swaymsg: &std::path::Path) -> Option<i64> {
    let info = path.and_then(|path| gio::DesktopAppInfo::from_filename(path));
    let startup_class = info.as_ref().and_then(|app| app.startup_wm_class());
    let exec_hint = info.as_ref().and_then(|app| {
        app.executable()
            .file_name()
            .map(|name| name.to_string_lossy().into_owned())
    });
    let output = Command::new(swaymsg)
        .args(["-r", "-t", "get_tree"])
        .output()
        .ok()?;
    if !output.status.success() || output.stdout.len() > 2 * 1024 * 1024 {
        return None;
    }
    let tree: serde_json::Value = serde_json::from_slice(&output.stdout).ok()?;
    // Our themed terminal wrappers advertise their Wayland app_id through
    // StartupWMClass; neither their desktop ID nor executable basename matches.
    k230_shell_rust::home_screen::find_running_con_id(&tree, id, startup_class.as_deref())
        .or_else(|| k230_shell_rust::home_screen::find_running_con_id(&tree, id, exec_hint.as_deref()))
}

fn focus_con(con_id: i64, swaymsg: &std::path::Path) -> Result<(), String> {
    let output = Command::new(swaymsg)
        .args(["-r", &format!("[con_id={con_id}] focus")])
        .output()
        .map_err(|error| error.to_string())?;
    if output.status.success() {
        Ok(())
    } else {
        Err("focus command failed".into())
    }
}

// Reserved logical contact emitted by Sway's trackpad-to-touch adapter.
// Multi-finger pans retain native motion/settle, but never become a tap or
// long press when the fingers return to their starting position.
const TRACKPAD_PAN_ID: i32 = i32::MAX - 2;

struct ShellClient {
    compositor: CompositorState,
    presentation: Option<PresentationTimeState>,
    trace_feedback: Vec<(wp_presentation_feedback::WpPresentationFeedback, u64)>,
    trace_frame: u64,
    trace_input: u64,
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
    pointer_device: Option<wl_pointer::WlPointer>,
    pointer_contact: PointerContact<wl_surface::WlSurface>,
    keyboard_device: Option<wl_keyboard::WlKeyboard>,
    /// Mirrors `WifiView::wants_keyboard()` as of the last `sync_wifi_
    /// keyboard` call -- lets that function tell "already showing" from
    /// "needs to change" without re-deriving it from `self.layer`'s own
    /// (write-only, from here) Wayland state.
    wifi_keyboard_active: bool,
    drawer_keyboard_active: bool,
    /// Mirrors whether Home's open-folder rename field currently holds
    /// keyboard focus (task 2, `HomeScreen::OpenFolder::editing_name`) --
    /// the exact same role `wifi_keyboard_active` plays for the Wi-Fi
    /// password field, just against `home_surface.layer` instead of
    /// `self.layer` (Home is its own always-mapped surface, not the
    /// on-demand overlay).
    home_keyboard_active: bool,
    /// `k230-keyboard-gesture-signal`'s path (`K230_KEYBOARD_SIGNAL`), the
    /// same helper the compositor's own two-finger keyboard gesture uses
    /// (`nix/shell.nix`'s `keyboardGestureSignal`, run from `adapter.c`) --
    /// reused here rather than inventing a second way to raise wvkbd.
    /// `None` when the shell runs somewhere that never wired it up (a QEMU
    /// probe build, say), in which case `sync_wifi_keyboard` still grants
    /// keyboard focus but cannot also show the keyboard.
    keyboard_signal_path: Option<PathBuf>,
    /// The on-screen keyboard's reserved height (`K230_KEYBOARD_HEIGHT`,
    /// matching `cfg.keyboardHeight`), in the 568x1232 artwork's own
    /// coordinate space -- what `sync_wifi_keyboard` feeds to `WifiView::
    /// set_keyboard_inset` so the Entry page's Cancel/Connect row reflows
    /// above it instead of underneath it.
    keyboard_height_px: f64,
    keyboard_grip_height_px: f64,
    route: Route,
    touch: TouchTrace,
    width: u32,
    height: u32,
    configured: bool,
    dirty: bool,
    frame_pending: bool,
    started: Instant,
    apps: Vec<AppEntry>,
    /// Set (or refreshed) whenever `app_watch::CatalogWatcher` sees a
    /// relevant change; cleared once the debounced rescan it names has run.
    /// See `serve`'s main loop for the debounce itself.
    catalog_pending_rescan: Option<Instant>,
    nav: DrawerNavigation,
    /// The drawer's own live search field state -- see
    /// `sync_drawer_search`'s own doc for how it reaches the renderer.
    drawer_search: DrawerSearch,
    nav_tick: Instant,
    launch_sender: Sender<(u64, Result<LaunchOutcome, String>)>,
    launch_results: Receiver<(u64, Result<LaunchOutcome, String>)>,
    launching: bool,
    launch_in_flight: bool,
    launch_seq: u64,
    /// The instant-feedback launch splash -- see `splash.rs`'s own doc.
    /// `None` means no launch is in flight. Shown from the moment an app is
    /// tapped (in the drawer, on Home, or in the dock) until its window
    /// maps, `SPLASH_TIMEOUT` elapses, or its process exits first.
    splash: Option<Splash>,
    /// Signals from the current attempt's background `sway_ipc::watch_
    /// window_events`/process-liveness thread -- see `SplashSignal`'s own
    /// doc. Paired with `launch_seq`'s `attempt` value exactly like
    /// `launch_results` above, so a thread from a superseded launch can
    /// never affect the splash a later tap started.
    splash_events: Receiver<(u64, SplashSignal)>,
    splash_sender: Sender<(u64, SplashSignal)>,
    /// Tells the current attempt's watcher thread to stop polling once its
    /// splash no longer needs it (matched, dismissed, or superseded by a
    /// new launch) -- cooperative, not a kill: the thread notices on its
    /// own next ~200ms poll and exits on its own.
    splash_watch_stop: Option<Arc<AtomicBool>>,
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
    trackpad_pan_start: Option<(f64, f64)>,
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
    /// Live-tracking/settle for a Shade/Settings close drag -- entirely
    /// client-side, unlike `reveal` below (the compositor-driven open),
    /// since the client already owns this touch throughout. See
    /// `PanelClose`'s own doc.
    panel_close: PanelClose,
    /// Set at touch-down: whether this contact started somewhere
    /// `close_drag_zone` allows. A touch that starts elsewhere (list
    /// content, a Settings control, a carousel) must never become a close
    /// drag later in the same gesture, no matter how it moves.
    panel_close_candidate: bool,
    /// Same velocity convention as `panel_scroll_velocity`
    /// (`-(pos.1 - last_y) / dt`, positive = upward = toward closing),
    /// sampled only while `panel_close` is tracking.
    panel_close_velocity: f64,
    panel_close_sample: Option<(f64, u32)>,
    /// Armed at touch-down when the touch lands on the shared brightness
    /// slider (`service_ui::slider_band`, Settings row or Shade header
    /// alike) -- owns the rest of that gesture entirely, preempting the
    /// close drag, notification swipe/scroll and (on Settings) the
    /// wifi/theme handling that would otherwise see this touch.
    brightness_drag: Option<slider::Drag>,
    /// Rate-limits `K230_DRAWER_FRAME` (see `draw`'s own doc): the last
    /// time one was actually emitted, so a continuous scroll/fling logs a
    /// sample every `DRAWER_FRAME_LOG_INTERVAL` instead of once per frame.
    drawer_frame_log_at: Option<Instant>,
    /// Armed the same way `brightness_drag` is, but against `service_ui::
    /// volume_slider_band` and a floor of `0` (`slider::Drag::start_with_
    /// floor`, not `start`) -- true silence is a reachable drag position,
    /// unlike the backlight.
    volume_drag: Option<slider::Drag>,
    /// The touch id, if any, that went down inside `volume_icon_tap_zone`
    /// (the speaker glyph's own hit box, left of the track `volume_drag`
    /// owns) -- distinct from `volume_drag` because a touch here must
    /// never become a drag at all (a tap on the icon at the track's own
    /// floor position would otherwise read as "drag to 0", not "toggle
    /// mute"). Resolved as a mute toggle on `up` if the same id releases,
    /// regardless of exactly where the finger ends up (a glyph this small
    /// gets the same "any release counts as its tap" leniency every other
    /// icon-sized hit zone in this shell already has).
    volume_icon_touch: Option<i32>,
    /// The touch id, if any, that went down on the Settings volume row's
    /// own "tap to change output" detail line
    /// (`service_ui::settings_output_picker_hit`) -- resolved on `up` by
    /// raising the HUD already expanded, reusing that one picker UI
    /// rather than building a second list inline in Settings
    /// (design.md's "one picker, two entry points"). Checked before, and
    /// mutually exclusive with, `volume_icon_touch`/`volume_drag` for the
    /// same touch.
    output_picker_touch: Option<i32>,
    /// This shell's own mirror of the default sink's level/mute, kept in
    /// sync from `service_view.audio`'s own PipeWire reads
    /// (`sync_volume_from_graph`) and from local drags/taps
    /// (`apply_volume_preview`) -- never itself sent anywhere; `volume_
    /// commit`/`volume_writer` below own the actual PipeWire-facing
    /// writes this state change should cause.
    volume_state: volume::VolumeState,
    hud: volume::Hud,
    /// Whether `hud.is_visible` read `true` on the previous loop wake --
    /// exists purely so the one frame where it flips back to `false` (the
    /// auto-hide firing, with no other event to mark it dirty) still gets
    /// painted; every other frame's dirtiness already follows `hud.is_
    /// visible` on its own.
    hud_last_visible: bool,
    /// The default sink's PipeWire node id, as last reported by `service_
    /// view.audio` -- `None` until the first snapshot names one. Every
    /// `wpctl`/`pw-cli` write this shell sends targets this id, not
    /// `@DEFAULT_AUDIO_SINK@`, so a write and the graph confirmation that
    /// follows it are unambiguously about the same node even if the
    /// default changes mid-gesture.
    default_sink_id: Option<u32>,
    /// Set (to `now + VOLUME_ECHO_GRACE_MS`) every time this shell itself
    /// sends a volume/mute write -- a throttled live drag sample
    /// (`submit_volume_live`) or an authoritative `wpctl` commit
    /// (`commit_volume`, reached from a drag's release, a mute tap, or a
    /// device-picker choice). `apply_pipewire_event` checks this the same
    /// way it checks `volume_drag.is_none()`: a graph confirmation
    /// arriving inside this window is this shell's own write echoing
    /// back, not a fact the user has not already seen on screen, and must
    /// never pop the HUD. A drag in progress is covered by `volume_drag`
    /// already; this field is what covers the gap a drag's own
    /// suppression does not -- the discrete mute-tap/picker commits,
    /// whose `wpctl` round trip completes on its own thread, after
    /// `volume_drag` has already gone back to `None`.
    volume_echo_until_ms: Option<u64>,
    /// The persistent `pw-dump --monitor` reader's own channel
    /// (`pipewire_ipc::spawn_monitor`) -- drained via `try_recv` on every
    /// loop wake, never polled on its own timer (task: "no polling").
    /// `None` if the child could never be spawned at all (PipeWire not
    /// installed/running); `service_view.audio_error` is what actually
    /// surfaces that to the UI.
    pipewire_events: Option<Receiver<pipewire_ipc::Event>>,
    /// The persistent `pw-cli` writer (`pipewire_ipc::WriterHandle`) this
    /// shell's throttled slider-drag writes go to -- see `pipewire_ipc.rs`'s
    /// own module doc for why a persistent child beats a `wpctl` spawn per
    /// sample. `None` under the same conditions as `pipewire_events`.
    pipewire_writer: Option<pipewire_ipc::WriterHandle>,
    /// `wpctl`'s own resolved path (an absolute override from `K230_WPCTL`,
    /// or the bare name for a `PATH` lookup -- `nix/shell.nix`'s own
    /// `shell-ui` service now carries `pkgs.wireplumber` on its `PATH` for
    /// exactly this). Used only for the rare, human-paced commits a drag's
    /// release, a mute tap, a hardware key already handles itself via Sway,
    /// or an output-sink pick -- never per live-drag sample.
    wpctl_command: PathBuf,
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
    /// The Home screen's always-mapped `Layer::Bottom` surface: sits above
    /// the wallpaper (`Layer::Background`) and below every ordinary
    /// toplevel and the drawer/shade/settings overlay (`Layer::Overlay`),
    /// so a focused app or an open overlay occludes it with no explicit
    /// "is anything else showing" check in this client at all. See
    /// `openspec/changes/the-shell-presents-a-pinned-home-screen/design.md`
    /// decision 1.
    home_surface: HomeSurface,
    home: HomeScreen,
    home_state_path: Option<PathBuf>,
    /// Which touch id, if any, `down()` routed to Home. `wl_touch`'s
    /// `up`/`motion` events carry no surface, only an id, so this is how
    /// this client remembers which of its two independently interactive
    /// surfaces (the on-demand overlay's own `self.touch`, or this) owns a
    /// live contact -- the same role `self.touch`'s tracked id already
    /// plays for the overlay.
    home_touch_id: Option<i32>,
    /// The last position `down()`/`motion()` observed for `home_touch_id`.
    /// `wl_touch`'s `up` event carries no position (only `id`/`time`), the
    /// same reason `self.touch: TouchTrace` keeps its own `.position` for
    /// the overlay surface.
    home_last_point: (f64, f64),
    /// Live while the drawer's long-press-drag hand-off (task 1, "Long-press
    /// an app in the drawer ... the icon lifts and follows the finger") is
    /// in progress: the touch id it is bound to. `Some` makes the Drawer's
    /// own `motion`/`up` dispatch skip its ordinary scroll/close-drag/search
    /// handling entirely for that touch and instead forward it into
    /// `self.home`'s external-drag API -- see those two `TouchHandler`
    /// methods' own Drawer branches. The dragged item itself lives in
    /// `self.home.drag` (a `DragSource::FromDrawer`), not duplicated here.
    drawer_home_drag: Option<i32>,
    /// Live only for the first `DRAWER_DRAG_REVEAL_MS` of a drawer
    /// long-press-drag -- the animated slide/fade transition; `None`
    /// before one starts, once it finishes, and whenever the drag itself
    /// is not live at all.
    drawer_drag_reveal: Option<DrawerDragReveal>,
    /// Last time a battery-widget poll ran (`home_widgets::battery::
    /// POLL_INTERVAL`) -- cheap synchronous `/sys` reads, safe to run
    /// directly on this thread, unlike weather's own network fetch.
    battery_polled_at: Option<Instant>,
    /// A weather fetch this client kicked off on a background thread
    /// (`home_widgets::weather::refresh` shells out to `curl`, which must
    /// never block this process's single manual poll loop); polled
    /// non-blockingly each tick, taken and applied to `self.home.weather`
    /// once the thread finishes.
    weather_pending: Option<Receiver<home_widgets::weather::WeatherDisplay>>,
    /// Last time this client checked whether a weather fetch is due
    /// (`home_widgets::weather::should_fetch`) -- throttles even that cheap
    /// check to about once a minute rather than every frame.
    weather_checked_at: Option<Instant>,
    /// Scheduled wall-clock instant for the Clock widget's next once-a-
    /// minute, minute-aligned redraw (task 7: "the clock redraws only its
    /// own area once a minute"); `None` until the first tick computes it.
    clock_next_tick: Option<Instant>,
    /// Rate-limits `K230_HOME_FRAME`, mirroring `drawer_frame_log_at`/
    /// `DRAWER_FRAME_LOG_INTERVAL` exactly, one surface over.
    home_frame_log_at: Option<Instant>,
    /// Set the instant an Apply tap submits a `ThemeRequest::Activate`
    /// (see `theme_action`'s `ThemeIntent::Apply` arm), read once by the
    /// optimistic-apply check in `serve`'s own loop to log how long the
    /// tap took to reach a shown frame. Not meaningful once
    /// `theme_optimistic_shown_for` has consumed it for this Apply.
    theme_apply_tapped_at: Option<Instant>,
    /// The `pending_id` (see `ThemeView::pending_id`) an optimistic show
    /// has already been attempted for -- whether or not it actually
    /// rendered (cold, not ready, video-backed) -- so a still-pending
    /// Activate is never re-attempted on a later tick, and a second,
    /// unrelated Apply (a new `pending_id`) is always free to try again.
    theme_optimistic_shown_for: Option<u64>,
    /// The card-shell compositor's own appearance socket, best-effort and
    /// advisory only -- see `show_appearance_optimistically`'s doc. `None`
    /// (an unset or empty `K230_CARD_APPEARANCE_SOCKET`) disables this
    /// side channel entirely; the compositor still settles correctly from
    /// the durable two-phase commit either way.
    card_appearance_socket: Option<PathBuf>,
    /// The generation `show_theme_optimistically` most recently rendered
    /// and successfully flushed, if any -- read once, by the very next
    /// `AppearancePhase::Commit` event's own handling, to skip a redundant
    /// redraw of a frame already on screen (see `pending_appearance`'s own
    /// `reuse_optimistic` element). Cleared unconditionally the moment any
    /// `Commit`/`Rollback` event is received, matching or not, so it can
    /// never be read by any event but the very next one.
    optimistic_active: Option<String>,
    /// A generation this receiver has already rendered ahead of Apply --
    /// see `PrerenderedOverlay`'s own doc. Bounded to one; a fresh
    /// computation (or a mismatch found at Apply time) always replaces or
    /// clears whatever was here, never grows.
    prerendered_overlay: Option<PrerenderedOverlay>,
}

/// An overlay/settings-panel frame rendered ahead of Apply for a specific,
/// not-yet-active candidate generation -- see `render_candidate_overlay`'s
/// own doc for what it does and does not capture. Valid only while every
/// field here still matches the live state at the moment it would be
/// used: a mismatch on any one of them (a different generation, a resized
/// or re-routed surface, or `content_generation` -- everything else
/// `render_candidate_overlay` read from `self` at compute time) means
/// something this render depended on may have changed, and the pre-render
/// must be discarded rather than risk showing stale content.
struct PrerenderedOverlay {
    generation: String,
    route: Route,
    width: u32,
    height: u32,
    content_generation: u64,
    pixels: Vec<u8>,
}

/// Speculative CPU work yields to both carousel gestures, including coast
/// and settle. Live drawing and durable appearance handling stay independent.
fn theme_prerender_at_rest(theme: &Carousel, backgrounds: &Carousel) -> bool {
    !theme.is_animating() && !backgrounds.is_animating()
}

/// Whether `candidate` may still be used as-is: an exact match on the
/// generation it was computed for and on every other input its own
/// content depended on (route, geometry, and everything the theme itself
/// does not capture, bundled into `content_generation`). Pure and
/// independent of `ShellClient`/`RendererCache` so it is trivially
/// testable without either.
fn prerendered_overlay_matches(
    candidate: &PrerenderedOverlay,
    generation: &str,
    route: Route,
    width: u32,
    height: u32,
    content_generation: u64,
) -> bool {
    prerendered_overlay_mismatch_reason(Some(candidate), generation, route, width, height, content_generation)
        .is_none()
}

/// The same check as `prerendered_overlay_matches`, but naming *why* not
/// when the answer is no -- board evidence, 2026-09-28: a plain
/// `prerendered=false` told the coordinator only that a stored pre-render
/// was not used, not which field made it stale. Checked in a fixed order
/// (no stored pre-render at all; generation; route; geometry; then
/// `content_generation`, the catch-all for everything else a render
/// depends on) so a candidate failing several checks at once still
/// reports one specific, reproducible reason rather than an arbitrary
/// one. Logged verbatim as `optimistic-apply shown ms=... prerendered=
/// false reason=<this>`.
fn prerendered_overlay_mismatch_reason(
    candidate: Option<&PrerenderedOverlay>,
    generation: &str,
    route: Route,
    width: u32,
    height: u32,
    content_generation: u64,
) -> Option<&'static str> {
    let Some(candidate) = candidate else {
        return Some("no-prerender-computed");
    };
    if candidate.generation != generation {
        Some("generation")
    } else if candidate.route != route {
        Some("route")
    } else if candidate.width != width || candidate.height != height {
        Some("geometry")
    } else if candidate.content_generation != content_generation {
        Some("content-changed")
    } else {
        None
    }
}

/// A live slider's own visible brightness change is already the feedback
/// -- a status toast on every drag release is noise, not information, in
/// both Settings and the Shade. Suppresses only the success/pending path
/// of the authoritative `Brightness` commit request itself (the
/// fire-and-forget `BrightnessLive` scrub writes never reach
/// `service_reply`'s outcome-handling arm at all -- see its own early
/// return); a genuine failure (`outcome_error` is `Some`, e.g. permission
/// denied or an unreachable backend) still surfaces normally, and every
/// other request keeps showing its own message exactly as before.
fn suppresses_action_message(request: &ServiceRequest, outcome_error: Option<&str>) -> bool {
    matches!(request, ServiceRequest::Brightness(_)) && outcome_error.is_none()
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

/// Home's own layer-shell surface state, deliberately parallel to
/// [`WallpaperState`]: a small, independently buffered surface with its own
/// configure/frame lifecycle, rather than a mode of the drawer/shade/
/// settings overlay (which sits on `Layer::Overlay`, always above normal
/// windows -- wrong side of the stack for something that must yield to a
/// focused app).
#[derive(Default)]
struct HomeSurface {
    layer: Option<LayerSurface>,
    buffers: Vec<Buffer>,
    width: u32,
    height: u32,
    configured: bool,
    frame_pending: bool,
    dirty: bool,
    recreate_after: Option<Instant>,
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
        self.sync_wifi_keyboard();
        self.service_view.wifi = Some(self.wifi_view.public());
        self.renderer.set_services(self.service_view.clone());
        self.dirty = true;
    }

    /// Keeps the overlay layer's keyboard focus, the system keyboard
    /// (wvkbd)'s visibility, and the Entry page's reflow in step with
    /// `WifiView::wants_keyboard`. Called from every place that can change
    /// whether the password field is the one that needs typing -- see
    /// `wifi_dirty` (most transitions) and this file's `wifi_view.close()`
    /// call sites (leaving Settings/Wi-Fi entirely).
    ///
    /// The overlay surface otherwise never asks for keyboard focus at all
    /// (`ensure_layer` maps it `KeyboardInteractivity::None`, like every
    /// other layer this shell owns) -- that is what forced Wi-Fi Settings to
    /// draw its own keypad in the first place, per
    /// `openspec/changes/the-handheld-configures-wifi-from-settings/design.md`:
    /// wvkbd's keys are ordinary `wl_keyboard` input, delivered to whichever
    /// surface holds keyboard focus, and a layer surface that never
    /// requests it can never be that surface. `Exclusive` is requested only
    /// for the narrow lifetime of this one field, then released back to
    /// `None`, so it never contests focus with an app the rest of the time.
    fn sync_wifi_keyboard(&mut self) {
        let want = self.wifi_view.wants_keyboard();
        if want == self.wifi_keyboard_active {
            return;
        }
        self.wifi_keyboard_active = want;
        if let Some(layer) = &self.layer {
            layer.set_keyboard_interactivity(if want {
                KeyboardInteractivity::Exclusive
            } else {
                KeyboardInteractivity::None
            });
            layer.commit();
        }
        self.wifi_view
            .set_keyboard_inset(if want { self.keyboard_height_px } else { 0.0 });
        if let Some(path) = &self.keyboard_signal_path {
            // Fire-and-forget, exactly like the compositor's own two-finger
            // gesture handler (`adapter.c`'s `keyboard_signal`) -- a helper
            // that fails to spawn must not block or crash the shell, it
            // just leaves the keyboard in whatever state it was already in.
            if let Err(error) = std::process::Command::new(path)
                .arg(if want { "show" } else { "hide" })
                .spawn()
            {
                self.log(&format!("wifi-keyboard-signal-failed {error}"));
            }
        }
        self.dirty = true;
    }

    /// Unconditionally drops keyboard focus/reflow bookkeeping, for when the
    /// keyboard capability itself just disappeared (`remove_capability`/
    /// `remove_seat`) -- there is no keyboard left to show or hide, so this
    /// only clears local state and the layer's own interactivity request,
    /// unlike `sync_wifi_keyboard`'s normal compare-and-toggle.
    fn forget_wifi_keyboard(&mut self) {
        self.wifi_keyboard_active = false;
        self.wifi_view.set_keyboard_inset(0.0);
        if let Some(layer) = &self.layer {
            layer.set_keyboard_interactivity(KeyboardInteractivity::None);
            layer.commit();
        }
        self.dirty = true;
    }

    /// The `KeyboardHandler::press_key`/`repeat_key` bridge: only acts while
    /// `sync_wifi_keyboard` has actually granted this surface focus for the
    /// password field (never on stray input from some other reason the
    /// overlay might one day hold focus), and reuses `wifi_action` --
    /// exactly the same dispatcher a touch-hit intent goes through -- so
    /// Enter/Escape get the same Connect/Cancel handling a tap on those
    /// buttons would (`can_connect`'s own guards included).
    fn handle_wifi_key(&mut self, event: KeyEvent) {
        if !self.wifi_keyboard_active {
            return;
        }
        if let Some(intent) = key_event_intent(u32::from(event.keysym), event.utf8.as_deref()) {
            self.wifi_action(intent);
        }
    }

    /// The Home surface's own `Exclusive` keyboard focus, granted only
    /// while the open-folder overlay's name field is being edited (task 2)
    /// -- otherwise an exact mirror of `sync_wifi_keyboard`, just against
    /// `home_surface.layer` (Home is its own always-mapped surface, not
    /// `self.layer`).
    fn sync_home_keyboard(&mut self) {
        let want = self.home.open_folder.as_ref().is_some_and(|open| open.editing_name);
        if want == self.home_keyboard_active {
            return;
        }
        self.home_keyboard_active = want;
        if let Some(layer) = self.home_surface.layer.as_ref() {
            layer.set_keyboard_interactivity(if want {
                KeyboardInteractivity::Exclusive
            } else {
                KeyboardInteractivity::None
            });
            layer.commit();
        }
        self.home.set_keyboard_inset(if want { self.keyboard_height_px } else { 0.0 });
        if let Some(path) = &self.keyboard_signal_path {
            if let Err(error) = std::process::Command::new(path)
                .arg(if want { "show" } else { "hide" })
                .spawn()
            {
                self.log(&format!("home-keyboard-signal-failed {error}"));
            }
        }
        self.home_mark_dirty();
    }

    /// Mirrors `forget_wifi_keyboard` for Home's own surface -- unconditionally
    /// drops keyboard focus/reflow when the keyboard capability itself just
    /// disappeared.
    fn forget_home_keyboard(&mut self) {
        self.home_keyboard_active = false;
        self.home.set_keyboard_inset(0.0);
        if let Some(layer) = self.home_surface.layer.as_ref() {
            layer.set_keyboard_interactivity(KeyboardInteractivity::None);
            layer.commit();
        }
        self.home_mark_dirty();
    }

    /// The `KeyboardHandler::press_key`/`repeat_key` bridge for Home's
    /// open-folder rename field, exactly mirroring `handle_wifi_key`:
    /// reuses `wifi_ui::key_event_intent`'s keysym/utf8 parsing (it is a
    /// plain backspace/enter/escape/char classifier, not Wi-Fi-specific in
    /// what it accepts) so this needs no second copy of that mapping.
    /// Enter commits (task 2: "Enter commits"), Escape cancels ("Escape
    /// cancels"), matching every other text field in this shell.
    fn handle_home_key(&mut self, qh: &QueueHandle<Self>, event: KeyEvent) {
        if !self.home_keyboard_active {
            return;
        }
        let Some(intent) = key_event_intent(u32::from(event.keysym), event.utf8.as_deref()) else {
            return;
        };
        match intent {
            WifiIntent::Backspace => self.home.backspace_folder_name(),
            WifiIntent::Connect => {
                if let Some(action) = self.home.apply_folder_rename() {
                    self.apply_home_action(qh, action);
                }
                self.sync_home_keyboard();
            }
            WifiIntent::Back => {
                self.home.cancel_folder_rename();
                self.sync_home_keyboard();
            }
            WifiIntent::Key(ch) => self.home.push_folder_name_char(ch),
            // `key_event_intent` (a plain keysym/utf8 classifier, not
            // Wi-Fi-specific in what it can produce) never actually
            // returns any of `Intent`'s other, touch-only variants
            // (`Refresh`/`Select`/etc.) -- this arm exists only so the
            // match stays exhaustive as that enum grows.
            _ => {}
        }
        self.home_mark_dirty();
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
                    self.sync_wifi_keyboard();
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
            WifiIntent::Key(_) | WifiIntent::Backspace => {
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

    // The outer loop draws after dispatching queued input. Drawing inside
    // each Themes-page motion/callback handler renders obsolete positions
    // before later touch samples from the same dispatch can be applied.
    fn coalesce_theme_motion(&self) -> bool {
        self.route == Route::Settings
            && self.theme_view.page == ThemePage::List
            && self.wifi_view.page == WifiPage::Closed
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

    /// Same as `sync_theme_pressed`, for the active theme's own background
    /// carousel, below the theme carousel on this same List page.
    fn sync_background_pressed(&mut self) {
        let center_x = f64::from(self.width) / 2.0;
        let want = (self.theme_view.page == ThemePage::List)
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
            Ok(id) => {
                // A fresh id always means a fresh optimistic-apply
                // opportunity for *this* request; a stale attempt against
                // an old id could otherwise linger and suppress a later,
                // unrelated Apply's own optimistic check.
                if matches!(request, ThemeRequest::Activate { .. }) {
                    self.theme_apply_tapped_at = Some(Instant::now());
                    self.theme_optimistic_shown_for = None;
                }
                self.theme_view.submitted(request, id);
            }
            Err(error) => self.theme_view.failed_to_submit(error),
        }
        self.theme_dirty();
    }

    fn theme_reply(&mut self, reply: ThemeReply) {
        // Task 3.2: a warm-up call issued by `poll_prepare_ahead` reuses the
        // ordinary `Preview` request/reply shape but was never registered
        // via `submitted`, so it must never reach `ThemeView::accept` --
        // that would (harmlessly, since pending_id never matches, but
        // needlessly) be indistinguishable in principle from a real
        // navigational Preview reply. `prepare_ahead_reply` recognises and
        // consumes exactly its own request id and nothing else, and its own
        // generation (if any) is still worth remembering -- see
        // `ThemeView::record_known_generation`'s own doc.
        if self.theme_view.prepare_ahead_reply(&reply) {
            if let Ok(ThemeResponse::Preview(preview)) = &reply.result {
                self.theme_view
                    .record_known_generation(&preview.theme.id, &preview.generation);
            }
            return;
        }
        let theme_position_before = self.theme_view.theme_position;
        let background_position_before = self.theme_view.background_position;
        if self.theme_view.accept(reply) {
            // `ThemeView::accept` may have just centered `theme_position`
            // (a freshly (re)loaded list) and/or `background_position`
            // (the active theme's own detail settling); jump the matching
            // physics carousel there too, with no animation (a fresh
            // list/preview is not a browsing gesture) -- but only the one
            // whose position this reply actually moved, so an in-flight
            // drag on the *other* carousel (both now live on the same
            // page) is never interrupted by an unrelated reply.
            if self.theme_view.theme_position != theme_position_before {
                self.theme_carousel
                    .set_index(self.theme_view.theme_position.max(0.0).round() as usize);
            }
            if self.theme_view.background_position != background_position_before {
                self.background_carousel
                    .set_index(self.theme_view.background_position.max(0.0).round() as usize);
            }
            // Coalescing: immediately move on to whatever is now desired
            // -- either the next step toward the same target (a Preview's
            // generation now known -> Activate), or, if a later tap
            // superseded this one while it was in flight, straight to
            // that instead. See `ThemeView::advance`'s own doc.
            if let Some(request) = self.theme_view.advance() {
                self.submit_theme(request);
            } else {
                self.theme_dirty();
            }
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
                if let Some(request) = self.theme_view.tap_theme(index) {
                    self.submit_theme(request);
                } else {
                    self.theme_dirty();
                }
            }
            ThemeIntent::Background(index) => {
                if let Some(request) = self.theme_view.tap_background(index) {
                    self.submit_theme(request);
                } else {
                    self.theme_dirty();
                }
            }
        }
    }

    /// Optimistic Apply (2026-09-25, user-approved: "theme swaps should be
    /// instant"). `snapshot` is `appearance`'s own already-validated
    /// `prepared` snapshot for the exact generation `submit_theme` just
    /// dispatched to `ThemeWorker` as a durable `Activate` -- see
    /// `should_apply_optimistically`'s doc for why this is safe to render
    /// ahead of that transaction's own real commit. This call never
    /// touches `appearance`'s `active`/`prepared` bookkeeping or the
    /// `Activate` request itself, both of which are left entirely to the
    /// real `AppearancePhase::Commit`/`Rollback` handling in `serve`'s own
    /// loop -- unchanged by this feature -- to settle authoritatively:
    /// on success that handling redraws (harmlessly redundant) and
    /// records the new `active` snapshot; on failure it redraws the
    /// *previous* generation and records that instead, which is exactly
    /// how a failed durable commit is rolled back visually. Skips (no
    /// draw, no log) for a video-backed selection, an unrenderable
    /// snapshot (defensive -- an already-prepared one should never fail
    /// this), or an overlay/wallpaper not immediately ready for a new
    /// frame; a real transaction's own commit/rollback readiness-retry
    /// handling covers all three correctly regardless of whether this
    /// optimistic attempt ran.
    fn show_theme_optimistically(
        &mut self,
        qh: &QueueHandle<Self>,
        queue: &mut wayland_client::EventQueue<Self>,
        snapshot: &AppearanceSnapshot,
        tapped_at: Instant,
    ) {
        let elapsed_ms = || tapped_at.elapsed().as_secs_f64() * 1000.0;
        if self.appearance_pending {
            self.log(&format!(
                "optimistic-apply skipped reason=commit-draw-in-flight ms={:.1}",
                elapsed_ms()
            ));
            return; // a real transaction's own commit/rollback draw already owns this tick
        }
        let geometry = self
            .wallpaper
            .configured
            .then_some((self.wallpaper.width, self.wallpaper.height));
        if geometry.is_some_and(|size| selected_video(Some(snapshot), size).is_some()) {
            self.log(&format!(
                "optimistic-apply skipped reason=video-background ms={:.1}",
                elapsed_ms()
            ));
            return; // a video swap needs its own decode/ready gate regardless
        }
        if appearance_renderable(Some(snapshot), &mut self.background_cache, geometry).is_err() {
            self.log(&format!(
                "optimistic-apply skipped reason=unrenderable-snapshot ms={:.1}",
                elapsed_ms()
            ));
            return; // defensive: an already-prepared snapshot should decode cleanly
        }
        // No further readiness pre-check here: `draw_wallpaper()` and
        // `draw()` (see `redraw_entry_ready`'s own doc) are themselves the
        // correct and sufficient gate, via the buffer pool's own
        // free-slot bookkeeping -- never an outstanding frame callback,
        // which a compositor may withhold indefinitely for either surface
        // while it is fully occluded (board evidence, 2026-09-27: a
        // separate `ready`/`overlay_ready` pre-check here, copied from
        // the durable commit path, skipped with `reason=not-ready-for-a-
        // frame` while the chooser's own panel -- the very thing being
        // drawn -- still had an outstanding callback from an earlier
        // redraw, even though a buffer slot was free). Attempting the
        // draws directly and reading their own return values is exactly
        // what the durable path's own `ready == true` branch already
        // does; this has no 1400 ms retry window because unlike a durable
        // commit, a missed optimistic frame costs nothing but the
        // optimism itself -- the real commit/rollback event still lands.
        self.wallpaper_path = fallback_still(Some(snapshot));
        self.wallpaper_generation_root = Some(snapshot.path.clone());
        self.video_display = None;
        // A pre-render (task: pre-render at prepare time) is bounded to
        // one slot and always consumed here, matching or not -- a stale
        // one must never linger for a later, unrelated Apply to trip
        // over. Only ever adopted when it matches this exact generation,
        // this exact geometry/route, and `content_generation` (everything
        // else the render depended on) unchanged since it was computed;
        // any mismatch falls back to `set_appearance`'s own ordinary
        // rebuild, exactly as if no pre-render had ever run.
        let content_generation = self.renderer.content_generation();
        let stored = self.prerendered_overlay.take();
        let mismatch_reason = if self.route != Route::Settings {
            Some("not-on-settings-route")
        } else {
            prerendered_overlay_mismatch_reason(
                stored.as_ref(),
                &snapshot.generation,
                Route::Settings,
                self.width,
                self.height,
                content_generation,
            )
        };
        let prerendered = mismatch_reason.is_none().then_some(stored).flatten();
        // Per-stage timing (coordinator ask, board evidence 2026-09-28: a
        // *matched* pre-render still took 161ms touch-up-to-commit on the
        // K230, far above the ~30ms target -- this breakdown is what a
        // later board run reads to find which stage actually dominates).
        // `adopt_ms` covers `adopt_prerendered_overlay`'s own pixel copy
        // (or, on a miss, `set_appearance`'s cache invalidation);
        // `wallpaper_ms` and `overlay_ms` each cover one surface's whole
        // `draw_*` call -- attach, damage, and `wl_surface::commit` all
        // happen inside those calls and are not separately timed here
        // (a finer breakdown inside `draw`/`draw_wallpaper` themselves,
        // and the wallpaper-buffer-attach optimization the same board
        // evidence asked for, are named as deferred follow-up work in
        // this task's own evidence doc, not attempted this stage).
        let stage_start = Instant::now();
        if let Some(candidate) = prerendered {
            self.renderer.adopt_prerendered_overlay(
                Some(snapshot.clone()),
                Route::Settings,
                candidate.width,
                candidate.height,
                candidate.pixels,
            );
        } else {
            self.renderer.set_appearance(Some(snapshot.clone()));
        }
        let adopt_ms = stage_start.elapsed().as_secs_f64() * 1000.0;
        self.dirty = true;
        self.wallpaper.dirty = true;
        let stage_start = Instant::now();
        let background = self.draw_wallpaper(qh);
        let wallpaper_ms = stage_start.elapsed().as_secs_f64() * 1000.0;
        if !background {
            self.log(&format!(
                "optimistic-apply skipped reason=draw-wallpaper-failed ms={:.1}",
                elapsed_ms()
            ));
        }
        let stage_start = Instant::now();
        let foreground = self.layer.is_none() || self.draw(qh);
        let overlay_ms = stage_start.elapsed().as_secs_f64() * 1000.0;
        if background && !foreground {
            self.log(&format!(
                "optimistic-apply skipped reason=draw-failed ms={:.1}",
                elapsed_ms()
            ));
        }
        self.appearance_pending = true;
        let stage_start = Instant::now();
        let flushed = queue.flush().is_ok();
        let flush_ms = stage_start.elapsed().as_secs_f64() * 1000.0;
        self.appearance_pending = false;
        if background && foreground && !flushed {
            self.log(&format!(
                "optimistic-apply skipped reason=flush-failed ms={:.1}",
                elapsed_ms()
            ));
        }
        if background && foreground && flushed {
            // The durable commit event for this exact generation, once it
            // arrives, may now skip redrawing entirely and just adopt
            // this already-flushed frame -- see `optimistic_active`'s own
            // doc and `pending_appearance`'s `reuse_optimistic` element.
            self.optimistic_active = Some(snapshot.generation.clone());
            // Named stage marker (task 6.6's own board re-check): how long
            // the Apply tap took to reach a real, flushed frame carrying
            // the new theme -- this is the number the ~30 ms target is
            // measured against. `prerendered` distinguishes a cache hit
            // (the panel's own scene reused, not rebuilt) from a full
            // synchronous rebuild; `reason=...` (only present when
            // `prerendered=false`) names exactly which field made a
            // stored pre-render not match, so a board run states the
            // cause directly instead of requiring a fresh multi-step
            // reconstruction each time (board evidence, 2026-09-28).
            match mismatch_reason {
                Some(reason) => self.log(&format!(
                    "optimistic-apply shown ms={:.1} prerendered=false reason={reason}",
                    elapsed_ms()
                )),
                None => self.log(&format!(
                    "optimistic-apply shown ms={:.1} prerendered=true",
                    elapsed_ms()
                )),
            }
            self.log(&format!(
                "optimistic-apply stage adopt_ms={adopt_ms:.1} wallpaper_ms={wallpaper_ms:.1} overlay_ms={overlay_ms:.1} flush_ms={flush_ms:.1}"
            ));
        }
    }

    /// The bookkeeping a successful commit/rollback always needs from
    /// `self.video_display` (already set) and `snapshot` (the event's own
    /// reported generation), whether this tick actually redrew the frame
    /// or is reusing one Optimistic Apply already drew and flushed (see
    /// `pending_appearance`'s own `reuse_optimistic` element). Never
    /// touches `appearance_pending`, the ack, or the "accepted" log line --
    /// the two call sites differ only in whether they draw first, and in
    /// exactly what they log.
    fn adopt_committed_video_state(&mut self, snapshot: Option<&AppearanceSnapshot>) {
        self.video_source = self.video_display.as_ref().map(|key| key.path.clone());
        self.video_start_attempted = self.video_source.is_some();
        let identity = video_identity(snapshot);
        self.video_generation = identity.0;
        self.video_relative = identity.1;
        self.video_error = None;
        self.video_submitted = 0;
        self.video_callbacks = 0;
        self.video_last_decoded_ms = None;
        self.video_last_submitted_ms = None;
        self.video_last_callback_ms = None;
        let slot = resolve_video_slot(
            self.video_display.as_ref(),
            self.video_active.as_ref().map(|video| &video.decoder.key),
            self.video_candidate.as_ref().map(|video| &video.decoder.key),
            self.video_previous.as_ref().map(|video| &video.decoder.key),
        );
        if slot != VideoSlot::Active {
            let mut former = self.video_active.take();
            if let Some(video) = former.as_mut() {
                video.pause();
            }
            self.video_active = match slot {
                VideoSlot::Candidate => self.video_candidate.take(),
                VideoSlot::Previous => self.video_previous.take(),
                VideoSlot::Active | VideoSlot::None => None,
            };
            self.video_previous = former;
        }
        if let Some(video) = self.video_active.as_mut() {
            if self.video_covered || self.reduced_motion {
                video.pause();
            }
        }
        self.video_candidate = None;
    }

    fn refresh_route(&mut self, route: Route) {
        match route {
            // The Shade now carries the same brightness slider the
            // Settings row does (task: "brightness should be a slider"),
            // so opening it needs the real backlight value too -- not
            // only the notification history this route used to refresh
            // alone -- so an external change (or the other sheet's own
            // drag) shows here as well (task: "sync the value").
            Route::Shade => {
                self.submit_service(ServiceRequest::RefreshNotifications);
                self.submit_service(ServiceRequest::RefreshSettings);
            }
            Route::Settings | Route::Power => {
                self.submit_service(ServiceRequest::RefreshSettings);
            }
            _ => {}
        }
    }

    /// Updates the locally-displayed brightness percent immediately, with
    /// no round trip -- mirrors how every other live drag in this shell
    /// (carousel position, notification swipe offset) paints from its own
    /// local state rather than waiting on a service reply mid-gesture.
    /// The real, verified value always arrives separately once the drag
    /// releases (`ServiceRequest::Brightness`'s own reply).
    fn apply_brightness_preview(&mut self, percent: u8) {
        if let Some(settings) = &mut self.service_view.settings {
            if settings.brightness.state == ControlState::Writable {
                settings.brightness.value = Some(ControlValue::Percent(percent));
            }
        }
        self.renderer.set_services(self.service_view.clone());
        self.dirty = true;
    }

    /// A local drag/tap moving `volume_state` (never an external graph
    /// read -- `sync_volume_from_graph` owns that side): updates the
    /// remembered level/mute, mirrors it into `service_view.settings.
    /// volume` (the Settings/Shade row's own paint source, exactly like
    /// `apply_brightness_preview`) so the slider repaints on every touch
    /// sample, and never itself raises the HUD -- the drag/tap is already
    /// its own on-screen feedback (`volume::ChangeOrigin::OwnSlider`).
    fn apply_volume_preview(&mut self, percent: u8) {
        self.volume_state.set_from_drag(percent);
        self.sync_volume_control();
    }

    /// Writes `volume_state`'s current displayed value/mute into
    /// `service_view.settings.volume` when a Settings/Shade snapshot
    /// already exists, and repaints. Never itself decides whether the
    /// value came from a local gesture or an external graph read --
    /// callers (`apply_volume_preview`, `sync_volume_from_graph`,
    /// `toggle_volume_mute`) own that distinction.
    fn sync_volume_control(&mut self) {
        if let Some(settings) = &mut self.service_view.settings {
            settings.volume.state = ControlState::Writable;
            settings.volume.value = Some(ControlValue::Percent(self.volume_state.displayed_percent()));
            settings.volume.label = "Volume".into();
        }
        self.renderer.set_services(self.service_view.clone());
        self.dirty = true;
    }

    /// The throttled, fire-and-forget live-drag write (task: "throttle
    /// live writes like brightness does") -- the persistent `pw-cli`
    /// writer, never a `wpctl` spawn per sample (`pipewire_ipc.rs`'s own
    /// cost argument). A missing writer or default sink id (PipeWire not
    /// up yet, or no sink reported) silently drops the write; the slider
    /// still visibly tracks the finger from `apply_volume_preview` alone,
    /// and the drag's own release (`commit_volume`) will try again with
    /// whatever id is known by then.
    fn submit_volume_live(&mut self, percent: u8) {
        let (Some(id), Some(writer)) = (self.default_sink_id, self.pipewire_writer.as_ref()) else {
            return;
        };
        let linear = volume::percent_to_linear(percent);
        writer.try_send(pipewire_ipc::set_volume_command(
            id,
            linear,
            self.volume_state.is_muted(),
        ));
        self.mark_own_volume_write();
    }

    /// Records that this shell itself just caused a volume/mute write, so
    /// the graph confirmation that follows is recognized as an echo, not
    /// a fresh external change (`VOLUME_ECHO_GRACE_MS`). Called from every
    /// write path (`submit_volume_live`'s throttled scrub and `commit_
    /// volume`'s authoritative `wpctl` call alike) -- `volume_drag.is_
    /// none()` alone only covers the drag itself, not a discrete mute-tap
    /// or device-picker commit that has no drag to check.
    fn mark_own_volume_write(&mut self) {
        let now = self.started.elapsed().as_millis() as u64;
        self.volume_echo_until_ms = Some(now + VOLUME_ECHO_GRACE_MS);
    }

    /// The authoritative, human-paced commit (a drag's release, a mute
    /// tap, an output-sink pick): a short-lived `wpctl` call, run off the
    /// Wayland thread so a slow/hung `wpctl` can never stall input or
    /// drawing. Rare enough (never per drag sample) that a spawned
    /// thread per call is the right cost trade-off, matching the
    /// brightness slider's own release-only authoritative write.
    fn commit_volume(&mut self, percent: u8, muted: bool) {
        let Some(id) = self.default_sink_id else {
            return;
        };
        let wpctl = self.wpctl_command.clone();
        let id_arg = id.to_string();
        let volume_arg = format!("{percent}%");
        let mute_arg = if muted { "1" } else { "0" }.to_string();
        thread::spawn(move || {
            let _ = Command::new(&wpctl)
                .args(["set-volume", &id_arg, &volume_arg])
                .stdin(Stdio::null())
                .stdout(Stdio::null())
                .stderr(Stdio::null())
                .status();
            let _ = Command::new(&wpctl)
                .args(["set-mute", &id_arg, &mute_arg])
                .stdin(Stdio::null())
                .stdout(Stdio::null())
                .stderr(Stdio::null())
                .status();
        });
        self.mark_own_volume_write();
    }

    /// The speaker-glyph tap (task: "toggles mute when tapped"): flips
    /// `volume_state`'s mute flag, previews it immediately (same as a
    /// drag), and commits it via `wpctl` -- a discrete action, not a
    /// throttled scrub, so it always goes straight to the authoritative
    /// path.
    fn toggle_volume_mute(&mut self) {
        self.volume_state.toggle_mute();
        self.sync_volume_control();
        self.commit_volume(
            self.volume_state.displayed_percent(),
            self.volume_state.is_muted(),
        );
    }

    /// Applies one freshly-drained `pipewire_ipc::Event` to this shell's
    /// own state: the default sink id/level/mute mirror
    /// (`volume_state`/`default_sink_id`), the full graph for the
    /// Settings/Shade row, the expanded HUD panel and the device picker
    /// (`service_view.audio`), and the HUD's own visibility -- raised
    /// only when nothing local is already showing the change
    /// (`volume_drag.is_none()`; a drag already in flight is this
    /// client's own write echoing back, not an external change, and the
    /// on-screen slider is already the feedback for it -- the same
    /// `ChangeOrigin::OwnSlider` suppression `volume.rs` documents,
    /// expressed here as "no local gesture in flight" rather than a
    /// separate origin tag, since the two conditions are equivalent for
    /// every write this shell itself ever makes).
    fn apply_pipewire_event(&mut self, event: pipewire_ipc::Event) {
        match event {
            pipewire_ipc::Event::Snapshot(graph) => {
                let previous = (
                    self.volume_state.displayed_percent(),
                    self.volume_state.is_muted(),
                );
                if let Some(sink) = graph.sinks.iter().find(|sink| sink.is_default) {
                    self.default_sink_id = Some(sink.id);
                    let percent = volume::linear_to_percent(sink.linear_volume);
                    self.volume_state.apply_external(percent, sink.muted);
                    let now = self.started.elapsed().as_millis() as u64;
                    let changed = previous
                        != (
                            self.volume_state.displayed_percent(),
                            self.volume_state.is_muted(),
                        );
                    let is_echo = self.volume_echo_until_ms.is_some_and(|until| now < until);
                    if changed && self.volume_drag.is_none() && !is_echo {
                        self.hud.show(now);
                    }
                } else {
                    self.default_sink_id = None;
                }
                self.service_view.audio = Some(graph);
                self.service_view.audio_error = None;
                self.sync_volume_control();
            }
            pipewire_ipc::Event::MonitorExited => {
                self.service_view.audio = None;
                self.service_view.audio_error =
                    Some("PipeWire monitor unavailable".into());
                self.pipewire_events = None;
                self.renderer.set_services(self.service_view.clone());
                self.dirty = true;
            }
        }
    }

    /// This HUD's own current on-screen rectangle: recomputed fresh from
    /// live state on every touch (never frozen for a gesture's duration
    /// the way `slider::Drag`'s track is) because the HUD's own bounds
    /// change with it -- expanding mid-drag is not a case this shell
    /// needs to defend against (the "..." affordance and a reposition
    /// drag can never be the same touch).
    fn hud_geometry(&self) -> volume::HudGeometry {
        let rows = if self.hud.is_expanded() {
            self.service_view
                .audio
                .as_ref()
                .map_or(0, |graph| graph.streams.len() + graph.sinks.len())
        } else {
            0
        };
        volume::hud_geometry(
            f64::from(self.width),
            f64::from(self.height),
            self.hud.position_fraction(),
            rows,
        )
    }

    /// A touch landing on the visible HUD is handled entirely here and
    /// never reaches any route-specific dispatch below it -- the HUD
    /// floats above whatever route is showing (task: "a vertical pill on
    /// the right edge", shown regardless of Home/Drawer/Shade/Settings).
    /// Returns whether the touch was consumed.
    fn hud_touch_down(&mut self, id: i32, pos: (f64, f64)) -> bool {
        let now = self.started.elapsed().as_millis() as u64;
        if !self.hud.is_visible(now) {
            return false;
        }
        let geometry = self.hud_geometry();
        if !geometry.contains(pos.0, pos.1) {
            return false;
        }
        if geometry.mute_icon_hit(pos.0, pos.1) {
            self.toggle_volume_mute();
        } else if geometry.expand_affordance_hit(pos.0, pos.1) {
            self.hud.toggle_expand(now);
            self.dirty = true;
        } else if let Some(row) = geometry.expanded_row_at(pos.0, pos.1) {
            self.tap_hud_row(row);
        } else {
            // The pill's own body, neither the icon, the affordance, nor
            // an expanded row: reposition drag (task: "can be dragged").
            self.hud.start_drag(id, now);
            self.dirty = true;
        }
        true
    }

    /// One expanded-panel row tap: `HudGeometry::expanded_row_at`'s own
    /// doc fixes the order (streams first, then sinks) both this and
    /// `render.rs`'s paint agree on. A stream row toggles that one
    /// stream's own mute (a per-app control, not the default sink's);
    /// a sink row picks it as the new default output -- the device
    /// picker task explicitly asks for both the expanded panel and
    /// Settings to offer this same pick.
    fn tap_hud_row(&mut self, row: usize) {
        let Some(audio) = self.service_view.audio.clone() else {
            return;
        };
        if let Some(stream) = audio.streams.get(row) {
            if let Some(writer) = self.pipewire_writer.as_ref() {
                writer.try_send(pipewire_ipc::set_volume_command(
                    stream.id,
                    stream.linear_volume,
                    !stream.muted,
                ));
                self.mark_own_volume_write();
            }
            return;
        }
        if let Some(sink) = audio.sinks.get(row - audio.streams.len()) {
            self.pick_output_sink(sink.id);
        }
    }

    /// The output device picker's own commit (expanded HUD panel and
    /// Settings alike): `wpctl set-default`, a rare, human-paced action,
    /// off the Wayland thread the same way `commit_volume` already is.
    fn pick_output_sink(&mut self, sink_id: u32) {
        let wpctl = self.wpctl_command.clone();
        let id_arg = sink_id.to_string();
        thread::spawn(move || {
            let _ = Command::new(&wpctl)
                .args(["set-default", &id_arg])
                .stdin(Stdio::null())
                .stdout(Stdio::null())
                .stderr(Stdio::null())
                .status();
        });
        self.mark_own_volume_write();
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
        if let ServiceRequest::BrightnessLive(_) = reply.request {
            // Fire-and-forget scrub write: the drag's own optimistic
            // slider position (`apply_brightness_preview`) is already the
            // visible truth, and the release that follows always sends
            // an authoritative `Brightness` request with real feedback.
            // Swallow this reply so ~20-30/s scrub writes never spam the
            // toast message or force an extra redraw beyond the one the
            // drag itself already triggered.
            return;
        }
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
                self.service_view.settings = Some(*settings);
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
                if !suppresses_action_message(&reply.request, outcome.error.as_deref()) {
                    self.service_view.message = Some(action_message(&outcome));
                }
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
            PanelIntent::Hide => self.begin_animated_close(),
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
        // -1, not 0: this is a fixed full-panel surface, never a panel that
        // should yield space to another layer's exclusive zone. See
        // `ensure_layer`'s own doc for the bug this fixes.
        layer.set_exclusive_zone(-1);
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

    /// Maps Home's own `Layer::Bottom` surface. Unlike the on-demand
    /// drawer/shade/settings overlay, this is created once, at startup, and
    /// stays mapped for the life of the process -- Home is what shows
    /// through whenever nothing else covers it, so there is no "hide" state
    /// for this surface to toggle. A full input region is set once here and
    /// never narrowed: `Layer::Bottom` already sits beneath every ordinary
    /// toplevel and the overlay surface, so wlroots only ever routes a
    /// touch here when nothing above it claims that point first.
    fn ensure_home(&mut self, qh: &QueueHandle<Self>) -> bool {
        if self.home_surface.layer.is_some() {
            return true;
        }
        let surface = self.compositor.create_surface(qh);
        let layer = self.layer_shell.create_layer_surface(
            qh,
            surface,
            Layer::Bottom,
            Some("k230-shell-home"),
            None,
        );
        layer.set_anchor(Anchor::TOP | Anchor::BOTTOM | Anchor::LEFT | Anchor::RIGHT);
        layer.set_size(0, 0);
        // -1, not 0: see `ensure_layer`'s own doc for why.
        layer.set_exclusive_zone(-1);
        layer.set_keyboard_interactivity(KeyboardInteractivity::None);
        layer.commit();
        self.home_surface.layer = Some(layer);
        self.home_surface.configured = false;
        self.home_surface.dirty = true;
        self.log("home-map-request");
        true
    }

    fn draw_home(&mut self, qh: &QueueHandle<Self>) -> bool {
        if !self.home_surface.configured || self.home_surface.frame_pending {
            return false;
        }
        let (width, height) = (self.home_surface.width, self.home_surface.height);
        if frame_bytes(width, height).is_none() {
            return false;
        }
        // Reflow the persisted grid to whatever column count this geometry
        // supports before anything paints or hit-tests against it -- see
        // `HomeScreen::sync_columns`'s own doc for why this is the one
        // choke point that guarantees the two never disagree.
        self.home.sync_columns(width, height);
        let stride = (width * 4) as i32;
        self.home_surface
            .buffers
            .retain(|b| b.stride() == stride && b.height() == height as i32);
        let available: Vec<bool> = self
            .home_surface
            .buffers
            .iter()
            .map(|b| b.canvas(&mut self.pool).is_some())
            .collect();
        let (index, canvas) = if let Some(index) = released_slot(&available) {
            (
                index,
                self.home_surface.buffers[index]
                    .canvas(&mut self.pool)
                    .expect("released home slot"),
            )
        } else {
            if self.home_surface.buffers.len() >= 2 {
                self.home_surface.dirty = true;
                return false;
            }
            let Ok((buffer, canvas)) = self.pool.create_buffer(
                width as i32,
                height as i32,
                stride,
                wl_shm::Format::Argb8888,
            ) else {
                self.log("home-shm-allocate-failed");
                return false;
            };
            self.home_surface.buffers.push(buffer);
            (self.home_surface.buffers.len() - 1, canvas)
        };
        // `K230_HOME_FRAME`: the same cheap, rate-limited timing log
        // `K230_DRAWER_FRAME` already gives the Drawer, one surface over
        // (task 7).
        let render_started = Instant::now();
        if let Err(error) = self.renderer.draw_home(canvas, width, height, &self.apps, &self.home) {
            self.home_surface.dirty = false;
            self.log(&format!("home-render-failed {error}"));
            return false;
        }
        let now = Instant::now();
        if self
            .home_frame_log_at
            .is_none_or(|last| now.duration_since(last) >= DRAWER_FRAME_LOG_INTERVAL)
        {
            self.home_frame_log_at = Some(now);
            let elapsed_ms = now.duration_since(render_started).as_secs_f64() * 1000.0;
            self.log(&format!("K230_HOME_FRAME ms={elapsed_ms:.2} pages={}", self.home.page_count()));
        }
        let Some(layer) = self.home_surface.layer.as_ref() else {
            return false;
        };
        layer
            .wl_surface()
            .damage_buffer(0, 0, width as i32, height as i32);
        layer.wl_surface().frame(qh, layer.wl_surface().clone());
        if self.home_surface.buffers[index]
            .attach_to(layer.wl_surface())
            .is_err()
        {
            self.log("home-attach-failed");
            return false;
        }
        layer.commit();
        self.home_surface.frame_pending = true;
        self.home_surface.dirty = false;
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
            // Three, not two: an optimistic show (task: Optimistic Apply)
            // can commit a frame the compositor has not yet released when
            // the durable commit's own redraw follows moments later --
            // board evidence, 2026-09-27 ("appearance-commit-rejected
            // draw-wallpaper-failed" right after a successful optimistic
            // show). Two buffers were exactly enough for ordinary
            // prepare/commit pacing; a third absorbs one extra in-flight
            // frame from the optimistic path without starving anything.
            if self.wallpaper.buffers.len() >= 3 {
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

    /// Every catalog index currently shown in the drawer grid, in display
    /// order -- see `service_ui::filter_app_indices`'s own doc for why
    /// this is cheap enough to recompute on demand rather than cache.
    /// `DrawerAction::Launch`/`LongPress` give a *display* index (their
    /// only source, `navigation::tile_at`, only ever sees what
    /// `renderer.draw`'s own filtered grid painted); this is how that
    /// maps back to a real `self.apps` index.
    fn drawer_filtered_apps(&self) -> Vec<usize> {
        filter_app_indices(&self.apps, &self.drawer_search.query)
    }

    /// Pushes `self.drawer_search` to the renderer (forcing a grid
    /// rebuild if it actually changed) and marks the frame dirty so the
    /// result is visible on the next `draw`.
    fn sync_drawer_search(&mut self) {
        self.sync_drawer_keyboard();
        if self
            .renderer
            .set_drawer_search(self.drawer_search.clone())
        {
            self.dirty = true;
        }
    }

    fn sync_drawer_keyboard(&mut self) {
        let want = self.route == Route::Drawer && self.layer.is_some()
            && self.splash.is_none() && self.drawer_search.focused;
        self.drawer_search.keyboard_inset = if want && self.keyboard_signal_path.is_some() {
            self.keyboard_height_px + self.keyboard_grip_height_px
        } else { 0.0 };
        if want == self.drawer_keyboard_active { return; }
        self.drawer_keyboard_active = want;
        if let Some(layer) = &self.layer {
            layer.set_keyboard_interactivity(if want {
                KeyboardInteractivity::Exclusive
            } else { KeyboardInteractivity::None });
            layer.commit();
        }
        if let Some(path) = &self.keyboard_signal_path {
            if let Err(error) = std::process::Command::new(path)
                .arg(if want { "show" } else { "hide" }).spawn() {
                self.log(&format!("drawer-keyboard-signal-failed {error}"));
            }
        }
        self.dirty = true;
    }

    fn forget_drawer_keyboard(&mut self) {
        self.drawer_keyboard_active = false;
        self.drawer_search.unfocus();
        self.renderer.set_drawer_search(self.drawer_search.clone());
        if let Some(layer) = &self.layer {
            layer.set_keyboard_interactivity(KeyboardInteractivity::None);
            layer.commit();
        }
        self.dirty = true;
    }

    fn handle_drawer_key(&mut self, event: &KeyEvent) {
        if self.drawer_keyboard_active && self.drawer_search.key_event(
            u32::from(event.keysym), event.utf8.as_deref()) {
            self.nav = DrawerNavigation::default();
            self.sync_drawer_search();
        }
    }

    /// `DrawerAction::Launch(display_index)` -> the real catalog app.
    fn launch_drawer_app(&mut self, qh: &QueueHandle<Self>, display_index: usize) {
        if let Some(&real_index) = self.drawer_filtered_apps().get(display_index) {
            self.launch_app(qh, real_index);
        }
    }

    fn launch_app(&mut self, qh: &QueueHandle<Self>, index: usize) {
        if self.launch_in_flight || self.route != Route::Drawer {
            if self.launch_in_flight {
                self.log("app-launch-worker-still-running");
            }
            return;
        }
        let Some(app) = self.apps.get(index) else {
            return;
        };
        let path = app.path.clone();
        let name = app.name.clone();
        let icon = app.icon.clone();
        let swaymsg = self.swaymsg.clone();
        let sender = self.launch_sender.clone();
        self.launch_seq = self.launch_seq.wrapping_add(1);
        let attempt = self.launch_seq;
        // Keeps this same overlay mapped and simply repaints it as the
        // splash -- see `start_splash`'s own doc for why this, not
        // `self.hide()`, is what keeps the previously active app from ever
        // flashing through.
        if !self.start_splash(qh, name, icon) {
            self.log("app-launch-splash-unavailable");
            return;
        }
        self.launching = true;
        self.launch_in_flight = true;
        thread::spawn(move || {
            let result = swaymsg
                .as_deref()
                .ok_or_else(|| "K230_SWAYMSG is unavailable".into())
                .and_then(|swaymsg| launch_selected(&path, swaymsg));
            let _ = sender.send((attempt, result));
        });
    }

    /// Home's tap-to-launch-or-focus, by desktop-entry id rather than a
    /// drawer index. Home has no overlay of its own, so unlike `launch_app`
    /// this may need `start_splash` to map one fresh rather than reuse an
    /// already-mapped one; either way this does not set `self.launching`
    /// (that flag exists only to let a failed *drawer* launch reopen the
    /// drawer it dismissed -- a Home/dock launch that fails or times out
    /// simply dismisses the splash back to Home, which was already showing
    /// underneath and needs no explicit reopen).
    fn launch_home_app(&mut self, qh: &QueueHandle<Self>, id: String) {
        if self.launch_in_flight {
            self.log("app-launch-worker-still-running");
            return;
        }
        let Some(swaymsg) = self.swaymsg.clone() else {
            self.log("home-launch-failed K230_SWAYMSG is unavailable");
            return;
        };
        // Looked up against the current catalog *now*, not inside the
        // spawned thread: a pin can outlive its app (see
        // `home_state`'s own `missing_entry_keeps_its_slot_on_load` doc),
        // and `path` being `None` here is exactly that case, not a race.
        let entry = self.apps.iter().find(|app| app.id == id);
        let path = entry.map(|app| app.path.clone());
        let name = entry.map(|app| app.name.clone()).unwrap_or_else(|| id.clone());
        let icon = entry.and_then(|app| app.icon.clone());
        let sender = self.launch_sender.clone();
        self.launch_seq = self.launch_seq.wrapping_add(1);
        let attempt = self.launch_seq;
        if !self.start_splash(qh, name, icon) {
            self.log("home-launch-splash-unavailable");
            return;
        }
        self.launch_in_flight = true;
        thread::spawn(move || {
            let result = focus_or_launch(&id, path.as_deref(), &swaymsg);
            let _ = sender.send((attempt, result));
        });
    }

    /// Shows the launch splash instantly and either reuses the overlay's
    /// existing mapped layer (a drawer tap: the layer is already mapped and
    /// already `configured`, so the very next `draw` call below actually
    /// paints, within the same event-loop turn as the tap) or maps it fresh
    /// (a Home/dock tap: `ensure_layer` requests a `configure` round trip
    /// first, so the first splash frame lands one compositor round trip
    /// later rather than in this same call -- still well under one visible
    /// frame on a local Wayland connection, but not literally synchronous).
    /// Either way the previously active app is never uncovered in between:
    /// the drawer path never unmaps its layer at all, and the Home path's
    /// freshly mapped layer is `Layer::Overlay`, which already occludes
    /// everything beneath it the instant it has any content.
    ///
    /// Cancels a previous launch's still-running window watcher first (a
    /// second tap before the first launch resolved supersedes it, and the
    /// old watcher must not later report a spurious match/failure for this
    /// new splash).
    fn start_splash(&mut self, qh: &QueueHandle<Self>, name: String, icon: Option<String>) -> bool {
        if let Some(stop) = self.splash_watch_stop.take() {
            stop.store(true, Ordering::Relaxed);
        }
        self.reset_overlay_interaction();
        if !self.ensure_layer(qh) {
            return false;
        }
        self.splash = Some(Splash::new(name, icon, SplashTarget::LaunchOrder, Instant::now()));
        // Force `input_region()` to recompute on the next `draw`: the
        // splash's own hit-test (nothing while `Pending`, full-screen while
        // dismissable) is unrelated to whatever `self.route`'s ordinary
        // input rect was a moment ago, and the cached key would otherwise
        // suppress the very first recompute.
        self.input_region_key = None;
        self.dirty = true;
        self.draw(qh);
        true
    }

    /// Task 1's drawer long-press-drag hand-off: fired from the tick loop
    /// once `navigation::DrawerNavigation::take_long_press_drag` arms it.
    /// Starts a live `HomeScreen` external drag for the held app, bound to
    /// `touch_id` so this client's `TouchHandler::motion`/`up` (see their
    /// own Drawer branches) keep forwarding the same touch into it instead
    /// of the drawer's ordinary scroll/close-drag handling. `display_index`
    /// is the search-filtered index `take_long_press_drag` resolved
    /// against (`navigation::tile_at`'s own domain), mapped back to the
    /// real catalog app exactly like `launch_drawer_app` does.
    fn begin_drawer_home_drag(&mut self, touch_id: i32, display_index: usize, point: (f64, f64)) {
        let Some(&real_index) = self.drawer_filtered_apps().get(display_index) else {
            return;
        };
        let Some(id) = self.apps.get(real_index).map(|app| app.id.clone()) else {
            return;
        };
        let snapshot = self.capture_drawer_snapshot();
        self.drawer_home_drag = Some(touch_id);
        self.drawer_drag_reveal = snapshot.map(|snapshot| DrawerDragReveal { started: Instant::now(), snapshot });
        self.home.begin_external_drag(id, point);
        // The drawer surface now paints transparently (Home shows through)
        // plus the lifted icon and the Cancel band -- see `draw`'s own
        // Drawer branch -- and Home paints its own drop-target highlight.
        self.dirty = true;
        self.home_mark_dirty();
        self.log("home-drag-begin");
    }

    /// A plain pixel copy of the drawer's own last-rendered frame (task 1's
    /// reveal animation): renders the current Route/scroll/search state
    /// exactly as `draw` itself would, into a scratch buffer instead of the
    /// live SHM canvas, so `DrawerDragReveal` can animate it afterward
    /// without re-rendering the scene on every subsequent frame. `None`
    /// only on a genuinely invalid panel geometry (`frame_bytes`) or a
    /// render failure -- the caller then just skips the animation and goes
    /// straight to the steady-state Cancel-band rendering.
    fn capture_drawer_snapshot(&mut self) -> Option<Vec<u8>> {
        let size = frame_bytes(self.width, self.height)?;
        let mut canvas = vec![0u8; size];
        let progress = if self.panel_close.active() {
            self.panel_close.progress()
        } else if self.reveal.surface().is_some() {
            self.reveal.progress()
        } else {
            1.0
        };
        self.renderer
            .draw_with_hud(
                &mut canvas,
                RenderParams {
                    width: self.width,
                    height: self.height,
                    route: self.route,
                    progress,
                    scroll: if self.route == Route::Drawer { self.nav.scroll } else { 0.0 },
                },
                &self.apps,
                &self.hud,
                self.started.elapsed().as_millis() as u64,
            )
            .ok()?;
        Some(canvas)
    }

    /// Resolves the drawer long-press-drag's release: Cancel (released over
    /// the drawer's own top chrome band -- `navigation::drag_cancel_zone_hit`
    /// -- task 1: "releasing over the drawer area ... cancels") leaves the
    /// layout untouched and reopens the drawer normally; anything else
    /// drops through to `HomeScreen::release_drag` (cell/folder/dock, or a
    /// `place_first_fit` fallback -- see that method's own doc) and then
    /// closes the drawer for real via the existing animated-close path, the
    /// same one a swipe-to-close release already uses.
    fn end_drawer_home_drag(&mut self, qh: &QueueHandle<Self>, point: (f64, f64)) {
        self.drawer_home_drag = None;
        self.drawer_drag_reveal = None;
        if navigation::drag_cancel_zone_hit(point, self.height) {
            self.home.cancel_external_drag();
            self.home_mark_dirty();
            self.log("home-drag-cancelled");
            self.dirty = true;
            self.draw(qh);
            return;
        }
        if let Some(action) = self.home.release_drag(point, self.home_surface.width, self.home_surface.height) {
            // `home-drag-placed`: a plain, always-emitted completion marker
            // for this hand-off (unlike `persist_home_layout`, which only
            // ever logs on a *failed* save) -- the QEMU harness's own
            // drag-to-place scenario waits on this rather than polling the
            // layout file mid-gesture.
            self.log("home-drag-placed");
            self.apply_home_action(qh, action);
        }
        self.home_mark_dirty();
        self.begin_animated_close();
        self.dirty = true;
        self.draw(qh);
    }

    /// Applies a `HomeAction` returned by any `HomeScreen` gesture entry
    /// point -- shared by the Home surface's own touch dispatch and the
    /// drawer-drag hand-off's release, so both stay in sync as
    /// `HomeAction` grows new variants (e.g. the widget-picker's
    /// `OpenWallpaperAndStyle`, coordinator follow-up).
    fn apply_home_action(&mut self, qh: &QueueHandle<Self>, action: HomeAction) {
        match action {
            HomeAction::Launch(app_id) => self.launch_home_app(qh, app_id),
            HomeAction::LayoutChanged => {
                // A plain, always-emitted completion marker for *any*
                // layout-changing gesture (rearrange, folder create/join/
                // rename, a widget or drag-out-of-folder placement, ...),
                // regardless of which touch surface drove it -- what a
                // QEMU proof's own synchronization waits on instead of a
                // fixed sleep. `home-drag-placed` (`end_drawer_home_drag`)
                // is the drawer-hand-off's own more specific version of
                // this same idea.
                self.log("home-layout-changed");
                self.persist_home_layout();
            }
            HomeAction::OpenWallpaperAndStyle => {
                // Reuses the existing, unmodified Settings/theme-picker
                // route exactly as its own "Theme" row tap would
                // (`theme_action`/`theme_ui.rs` untouched) -- see
                // `design.md`'s note on why this is a navigation, not a
                // reimplementation.
                self.show(qh, Route::Settings);
                self.theme_action(ThemeIntent::Open);
            }
        }
    }

    /// Called after any Home layout mutation (pin/unpin/reorder/page move);
    /// persists it to `home_state_path`, matching every other pinned
    /// desktop-entry id in a page or the dock.
    fn persist_home_layout(&self) {
        let Some(path) = self.home_state_path.as_deref() else {
            return;
        };
        if let Err(error) = home_state::save(path, &self.home.layout) {
            self.log(&format!("home-layout-save-failed {error}"));
        }
    }

    fn home_mark_dirty(&mut self) {
        self.home_surface.dirty = true;
    }

    /// Refreshes the Clock/Battery/Weather widget content Home paints
    /// (task 4/7): battery is a cheap synchronous `/sys` poll every
    /// `home_widgets::battery::POLL_INTERVAL` (about 30s, matching the
    /// task's "or a slow poll of about 30s" fallback -- this board has no
    /// inotify-worthy battery driver to watch, since no supply exists at
    /// all today); weather is checked for staleness at most once a minute
    /// and, only when actually due, fetched on a background thread (never
    /// this one -- `home_widgets::weather::refresh` shells out to `curl`,
    /// which must not block this client's single manual poll loop); the
    /// clock schedules its own next once-a-minute, minute-aligned wake
    /// rather than redrawing every frame.
    fn tick_home_widgets(&mut self, now: Instant) {
        let battery_due = self
            .battery_polled_at
            .is_none_or(|last| now.duration_since(last) >= home_widgets::battery::POLL_INTERVAL);
        if battery_due {
            self.battery_polled_at = Some(now);
            let state = home_widgets::battery::read_state(Path::new("/sys/class/power_supply"));
            if state != self.home.battery {
                self.home.battery = state;
                self.home_mark_dirty();
            }
        }

        if let Some(receiver) = self.weather_pending.as_ref() {
            if let Ok(display) = receiver.try_recv() {
                self.weather_pending = None;
                if display != self.home.weather {
                    self.home.weather = display;
                    self.home_mark_dirty();
                }
            }
        } else {
            let check_due = self
                .weather_checked_at
                .is_none_or(|last| now.duration_since(last) >= Duration::from_secs(60));
            if check_due {
                self.weather_checked_at = Some(now);
                if let Some(cache_path) = home_widgets::weather::cache_path() {
                    let cached = home_widgets::weather::load_cache(&cache_path);
                    let system_now = std::time::SystemTime::now();
                    // Fold in whatever cache exists immediately, so a fresh
                    // boot shows the last-known reading rather than
                    // "Unavailable" until the first fetch completes.
                    let display_now = home_widgets::weather::display_for(cached.clone(), system_now);
                    if display_now != self.home.weather {
                        self.home.weather = display_now;
                        self.home_mark_dirty();
                    }
                    if home_widgets::weather::should_fetch(cached.as_ref(), system_now) {
                        let (sender, receiver) = mpsc::channel();
                        self.weather_pending = Some(receiver);
                        thread::spawn(move || {
                            let display = home_widgets::weather::refresh(&cache_path, "curl", std::time::SystemTime::now());
                            let _ = sender.send(display);
                        });
                    }
                }
            }
        }

        let clock_due = self.clock_next_tick.is_none_or(|next| now >= next);
        if clock_due {
            let ms = home_widgets::clock::now_local()
                .map(|local| home_widgets::clock::ms_until_next_minute(local.second))
                .unwrap_or(60_000)
                .max(1_000);
            self.clock_next_tick = Some(now + Duration::from_millis(u64::from(ms)));
            self.home_mark_dirty();
        }
    }

    /// If `app_watch::CatalogWatcher` armed a debounced rescan and its
    /// deadline has now passed, re-scans `candidates` and, only if the
    /// resulting list actually differs from `self.apps`, adopts it and
    /// marks both the drawer (`self.dirty`) and Home (`home_mark_dirty`)
    /// dirty so each repaints against the new catalog. A rescan that comes
    /// back identical (a `close-write` on a file whose content didn't
    /// change the catalog's shape, say) never touches `self.apps` or marks
    /// anything dirty -- this must not repaint on every burst of
    /// filesystem noise, only on an actual change.
    fn maybe_rescan_catalog(&mut self, candidates: &[PathBuf]) {
        let Some(deadline) = self.catalog_pending_rescan else {
            return;
        };
        if Instant::now() < deadline {
            return;
        }
        self.catalog_pending_rescan = None;
        let fresh = scan_apps(candidates);
        if fresh != self.apps {
            self.log("catalog-changed");
            self.apps = fresh;
            self.dirty = true;
            self.home_mark_dirty();
            // Task 5: re-warm the drawer grid for the changed catalog now,
            // not on whatever tap next opens the drawer.
            let (reference_width, reference_height) = if self.width > 0 && self.height > 0 {
                (self.width, self.height)
            } else {
                (568, 1232)
            };
            self.renderer.prebuild_drawer_grid(&self.apps, reference_width, reference_height);
        }
    }

    /// Maps the drawer/shade/settings overlay's `Layer::Overlay` surface.
    ///
    /// `set_exclusive_zone(-1)` (not `0`): a `0` exclusive zone means, per
    /// wlr-layer-shell-unstable-v1's own doc for `set_exclusive_zone`, "the
    /// surface indicates that it would like to be moved to avoid occluding
    /// surfaces with a positive exclusive zone" -- since this surface is
    /// anchored to all four edges, wlroots' `arrange_layers` acted on that by
    /// *shrinking* it (not moving it) whenever `wvkbd`'s own layer surface
    /// raised a real positive exclusive zone for its height. This shell's
    /// `configure` handler (`configure_size`) accepted that smaller size
    /// like any legitimate resize, and every page painted onto this surface
    /// (`render::paint_wifi` and its siblings) scales its fixed 568x1232
    /// design-unit artwork to fill whatever it is given
    /// (`cr.scale(width / 568.0, height / 1232.0)`) -- entirely reasonably
    /// for a genuine output resize, but wrong here: the configure was never
    /// really about this surface's own size, only about wvkbd wanting floor
    /// space, and shrinking only the *height* stretched every glyph and
    /// button vertically (real board capture, 2026-09-28: the Wi-Fi page
    /// visibly squashed to about 0.66x height the instant wvkbd appeared).
    /// `-1` tells the compositor this surface "would not like to be moved
    /// [or resized] to accommodate for other surfaces... and \[should\]
    /// extend it all the way to the edges it is anchored to" -- so it always
    /// gets the full 568x1232 panel regardless of what wvkbd or any other
    /// layer surface requests, and pages that need to react to the keyboard
    /// (only the Wi-Fi password field does today) do it by reflowing their
    /// own content against the keyboard's known height
    /// (`wifi_ui::entry_buttons_rect`, driven by `sync_wifi_keyboard`), never
    /// by asking the compositor to resize the surface itself. `ensure_home`
    /// and `ensure_wallpaper` carry the identical fix for the identical
    /// reason: neither is keyboard-aware, so either would otherwise squash
    /// the same way the moment the keyboard shows while they are visible.
    /// Whether a proposed `(width, height)` configure equals some currently
    /// known output's own logical size -- the distinction `configure`'s own
    /// three branches need between a legitimate whole-output resize (an
    /// HDMI monitor, at any aspect: 1920x1080 landscape, 1080x1920 rotated
    /// portrait) and a keyboard-exclusive-zone squish, which shrinks only
    /// one axis and is therefore never a whole output. Both change the
    /// surface's aspect ratio away from `configure_preserves_aspect`'s
    /// design band, so that check alone cannot tell them apart; this one
    /// can, because a squish's `(width, height)` is smaller than the output
    /// it sits on while a real output resize's is exactly the output.
    ///
    /// Used to *accept* the configure at its own full size instead of
    /// `feat/hdmi-pillarbox`'s (2026-09-29, commit 4c2eb57c) now-removed
    /// `pillarbox` fallback, which asked the compositor for a centered
    /// design-aspect column: the operator did not want an HDMI monitor
    /// letterboxed, they wanted the shell to fill it. See
    /// `openspec/changes/the-shell-adapts-to-output-resolution/design.md`.
    fn is_whole_output(&self, width: u32, height: u32) -> bool {
        self.output_state.outputs().any(|output| {
            self.output_state
                .info(&output)
                .and_then(|info| info.logical_size)
                .is_some_and(|(w, h)| (w, h) == (width as i32, height as i32))
        })
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
            layer.set_exclusive_zone(-1);
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

    /// The distance (in device pixels) this route's panel travels between
    /// fully hidden and fully shown -- what a live close drag's finger
    /// travel is measured against, and what `RendererCache::draw`'s own
    /// row-shift already uses for the same route (`panel_travel_height`'s
    /// own doc). Reads `theme_view`/`service_view` live, exactly like
    /// `RendererCache`'s internal `chooser`/`services` copies do, since a
    /// Settings sub-page (Wi-Fi, the theme chooser) changes its own
    /// content-sized height.
    fn panel_travel(&self) -> f64 {
        panel_travel_height(
            self.route,
            self.width,
            self.height,
            Some(&self.theme_view),
            Some(&self.service_view),
        )
    }

    /// A non-drag close (a Settings back/close tap, a notification
    /// dismiss-all zone Hide, or the top dismiss zone's own tap/short-drag
    /// fallback in `panel_intent`) animates the same way a released close
    /// drag settles closed, instead of the instant unmap `hide()` alone
    /// used to be. `hide()` itself still runs, unchanged, once the settle
    /// this starts actually reaches 0.0 -- see the event loop's own
    /// `panel_close.tick`/`take_settled_closed` handling.
    fn begin_animated_close(&mut self) {
        self.drawer_search.unfocus();
        self.sync_drawer_search();
        let now = self.started.elapsed().as_millis() as u64;
        self.panel_close
            .begin_settle(1.0, 0.0, now, self.reduced_motion);
        self.dirty = true;
    }

    fn show(&mut self, qh: &QueueHandle<Self>, route: Route) -> bool {
        if route == Route::Hide {
            self.hide();
            return true;
        }
        self.reveal.clear();
        self.panel_close.cancel();
        if route == Route::Power {
            // A key hold starts a fresh decision; a token left by Settings
            // must never appear as a ready-to-confirm hardware action.
            self.service_view.confirmation = None;
            self.service_view.message = None;
            self.renderer.set_services(self.service_view.clone());
        }
        if route != Route::Settings && self.wifi_view.page != WifiPage::Closed {
            if let Some((id, WifiKind::Connect | WifiKind::ConnectSaved)) = self.wifi_view.pending {
                self.wifi_worker.cancel(id);
            }
            self.wifi_view.close();
            self.sync_wifi_keyboard();
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
            // A reopened drawer starts with a fresh search, matching
            // Android's own launchers -- not the previous open's query.
            self.drawer_search = DrawerSearch::default();
            self.sync_drawer_search();
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

    fn reveal_message(&mut self, qh: &QueueHandle<Self>, mut message: RevealMessage) {
        let now = self.started.elapsed().as_millis() as u64;
        if message.dismiss {
            let valid = self.layer.is_some() && match message.surface {
                Route::Shade => matches!(self.route, Route::Shade | Route::Settings),
                Route::Drawer => self.route == Route::Drawer,
                _ => false,
            };
            if !valid { return; }
            message.surface = self.route;
            if message.phase == Phase::Begin {
                self.reveal.clear(); self.panel_close.cancel();
                self.panel_start = None; self.panel_swipe_owned = false;
            } else if message.phase == Phase::Update {
                // The compositor sends displacement / output height. Match
                // actual content-sized sheet travel without amplification.
                message.progress = ((1.0 - (1.0 - f64::from(message.progress) / 1000.0)
                    * self.height as f64 / self.panel_travel().max(1.0)).clamp(0.0,1.0) * 1000.0).round() as u16;
            }
        }
        if !self.reveal.apply(message, now, self.reduced_motion) {
            self.log("reveal-rejected");
            return;
        }
        if message.surface != Route::Settings && self.wifi_view.page != WifiPage::Closed {
            if let Some((id, WifiKind::Connect | WifiKind::ConnectSaved)) = self.wifi_view.pending {
                self.wifi_worker.cancel(id);
            }
            self.wifi_view.close();
            self.sync_wifi_keyboard();
            self.service_view.wifi = None;
            self.renderer.set_services(self.service_view.clone());
        }
        if self.route != message.surface {
            self.panel_start = None;
            self.panel_swipe_owned = false;
            self.panel_close.cancel();
            self.notification_coast.stop();
            self.notification_settle = None;
            self.notification_wait = None;
            self.service_view.notification_swipe = None;
            self.renderer.set_services(self.service_view.clone());
        }
        if self.route != message.surface {
            self.drawer_search = DrawerSearch::default();
            self.sync_drawer_search();
        }
        self.route = message.surface;
        if message.phase == Phase::Begin && !message.dismiss {
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
        if let Some(splash) = self.splash.as_ref() {
            // The splash's own hit-test, entirely independent of whatever
            // `self.route`'s ordinary input rect was a moment ago: nothing
            // is tappable while `Pending` (there is nothing to press), and
            // the whole screen is one big dismiss target once it becomes
            // recoverable (`TimedOut`/`Failed`) -- see `dismiss_splash`.
            // `Route::Hide` is a placeholder in this key; it is never
            // compared against a real `Route::Hide` input-region computation
            // because that path always has `self.layer.is_none()` by then
            // (`hide()` clears `input_region_key` in the same call that
            // drops the layer).
            let dismissable = matches!(splash.status, SplashStatus::TimedOut | SplashStatus::Failed);
            let key = (Route::Hide, self.width, self.height, dismissable);
            if self.input_region_key == Some(key) {
                return;
            }
            let Some(layer) = self.layer.as_ref() else {
                return;
            };
            let Ok(region) = Region::new(&self.compositor) else {
                return;
            };
            if dismissable {
                region.add(0, 0, self.width as i32, self.height as i32);
            }
            layer
                .wl_surface()
                .set_input_region(Some(region.wl_region()));
            self.input_ready = dismissable;
            self.input_region_key = Some(key);
            return;
        }
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

    /// Everything `hide()` resets besides actually unmapping the layer --
    /// split out so `start_splash` can clear all of this same interactive
    /// state (a drawer tap's nav/gesture/panel-close tracking becomes
    /// meaningless the instant the splash takes over) while keeping an
    /// already-mapped layer alive, which is what avoids ever uncovering
    /// the previously active app between the drawer and the splash.
    fn reset_overlay_interaction(&mut self) {
        self.drawer_search.unfocus();
        self.sync_drawer_search();
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
        self.sync_wifi_keyboard();
        self.service_view.wifi = None;
        self.renderer.set_services(self.service_view.clone());
        self.theme_view = ThemeView::default();
        self.renderer.set_theme_view(self.theme_view.clone());
        self.nav = DrawerNavigation::default();
        self.renderer.set_drawer_pressed(None);
        self.reveal.clear();
        self.panel_close.cancel();
        self.panel_close_candidate = false;
        self.panel_close_sample = None;
        self.panel_close_velocity = 0.0;
    }

    /// Tells the current splash's background watcher thread to stop
    /// polling -- cooperative, not a kill; see `splash_watch_stop`'s own
    /// doc. Idempotent (a `None` is simply a no-op), and safe to call even
    /// when no splash is active at all.
    fn stop_splash_watch(&mut self) {
        if let Some(stop) = self.splash_watch_stop.take() {
            stop.store(true, Ordering::Relaxed);
        }
    }

    /// The launched app's window actually mapped: end the splash and unmap
    /// this overlay so the now-focused app shows, uncontested. Unlike
    /// `dismiss_splash` this never reopens the drawer -- the app itself is
    /// what should be visible now, not the launcher that started it. Also
    /// the path for `LaunchOutcome::Focused` (an already-running app):
    /// there was never a window to wait for in the first place, so this
    /// runs the instant that outcome is known, which is what keeps an
    /// already-running app's splash "very brief" rather than waiting for
    /// its own timeout.
    fn splash_matched(&mut self) {
        self.launching = false;
        self.hide();
    }

    /// A user's tap dismissing a `TimedOut`/`Failed` splash, or that
    /// splash's own automatic dismissal (`Failed` only -- see
    /// `should_auto_dismiss_failed`). Returns to the drawer if this launch
    /// started there (matching this feature's predecessor behavior of
    /// reopening a dismissed drawer on failure/timeout), or simply unmaps
    /// back to whatever was already showing underneath (Home) otherwise.
    fn dismiss_splash(&mut self, qh: &QueueHandle<Self>) {
        self.stop_splash_watch();
        self.splash = None;
        let was_drawer_launch = self.launching;
        self.launching = false;
        if was_drawer_launch {
            self.show(qh, Route::Drawer);
        } else {
            self.hide();
        }
    }

    fn hide(&mut self) {
        self.reset_overlay_interaction();
        self.stop_splash_watch();
        self.splash = None;
        self.layer.take();
        self.configured = false;
        self.frame_pending = false;
        self.dirty = false;
        self.buffers.clear();
        self.input_ready = false;
        self.input_region_key = None;
        self.log("unmap");
    }

    fn trace_picker_input(&mut self, kind: &'static str, time_ms: u32, id: i32) {
        if runtime_trace::active() && self.coalesce_theme_motion() {
            self.trace_input += 1;
            runtime_trace::event(kind, [self.trace_input, u64::from(time_ms), id as u64, 0, 0, 0]);
        }
    }

    fn draw(&mut self, qh: &QueueHandle<Self>) -> bool {
        if !redraw_entry_ready(self.appearance_pending, self.configured, self.layer.is_some()) {
            return false;
        }
        let Some(size) = frame_bytes(self.width, self.height) else {
            self.log("invalid-geometry");
            return false;
        };
        let tracing = runtime_trace::active();
        if tracing {
            self.trace_frame += 1;
            runtime_trace::event("draw_begin", [self.trace_frame, self.trace_input,
                self.width as u64, self.height as u64, self.renderer.rebuild_count(),
                u64::from(self.theme_carousel.is_animating()) | (u64::from(self.background_carousel.is_animating()) << 1)]);
        }
        let _draw_profile = runtime_trace::Span::new("overlay_draw");
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
        if self.drawer_home_drag.is_some() {
            // Task 1's live drag: for the first ~200ms, animate the
            // drawer's own last-rendered frame sliding down and fading out
            // (`RendererCache::draw_drawer_reveal`); once that finishes,
            // paint nothing but the Cancel band, so Home's own
            // `Layer::Bottom` surface (already painting the lifted icon and
            // drop-target highlight) shows through everywhere else -- see
            // `RendererCache::draw_drawer_drag`'s own doc.
            let mut reveal_expired = true;
            if let Some(reveal) = self.drawer_drag_reveal.as_ref() {
                let progress = (reveal.started.elapsed().as_millis() as f64 / DRAWER_DRAG_REVEAL_MS as f64).clamp(0.0, 1.0);
                if progress < 1.0 {
                    reveal_expired = false;
                    if let Err(error) = self.renderer.draw_drawer_reveal(canvas, self.width, self.height, &reveal.snapshot, progress) {
                        self.log(&format!("home-drag-reveal-render-failed {error}"));
                        return false;
                    }
                }
            }
            if reveal_expired {
                self.drawer_drag_reveal = None;
                if let Err(error) = self.renderer.draw_drawer_drag(canvas, self.width, self.height) {
                    self.log(&format!("home-drag-render-failed {error}"));
                    return false;
                }
            }
        } else if let Some(splash) = self.splash.clone() {
            // No slide/reveal progress at all: the splash is always
            // full-screen from its very first frame (see `start_splash`'s
            // own doc on why the backdrop is opaque immediately), so this
            // skips the panel-close/reveal shift entirely rather than
            // asking it to represent a state it was never designed for.
            let alpha = fade_alpha(splash.started, Instant::now());
            if let Err(error) = self.renderer.draw_splash(
                canvas,
                SplashParams {
                    width: self.width,
                    height: self.height,
                    name: &splash.name,
                    icon: splash.icon.as_deref(),
                    status: splash.status,
                    icon_alpha: alpha,
                },
            ) {
                self.log(&format!("splash-render-failed {error}"));
                return false;
            }
        } else {
            // A close drag (live or settling) is entirely client-side and
            // takes priority over the compositor-driven open reveal below --
            // the two can never be active together in practice (a close drag
            // only ever begins once a route is fully open and `input_ready`,
            // by which point `self.reveal` has already gone quiet), but this
            // ordering is what makes that true rather than assumed.
            let progress = if self.panel_close.active() {
                self.panel_close.progress()
            } else if self.reveal.surface().is_some() {
                self.reveal.progress()
            } else {
                1.0
            };
            // `K230_DRAWER_FRAME`: a cheap, always-on timing log for the
            // Drawer's own frame-render cost (`docs/design/
            // app-drawer-review.md`'s performance section) -- the coordinator
            // can grep the board's journal for this without a
            // `K230_TRACE_PATH` capture session. Scoped to the Drawer route
            // only and rate-limited (`DRAWER_FRAME_LOG_INTERVAL`), never
            // more than a plain `Instant` sample plus an occasional
            // `eprintln!` -- no allocation on the frames it does not log.
            let drawer_timing = self.route == Route::Drawer;
            let render_started = drawer_timing.then(Instant::now);
            let render_result = self.renderer.draw_with_hud(
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
                &self.hud,
                self.started.elapsed().as_millis() as u64,
            );
            if let Some(started) = render_started {
                let now = Instant::now();
                if self
                    .drawer_frame_log_at
                    .is_none_or(|last| now.duration_since(last) >= DRAWER_FRAME_LOG_INTERVAL)
                {
                    self.drawer_frame_log_at = Some(now);
                    let elapsed_ms = now.duration_since(started).as_secs_f64() * 1000.0;
                    self.log(&format!(
                        "K230_DRAWER_FRAME ms={elapsed_ms:.2} apps={} scroll={:.0}",
                        self.apps.len(),
                        self.nav.scroll
                    ));
                }
            }
            if let Err(error) = render_result {
                self.log(&format!("render-failed {error}"));
                return false;
            }
        }
        if tracing {
            runtime_trace::event("draw_end", [self.trace_frame, self.trace_input,
                self.renderer.rebuild_count(), 0, 0, 0]);
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
        if tracing && self.trace_feedback.len() < 128 {
            if let Some(presentation) = &self.presentation {
                match presentation.feedback(layer.wl_surface(), qh) {
                    Ok(feedback) => self.trace_feedback.push((feedback, self.trace_frame)),
                    Err(_) => runtime_trace::event("feedback_unavailable", [self.trace_frame, 0, 0, 0, 0, 0]),
                }
            }
        } else if tracing {
            runtime_trace::event("feedback_overflow", [self.trace_frame, 0, 0, 0, 0, 0]);
        }
        layer.commit();
        if tracing { runtime_trace::event("commit", [self.trace_frame, self.trace_input, 0, 0, 0, 0]); }
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
        if self
            .home_surface
            .layer
            .as_ref()
            .is_some_and(|l| l.wl_surface() == surface)
        {
            self.home_surface.frame_pending = false;
            if self.home_surface.dirty {
                self.draw_home(qh);
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
        runtime_trace::event("frame_callback", [0; 6]);
        if self.dirty && !self.appearance_pending && !self.coalesce_theme_motion() {
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


impl PresentationTimeHandler for ShellClient {
    fn presentation_time_state(&mut self) -> &mut PresentationTimeState {
        self.presentation.as_mut().expect("presentation was bound for trace")
    }
    fn presented(&mut self, _: &Connection, _: &QueueHandle<Self>,
        feedback: &wp_presentation_feedback::WpPresentationFeedback,
        _: &wl_surface::WlSurface, _: Vec<wl_output::WlOutput>, time: PresentTime,
        refresh: u32, seq: u64, flags: WEnum<wp_presentation_feedback::Kind>) {
        if let Some(index) = self.trace_feedback.iter().position(|(f, _)| f == feedback) {
            let (_, frame) = self.trace_feedback.remove(index);
            let flags = match flags { WEnum::Value(v) => v.bits(), WEnum::Unknown(v) => v };
            runtime_trace::event("presented", [frame,
                time.tv_sec.saturating_mul(1_000_000_000).saturating_add(time.tv_nsec as u64),
                refresh as u64, seq, flags as u64, time.clk_id as u64]);
        }
    }
    fn discarded(&mut self, _: &Connection, _: &QueueHandle<Self>,
        feedback: &wp_presentation_feedback::WpPresentationFeedback, _: &wl_surface::WlSurface) {
        if let Some(index) = self.trace_feedback.iter().position(|(f, _)| f == feedback) {
            let (_, frame) = self.trace_feedback.remove(index);
            runtime_trace::event("discarded", [frame, 0, 0, 0, 0, 0]);
        }
    }
}
delegate_presentation_time!(ShellClient);

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
        if self
            .home_surface
            .layer
            .as_ref()
            .is_some_and(|home| home.wl_surface() == layer.wl_surface())
        {
            // Home is meant to be always mapped; unlike the wallpaper, a
            // closed Home surface is remapped immediately on the next
            // `ensure_home` call rather than after a delay, since nothing
            // else shows a person their pinned icons in the meantime.
            self.home_surface = HomeSurface {
                recreate_after: Some(Instant::now() + Duration::from_millis(500)),
                ..HomeSurface::default()
            };
            self.log("home-closed");
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
            if configure_size(&mut geometry, width, height).is_none()
                || !(configure_preserves_aspect(width, height) || self.is_whole_output(width, height))
            {
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
        if self
            .home_surface
            .layer
            .as_ref()
            .is_some_and(|home| home.wl_surface() == layer.wl_surface())
        {
            let mut geometry = (self.home_surface.width, self.home_surface.height);
            if configure_size(&mut geometry, width, height).is_none()
                || !(configure_preserves_aspect(width, height) || self.is_whole_output(width, height))
            {
                self.log("home-configure-rejected");
                return;
            }
            let page_width_changed = (self.home_surface.width, self.home_surface.height) != geometry;
            (self.home_surface.width, self.home_surface.height) = geometry;
            self.home_surface.configured = true;
            self.home_surface.dirty = true;
            if page_width_changed {
                self.home.pager.set_page_width(f64::from(geometry.0));
            }
            self.log(&format!("home-configure {width}x{height}"));
            self.draw_home(qh);
            return;
        }
        let mut geometry = (self.width, self.height);
        if configure_size(&mut geometry, width, height).is_none()
            || !(configure_preserves_aspect(width, height) || self.is_whole_output(width, height))
        {
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
        if cap == Capability::Pointer && self.pointer_device.is_none() {
            self.pointer_device = self.seat_state.get_pointer(qh, &seat).ok();
            self.log("pointer-capability");
        }
        if cap == Capability::Keyboard && self.keyboard_device.is_none() {
            self.keyboard_device = self.seat_state.get_keyboard(qh, &seat, None).ok();
            self.log("keyboard-capability");
        }
    }
    fn remove_capability(
        &mut self,
        _: &Connection,
        qh: &QueueHandle<Self>,
        _: wl_seat::WlSeat,
        cap: Capability,
    ) {
        if cap == Capability::Touch {
            if self.pointer_contact.cancel().is_some() {
                self.contact_cancel(qh);
            }
            self.touch_device.take();
            self.touch.cancel();
            self.panel_start = None;
            self.panel_scrolled = false;
            self.panel_swipe_owned = false;
            self.panel_close.cancel();
            self.panel_close_candidate = false;
            self.panel_close_sample = None;
            self.panel_close_velocity = 0.0;
            self.notification_coast.stop();
            self.notification_settle = None;
            self.notification_wait = None;
            self.service_view.notification_swipe = None;
            self.renderer.set_services(self.service_view.clone());
            self.dirty = true;
            self.log("touch-capability-lost");
        }
        if cap == Capability::Pointer {
            if self.pointer_contact.cancel().is_some() {
                self.contact_cancel(qh);
            }
            if let Some(pointer) = self.pointer_device.take() {
                pointer.release();
            }
            self.log("pointer-capability-lost");
        }
        if cap == Capability::Keyboard {
            if let Some(keyboard) = self.keyboard_device.take() {
                keyboard.release();
            }
            self.forget_wifi_keyboard();
            self.forget_home_keyboard();
            self.forget_drawer_keyboard();
            self.log("keyboard-capability-lost");
        }
    }
    fn remove_seat(&mut self, _: &Connection, qh: &QueueHandle<Self>, _: wl_seat::WlSeat) {
        if self.pointer_contact.cancel().is_some() {
            self.contact_cancel(qh);
        }
        if let Some(pointer) = self.pointer_device.take() {
            pointer.release();
        }
        self.touch_device.take();
        self.touch.cancel();
        self.panel_start = None;
        self.panel_scrolled = false;
        self.panel_swipe_owned = false;
        self.panel_close.cancel();
        self.panel_close_candidate = false;
        self.panel_close_sample = None;
        self.panel_close_velocity = 0.0;
        self.notification_coast.stop();
        self.notification_settle = None;
        self.notification_wait = None;
        self.service_view.notification_swipe = None;
        self.renderer.set_services(self.service_view.clone());
        self.dirty = true;
        if let Some(keyboard) = self.keyboard_device.take() {
            keyboard.release();
        }
        self.forget_wifi_keyboard();
        self.forget_home_keyboard();
        self.forget_drawer_keyboard();
    }
}

impl ShellClient {
    fn contact_down(
        &mut self,
        qh: &QueueHandle<Self>,
        time_ms: u32,
        surface: wl_surface::WlSurface,
        id: i32,
        pos: (f64, f64),
    ) {
        self.trace_picker_input("input_down", time_ms, id);
        if id == TRACKPAD_PAN_ID { self.trackpad_pan_start = Some(pos); }
        if self
            .layer
            .as_ref()
            .is_some_and(|l| l.wl_surface() == &surface)
        {
            if self.touch.down(id, pos) {
                if self.wifi_view.page == WifiPage::Closed {
                    self.log(&format!("touch-down {id} {:.1} {:.1}", pos.0, pos.1));
                }
                if self.hud_touch_down(id, pos) {
                    // Handled entirely -- the HUD floats above whatever
                    // route is showing (task: "a vertical pill on the
                    // right edge") and never falls through to the
                    // route-specific dispatch below.
                } else if self.splash.is_some() {
                    // Nothing to track on `down` -- a dismissable splash
                    // (the only state that ever reaches this branch at all;
                    // see `input_region`'s own doc) only acts on `up`.
                } else if self.route == Route::Drawer && self.input_ready {
                    // Captured *before* `nav.down` below, which
                    // unconditionally zeroes any in-flight fling velocity
                    // the instant a new touch lands (`DrawerNavigation::
                    // down`'s own "touching a coasting list stops it
                    // immediately") -- reading `coasting()` after that call
                    // would always see `false` and could never gate
                    // anything. Required behaviour: a downward drag may
                    // only close the Drawer if the grid was already at
                    // rest at its own top when the finger went down, and a
                    // fling still decelerating toward the top does not
                    // count as "at rest" even if `scroll` already reads
                    // near zero.
                    let was_coasting = self.nav.coasting();
                    self.nav.down(id, pos, time_ms);
                    if self.renderer.set_drawer_pressed(self.nav.pressed(
                        self.width,
                        self.drawer_search.viewport_height(self.height),
                        self.drawer_filtered_apps().len(),
                    )) {
                        self.dirty = true;
                    }
                    // Shares `panel_start`/`panel_close*` with Shade/Settings
                    // below rather than a second set of fields -- only one
                    // route is ever open at a time. `nav.down` above still
                    // always runs too, so an eligible-zone touch that never
                    // engages still resolves as an ordinary tap/long-press
                    // at release (`nav.up` only needs `contact.start`/the
                    // final release point, never the intermediate motion
                    // this close drag may intercept -- see `motion`'s own
                    // doc on this branch).
                    self.panel_start = Some((id, pos));
                    self.panel_close_candidate = !self.panel_close.active()
                        && !was_coasting
                        && drawer_close_drag_zone(pos.1, self.height, self.nav.scroll);
                    self.panel_close_sample = Some((pos.1, time_ms));
                    self.panel_close_velocity = 0.0;
                } else if matches!(self.route, Route::Shade | Route::Settings | Route::Power)
                    && self.input_ready
                {
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
                    // Only a fresh touch, starting somewhere `close_drag_
                    // zone` allows, may ever become a close drag; nothing
                    // later in this same gesture can promote it (so it can
                    // never hijack a scroll/swipe/control started
                    // elsewhere), and none of this races an already-
                    // animating close from an earlier gesture.
                    self.panel_close_candidate = !self.panel_close.active()
                        && (close_drag_zone(self.route, pos.1, self.panel_travel())
                            || (self.route == Route::Shade
                                && shade_panel_close_zone(pos.1, self.height, &self.service_view)));
                    self.panel_close_sample = Some((pos.1, time_ms));
                    self.panel_close_velocity = 0.0;
                    // Brightness slider (task: "brightness should be a
                    // slider"): a touch landing on the shared slider band
                    // is armed here and owns the rest of the gesture --
                    // `panel_close_candidate` above already excludes this
                    // band (`slider_band`, folded into `shade_panel_
                    // close_zone`), so this never races the close drag.
                    // On Settings, `slider_band`'s row-1 range can
                    // coincide with a Wi-Fi or Theme sub-page's own rows
                    // (both still Route::Settings) -- only arm on the
                    // plain capabilities page itself, exactly the same
                    // gate `panel_intent`'s own Settings arm already
                    // needs (`theme_view.page == ThemePage::Controls`).
                    let on_settings_capabilities_page = self.route != Route::Settings
                        || (self.wifi_view.page == WifiPage::Closed
                            && self.theme_view.page == ThemePage::Controls);
                    self.brightness_drag = if on_settings_capabilities_page
                        && slider_band(self.route, pos.1, &self.service_view)
                    {
                        let mut drag = slider::Drag::start(id, f64::from(self.width));
                        let value = drag.value_at(pos.0);
                        self.apply_brightness_preview(value);
                        if drag.should_write(time_ms) {
                            self.submit_service(ServiceRequest::BrightnessLive(value));
                        }
                        Some(drag)
                    } else {
                        None
                    };
                    // Volume slider: same arming shape as brightness's own,
                    // just below it (`volume_slider_band`), floor `0`
                    // (`start_with_floor`) so a drag can reach true
                    // silence, and its live writes go to the persistent
                    // `pw-cli` writer, not `submit_service` -- there is no
                    // PipeWire-backed request in `ServiceRequest` at all,
                    // by design (`service_view.audio`/`pipewire_ipc.rs`
                    // already own this data, off the k230-settings path).
                    // Settings' own device-picker entry point (design.md's
                    // "one picker, two entry points"): the "tap to change
                    // output" detail line, checked first so it can never
                    // be shadowed by the drag/icon zones sharing the same
                    // row's Y band.
                    self.output_picker_touch = if on_settings_capabilities_page
                        && settings_output_picker_hit(pos.1, self.route, &self.service_view)
                    {
                        Some(id)
                    } else {
                        None
                    };
                    let volume_row_touched = self.output_picker_touch.is_none()
                        && on_settings_capabilities_page
                        && volume_slider_band(self.route, pos.1, &self.service_view);
                    // The speaker glyph shares the volume row's own Y band
                    // but must never arm a drag (`volume_icon_tap_zone` is
                    // left of `slider::track_bounds`'s own `left`, i.e.
                    // outside the track a drag would otherwise map to its
                    // floor) -- checked first so the drag arm below only
                    // ever sees a touch that actually landed on the track.
                    self.volume_icon_touch =
                        if volume_row_touched && volume_icon_tap_zone(pos.0, f64::from(self.width)) {
                            Some(id)
                        } else {
                            None
                        };
                    self.volume_drag = if volume_row_touched && self.volume_icon_touch.is_none() {
                        let mut drag = slider::Drag::start_with_floor(id, f64::from(self.width), 0);
                        let value = drag.value_at(pos.0);
                        self.apply_volume_preview(value);
                        if drag.should_write(time_ms) {
                            self.submit_volume_live(value);
                        }
                        Some(drag)
                    } else {
                        None
                    };
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
                        // Task: tap-to-apply (2026-09-25) put both
                        // carousels on the one List page at once; each is
                        // armed independently by its own band, rather than
                        // by which page is showing.
                        if self.theme_view.page == ThemePage::List {
                            if (THEME_CAROUSEL_TOP..THEME_CAROUSEL_TOP + THEME_GEOMETRY.expanded_h)
                                .contains(&pos.1)
                            {
                                self.theme_carousel.down(id, pos, time_ms);
                                self.sync_theme_pressed();
                            } else if (BACKGROUND_CAROUSEL_TOP
                                ..BACKGROUND_CAROUSEL_TOP + BACKGROUND_GEOMETRY.expanded_h)
                                .contains(&pos.1)
                            {
                                self.background_carousel.down(id, pos, time_ms);
                                self.sync_background_pressed();
                            }
                        }
                    }
                }
            } else {
                self.log("touch-second-cancel");
                self.brightness_drag = None;
                self.volume_drag = None;
                self.volume_icon_touch = None;
                self.output_picker_touch = None;
                if self.drawer_home_drag.take().is_some() {
                    self.drawer_drag_reveal = None;
                    self.home.cancel_external_drag();
                    self.home_mark_dirty();
                }
                self.nav.cancel();
                if self.renderer.set_drawer_pressed(None) {
                    self.dirty = true;
                }
                self.panel_start = None;
                self.panel_scrolled = false;
                self.panel_swipe_owned = false;
                let now = self.started.elapsed().as_millis() as u64;
                self.panel_close.abandon_to_open(now, self.reduced_motion);
                self.panel_close_candidate = false;
                self.panel_close_sample = None;
                self.panel_close_velocity = 0.0;
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
        } else if self
            .home_surface
            .layer
            .as_ref()
            .is_some_and(|l| l.wl_surface() == &surface)
            && self.home_surface.configured
        {
            self.home_touch_id = Some(id);
            self.home_last_point = pos;
            self.home.down(id, pos, time_ms, self.home_surface.width, self.home_surface.height);
            // A touch-down on a filled icon shows an immediate pressed
            // highlight (the same "feedback within one frame" convention
            // `theme_carousel.rs`'s own `pressed()` doc describes), so this
            // always redraws rather than trying to detect the highlight
            // change first.
            self.home_mark_dirty();
            self.draw_home(qh);
        }
    }
    fn contact_up(
        &mut self,
        qh: &QueueHandle<Self>,
        time_ms: u32,
        id: i32,
    ) {
        self.trace_picker_input("input_up", time_ms, id);
        if id == TRACKPAD_PAN_ID {
            if let Some(start) = self.trackpad_pan_start.take() {
                let point = if self.home_touch_id == Some(id) { self.home_last_point } else { self.touch.position };
                if (point.0 - start.0).hypot(point.1 - start.1) <= 22.0 {
                    self.contact_cancel(qh);
                    return;
                }
            }
        }
        self.hud.end_drag(id);
        if self.home_touch_id == Some(id) {
            self.home_touch_id = None;
            if let Some(action) = self.home.up(
                id,
                self.home_last_point,
                time_ms,
                self.home_surface.width,
                self.home_surface.height,
            ) {
                self.apply_home_action(qh, action);
            }
            self.sync_home_keyboard();
            self.home_mark_dirty();
            self.draw_home(qh);
            return;
        }
        let point = self.touch.position;
        if self.touch.up(id) {
            if self.wifi_view.page == WifiPage::Closed {
                self.log(&format!("touch-up {id}"));
            }
            if self.splash.is_some() {
                // Only reachable at all when `input_region` made the
                // splash dismissable (`TimedOut`/`Failed` -- see its own
                // doc); a `Pending` splash's empty input region means the
                // compositor never delivers a touch here in the first
                // place.
                self.dismiss_splash(qh);
            } else if self.route == Route::Drawer && self.input_ready {
                if self.drawer_home_drag == Some(id) {
                    self.end_drawer_home_drag(qh, point);
                    return;
                }
                if self.renderer.set_drawer_pressed(None) {
                    self.dirty = true;
                }
                let start = self
                    .panel_start
                    .take()
                    .filter(|(start_id, _)| *start_id == id);
                let engaged_close = start.is_some() && self.panel_close.tracking();
                self.panel_close_candidate = false;
                if engaged_close {
                    // Live close-drag release: settle to whichever endpoint
                    // `close_drag_release_target` picks from wherever the
                    // finger left it -- `nav.up` is not consulted at all,
                    // matching Shade/Settings (a touch this deep into a
                    // close drag was never a tap/scroll/long-press
                    // candidate any more).
                    let velocity = self.panel_close_velocity;
                    let target = close_drag_release_target(self.panel_close.progress(), velocity);
                    let now = self.started.elapsed().as_millis() as u64;
                    self.panel_close
                        .release(id, target, now, self.reduced_motion);
                    self.panel_close_sample = None;
                    self.panel_close_velocity = 0.0;
                    self.dirty = true;
                } else if start.is_some_and(|(_, start_pos)| {
                    // The visible handle also works as a tap/click dismiss
                    // target; search immediately below keeps its own action.
                    let (_, handle_y, _, _) = navigation::handle_rect(self.width, self.height);
                    (handle_y - 10.0..handle_y + 10.0).contains(&start_pos.1)
                        && (point.0 - start_pos.0).abs() <= 12.0
                        && (point.1 - start_pos.1).abs() <= 12.0
                }) {
                    self.nav.cancel();
                    self.begin_animated_close();
                } else if start.is_some_and(|(_, start_pos)| {
                    navigation::search_field_hit(start_pos, self.width, self.height)
                        && (point.0 - start_pos.0).abs() <= 12.0
                        && (point.1 - start_pos.1).abs() <= 12.0
                }) {
                    // A plain tap (small total movement) that started and
                    // ended on the search field opens it -- the field
                    // itself is never `nav`'s (it hit-tests only the grid),
                    // so a released drag/close-drag candidate that landed
                    // here otherwise resolves as nothing at all.
                    let already_active = self.drawer_keyboard_active;
                    self.nav.cancel();
                    self.drawer_search.focus();
                    self.sync_drawer_search();
                    // A tap also reopens a keyboard hidden with its grip gesture.
                    if already_active {
                        if let Some(path) = &self.keyboard_signal_path {
                            let _ = std::process::Command::new(path).arg("show").spawn();
                        }
                    }
                } else {
                    match self.nav.up(
                        id,
                        point,
                        time_ms,
                        self.width,
                        self.drawer_search.viewport_height(self.height),
                        self.drawer_filtered_apps().len(),
                    ) {
                        Some(DrawerAction::Launch(index)) => self.launch_drawer_app(qh, index),
                        // `nav`'s own release-only "dy > 110 && scroll <=
                        // 0.5" check is now just a backstop for whatever
                        // reason the live drag above never engaged (see
                        // its own doc); animate it the same way a released
                        // close drag settles, instead of vanishing.
                        Some(DrawerAction::Close) => self.begin_animated_close(),
                        None => {}
                    }
                }
            } else if self.input_ready {
                if let Some((start_id, start)) = self.panel_start.take() {
                    if start_id == id {
                        let swipe = self.service_view.notification_swipe.clone();
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
                        } else if self.panel_close.tracking() {
                            // Live close-drag release: settle to whichever
                            // endpoint `close_drag_release_target` picks
                            // (dismiss threshold or a decisive upward
                            // flick) from wherever the finger left it --
                            // never a jump, and never the old release-only
                            // heuristics this replaces.
                            let velocity = self.panel_close_velocity;
                            let target =
                                close_drag_release_target(self.panel_close.progress(), velocity);
                            let now = self.started.elapsed().as_millis() as u64;
                            self.panel_close
                                .release(start_id, target, now, self.reduced_motion);
                            self.panel_close_sample = None;
                            self.panel_close_velocity = 0.0;
                            self.dirty = true;
                        } else if matches!(&self.brightness_drag, Some(drag) if drag.matches(start_id))
                        {
                            // Release: always sends the authoritative,
                            // verified `Brightness` request regardless of
                            // the live-write throttle (task: "always
                            // write the final value on release").
                            let drag = self
                                .brightness_drag
                                .take()
                                .expect("checked by this branch's own guard");
                            let value = drag.value_at(point.0);
                            self.apply_brightness_preview(value);
                            self.submit_service(ServiceRequest::Brightness(value));
                        } else if matches!(&self.volume_drag, Some(drag) if drag.matches(start_id))
                        {
                            // Release: always commits the authoritative
                            // `wpctl` write regardless of the live-write
                            // throttle, mirroring brightness's own "always
                            // write the final value on release" -- but via
                            // `wpctl`, not `submit_service`, since there is
                            // no PipeWire-backed `ServiceRequest` (`design.md`:
                            // rare, human-paced commits use `wpctl`; only
                            // the live-drag path uses the persistent
                            // `pw-cli` writer).
                            let drag = self
                                .volume_drag
                                .take()
                                .expect("checked by this branch's own guard");
                            let value = drag.value_at(point.0);
                            self.apply_volume_preview(value);
                            self.commit_volume(value, self.volume_state.is_muted());
                        } else if self.volume_icon_touch == Some(start_id) {
                            // The speaker glyph never armed a drag (see the
                            // `down` arm's own doc); any release of this
                            // same touch, wherever the finger ends up, is
                            // its tap -- the same "any release counts"
                            // leniency every other icon-sized hit zone in
                            // this shell already has.
                            self.volume_icon_touch = None;
                            self.toggle_volume_mute();
                        } else if self.output_picker_touch == Some(start_id) {
                            // Settings' "tap to change output" line: opens
                            // the same expanded HUD panel/picker the "..."
                            // affordance does, already expanded rather
                            // than making a second tap discover that.
                            self.output_picker_touch = None;
                            let now = self.started.elapsed().as_millis() as u64;
                            if !self.hud.is_expanded() {
                                self.hud.toggle_expand(now);
                            } else {
                                self.hud.show(now);
                            }
                            self.dirty = true;
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
                                // Task: tap-to-apply (2026-09-25): both
                                // carousels live on the one List page now.
                                // `Carousel::up` returns `None` for a
                                // touch id it never armed (see its own
                                // doc), so trying the theme carousel
                                // first and falling through to the
                                // background carousel only on `None`
                                // correctly finds whichever one (if
                                // either) actually owns this touch,
                                // regardless of which is visually
                                // "current".
                                let (carousel_outcome, from_background) =
                                    if self.theme_view.page == ThemePage::List {
                                        let theme_count = self
                                            .theme_view
                                            .list
                                            .as_ref()
                                            .map_or(0, |list| list.themes.len());
                                        let outcome = self.theme_carousel.up(
                                            id,
                                            point,
                                            time_ms,
                                            theme_count,
                                            center_x,
                                            THEME_CAROUSEL_TOP,
                                        );
                                        if outcome.is_some() {
                                            (outcome, false)
                                        } else {
                                            let background_count = self
                                                .theme_view
                                                .preview
                                                .as_ref()
                                                .map_or(0, |preview| preview.backgrounds.len());
                                            let outcome = self.background_carousel.up(
                                                id,
                                                point,
                                                time_ms,
                                                background_count,
                                                center_x,
                                                BACKGROUND_CAROUSEL_TOP,
                                            );
                                            (outcome, true)
                                        }
                                    } else {
                                        (None, false)
                                    };
                                self.sync_theme_pressed();
                                self.sync_background_pressed();
                                match carousel_outcome {
                                    Some(CarouselOutcome::Confirm(index)) => {
                                        let intent = if from_background {
                                            ThemeIntent::Background(index)
                                        } else {
                                            ThemeIntent::Theme(index)
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
                        } else if backdrop_tap(self.route, start, point, self.panel_travel()) {
                            // A tap on the dim backdrop below the sheet closes it, the
                            // same animated way a released close drag does.
                            self.begin_animated_close();
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
    fn contact_motion(
        &mut self,
        qh: &QueueHandle<Self>,
        time_ms: u32,
        id: i32,
        pos: (f64, f64),
    ) {
        self.trace_picker_input("input_motion", time_ms, id);
        if self.home_touch_id == Some(id) {
            self.home_last_point = pos;
            if self.home.motion(id, pos, time_ms, self.home_surface.width, self.home_surface.height) {
                self.home_mark_dirty();
                self.draw_home(qh);
            }
            return;
        }
        if self.hud.drag_owner() == Some(id) {
            // Reposition drag (task: "can be dragged"): the pill's own
            // vertical center follows the finger as a fraction of the
            // panel height, the same normalized-position convention
            // `Hud::drag_to` already stores it in.
            let now = self.started.elapsed().as_millis() as u64;
            let fraction = (pos.1 / f64::from(self.height)).clamp(0.0, 1.0);
            self.hud.drag_to(id, fraction, now);
            self.dirty = true;
            return;
        }
        if self.touch.motion(id, pos) {
            if self.wifi_view.page == WifiPage::Closed {
                self.log(&format!("touch-move {id} {:.1} {:.1}", pos.0, pos.1));
            }
            if self
                .brightness_drag
                .as_ref()
                .is_some_and(|drag| drag.matches(id))
            {
                // Owns this gesture entirely once armed at touch-down
                // (`slider_band`) -- the visible thumb tracks every touch
                // sample; only the backlight write itself is throttled
                // (task: "throttle writes to about 20-30 per second").
                // Taken and put back (rather than `as_mut()`) so the
                // update methods below, which need `&mut self` in full,
                // are never called while still borrowing through it.
                if let Some(mut drag) = self.brightness_drag.take() {
                    let value = drag.value_at(pos.0);
                    self.apply_brightness_preview(value);
                    if drag.should_write(time_ms) {
                        self.submit_service(ServiceRequest::BrightnessLive(value));
                    }
                    self.brightness_drag = Some(drag);
                }
            } else if self
                .volume_drag
                .as_ref()
                .is_some_and(|drag| drag.matches(id))
            {
                if let Some(mut drag) = self.volume_drag.take() {
                    let value = drag.value_at(pos.0);
                    self.apply_volume_preview(value);
                    if drag.should_write(time_ms) {
                        self.submit_volume_live(value);
                    }
                    self.volume_drag = Some(drag);
                }
            } else if self.route == Route::Drawer && self.input_ready {
                if self.drawer_home_drag == Some(id) {
                    // Task 1's live drag: this touch is bound to
                    // `self.home`'s external drag, not the drawer's own
                    // scroll/close-drag/search handling -- skip all of that
                    // entirely for as long as this touch is the armed drag.
                    self.home.external_drag_motion(pos, time_ms, self.home_surface.width, self.home_surface.height);
                    self.home_mark_dirty();
                    self.dirty = true; // the drawer surface repaints the lifted icon/Cancel band too
                    self.draw_home(qh);
                    self.draw(qh);
                    return;
                }
                // A close drag only ever *takes over* this touch once it
                // actually engages (`close_drag_engaged`, downward for the
                // Drawer); until then, every motion sample still reaches
                // `nav.motion` below exactly as it would with no close-drag
                // feature at all. This matters here in a way it does not
                // for Shade/Settings: an eligible Drawer close-drag zone
                // can be the scrollable grid itself (when already at its
                // top), and an ordinary "scroll down through the list"
                // drag starts with the same *upward* finger motion whether
                // or not the grid happens to be at its top already -- only
                // once the drag turns out to go the other way (downward,
                // toward closing) does this stop calling `nav.motion` for
                // it.
                let mut engaged_this_sample = false;
                if self.panel_start.is_some_and(|(start_id, _)| start_id == id)
                    && (self.panel_close.tracking() || self.panel_close_candidate)
                {
                    let (_, start) = self
                        .panel_start
                        .expect("checked by this branch's own guard");
                    let dx = pos.0 - start.0;
                    let dy = pos.1 - start.1;
                    if !self.panel_close.tracking() && close_drag_engaged(Route::Drawer, dx, dy) {
                        self.panel_close.begin(id);
                    }
                    if self.panel_close.tracking() {
                        let travel = self.panel_travel();
                        if self
                            .panel_close
                            .update(id, close_drag_progress(Route::Drawer, dy, travel))
                        {
                            self.dirty = true;
                        }
                        if let Some((last_y, last_time)) = self.panel_close_sample {
                            let dt = time_ms.wrapping_sub(last_time);
                            if (1..=120).contains(&dt) {
                                // Drawer closes downward: positive velocity
                                // means downward, toward closing -- the
                                // mirror image of Shade/Settings' upward
                                // convention just below.
                                self.panel_close_velocity =
                                    ((pos.1 - last_y) / f64::from(dt)).clamp(-2.5, 2.5);
                            }
                        }
                        self.panel_close_sample = Some((pos.1, time_ms));
                        engaged_this_sample = true;
                    }
                }
                if !engaged_this_sample {
                    let filtered_count = self.drawer_filtered_apps().len();
                    if self.nav.motion(id, pos, time_ms, self.width, self.drawer_search.viewport_height(self.height), filtered_count) {
                        self.dirty = true;
                    }
                    // Once this sample's ordinary scroll has actually
                    // carried the grid away from its own top, permanently
                    // disqualify the rest of *this* gesture from closing --
                    // never re-armed even if the finger later reverses and
                    // the scroll returns to 0.0. Without this, a candidate
                    // decided once at touch-down (true, because the grid
                    // started at rest at the top) stayed true for the
                    // gesture's entire duration; scrolling down through the
                    // list and then swiping back up within the same held
                    // touch could cross `close_drag_engaged`'s slop
                    // relative to the *original* touch-down point and
                    // engage a close, even though the grid was no longer
                    // anywhere near its top. This is the exact reported
                    // bug ("swipe down to scroll back up closes the
                    // drawer").
                    self.panel_close_candidate = drawer_close_candidate_after_scroll(
                        self.panel_close_candidate,
                        self.nav.scroll,
                    );
                    if self
                        .renderer
                        .set_drawer_pressed(self.nav.pressed(self.width, self.drawer_search.viewport_height(self.height), filtered_count))
                    {
                        self.dirty = true;
                    }
                }
            } else if matches!(self.route, Route::Shade | Route::Settings | Route::Power)
                && self.input_ready
                && self.panel_start.is_some_and(|(start_id, _)| start_id == id)
                && (self.panel_close.tracking() || self.panel_close_candidate)
            {
                // Live close drag: either already engaged (follow the
                // finger 1:1 every frame) or still a slop/direction-lock
                // candidate from an eligible start zone (`close_drag_
                // zone`, checked once at touch-down into `panel_close_
                // candidate`) waiting to engage. Nothing here ever runs
                // for a touch that started on scrollable/interactive
                // content -- that candidate flag is false from the start
                // for those, so control falls through to the ordinary
                // per-route branches below exactly as before.
                let (_, start) = self
                    .panel_start
                    .expect("checked by this branch's own guard");
                let dx = pos.0 - start.0;
                let dy = pos.1 - start.1;
                if !self.panel_close.tracking() && close_drag_engaged(self.route, dx, dy) {
                    self.panel_close.begin(id);
                }
                if self.panel_close.tracking() {
                    let travel = self.panel_travel();
                    if self
                        .panel_close
                        .update(id, close_drag_progress(self.route, dy, travel))
                    {
                        self.dirty = true;
                    }
                    if let Some((last_y, last_time)) = self.panel_close_sample {
                        let dt = time_ms.wrapping_sub(last_time);
                        if (1..=120).contains(&dt) {
                            // Same convention as `panel_scroll_velocity`:
                            // positive = upward = toward closing.
                            self.panel_close_velocity =
                                (-(pos.1 - last_y) / f64::from(dt)).clamp(-2.5, 2.5);
                        }
                    }
                    self.panel_close_sample = Some((pos.1, time_ms));
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
                && self.theme_view.page == ThemePage::List
                && self.wifi_view.page == WifiPage::Closed
            {
                // Task: tap-to-apply (2026-09-25): both carousels are live
                // at once now; `Carousel::motion` is keyed by its own
                // armed `contact.id` internally, so calling it on both
                // unconditionally is safe -- only the one actually
                // holding this touch id (if either) moves.
                let theme_count = self.theme_view.list.as_ref().map_or(0, |l| l.themes.len());
                let background_count = self
                    .theme_view
                    .preview
                    .as_ref()
                    .map_or(0, |p| p.backgrounds.len());
                if self.theme_carousel.motion(id, pos, time_ms, theme_count) {
                    self.theme_view.theme_position = self.theme_carousel.position();
                    self.theme_dirty();
                }
                if self
                    .background_carousel
                    .motion(id, pos, time_ms, background_count)
                {
                    self.theme_view.background_position = self.background_carousel.position();
                    self.theme_dirty();
                }
                self.sync_theme_pressed();
                self.sync_background_pressed();
            }
            if self.dirty && !self.coalesce_theme_motion() {
                self.draw(qh);
            }
        }
    }
    fn contact_cancel(&mut self, qh: &QueueHandle<Self>) {
        self.trackpad_pan_start = None;
        self.pointer_contact.cancel();
        self.touch.cancel();
        self.nav.cancel();
        self.renderer.set_drawer_pressed(None);
        self.panel_start = None;
        self.panel_scrolled = false;
        self.panel_swipe_owned = false;
        let now = self.started.elapsed().as_millis() as u64;
        self.panel_close.abandon_to_open(now, self.reduced_motion);
        self.panel_close_candidate = false;
        self.panel_close_sample = None;
        self.panel_close_velocity = 0.0;
        self.brightness_drag = None;
        self.volume_drag = None;
        if let Some(owner) = self.hud.drag_owner() {
            self.hud.end_drag(owner);
        }
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
        if self.home_touch_id.take().is_some() {
            self.home.cancel();
            self.home_mark_dirty();
            self.draw_home(qh);
        }
    }
}

impl TouchHandler for ShellClient {
    fn down(&mut self, _: &Connection, qh: &QueueHandle<Self>, _: &wl_touch::WlTouch,
            _: u32, time_ms: u32, surface: wl_surface::WlSurface, id: i32, pos: (f64, f64)) {
        if self.pointer_contact.cancel().is_some() {
            self.contact_cancel(qh);
        }
        self.contact_down(qh, time_ms, surface, id, pos);
    }
    fn up(&mut self, _: &Connection, qh: &QueueHandle<Self>, _: &wl_touch::WlTouch,
          _: u32, time_ms: u32, id: i32) {
        self.contact_up(qh, time_ms, id);
    }
    fn motion(&mut self, _: &Connection, qh: &QueueHandle<Self>, _: &wl_touch::WlTouch,
              time_ms: u32, id: i32, pos: (f64, f64)) {
        self.contact_motion(qh, time_ms, id, pos);
    }
    fn shape(&mut self, _: &Connection, _: &QueueHandle<Self>, _: &wl_touch::WlTouch,
             _: i32, _: f64, _: f64) {}
    fn orientation(&mut self, _: &Connection, _: &QueueHandle<Self>, _: &wl_touch::WlTouch,
                   _: i32, _: f64) {}
    fn cancel(&mut self, _: &Connection, qh: &QueueHandle<Self>, _: &wl_touch::WlTouch) {
        self.contact_cancel(qh);
    }
}

impl ShellClient {
    fn log_pointer_state(&self) {
        self.log(&format!("pointer-state route={:?} wifi={:?} themes={:?} drawer_scroll={:.1} notification_scroll={:.1} wifi_scroll={:.1} theme_position={:.3} background_position={:.3}",
            self.route, self.wifi_view.page, self.theme_view.page, self.nav.scroll,
            self.service_view.notification_scroll, self.wifi_view.scroll,
            self.theme_carousel.position(), self.background_carousel.position()));
    }
    fn pointer_scroll(&mut self, qh: &QueueHandle<Self>, event: &PointerEvent,
                      horizontal: smithay_client_toolkit::seat::pointer::AxisScroll,
                      vertical: smithay_client_toolkit::seat::pointer::AxisScroll) {
        if self.touch.id.is_some() || self.home_touch_id.is_some() { return; }
        let dx = pointer_input::axis_delta(horizontal.absolute, horizontal.discrete, horizontal.value120);
        let dy = pointer_input::axis_delta(vertical.absolute, vertical.discrete, vertical.value120);
        if !self.layer.as_ref().is_some_and(|layer| layer.wl_surface() == &event.surface) { return; }
        let mut changed = false;
        match self.route {
            Route::Drawer => {
                let count = self.drawer_filtered_apps().len();
                changed = self.nav.scroll_by(dy, self.width, self.height, count);
            }
            Route::Shade => {
                self.notification_coast.stop();
                let max = self.service_view.notifications.as_ref().map_or(0.0,
                    |snapshot| notification_max_scroll(snapshot.events.len(), self.height));
                let old = self.service_view.notification_scroll;
                self.service_view.notification_scroll = (old + dy).clamp(0.0, max);
                changed = old != self.service_view.notification_scroll;
                if changed { self.renderer.set_services(self.service_view.clone()); }
            }
            Route::Settings if self.wifi_view.page != WifiPage::Closed => {
                self.wifi_view.scroll(dy * 1232.0 / f64::from(self.height.max(1)));
                self.wifi_dirty(); changed = dy != 0.0;
            }
            Route::Settings if self.theme_view.page == ThemePage::List => {
                let delta = if dx != 0.0 { dx } else { dy };
                let settle = horizontal.stop || vertical.stop || horizontal.value120 != 0 ||
                    vertical.value120 != 0 || horizontal.discrete != 0 || vertical.discrete != 0;
                if (THEME_CAROUSEL_TOP..THEME_CAROUSEL_TOP + THEME_GEOMETRY.expanded_h).contains(&event.position.1) {
                    let count = self.theme_view.list.as_ref().map_or(0, |l| l.themes.len());
                    changed = self.theme_carousel.scroll_by(delta, count, settle);
                    self.theme_view.theme_position = self.theme_carousel.position();
                } else if (BACKGROUND_CAROUSEL_TOP..BACKGROUND_CAROUSEL_TOP + BACKGROUND_GEOMETRY.expanded_h).contains(&event.position.1) {
                    let count = self.theme_view.preview.as_ref().map_or(0, |p| p.backgrounds.len());
                    changed = self.background_carousel.scroll_by(delta, count, settle);
                    self.theme_view.background_position = self.background_carousel.position();
                }
                if changed { self.theme_dirty(); }
            }
            _ => {}
        }
        if changed { self.log("pointer-scroll"); self.log_pointer_state(); self.dirty = true; self.draw(qh); }
    }
}

impl PointerHandler for ShellClient {
    fn pointer_frame(&mut self, _: &Connection, qh: &QueueHandle<Self>,
                     _: &wl_pointer::WlPointer, events: &[PointerEvent]) {
        for event in events {
            if let PointerEventKind::Axis { horizontal, vertical, .. } = event.kind {
                self.pointer_scroll(qh, event, horizontal, vertical);
                continue;
            }
            let (update, time_ms) = match event.kind {
                PointerEventKind::Press { button, time, .. } => {
                    // Do not steal a contact already owned by the real touchscreen.
                    if self.touch.id.is_some() || self.home_touch_id.is_some() { continue; }
                    (pointer_input::Update::Press(button), time)
                }
                PointerEventKind::Motion { time } => (pointer_input::Update::Motion, time),
                PointerEventKind::Release { button, time, .. } =>
                    (pointer_input::Update::Release(button), time),
                PointerEventKind::Leave { .. } => (pointer_input::Update::Leave, 0),
                _ => continue,
            };
            match self.pointer_contact.update(event.surface.clone(), update) {
                Some(pointer_input::Action::Down) => {
                    self.log("pointer-down");
                    self.contact_down(qh, time_ms, event.surface.clone(), POINTER_CONTACT_ID, event.position);
                }
                Some(pointer_input::Action::Motion) =>
                    self.contact_motion(qh, time_ms, POINTER_CONTACT_ID, event.position),
                Some(pointer_input::Action::Up) => {
                    // Use the release position, without adding a zero-distance sample
                    // that would erase a drag's measured release velocity.
                    let last = if self.home_touch_id == Some(POINTER_CONTACT_ID) {
                        self.home_last_point
                    } else { self.touch.position };
                    if last != event.position {
                        self.contact_motion(qh, time_ms, POINTER_CONTACT_ID, event.position);
                    }
                    self.log("pointer-up");
                    self.contact_up(qh, time_ms, POINTER_CONTACT_ID);
                    self.log_pointer_state();
                }
                Some(pointer_input::Action::Cancel) => self.contact_cancel(qh),
                None => {},
            }
        }
    }
}

impl KeyboardHandler for ShellClient {
    fn enter(
        &mut self,
        _: &Connection,
        _: &QueueHandle<Self>,
        _: &wl_keyboard::WlKeyboard,
        surface: &wl_surface::WlSurface,
        _: u32,
        _: &[u32],
        _: &[smithay_client_toolkit::seat::keyboard::Keysym],
    ) {
        // Logged (rather than silently assumed) because the compositor
        // grants a layer surface's requested `Exclusive` keyboard focus
        // asynchronously, on its own next event-loop turn -- this is the
        // one authoritative confirmation that the Wi-Fi password field can
        // now actually receive typed keys, and what QEMU proof waits on
        // before sending any (see `tests/rust_wifi_settings_qemu.py`).
        if self.layer.as_ref().is_some_and(|layer| layer.wl_surface() == surface) {
            if self.drawer_keyboard_active { self.log("drawer-keyboard-focus-granted"); }
            else if self.wifi_keyboard_active { self.log("wifi-keyboard-focus-granted"); }
        }
        if self.home_surface.layer.as_ref().is_some_and(|layer| layer.wl_surface() == surface) {
            // Same role as `wifi-keyboard-focus-granted`, for Home's own
            // open-folder rename field (task 2) -- what a QEMU proof of
            // that flow waits on before sending any keys.
            self.log("home-keyboard-focus-granted");
        }
    }
    fn leave(
        &mut self,
        _: &Connection,
        _: &QueueHandle<Self>,
        _: &wl_keyboard::WlKeyboard,
        surface: &wl_surface::WlSurface,
        _: u32,
    ) {
        if self.drawer_keyboard_active
            && self.layer.as_ref().is_some_and(|layer| layer.wl_surface() == surface) {
            self.drawer_search.unfocus();
            self.sync_drawer_search();
        }
    }
    /// Routes one physical or virtual (wvkbd) key press through to the Wi-Fi
    /// password field. Guarded by `wifi_keyboard_active` (only ever true
    /// while `sync_wifi_keyboard` has actually granted this surface
    /// `Exclusive` keyboard focus for exactly that field) rather than
    /// trusting that focus alone, since a key can arrive the same tick
    /// focus is being torn down.
    fn press_key(
        &mut self,
        _: &Connection,
        qh: &QueueHandle<Self>,
        _: &wl_keyboard::WlKeyboard,
        _: u32,
        event: KeyEvent,
    ) {
        self.handle_drawer_key(&event);
        self.handle_wifi_key(event.clone());
        self.handle_home_key(qh, event);
    }
    fn repeat_key(
        &mut self,
        _: &Connection,
        qh: &QueueHandle<Self>,
        _: &wl_keyboard::WlKeyboard,
        _: u32,
        event: KeyEvent,
    ) {
        self.handle_drawer_key(&event);
        self.handle_wifi_key(event.clone());
        self.handle_home_key(qh, event);
    }
    fn release_key(
        &mut self,
        _: &Connection,
        _: &QueueHandle<Self>,
        _: &wl_keyboard::WlKeyboard,
        _: u32,
        _: KeyEvent,
    ) {
    }
    fn update_modifiers(
        &mut self,
        _: &Connection,
        _: &QueueHandle<Self>,
        _: &wl_keyboard::WlKeyboard,
        _: u32,
        _: Modifiers,
        _: RawModifiers,
        _: u32,
    ) {
        // Nothing to track here: xkbcommon has already folded Shift/Caps
        // into `KeyEvent::utf8` by the time `press_key` sees it, which is
        // exactly why this path needs no `symbols`/`shifted` state of its
        // own the way the old in-app keypad did.
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
delegate_pointer!(ShellClient);
delegate_keyboard!(ShellClient);
delegate_layer!(ShellClient);
delegate_registry!(ShellClient);
impl ProvidesRegistryState for ShellClient {
    fn registry(&mut self) -> &mut RegistryState {
        &mut self.registry_state
    }
    registry_handlers![OutputState, SeatState];
}

fn serve() -> Result<(), String> {
    if let Err(error) = runtime_trace::init() {
        eprintln!("rust-shell trace unavailable: {error}");
    }
    // Catalog discovery runs before connecting Wayland. A slow XDG scan never
    // stalls an owned touch stream or a route acknowledgement. `candidates`
    // -- the `applications` dirs in XDG precedence order -- is also exactly
    // what `CatalogWatcher` watches and every later rescan re-scans, so the
    // watch set and the live catalog can never drift apart.
    let candidates = applications_dirs();
    let apps = scan_apps(&candidates);
    let mut catalog_watch = match CatalogWatcher::new(&candidates) {
        Ok(watcher) => Some(watcher),
        Err(error) => {
            eprintln!("rust-shell 0ms catalog-watch-unavailable {error}");
            None
        }
    };
    let mut routes = RouteServer::new(socket_path()?)?;
    let mut appearance = AppearanceReceiver::bind(
        appearance_socket_path()?,
        std::env::var_os("K230_THEME_DEFAULT_GENERATION").map(PathBuf::from),
    )?;
    // The trailing `bool` is `reuse_optimistic`: true when this event's own
    // target generation is exactly what an earlier Optimistic Apply already
    // rendered and flushed, so the deferred completion below skips drawing
    // again entirely (see `optimistic_active`'s own doc).
    let mut pending_appearance: Option<(AppearanceEvent, Instant, Option<AppearanceSnapshot>, bool)> =
        None;
    let mut pending_video_prepare: Option<(AppearanceEvent, Instant, VideoKey)> = None;
    let conn = Connection::connect_to_env().map_err(|e| e.to_string())?;
    let (globals, mut queue) = registry_queue_init(&conn).map_err(|e| e.to_string())?;
    let qh = queue.handle();
    let compositor = CompositorState::bind(&globals, &qh).map_err(|e| e.to_string())?;
    let layer_shell = LayerShell::bind(&globals, &qh).map_err(|e| e.to_string())?;
    let shm = Shm::bind(&globals, &qh).map_err(|e| e.to_string())?;
    // 6, not 5: the overlay surface's own pool (up to 3 buffers) plus the
    // wallpaper surface's own (now up to 3, not 2 -- see draw_wallpaper's
    // own comment). This is only a pre-allocation size hint; the pool
    // itself grows automatically on any further allocation regardless
    // (`SlotPool::resize`'s own doc), so an under-estimate here would
    // cost an extra mmap resize, never a hard failure.
    let pool = SlotPool::new(568 * 1232 * 4 * 6, &shm).map_err(|e| e.to_string())?;
    let (launch_sender, launch_results) = mpsc::channel();
    let (splash_sender, splash_events) = mpsc::channel();
    let settings_command = std::env::var_os("K230_SETTINGS")
        .map(PathBuf::from)
        .unwrap_or_default();
    let notification_socket = std::env::var_os("K230_NOTIFICATION_SOCKET")
        .map(PathBuf::from)
        .unwrap_or_default();
    let services = ServiceWorker::spawn(settings_command, notification_socket);
    let wpctl_command = std::env::var_os("K230_WPCTL")
        .map(PathBuf::from)
        .unwrap_or_else(|| PathBuf::from("wpctl"));
    let pw_dump_command = std::env::var_os("K230_PW_DUMP")
        .map(PathBuf::from)
        .unwrap_or_else(|| PathBuf::from("pw-dump"));
    let pw_cli_command = std::env::var_os("K230_PW_CLI")
        .map(PathBuf::from)
        .unwrap_or_else(|| PathBuf::from("pw-cli"));
    // Both children are spawned once, here, for this process's whole
    // life -- never per volume change (`pipewire_ipc.rs`'s own module
    // doc has the cost argument). A spawn failure (no PipeWire on this
    // image, or the binary missing from `PATH`) degrades to `None`
    // rather than a hard error: the shell still starts, the volume
    // row/HUD just show "unavailable" (`service_view.audio_error`).
    // Board evidence (system z3zbk6gx) found this shell's own journal
    // had nothing to say when `pw-dump`/`pw-cli` failed to spawn -- an
    // earlier version of this code discarded the `Result`'s own error
    // straight into `.ok()` with no log line at all, exactly the kind of
    // silent failure that makes "is the persistent helper actually
    // starting?" unanswerable from a journal alone. `eprintln!` (this
    // process's own stderr, captured by systemd into the unit's journal
    // like every other early-startup failure in this function, e.g. the
    // `catalog-watch-unavailable` line above) now names which of the two
    // children failed and why, before the same `.ok()` degrade.
    let pipewire_events = pipewire_ipc::spawn_monitor(pw_dump_command, &["--monitor"])
        .inspect_err(|error| eprintln!("rust-shell pipewire-monitor-spawn-failed {error}"))
        .ok();
    let pipewire_writer = pipewire_ipc::WriterHandle::spawn(pw_cli_command)
        .inspect_err(|error| eprintln!("rust-shell pipewire-writer-spawn-failed {error}"))
        .ok();
    let wifi_socket = std::env::var_os("K230_WIFI_SOCKET")
        .map(PathBuf::from)
        .unwrap_or_else(|| PathBuf::from("/run/k230-wifi-settings/broker.sock"));
    let wifi_worker = WifiWorker::spawn(wifi_socket);
    let theme_command = std::env::var_os("K230_THEME_COMMAND")
        .map(PathBuf::from)
        .unwrap_or_default();
    // Same socket `tools/theme_client.py`'s own `DEFAULT_SOCKET` targets;
    // an empty path (an explicitly empty env var) disables the direct
    // socket path, matching `theme_command`'s own unset-env convention.
    let theme_helper_socket = std::env::var_os("K230_THEME_HELPER_SOCKET")
        .map(PathBuf::from)
        .unwrap_or_else(|| PathBuf::from("/run/shell/theme-helper.sock"));
    let themes = ThemeWorker::spawn(theme_command, theme_helper_socket);
    // The panel is always 568x1232 on this board (`width`/`height` below use
    // the same literal default); Home's own initial layout is seeded/loaded
    // against that same reference geometry before the first `configure`
    // ever arrives, exactly like every other fixed-geometry assumption this
    // client already makes at construction.
    let home_state_path = home_state::state_path();
    let home_layout = home_state::load_or_seed(
        home_state_path.as_deref(),
        &apps,
        home_grid::DOCK_SLOTS,
        home_grid::apps_per_page(568, 1232),
    );
    let home = HomeScreen::new(home_layout, 568.0);
    let mut state = ShellClient {
        presentation: runtime_trace::active().then(|| PresentationTimeState::bind(&globals, &qh)),
        trace_feedback: Vec::new(), trace_frame: 0, trace_input: 0,
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
        pointer_device: None,
        pointer_contact: PointerContact::default(),
        keyboard_device: None,
        wifi_keyboard_active: false,
        drawer_keyboard_active: false,
        home_keyboard_active: false,
        keyboard_signal_path: std::env::var_os("K230_KEYBOARD_SIGNAL").map(PathBuf::from),
        // Matches card_shell_keyboard_adjust_usable's grip allocation when
        // the configured shared gesture policy is enabled.
        keyboard_grip_height_px: if std::env::var("K230_KEYBOARD_TOUCH_GESTURES").as_deref() == Ok("1") { 56.0 } else { 0.0 },
        keyboard_height_px: std::env::var("K230_KEYBOARD_HEIGHT")
            .ok()
            .and_then(|value| value.parse::<f64>().ok())
            .filter(|value| *value > 0.0)
            .unwrap_or(400.0),
        route: Route::Drawer,
        touch: TouchTrace::default(),
        width: 568,
        height: 1232,
        configured: false,
        dirty: false,
        frame_pending: false,
        started: Instant::now(),
        apps,
        catalog_pending_rescan: None,
        nav: DrawerNavigation::default(),
        drawer_search: DrawerSearch::default(),
        nav_tick: Instant::now(),
        launch_sender,
        launch_results,
        launching: false,
        launch_in_flight: false,
        launch_seq: 0,
        splash: None,
        splash_events,
        splash_sender,
        splash_watch_stop: None,
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
        trackpad_pan_start: None,
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
        panel_close: PanelClose::default(),
        panel_close_candidate: false,
        panel_close_velocity: 0.0,
        panel_close_sample: None,
        brightness_drag: None,
        drawer_frame_log_at: None,
        volume_drag: None,
        volume_icon_touch: None,
        output_picker_touch: None,
        volume_state: volume::VolumeState::default(),
        hud: volume::Hud::new(),
        hud_last_visible: false,
        default_sink_id: None,
        volume_echo_until_ms: None,
        pipewire_events,
        pipewire_writer,
        wpctl_command,
        reveal: RevealState::default(),
        input_ready: false,
        input_region_key: None,
        reduced_motion: reduced_motion_enabled(
            std::env::var("K230_SETTINGS_REDUCED_MOTION")
                .ok()
                .as_deref(),
        ),
        theme_pulse_at: Instant::now(),
        home_surface: HomeSurface::default(),
        home,
        home_state_path,
        home_touch_id: None,
        home_last_point: (0.0, 0.0),
        drawer_home_drag: None,
        drawer_drag_reveal: None,
        battery_polled_at: None,
        weather_pending: None,
        weather_checked_at: None,
        clock_next_tick: None,
        home_frame_log_at: None,
        theme_apply_tapped_at: None,
        theme_optimistic_shown_for: None,
        card_appearance_socket: card_appearance_socket_path(),
        optimistic_active: None,
        prerendered_overlay: None,
    };
    state.service_view.keyboard_gesture_hint =
        std::env::var("K230_KEYBOARD_TOUCH_GESTURES").as_deref() == Ok("1");
    state.renderer.set_appearance(appearance.active().cloned());
    state.renderer.set_services(state.service_view.clone());
    state.renderer.set_theme_view(state.theme_view.clone());
    // Task 5 (coordinator follow-up): warm the drawer's own pre-rendered
    // grid bitmap now, before this client has even mapped a surface, so
    // its first real open (`K230_DRAWER_FRAME`'s own board measurement:
    // ms=549.89 cold, ms=1.04 once warm) reuses this instead of paying
    // that cost the instant a person taps Apps. Uses the panel's reference
    // size (568x1232) since no `configure` has arrived yet to say
    // otherwise -- the same fallback `pin_app_from_drawer`'s own history
    // already established for this exact "before first configure" gap.
    state.renderer.prebuild_drawer_grid(&state.apps, 568, 1232);
    if !state.ensure_wallpaper(&qh) {
        return Err("wallpaper layer unavailable".into());
    }
    if !state.ensure_home(&qh) {
        return Err("home layer unavailable".into());
    }
    state.log("ready-idle");
    loop {
        if let Err(error) = runtime_trace::finish_if_due() { state.log(&format!("trace-write-failed {error}")); }
        let _loop_profile = runtime_trace::Span::new("event_loop_work");
        {
            let _dispatch_profile = runtime_trace::Span::new("wayland_dispatch");
            queue.dispatch_pending(&mut state).map_err(|e| e.to_string())?;
        }
        // Optimistic Apply: `dispatch_pending` above is where a Settings
        // touch-up would have just called `theme_action(ThemeIntent::
        // Apply)` -> `submit_theme`, setting `theme_view.pending`/
        // `pending_id` and `theme_apply_tapped_at`. Checked once per fresh
        // `pending_id` (never re-armed until the next `submit_theme` call,
        // including on a genuinely cold generation -- see
        // `should_apply_optimistically`'s doc), so this never repeats work
        // across ticks for the same still-pending Activate, and a rapid
        // second Apply (a new, higher `pending_id`, only possible once the
        // first Activate's own reply has cleared `pending`) always gets its
        // own fresh check.
        if optimistic_apply_due(state.theme_optimistic_shown_for, state.theme_view.pending_id) {
            if let (Some(request), Some(tapped_at)) =
                (state.theme_view.pending.clone(), state.theme_apply_tapped_at)
            {
                state.theme_optimistic_shown_for = state.theme_view.pending_id;
                // Only an Activate is ever eligible (see
                // `optimistic_apply_skip_reason`'s own `not-an-activate-
                // request` case); logging is scoped to that case too, so
                // this line is exactly "the decision on the Apply tap"
                // the board's own diagnosis needs, not noise from every
                // List/Preview reply this same one-shot check also runs
                // against.
                if matches!(request, ThemeRequest::Activate { .. }) {
                    let prepared = appearance.prepared().cloned();
                    let prepared_generation =
                        prepared.as_ref().map(|snapshot| snapshot.generation.as_str());
                    if should_apply_optimistically(&request, prepared_generation) {
                        let snapshot =
                            prepared.expect("should_apply_optimistically implies a prepared match");
                        state.show_theme_optimistically(&qh, &mut queue, &snapshot, tapped_at);
                        if let Some(socket) = state.card_appearance_socket.clone() {
                            show_appearance_optimistically(
                                &socket,
                                &snapshot.generation,
                                &snapshot.path,
                            );
                        }
                    } else {
                        let reason = optimistic_apply_skip_reason(&request, prepared_generation)
                            .unwrap_or("prepared-snapshot-vanished");
                        state.log(&format!(
                            "optimistic-apply skipped reason={reason} ms={:.1}",
                            tapped_at.elapsed().as_secs_f64() * 1000.0
                        ));
                    }
                }
            }
        }
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
        // The persistent `pw-dump --monitor` reader (task: "watch the
        // graph for changes" -- event-driven, never a poll of its own).
        // This loop iteration's own wake -- a Wayland event, an input
        // sample, or the existing idle timeout below -- is what drains
        // this channel; there is no separate timer for it.
        if let Some(receiver) = state.pipewire_events.as_ref() {
            let mut events = Vec::new();
            for _ in 0..8 {
                match receiver.try_recv() {
                    Ok(event) => events.push(event),
                    Err(_) => break,
                }
            }
            for event in events {
                state.apply_pipewire_event(event);
            }
        }
        // The volume HUD's own auto-hide (task: "auto-hides after about
        // 2-3s"): checked on every wake rather than a dedicated timer,
        // same reasoning as every other timed UI state in this loop
        // (`catalog_pending_rescan`, splash fade). `hud.is_visible`
        // itself is what actually decides whether the next `state.draw`
        // paints anything for it at all.
        let hud_now_visible = state.hud.is_visible(state.started.elapsed().as_millis() as u64);
        if hud_now_visible || state.hud_last_visible {
            state.dirty = true;
        }
        state.hud_last_visible = hud_now_visible;
        state.maybe_rescan_catalog(&candidates);
        if state.renderer.poll_theme_image(state.width, state.height) {
            state.dirty = true;
        }
        // Each theme/background row thumbnail decodes independently of the
        // single live wallpaper preview above; without this, a completed
        // decode would sit undrained until some unrelated event happened to
        // mark the frame dirty, and later rows would never even get
        // requested past the worker's bounded queue depth.
        if state.renderer.poll_theme_thumbnails(state.width) {
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
        if state.home_surface.layer.is_none()
            && state
                .home_surface
                .recreate_after
                .is_some_and(|when| Instant::now() >= when)
        {
            if state.ensure_home(&qh) {
                state.home_surface.recreate_after = None;
            } else {
                state.home_surface.recreate_after = Some(Instant::now() + Duration::from_secs(1));
                state.log("home-remap-deferred");
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
                        let _profile = runtime_trace::Span::new("appearance_prepare");
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
                        } else {
                            // Named stage marker for tools/theme-swap-jank.py's
                            // merged timeline (task 1): when this candidate is
                            // browsed ahead (task 3.2) or activate_generation's
                            // own internal re-prepare lands, this is the exact
                            // point the wallpaper decode either hit
                            // `state.background_cache`'s in-memory LRU or paid
                            // a `background.cache` read/full decode.
                            state.log("appearance-prepare-accepted");
                        }
                        if let Err(error) = appearance.respond(event, accepted) {
                            state.log(&format!("appearance-prepare-ack-failed {error}"));
                        }
                    }
                    AppearancePhase::Commit | AppearancePhase::Rollback => {
                        let previous = appearance.active().cloned();
                        // Reuse an already-shown Optimistic Apply frame
                        // instead of redrawing an identical one -- see
                        // `may_reuse_optimistic_frame`'s own doc. Cleared
                        // unconditionally, matching or not, so it can only
                        // ever be read by the very next Commit/Rollback
                        // event, never a later, unrelated one.
                        let reuse_optimistic = may_reuse_optimistic_frame(
                            event.phase,
                            state.optimistic_active.as_deref(),
                            event.snapshot.as_ref().map(|snapshot| snapshot.generation.as_str()),
                        );
                        state.optimistic_active = None;
                        if reuse_optimistic {
                            pending_appearance = Some((event, Instant::now(), previous, true));
                        } else {
                            let geometry = state
                                .wallpaper
                                .configured
                                .then_some((state.wallpaper.width, state.wallpaper.height));
                            let video_key = geometry
                                .and_then(|size| selected_video(event.snapshot.as_ref(), size));
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
                                // Task 5: re-warm the drawer grid for the
                                // new theme now, at this settled Commit/
                                // Rollback point, rather than waiting for
                                // whatever taps Apps next -- a no-op
                                // (`DrawerGridCache::ensure`'s own freshness
                                // check) if the generation did not actually
                                // change.
                                let (reference_width, reference_height) = if state.width > 0 && state.height > 0 {
                                    (state.width, state.height)
                                } else {
                                    (568, 1232)
                                };
                                state.renderer.prebuild_drawer_grid(&state.apps, reference_width, reference_height);
                                state.appearance_pending = true;
                                state.dirty = true;
                                state.wallpaper.dirty = true;
                                pending_appearance = Some((event, Instant::now(), previous, false));
                            }
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
            if attempt != state.launch_seq {
                state.log("stale-app-launch-result");
                continue;
            }
            state.launch_in_flight = false;
            match result {
                Ok(LaunchOutcome::Focused) => {
                    state.log("app-launch-focused");
                    state.splash_matched();
                }
                Ok(LaunchOutcome::Spawned(pid)) => {
                    state.log("app-launch-requested");
                    let target = pid.map(SplashTarget::Pid).unwrap_or(SplashTarget::LaunchOrder);
                    if let Some(splash) = state.splash.as_mut() {
                        splash.target = target;
                    } else {
                        // The splash was dismissed (e.g. a Back tap) while
                        // this launch was still in flight; nothing left to
                        // watch for on this client's own side, but the
                        // process itself was still asked to start.
                        continue;
                    }
                    state.splash_watch_stop = Some(spawn_splash_watcher(
                        target,
                        pid,
                        attempt,
                        state.splash_sender.clone(),
                    ));
                }
                Err(error) => {
                    state.log(&format!("app-launch-failed {error}"));
                    if let Some(splash) = state.splash.as_mut() {
                        splash.set_status(SplashStatus::Failed, Instant::now());
                        state.dirty = true;
                    } else {
                        // Same stale-splash situation as above, on the
                        // failure path instead.
                        state.launching = false;
                    }
                }
            }
        }
        for _ in 0..4 {
            let Ok((attempt, signal)) = state.splash_events.try_recv() else {
                break;
            };
            if attempt != state.launch_seq {
                continue;
            }
            match signal {
                SplashSignal::Matched => {
                    state.log("app-launch-mapped");
                    state.splash_watch_stop = None; // the watcher already exited on its own
                    state.splash_matched();
                }
                SplashSignal::ProcessExited => {
                    state.log("app-launch-process-exited");
                    state.splash_watch_stop = None;
                    if let Some(splash) = state.splash.as_mut() {
                        splash.set_status(SplashStatus::Failed, Instant::now());
                        state.dirty = true;
                    }
                }
            }
        }
        // Extracted as plain `Copy` values up front (never a live reference
        // into `state.splash`) so the `TimedOut`/`Failed` transitions below
        // are free to call back into `state` (`dismiss_splash` mutably
        // borrows all of it) without a borrow-checker conflict.
        if let Some((status, started, status_since)) = state
            .splash
            .as_ref()
            .map(|splash| (splash.status, splash.started, splash.status_since))
        {
            let now = Instant::now();
            match status {
                SplashStatus::Pending => {
                    if fade_alpha(started, now) < 1.0 {
                        state.dirty = true;
                    }
                    if should_time_out(started, now) {
                        state.log("app-launch-splash-timeout");
                        if let Some(splash) = state.splash.as_mut() {
                            splash.set_status(SplashStatus::TimedOut, now);
                        }
                        state.dirty = true;
                    }
                }
                SplashStatus::TimedOut => {}
                SplashStatus::Failed => {
                    if should_auto_dismiss_failed(status_since, now) {
                        state.dismiss_splash(&qh);
                    }
                }
            }
        }
        let now = Instant::now();
        let elapsed = now
            .duration_since(state.nav_tick)
            .as_millis()
            .min(u128::from(u32::MAX)) as u32;
        state.nav_tick = now;
        if state.route == Route::Drawer && state.drawer_home_drag.is_none() && state.touch.id != Some(TRACKPAD_PAN_ID) {
            let filtered = state.drawer_filtered_apps().len();
            if let Some((display_index, point)) =
                state.nav.take_long_press_drag(elapsed, state.width, state.drawer_search.viewport_height(state.height), filtered)
            {
                if let Some(id) = state.touch.id {
                    state.begin_drawer_home_drag(id, display_index, point);
                }
            }
        }
        if state.route == Route::Drawer && state.nav.tick(elapsed, state.width, state.drawer_search.viewport_height(state.height), state.drawer_filtered_apps().len()) {
            state.dirty = true;
        }
        // Keeps the drawer-drag reveal animation (task 1) advancing every
        // tick even while the finger holds still right after arming it --
        // otherwise, with no further motion event, nothing would ever mark
        // this surface dirty again until the touch moves or lifts.
        if state.drawer_drag_reveal.is_some() {
            state.dirty = true;
        }
        state.tick_home_widgets(now);
        if state.home_touch_id != Some(TRACKPAD_PAN_ID) && state.home.tick(elapsed) {
            state.home_surface.dirty = true;
        }
        if state.home_surface.dirty {
            state.draw_home(&qh);
        }
        state.tick_notifications(elapsed);
        if state.route == Route::Settings {
            let theme_count = state.theme_view.list.as_ref().map_or(0, |l| l.themes.len());
            let background_count = state
                .theme_view
                .preview
                .as_ref()
                .map_or(0, |p| p.backgrounds.len());
            // Task: tap-to-apply (2026-09-25): both carousels tick every
            // frame now, independent of which (if either) currently has
            // an armed touch -- `Carousel::tick` drives momentum/settle
            // physics purely from elapsed time, not touch ownership, and
            // both are visible at once on the one List page.
            if state.theme_carousel.tick(elapsed, theme_count) {
                state.theme_view.theme_position = state.theme_carousel.position();
                state.theme_dirty();
            }
            if state.background_carousel.tick(elapsed, background_count) {
                state.theme_view.background_position = state.background_carousel.position();
                state.theme_dirty();
            }
            // Task 3.2 (+ neighbour warm-up): as a theme becomes (and stays)
            // the carousel's centred item on the List page, warm it ahead
            // of a possible Apply -- see `ThemeView::poll_prepare_ahead`'s
            // own doc. Only considered while the carousel itself is at rest
            // (`is_animating()` distinguishes "a drag/coast/settle is
            // still live" from "nothing is moving"), so a fast flick
            // fires nothing until the finger actually settles somewhere.
            // When nothing is dwell-driven, the same call also drains a
            // queued neighbour warm-up (the index returned may not be
            // `centered` in that case -- `poll_prepare_ahead` reports
            // exactly which one it means). Theme-carousel only, same as
            // before this task.
            if state.theme_view.page == ThemePage::List {
                let centered = (!state.theme_carousel.is_animating() && theme_count > 0)
                    .then(|| state.theme_carousel.index(theme_count));
                if let Some((index, request)) = state.theme_view.poll_prepare_ahead(elapsed, centered) {
                    if let Ok(id) = state.themes.try_submit(request) {
                        runtime_trace::event("speculative_admission", [id, index as u64,
                            u64::from(state.theme_carousel.is_animating()),
                            u64::from(state.background_carousel.is_animating()), 0, 0]);
                        state.theme_view.prepare_ahead_submitted(index, id);
                    } // queue full/unavailable: the next settled tick tries again
                }
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
            let waiting_on_background_work = state.renderer.theme_thumbnails_pending(state.width)
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
        if state
            .panel_close
            .tick(state.started.elapsed().as_millis() as u64)
        {
            if state.panel_close.take_settled_closed() {
                state.hide();
            } else {
                state.dirty = true;
            }
        }
        // A release can arrive after all bounded slots were busy. Retry from
        // the event loop so the deferred touch frame is eventually submitted.
        if let Some((event, started, previous, reuse_optimistic)) = pending_appearance.take() {
            if reuse_optimistic {
                // Already drawn and flushed by Optimistic Apply -- see
                // `optimistic_active`'s own doc. Nothing left to render;
                // only the bookkeeping and the ack, still only sent after
                // that already-real frame, never before one.
                state.adopt_committed_video_state(event.snapshot.as_ref());
                state.appearance_pending = false;
                state.log("appearance-commit-accepted reused=optimistic");
                if let Err(error) = appearance.respond(event, true) {
                    state.log(&format!("appearance-ack-failed {error}"));
                }
            } else {
                // Neither `draw_wallpaper()` nor `draw()` require their own
                // outstanding frame callback to have fired any more (see
                // `redraw_entry_ready`'s own doc): either surface can be fully
                // occluded -- the background layer by a maximized app or the
                // card deck's own backdrop, the overlay/settings layer by
                // nothing more than an earlier redraw of itself the
                // compositor has not yet acked -- and a compositor is not
                // obligated to keep sending frame-done callbacks for a
                // surface nothing is presently compositing. Mirror that same
                // relaxed condition here so this readiness check does not
                // itself keep the transaction pending, waiting on a signal
                // that may never arrive (board evidence, 2026-09-27:
                // Optimistic Apply's own one-shot check hit exactly this,
                // with `overlay-frame-pending=true` while a free buffer slot
                // was available).
                let overlay_ready = state.layer.is_none() || state.configured;
                let ready = state.wallpaper.configured && overlay_ready;
                if !ready && started.elapsed() < Duration::from_millis(1400) {
                    pending_appearance = Some((event, started, previous, false));
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
                        let accepted = background && foreground && flushed;
                        if accepted {
                            // Named stage marker (task 1): the redrawn/flushed
                            // frame carrying the new theme's wallpaper has just
                            // been submitted to the compositor -- this is the
                            // Rust-shell side of "tap to visible", paired with
                            // "wallpaper-commit"/"commit" a real frame-done
                            // callback later confirms was actually presented.
                            state.log("appearance-commit-accepted");
                        }
                        accepted
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
                        state.adopt_committed_video_state(event.snapshot.as_ref());
                    }
                    state.appearance_pending = false;
                    if let Err(error) = appearance.respond(event, accepted) {
                        state.log(&format!("appearance-ack-failed {error}"));
                    }
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
        {
            let _profile = runtime_trace::Span::new("wayland_flush");
            queue.flush().map_err(|e| e.to_string())?;
        }
        // Optimistic Apply's own pre-render (task: pre-render at prepare
        // time so Apply itself is just an attach+commit). Deliberately
        // placed *after* this tick's own flush above, never before it:
        // the render below is real, synchronous Cairo work -- the same
        // ~200ms cost Apply's own optimistic show pays without this --
        // and running it earlier in this same iteration would delay
        // sending whatever this tick's own draw already queued.
        //
        // Task: tap-to-apply (2026-09-25) retargeted this from the old
        // separate Preview page's own currently-loaded theme to the
        // theme carousel's own *centred* candidate on this one List
        // page -- whatever a tap right now would actually apply -- using
        // `known_generations` (populated by `poll_prepare_ahead`'s own
        // warm-up replies, via `record_known_generation`) rather than a
        // fresh Preview round trip, so this never itself becomes the
        // thing a tap has to wait on. Requires nothing at all pending --
        // not just excluding an Activate specifically -- because the
        // busy-spinner state a request in flight paints is baked into
        // the ordinary cached body the same as everything else `content_
        // generation` does not track, so computing while anything is
        // pending risks caching a stale busy indicator.
        if state.route == Route::Settings
            && state.configured
            && state.theme_view.page == ThemePage::List
            && pending_appearance.is_none()
            && state.theme_view.pending.is_none()
            && theme_prerender_at_rest(&state.theme_carousel, &state.background_carousel)
        {
            let centered_theme_id = state.theme_view.list.as_ref().and_then(|list| {
                if list.themes.is_empty() {
                    return None;
                }
                let index = state
                    .theme_view
                    .theme_position
                    .round()
                    .clamp(0.0, (list.themes.len() - 1) as f64) as usize;
                list.themes.get(index).map(|entry| entry.id.clone())
            });
            if let Some(generation) = centered_theme_id
                .and_then(|id| state.theme_view.known_generations.get(&id).cloned())
            {
                let content_generation = state.renderer.content_generation();
                let fresh = state.prerendered_overlay.as_ref().is_some_and(|candidate| {
                    prerendered_overlay_matches(
                        candidate,
                        &generation,
                        Route::Settings,
                        state.width,
                        state.height,
                        content_generation,
                    )
                });
                // Only the receiver's own already-`prepare`d generation --
                // the same precondition Optimistic Apply itself checks --
                // is eligible: this never triggers preparing a cold
                // generation early, only pre-rendering one this process
                // already validated and staged.
                let prepared_snapshot = (!fresh)
                    .then(|| appearance.prepared())
                    .flatten()
                    .filter(|snapshot| snapshot.generation == generation)
                    .cloned();
                if let Some(snapshot) = prepared_snapshot {
                    match state.renderer.render_candidate_overlay(
                        Some(&snapshot),
                        Route::Settings,
                        state.width,
                        state.height,
                        &state.apps,
                    ) {
                        Ok(pixels) => {
                            state.prerendered_overlay = Some(PrerenderedOverlay {
                                generation: generation.clone(),
                                route: Route::Settings,
                                width: state.width,
                                height: state.height,
                                content_generation,
                                pixels,
                            });
                            state.log(&format!(
                                "optimistic-apply prerendered generation={}",
                                &generation[..12.min(generation.len())]
                            ));
                        }
                        Err(error) => {
                            state.log(&format!("optimistic-apply prerender-failed {error}"));
                        }
                    }
                }
            }
        }
        drop(_loop_profile);
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
            libc::pollfd {
                fd: catalog_watch.as_ref().map_or(-1, CatalogWatcher::as_raw_fd),
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
            || state.home.is_animating()
            || state.drawer_drag_reveal.is_some()
            || state.catalog_pending_rescan.is_some()
            || state
                .splash
                .as_ref()
                .is_some_and(|splash| fade_alpha(splash.started, Instant::now()) < 1.0)
            || (state.route == Route::Settings
                && (state.theme_carousel.is_animating()
                    || state.background_carousel.is_animating()
                    || state.renderer.theme_thumbnails_pending(state.width)
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
        if fds[5].revents & libc::POLLIN != 0 {
            if let Some(watcher) = catalog_watch.as_mut() {
                if watcher.drain(&candidates) {
                    // Debounced, not immediate: a NixOS switch or a busy
                    // profile rebuild touches many files in a burst, and
                    // rescanning once per burst (not once per event) is the
                    // whole point of this deadline -- see the loop's own
                    // `catalog_pending_rescan` check below for where it
                    // actually fires.
                    state.catalog_pending_rescan = Some(Instant::now() + Duration::from_millis(250));
                }
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
                &PathBuf::from(output), 568, 1232, selected, &scan_apps(&applications_dirs())))
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
    fn brightness_commit_suppresses_its_own_success_toast_but_not_a_failure() {
        // The live slider drag itself is the feedback (review follow-up
        // on the brightness-slider task): a "Brightness changed" toast on
        // every release is noise, not information.
        assert!(suppresses_action_message(
            &ServiceRequest::Brightness(50),
            None
        ));
        // A genuine failure (permission denied, an unreachable backend)
        // must still surface.
        assert!(!suppresses_action_message(
            &ServiceRequest::Brightness(50),
            Some("brightness-denied")
        ));
        // Every other request keeps its own message exactly as before,
        // success or failure.
        assert!(!suppresses_action_message(
            &ServiceRequest::KeyboardToggle,
            None
        ));
        assert!(!suppresses_action_message(
            &ServiceRequest::BrightnessLive(50),
            None
        ));
    }

    #[test]
    fn theme_prerender_waits_for_both_carousels_to_finish_moving() {
        for background in [false, true] {
            let mut themes = Carousel::new(THEME_GEOMETRY);
            let mut backgrounds = Carousel::new(BACKGROUND_GEOMETRY);
            assert!(theme_prerender_at_rest(&themes, &backgrounds));
            let active = if background {
                &mut backgrounds
            } else {
                &mut themes
            };
            active.set_index(10);
            active.down(7, (284.0, 400.0), 0);
            assert!(!theme_prerender_at_rest(&themes, &backgrounds));
            let active = if background {
                &mut backgrounds
            } else {
                &mut themes
            };
            active.motion(7, (243.0, 400.0), 20, 40);
            active.up(7, (243.0, 400.0), 21, 40, 284.0, 0.0);
            assert!(!theme_prerender_at_rest(&themes, &backgrounds)); // released coast/settle
            for _ in 0..1000 {
                themes.tick(16, 40);
                backgrounds.tick(16, 40);
                if theme_prerender_at_rest(&themes, &backgrounds) {
                    break;
                }
            }
            assert!(theme_prerender_at_rest(&themes, &backgrounds));
        }
    }

    #[test]
    fn shade_upward_drag_engages_only_from_an_eligible_zone_past_slop() {
        // The live close-drag replacement for the old release-only
        // `shade_close_swipe`/`shade_release_closes` pair: a touch is only
        // ever a close-drag candidate from `close_drag_zone` (the top
        // dismiss band, or at/after the panel's own bottom edge -- never
        // from within the scrollable list itself), and only actually
        // engages once it clears `close_drag_engaged`'s slop.
        let travel = panel_travel_height(Route::Shade, 568, 1232, None, None);
        let mut touch = TouchTrace::default();
        assert!(touch.down(3, (282.0, 80.0)));
        assert!(touch.motion(3, (280.0, 40.0)));
        assert!(touch.up(3));
        let start = (282.0, 80.0);
        assert!(
            close_drag_zone(Route::Shade, start.1, travel),
            "top dismiss band is an eligible start"
        );
        assert!(
            close_drag_engaged(
                Route::Shade,
                touch.position.0 - start.0,
                touch.position.1 - start.1
            ),
            "a real upward drag from there engages"
        );
        assert!(
            !close_drag_engaged(Route::Shade, 2.0, -2.0),
            "a sub-slop wobble must not engage"
        );
        // Starting on the live notification list itself is never an
        // eligible close-drag zone, regardless of direction -- that
        // touch stays a scroll/swipe candidate (`panel_intent`'s own
        // domain), not a close drag.
        assert!(!close_drag_zone(
            Route::Shade,
            k230_shell_rust::service_ui::NOTIFICATION_TOP + 10.0,
            travel
        ));
        // The backdrop below the panel is eligible too.
        assert!(close_drag_zone(Route::Shade, travel + 50.0, travel));
        assert_eq!(close_drag_progress(Route::Shade, 0.0, travel), 1.0);
    }

    #[test]
    fn drawer_downward_drag_engages_only_from_an_eligible_zone_past_slop() {
        // The Drawer's own mirror of the Shade test above: bottom-anchored,
        // so it closes on a *downward* drag instead of upward, and its
        // eligible zones are the header/handle band (always) or the tile
        // grid itself (only once already scrolled to its own top) --
        // `drawer_close_drag_zone`, not `close_drag_zone`, since it needs
        // scroll state Shade/Settings never do.
        let travel = panel_travel_height(Route::Drawer, 568, 1232, None, None);
        let header_top = k230_shell_rust::navigation::panel_top(1232);
        let mut touch = TouchTrace::default();
        assert!(touch.down(3, (280.0, header_top + 20.0)));
        assert!(touch.motion(3, (282.0, header_top + 60.0)));
        assert!(touch.up(3));
        let start = (280.0, header_top + 20.0);
        assert!(
            drawer_close_drag_zone(start.1, 1232, 0.0),
            "top handle band is an eligible start regardless of scroll"
        );
        assert!(
            close_drag_engaged(
                Route::Drawer,
                touch.position.0 - start.0,
                touch.position.1 - start.1
            ),
            "a real downward drag from there engages"
        );
        assert!(
            !close_drag_engaged(Route::Drawer, 2.0, 2.0),
            "a sub-slop wobble must not engage"
        );
        assert!(
            !close_drag_engaged(Route::Drawer, 0.0, -20.0),
            "an upward drag (scrolling down through the list) never engages a Drawer close"
        );
        // The grid is only an eligible start once already scrolled to its
        // own top -- otherwise this must stay a plain scroll, never a
        // close-drag candidate.
        let grid_y = k230_shell_rust::navigation::list_top(1232) + 10.0;
        assert!(
            drawer_close_drag_zone(grid_y, 1232, 0.0),
            "grid start, scrolled to top, is eligible"
        );
        assert!(
            !drawer_close_drag_zone(grid_y, 1232, 300.0),
            "grid start, scrolled away from the top, must not hijack scrolling"
        );
        assert_eq!(close_drag_progress(Route::Drawer, 0.0, travel), 1.0);
        assert_eq!(close_drag_progress(Route::Drawer, travel, travel), 0.0);
    }

    /// Reproduces the reported bug end-to-end at the same level `main.rs`'s
    /// own `down`/`motion` handlers operate at: `DrawerNavigation` plus the
    /// exact same live-close-drag decision (`drawer_close_drag_zone` at
    /// touch-down, `close_drag_engaged`/`drawer_close_candidate_after_
    /// scroll` on every sample) those handlers call into. A touch starts
    /// inside the grid while it is at its own top (an eligible close-drag
    /// candidate), scrolls away by dragging up, then reverses and drags
    /// back down past the original point -- the drawer must never engage
    /// a close, in either the live-drag path here or `DrawerNavigation::
    /// up`'s own release-only backstop (covered separately in
    /// `navigation.rs`'s tests).
    #[test]
    fn drawer_live_close_drag_never_engages_after_a_mid_gesture_scroll_reversal() {
        let height = 1232u32;
        let apps = 200;
        let grid_y = k230_shell_rust::navigation::list_top(height) + 10.0;
        let start = (100.0, grid_y);

        let mut nav = DrawerNavigation::default();
        let close = PanelClose::default();
        assert!(nav.down(1, start, 0));
        let mut candidate =
            !close.active() && !nav.coasting() && drawer_close_drag_zone(start.1, height, nav.scroll);
        assert!(candidate, "grid at rest at its own top is an eligible start");

        // Sample 1: drag up 200px (ordinary scroll-down-the-list motion).
        // Below Drawer's engage slop in the *closing* (downward) direction,
        // so this never attempts to engage regardless of `candidate`.
        let pos1 = (100.0, grid_y - 200.0);
        let (dx1, dy1) = (pos1.0 - start.0, pos1.1 - start.1);
        assert!(!close.tracking() && !close_drag_engaged(Route::Drawer, dx1, dy1));
        assert!(nav.motion(1, pos1, 40, 568, height, apps));
        candidate = drawer_close_candidate_after_scroll(candidate, nav.scroll);
        assert!(!candidate, "real scrolling away from the top disqualifies this gesture");

        // Sample 2: reverse and drag back down past the *original* start
        // point -- past the engage slop in the closing direction, which is
        // exactly what the un-fixed logic let through because `candidate`
        // was still (stale) true from touch-down.
        let pos2 = (100.0, grid_y + 150.0);
        let (dx2, dy2) = (pos2.0 - start.0, pos2.1 - start.1);
        assert!(
            close_drag_engaged(Route::Drawer, dx2, dy2),
            "past slop in the closing direction, same as the un-fixed bug would have hit"
        );
        // But `candidate` is already disqualified, so `main.rs`'s own
        // engage guard (`!close.tracking() && close_drag_engaged(..) &&
        // candidate`) never lets this call `close.begin`.
        assert!(!candidate);
        assert!(nav.motion(1, pos2, 90, 568, height, apps));
        assert!(!close.tracking(), "the close drag must never have engaged");
    }

    #[test]
    fn shade_and_settings_map_full_height_drawer_keeps_its_own_offset() {
        // Shade used to map only its own 0.65h panel (previously named
        // "expands" for the jump to full height on entering Settings); it
        // now maps the same full remaining height Settings already did, so
        // a close drag can start anywhere on the dim backdrop below the
        // panel (`close_drag_zone`), not only inside the panel itself.
        assert_eq!(
            panel_input_rect(Route::Shade, 568, 1232, true),
            Some((0, 0, 568, 1232))
        );
        assert_eq!(
            panel_input_rect(Route::Settings, 568, 1232, true),
            Some((0, 0, 568, 1232))
        );
        assert_eq!(panel_input_rect(Route::Shade, 568, 1232, false), None);
        // Drawer no longer offsets its top edge either: the pre-redesign
        // `height*0.19` exclusion (a stand-in for a since-removed empty
        // band above a once bottom-anchored sheet) silently made the
        // search field and the drawer's entire first row of tiles
        // untouchable -- every such touch fell through to whatever surface
        // sits below the drawer instead. See `panel_input_rect`'s own doc.
        assert_eq!(
            panel_input_rect(Route::Drawer, 600, 1200, true),
            Some((0, 0, 600, 1200))
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
    fn optimistic_apply_fires_only_for_an_activate_matching_the_prepared_generation() {
        let target = "aaaaaaaaaaaaaaaaaaaaaaaa".to_string();
        let other = "bbbbbbbbbbbbbbbbbbbbbbbb".to_string();
        let activate = ThemeRequest::Activate {
            theme_id: "gruvbox".into(),
            expected_generation: target.clone(),
            background_id: None,
        };
        // Warm: the receiver's own prepared snapshot is this exact
        // generation.
        assert!(should_apply_optimistically(&activate, Some(target.as_str())));
        // Cold: nothing prepared at all -- must keep today's (non-
        // optimistic) behaviour.
        assert!(!should_apply_optimistically(&activate, None));
        // Stale/mismatched: prepared, but for a *different* generation --
        // e.g. a since-superseded browse-ahead. Never optimistic for the
        // wrong theme.
        assert!(!should_apply_optimistically(&activate, Some(other.as_str())));
        // A Preview (not an Apply) is never eligible, even if it happens
        // to name a generation that is already prepared -- only an
        // explicit Activate may show ahead of its own durable commit.
        let preview = ThemeRequest::Preview {
            theme_id: "gruvbox".into(),
            background_id: None,
        };
        assert!(!should_apply_optimistically(&preview, Some(target.as_str())));
        assert!(!should_apply_optimistically(&ThemeRequest::List, Some(target.as_str())));
    }

    #[test]
    fn optimistic_apply_skip_reason_names_the_specific_cause() {
        // Board evidence (2026-09-26): a plain bool told the coordinator
        // *that* the optimistic path did not fire, not *why* -- this is
        // the diagnostic surface `optimistic-apply skipped reason=...`
        // logs verbatim.
        let target = "aaaaaaaaaaaaaaaaaaaaaaaa".to_string();
        let other = "bbbbbbbbbbbbbbbbbbbbbbbb".to_string();
        let activate = ThemeRequest::Activate {
            theme_id: "gruvbox".into(),
            expected_generation: target.clone(),
            background_id: None,
        };
        assert_eq!(optimistic_apply_skip_reason(&activate, Some(target.as_str())), None);
        assert_eq!(
            optimistic_apply_skip_reason(&activate, None),
            Some("not-prepared")
        );
        assert_eq!(
            optimistic_apply_skip_reason(&activate, Some(other.as_str())),
            Some("generation-mismatch")
        );
        assert_eq!(
            optimistic_apply_skip_reason(&ThemeRequest::List, Some(target.as_str())),
            Some("not-an-activate-request")
        );
    }

    #[test]
    fn redraw_entry_never_gates_on_a_surfaces_own_outstanding_frame_callback() {
        // Board evidence (2026-09-27): Optimistic Apply's own readiness
        // check (since removed -- `draw_wallpaper()`/`draw()` are
        // themselves the gate) skipped with `reason=not-ready-for-a-frame`
        // while the theme chooser's own overlay panel -- the very surface
        // being drawn -- still had an outstanding frame callback from an
        // earlier redraw the compositor had not yet acked, even with a
        // free buffer slot sitting right there. This is the same class of
        // bug cd36242b already fixed for the wallpaper/background layer
        // (a compositor may withhold frame-done callbacks indefinitely
        // for a surface it is not presently compositing -- there, because
        // an app fully occluded the wallpaper; here, because nothing
        // guarantees the overlay's own prior frame is acked before the
        // next one is wanted) -- `draw()`'s own entry guard had never
        // received that fix. `redraw_entry_ready`'s signature is the
        // proof: it has no parameter to gate on a frame-pending flag at
        // all, for either surface, so this mistake cannot be reintroduced
        // by accident.
        assert!(redraw_entry_ready(false, true, true));
        // A real transaction's own commit/rollback draw already owns this
        // tick: still correctly refused, on its own explicit flag, never
        // on a stuck frame callback.
        assert!(!redraw_entry_ready(true, true, true));
        // Never configured yet (no `configure` event received): correctly
        // refused, a real readiness gate distinct from frame_pending.
        assert!(!redraw_entry_ready(false, false, true));
        // The overlay surface is not even mapped: correctly refused.
        assert!(!redraw_entry_ready(false, true, false));
    }

    #[test]
    fn optimistic_apply_due_is_scoped_to_each_fresh_pending_id_for_a_rapid_double_apply() {
        // Nothing pending: never due.
        assert!(!optimistic_apply_due(None, None));
        // A fresh Apply (id 7), nothing attempted yet: due.
        assert!(optimistic_apply_due(None, Some(7)));
        // Already attempted for this exact id (rendered or not): not due
        // again on a later tick while it is still the same pending Apply.
        assert!(!optimistic_apply_due(Some(7), Some(7)));
        // Rapid double Apply: id 7's own reply lands (main.rs's
        // `ThemeView::accept` clears `pending_id` back to `None`), so
        // nothing is due in the gap...
        assert!(!optimistic_apply_due(Some(7), None));
        // ...then a second Apply is submitted immediately as a fresh,
        // higher id 8 (`submit_theme` also resets
        // `theme_optimistic_shown_for` to `None`, but even without that
        // reset this check alone already treats a new id as due).
        assert!(optimistic_apply_due(Some(7), Some(8)));
    }

    #[test]
    fn may_reuse_optimistic_frame_only_for_a_commit_matching_exactly() {
        // The ordinary case: a Commit for exactly the generation
        // Optimistic Apply already showed.
        assert!(may_reuse_optimistic_frame(
            AppearancePhase::Commit,
            Some("aaaaaaaaaaaaaaaaaaaaaaaa"),
            Some("aaaaaaaaaaaaaaaaaaaaaaaa"),
        ));
        // Nothing was ever shown optimistically: never reused.
        assert!(!may_reuse_optimistic_frame(
            AppearancePhase::Commit,
            None,
            Some("aaaaaaaaaaaaaaaaaaaaaaaa"),
        ));
        // A stale/mismatched generation (some other transaction's own
        // commit landed instead): never reused.
        assert!(!may_reuse_optimistic_frame(
            AppearancePhase::Commit,
            Some("aaaaaaaaaaaaaaaaaaaaaaaa"),
            Some("bbbbbbbbbbbbbbbbbbbbbbbb"),
        ));
        // A Rollback can never reuse the optimistic frame, even if its own
        // (synthetic, would-never-happen) generation happened to match --
        // a rollback's own target is by definition the previous
        // generation, not the one just optimistically shown.
        assert!(!may_reuse_optimistic_frame(
            AppearancePhase::Rollback,
            Some("aaaaaaaaaaaaaaaaaaaaaaaa"),
            Some("aaaaaaaaaaaaaaaaaaaaaaaa"),
        ));
        // Neither side names a generation (a rollback to the packaged
        // default): `None == None` is never treated as a match.
        assert!(!may_reuse_optimistic_frame(AppearancePhase::Commit, None, None));
    }

    #[test]
    fn prerendered_overlay_matches_requires_every_field_to_agree() {
        let candidate = PrerenderedOverlay {
            generation: "aaaaaaaaaaaaaaaaaaaaaaaa".into(),
            route: Route::Settings,
            width: 568,
            height: 1232,
            content_generation: 3,
            pixels: Vec::new(),
        };
        assert!(prerendered_overlay_matches(
            &candidate,
            "aaaaaaaaaaaaaaaaaaaaaaaa",
            Route::Settings,
            568,
            1232,
            3
        ));
        // A different generation (a different theme entirely): no match.
        assert!(!prerendered_overlay_matches(
            &candidate,
            "bbbbbbbbbbbbbbbbbbbbbbbb",
            Route::Settings,
            568,
            1232,
            3
        ));
        // A different route (page change): no match.
        assert!(!prerendered_overlay_matches(
            &candidate,
            "aaaaaaaaaaaaaaaaaaaaaaaa",
            Route::Drawer,
            568,
            1232,
            3
        ));
        // A different geometry (resize/rotate): no match.
        assert!(!prerendered_overlay_matches(
            &candidate,
            "aaaaaaaaaaaaaaaaaaaaaaaa",
            Route::Settings,
            600,
            1232,
            3
        ));
        assert!(!prerendered_overlay_matches(
            &candidate,
            "aaaaaaaaaaaaaaaaaaaaaaaa",
            Route::Settings,
            568,
            1200,
            3
        ));
        // A stale content_generation (theme_view/services/pressed/
        // thumbnails/preview changed since this was computed): no match.
        assert!(!prerendered_overlay_matches(
            &candidate,
            "aaaaaaaaaaaaaaaaaaaaaaaa",
            Route::Settings,
            568,
            1232,
            4
        ));
    }

    #[test]
    fn prerendered_overlay_mismatch_reason_names_the_specific_field() {
        // Board evidence, 2026-09-28: a plain `prerendered=false` told
        // the coordinator only that a stored pre-render was not used, not
        // which of generation/route/geometry/content_generation made it
        // stale. Checked in a fixed order, so a candidate failing several
        // checks at once still reports one specific, reproducible reason.
        let candidate = PrerenderedOverlay {
            generation: "aaaaaaaaaaaaaaaaaaaaaaaa".into(),
            route: Route::Settings,
            width: 568,
            height: 1232,
            content_generation: 3,
            pixels: Vec::new(),
        };
        assert_eq!(
            prerendered_overlay_mismatch_reason(
                None,
                "aaaaaaaaaaaaaaaaaaaaaaaa",
                Route::Settings,
                568,
                1232,
                3
            ),
            Some("no-prerender-computed")
        );
        assert_eq!(
            prerendered_overlay_mismatch_reason(
                Some(&candidate),
                "bbbbbbbbbbbbbbbbbbbbbbbb",
                Route::Settings,
                568,
                1232,
                3
            ),
            Some("generation")
        );
        assert_eq!(
            prerendered_overlay_mismatch_reason(
                Some(&candidate),
                "aaaaaaaaaaaaaaaaaaaaaaaa",
                Route::Drawer,
                568,
                1232,
                3
            ),
            Some("route")
        );
        assert_eq!(
            prerendered_overlay_mismatch_reason(
                Some(&candidate),
                "aaaaaaaaaaaaaaaaaaaaaaaa",
                Route::Settings,
                600,
                1232,
                3
            ),
            Some("geometry")
        );
        assert_eq!(
            prerendered_overlay_mismatch_reason(
                Some(&candidate),
                "aaaaaaaaaaaaaaaaaaaaaaaa",
                Route::Settings,
                568,
                1232,
                4
            ),
            Some("content-changed")
        );
        assert_eq!(
            prerendered_overlay_mismatch_reason(
                Some(&candidate),
                "aaaaaaaaaaaaaaaaaaaaaaaa",
                Route::Settings,
                568,
                1232,
                3
            ),
            None
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
    fn running_con_id_honors_startup_class_for_floating_apps() {
        let dir = std::env::temp_dir().join(format!("k230-home-focus-{}", std::process::id()));
        fs::create_dir_all(&dir).unwrap();
        let desktop = dir.join("foot.desktop");
        fs::write(&desktop, "[Desktop Entry]\nType=Application\nName=Terminal\nExec=/bin/true\nStartupWMClass=k230-terminal\n").unwrap();
        let swaymsg = dir.join("swaymsg");
        fs::write(&swaymsg, r##"#!/bin/sh
printf '%s\n' '{"type":"root","floating_nodes":[{"type":"floating_con","app_id":"k230-terminal","id":42}]}'
"##).unwrap();
        fs::set_permissions(&swaymsg, fs::Permissions::from_mode(0o700)).unwrap();
        assert_eq!(running_con_id("foot.desktop", Some(&desktop), &swaymsg), Some(42));
        assert_eq!(running_con_id("other.desktop", None, &swaymsg), None);
        fs::remove_dir_all(dir).unwrap();
    }

    /// The riskiest assumption this feature makes, proven against the real
    /// `gio`/`glib` runtime rather than reasoned about: `AppLaunchContext`'s
    /// `launched` signal fires synchronously inside `launch()` itself, with
    /// no `GMainLoop` iterating on this thread, and its `pid` platform-data
    /// key names the actual spawned process -- not a value only a running
    /// main loop would ever deliver, and not a wrapper process's pid.
    #[test]
    fn launch_selected_captures_the_real_spawned_pid_with_no_glib_main_loop_running() {
        let dir = std::env::temp_dir().join(format!(
            "k230-launch-selected-{}-{}",
            std::process::id(),
            std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .unwrap()
                .as_nanos()
        ));
        fs::create_dir_all(&dir).unwrap();
        let swaymsg = dir.join("swaymsg");
        fs::write(&swaymsg, "#!/bin/sh\nexit 0\n").unwrap();
        fs::set_permissions(&swaymsg, fs::Permissions::from_mode(0o700)).unwrap();
        let marker = dir.join("marker");
        let desktop = dir.join("fixture.desktop");
        fs::write(
            &desktop,
            format!(
                "[Desktop Entry]\nType=Application\nName=Fixture\nExec=/bin/sh -c 'echo $$ >{}; sleep 5'\n",
                marker.display()
            ),
        )
        .unwrap();
        let outcome = launch_selected(&desktop, &swaymsg).expect("launch_selected");
        let LaunchOutcome::Spawned(pid) = outcome else {
            panic!("expected LaunchOutcome::Spawned, got {outcome:?}");
        };
        let deadline = Instant::now() + Duration::from_secs(2);
        while !marker.exists() && Instant::now() < deadline {
            thread::sleep(Duration::from_millis(20));
        }
        let observed_pid: i32 = fs::read_to_string(&marker)
            .expect("spawned process should have written its own pid")
            .trim()
            .parse()
            .unwrap();
        unsafe {
            libc::kill(observed_pid, libc::SIGKILL);
        }
        assert_eq!(
            pid,
            Some(observed_pid),
            "the captured pid must be the real spawned process, with no shell-wrapper indirection"
        );
        fs::remove_dir_all(&dir).unwrap();
    }

    #[test]
    fn spawn_splash_watcher_ignores_events_with_no_swaysock_and_never_signals() {
        // With `SWAYSOCK` unset (or pointing nowhere), the watcher thread
        // must degrade to silence -- the splash's own `SPLASH_TIMEOUT` is
        // the fallback -- rather than panicking or spuriously reporting a
        // match/failure.
        let previous = std::env::var_os("SWAYSOCK");
        unsafe {
            std::env::remove_var("SWAYSOCK");
        }
        let (sender, receiver) = mpsc::channel::<(u64, SplashSignal)>();
        let stop = spawn_splash_watcher(SplashTarget::LaunchOrder, None, 1, sender);
        let deadline = Instant::now() + Duration::from_millis(500);
        let mut received = None;
        while Instant::now() < deadline {
            if let Ok(message) = receiver.try_recv() {
                received = Some(message);
                break;
            }
            thread::sleep(Duration::from_millis(10));
        }
        assert_eq!(received, None, "no SWAYSOCK must never fabricate a signal");
        stop.store(true, Ordering::Relaxed);
        if let Some(value) = previous {
            unsafe {
                std::env::set_var("SWAYSOCK", value);
            }
        }
    }

    #[test]
    fn splash_window_event_matches_by_pid_through_the_real_thin_wrapper() {
        // An exact pid match never touches `/proc` at all (see
        // `pid_or_ancestor`'s own short-circuit), so this is deterministic
        // regardless of whatever else happens to be running on the host.
        let event = sway_ipc::WindowEvent {
            change: "new".into(),
            pid: Some(4242),
        };
        assert!(splash_window_event_matches(SplashTarget::Pid(4242), &event));
        // `i32::MAX` almost certainly names no real process at all, so the
        // real `sway_ipc::parent_pid`'s `/proc` read fails deterministically
        // on any host -- unlike an arbitrary low pid, which could coincide
        // with a real, shallow process tree (a container's own pid 1 child,
        // say) and reach the target within the bounded walk by accident.
        let bogus_event = sway_ipc::WindowEvent {
            change: "new".into(),
            pid: Some(i32::MAX),
        };
        assert!(!splash_window_event_matches(SplashTarget::Pid(1), &bogus_event));
        let no_pid_event = sway_ipc::WindowEvent {
            change: "new".into(),
            pid: None,
        };
        assert!(splash_window_event_matches(
            SplashTarget::LaunchOrder,
            &no_pid_event
        ));
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
