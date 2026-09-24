//! Opt-in layer-shell/SHM client. Live app pixels stay with Sway.
//! The layer/event plumbing began from the pinned Rust probe, which follows
//! Smithay Client Toolkit's MIT-licensed v0.20.0 simple_layer example.
use k230_shell_rust::{
    catalog::{installed_apps, AppEntry},
    configure_size, frame_bytes,
    protocol::{Phase, RevealMessage, RevealState, MAX_LINE},
    released_slot,
    render::{export_png, RendererCache},
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
    time::{Duration, Instant},
};
use wayland_client::{
    globals::registry_queue_init,
    protocol::{wl_output, wl_seat, wl_shm, wl_surface, wl_touch},
    Connection, QueueHandle,
};

const SOCKET_NAME: &str = "k230-shell-rust.sock";
const MAX_PENDING_BYTES: usize = 4096;
const PEER_IDLE_TIMEOUT: Duration = Duration::from_secs(5);

fn socket_path() -> Result<PathBuf, String> {
    let runtime = std::env::var_os("XDG_RUNTIME_DIR").ok_or("XDG_RUNTIME_DIR is unset")?;
    Ok(PathBuf::from(runtime).join(SOCKET_NAME))
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
    renderer: RendererCache,
    reveal: RevealState,
    input_ready: bool,
}

impl ShellClient {
    fn log(&self, event: &str) {
        eprintln!(
            "rust-shell {}ms {event}",
            self.started.elapsed().as_millis()
        );
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
        if !self.reveal.apply(message, now, false) {
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
        self.draw(qh);
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
        self.reveal.clear();
        self.layer.take();
        self.configured = false;
        self.frame_pending = false;
        self.dirty = false;
        self.buffers.clear();
        self.input_ready = false;
        self.log("unmap");
    }

    fn draw(&mut self, qh: &QueueHandle<Self>) {
        if !self.configured || self.frame_pending || self.layer.is_none() {
            return;
        }
        let Some(size) = frame_bytes(self.width, self.height) else {
            self.log("invalid-geometry");
            return;
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
                return;
            }
            let Ok((buffer, canvas)) = self.pool.create_buffer(
                self.width as i32,
                self.height as i32,
                stride,
                wl_shm::Format::Argb8888,
            ) else {
                self.log("shm-allocate-failed");
                return;
            };
            if canvas.len() != size {
                self.log("shm-size-mismatch");
                return;
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
            self.width,
            self.height,
            self.route,
            &self.apps,
            progress,
        ) {
            self.log(&format!("render-failed {error}"));
            return;
        }
        self.input_region();
        let layer = self.layer.as_ref().expect("mapped");
        layer
            .wl_surface()
            .damage_buffer(0, 0, self.width as i32, self.height as i32);
        layer.wl_surface().frame(qh, layer.wl_surface().clone());
        if self.buffers[index].attach_to(layer.wl_surface()).is_err() {
            self.log("shm-attach-failed");
            return;
        }
        layer.commit();
        self.frame_pending = true;
        self.dirty = false;
        self.log("commit");
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
        if !self
            .layer
            .as_ref()
            .is_some_and(|l| l.wl_surface() == surface)
        {
            return;
        }
        self.frame_pending = false;
        self.log("frame-done");
        if self.dirty {
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
    fn closed(&mut self, _: &Connection, _: &QueueHandle<Self>, _: &LayerSurface) {
        self.hide();
    }
    fn configure(
        &mut self,
        _: &Connection,
        qh: &QueueHandle<Self>,
        _: &LayerSurface,
        configure: LayerSurfaceConfigure,
        _: u32,
    ) {
        let (width, height) = configure.new_size;
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
        qh: &QueueHandle<Self>,
        _: &wl_touch::WlTouch,
        _: u32,
        _: u32,
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
            } else {
                self.log("touch-second-cancel");
            }
            self.dirty = true;
            self.draw(qh);
        }
    }
    fn up(
        &mut self,
        _: &Connection,
        qh: &QueueHandle<Self>,
        _: &wl_touch::WlTouch,
        _: u32,
        _: u32,
        id: i32,
    ) {
        if self.touch.up(id) {
            self.log(&format!("touch-up {id}"));
            self.dirty = true;
            self.draw(qh);
        }
    }
    fn motion(
        &mut self,
        _: &Connection,
        qh: &QueueHandle<Self>,
        _: &wl_touch::WlTouch,
        _: u32,
        id: i32,
        pos: (f64, f64),
    ) {
        if self.touch.motion(id, pos) {
            self.log(&format!("touch-move {id} {:.1} {:.1}", pos.0, pos.1));
            self.dirty = true;
            self.draw(qh);
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
    let conn = Connection::connect_to_env().map_err(|e| e.to_string())?;
    let (globals, mut queue) = registry_queue_init(&conn).map_err(|e| e.to_string())?;
    let qh = queue.handle();
    let compositor = CompositorState::bind(&globals, &qh).map_err(|e| e.to_string())?;
    let layer_shell = LayerShell::bind(&globals, &qh).map_err(|e| e.to_string())?;
    let shm = Shm::bind(&globals, &qh).map_err(|e| e.to_string())?;
    let pool = SlotPool::new(568 * 1232 * 4 * 3, &shm).map_err(|e| e.to_string())?;
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
        renderer: RendererCache::default(),
        reveal: RevealState::default(),
        input_ready: false,
    };
    state.log("ready-idle");
    loop {
        queue
            .dispatch_pending(&mut state)
            .map_err(|e| e.to_string())?;
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
        if state.dirty && !state.frame_pending {
            state.draw(&qh);
        }
        queue.flush().map_err(|e| e.to_string())?;
        let Some(read_guard) = queue.prepare_read() else {
            continue;
        };
        let peer_fd = routes.peer.as_ref().map_or(-1, |p| p.stream.as_raw_fd());
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
        ];
        let timeout = if state.reveal.settling() || routes.has_line() {
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
        if routes.has_line()
            || fds[2].revents & (libc::POLLIN | libc::POLLHUP) != 0
            || routes
                .peer
                .as_ref()
                .is_some_and(|p| Instant::now() >= p.deadline)
        {
            match routes.receive() {
                Some(Received::Route(route, mut peer)) => {
                    let mapped = state.show(&qh, route);
                    let reply: &[u8] = if mapped && queue.flush().is_ok() {
                        b"OK\n"
                    } else {
                        b"ERR\n"
                    };
                    let _ = peer.write_all(reply);
                }
                Some(Received::Reveal(message)) => state.reveal_message(&qh, message),
                Some(Received::Abort) => {
                    state
                        .reveal
                        .eof(state.started.elapsed().as_millis() as u64, false);
                    state.dirty = true;
                }
                None => {}
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
        drop(client);
        assert!(matches!(server.receive(), Some(Received::Abort)));

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
}
