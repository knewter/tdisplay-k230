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
        .render(still, width, height, FitMode::Crop)
        .map(|_| ())
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
    appearance_pending: bool,
    reveal: RevealState,
    input_ready: bool,
    reduced_motion: bool,
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
        if self.appearance_pending || !self.wallpaper.configured || self.wallpaper.frame_pending {
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
        let rendered = if let Some(path) = self.wallpaper_path.as_deref() {
            self.background_cache
                .render(path, width, height, FitMode::Crop)
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
        if self.route != route {
            self.nav = DrawerNavigation::default();
        }
        self.route = route;
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
        self.route = message.surface;
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
        if ready == self.input_ready {
            return;
        }
        let Some(layer) = self.layer.as_ref() else {
            return;
        };
        let Ok(region) = Region::new(&self.compositor) else {
            return;
        };
        if ready {
            let y = if self.route == Route::Drawer {
                (self.height as f64 * 0.19) as i32
            } else {
                0
            };
            let bottom = if self.route == Route::Shade {
                (self.height as f64 * 0.65) as i32
            } else {
                self.height as i32
            };
            region.add(0, y, self.width as i32, bottom - y);
        }
        layer
            .wl_surface()
            .set_input_region(Some(region.wl_region()));
        self.input_ready = ready;
    }

    fn hide(&mut self) {
        self.touch.cancel();
        self.nav = DrawerNavigation::default();
        self.reveal.clear();
        self.layer.take();
        self.configured = false;
        self.frame_pending = false;
        self.dirty = false;
        self.buffers.clear();
        self.input_ready = false;
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
            self.log("touch-capability-lost");
        }
    }
    fn remove_seat(&mut self, _: &Connection, _: &QueueHandle<Self>, _: wl_seat::WlSeat) {}
}

impl TouchHandler for ShellClient {
    fn down(
        &mut self,
        _: &Connection,
        _qh: &QueueHandle<Self>,
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
                self.log(&format!("touch-down {id} {:.1} {:.1}", pos.0, pos.1));
                if self.route == Route::Drawer && self.input_ready {
                    self.nav.down(id, pos, time_ms);
                }
            } else {
                self.log("touch-second-cancel");
                self.nav.cancel();
            }
            // The contact itself is invisible; only a changed scene paints.
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
            self.log(&format!("touch-up {id}"));
            if self.route == Route::Drawer && self.input_ready {
                match self
                    .nav
                    .up(id, point, time_ms, self.height, self.apps.len())
                {
                    Some(DrawerAction::Launch(index)) => self.launch_app(index),
                    Some(DrawerAction::Close) => self.hide(),
                    None => {}
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
            self.log(&format!("touch-move {id} {:.1} {:.1}", pos.0, pos.1));
            if self.route == Route::Drawer
                && self.input_ready
                && self
                    .nav
                    .motion(id, pos, time_ms, self.height, self.apps.len())
            {
                self.dirty = true;
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
    let conn = Connection::connect_to_env().map_err(|e| e.to_string())?;
    let (globals, mut queue) = registry_queue_init(&conn).map_err(|e| e.to_string())?;
    let qh = queue.handle();
    let compositor = CompositorState::bind(&globals, &qh).map_err(|e| e.to_string())?;
    let layer_shell = LayerShell::bind(&globals, &qh).map_err(|e| e.to_string())?;
    let shm = Shm::bind(&globals, &qh).map_err(|e| e.to_string())?;
    let pool = SlotPool::new(568 * 1232 * 4 * 5, &shm).map_err(|e| e.to_string())?;
    let (launch_sender, launch_results) = mpsc::channel();
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
        wallpaper_path: appearance
            .active()
            .and_then(|snapshot| snapshot.background.clone()),
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
        appearance_pending: false,
        reveal: RevealState::default(),
        input_ready: false,
        reduced_motion: reduced_motion_enabled(
            std::env::var("K230_SETTINGS_REDUCED_MOTION")
                .ok()
                .as_deref(),
        ),
    };
    state.renderer.set_appearance(appearance.active().cloned());
    if !state.ensure_wallpaper(&qh) {
        return Err("wallpaper layer unavailable".into());
    }
    state.log("ready-idle");
    loop {
        queue
            .dispatch_pending(&mut state)
            .map_err(|e| e.to_string())?;
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
        match appearance.receive() {
            Ok(Some(event)) => match event.phase {
                AppearancePhase::Prepare => {
                    let geometry = state
                        .wallpaper
                        .configured
                        .then_some((state.wallpaper.width, state.wallpaper.height));
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
                    if let Err(error) = appearance_renderable(
                        event.snapshot.as_ref(),
                        &mut state.background_cache,
                        geometry,
                    ) {
                        state.log(&format!("appearance-commit-rejected {error}"));
                        let _ = appearance.respond(event, false);
                    } else {
                        state.wallpaper_path = event
                            .snapshot
                            .as_ref()
                            .and_then(|snapshot| snapshot.background.clone());
                        state.renderer.set_appearance(event.snapshot.clone());
                        state.appearance_pending = true;
                        state.dirty = true;
                        state.wallpaper.dirty = true;
                        pending_appearance = Some((event, Instant::now(), previous));
                    }
                }
            },
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
            let ready =
                state.wallpaper.configured && !state.wallpaper.frame_pending && overlay_ready;
            if !ready && started.elapsed() < Duration::from_millis(1400) {
                pending_appearance = Some((event, started, previous));
            } else {
                let accepted = if ready {
                    state.appearance_pending = false;
                    let background = state.draw_wallpaper(&qh);
                    let foreground = state.layer.is_none() || state.draw(&qh);
                    state.appearance_pending = true;
                    background && foreground && queue.flush().is_ok()
                } else {
                    false
                };
                if !accepted {
                    state.wallpaper_path = previous
                        .as_ref()
                        .and_then(|snapshot| snapshot.background.clone());
                    state.renderer.set_appearance(previous);
                    state.dirty = true;
                    state.wallpaper.dirty = true;
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
            || routes.has_line()
            || pending_appearance.is_some()
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
        _ => Err(
            "usage: k230-shell-rust --serve | --surface drawer|shade|settings|hide | --render-fixture drawer|shade|settings OUTPUT.png".into(),
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
