//! egui software probe: the Qt Quick probe's scene (nix/qtquick-software-probe/Probe.qml)
//! drawn by egui, rasterised by egui_software_backend into a wl_shm buffer.
//! No OpenGL, Vulkan, winit or softbuffer is linked. Events are JSONL on stdout in
//! the schema tools/qtquick_analysis.py reads (start, first_frame, input, commit),
//! with `r` (microseconds to run, tessellate and rasterise the frame) added to commits.

use std::os::fd::{AsFd, AsRawFd};
use std::time::{Duration, Instant};

use egui::{Align2, Color32, FontId, Pos2, Rect, Sense, Stroke, Vec2};
use egui_software_backend::{BufferMutRef, ColorFieldOrder, EguiSoftwareRender};
use wayland_client::protocol::{
    wl_buffer, wl_callback, wl_compositor, wl_pointer, wl_registry, wl_seat, wl_shm, wl_shm_pool, wl_surface, wl_touch,
};
use wayland_client::{delegate_noop, Connection, Dispatch, QueueHandle, WEnum};
use wayland_protocols::wp::text_input::zv3::client::{zwp_text_input_manager_v3, zwp_text_input_v3};
use wayland_protocols::xdg::shell::client::{xdg_surface, xdg_toplevel, xdg_wm_base};

// Geometry mirrors Probe.qml; tests/test_egui_probe_scene.py compares these with it.
const SC_WIDTH: i32 = 1232;
const SC_HEIGHT: i32 = 568;
const SC_BG: u32 = 0x161b28;
const SC_HEADER_H: f32 = 80.0;
const SC_HEADER_COLOR: u32 = 0x26344c;
const SC_LIST_X: f32 = 20.0;
const SC_LIST_Y: f32 = 96.0;
const SC_LIST_W: f32 = 580.0;
const SC_LIST_H: f32 = 452.0;
const SC_ROW_COUNT: usize = 20;
const SC_ROW_H: f32 = 74.0;
const SC_ROW_SPACING: f32 = 12.0;
const SC_ROW_COLOR: u32 = 0x31415d;
const SC_ROW_SELECTED: u32 = 0x4b6ea8;
const SC_EDITOR_X: f32 = 628.0;
const SC_EDITOR_Y: f32 = 96.0;
const SC_EDITOR_W: f32 = 584.0;
const SC_EDITOR_H: f32 = 90.0;
const SC_MOVER_Y: f32 = 206.0;
const SC_MOVER_W: f32 = 172.0;
const SC_MOVER_H: f32 = 90.0;
const SC_MOVER_X_LEFT: f32 = 628.0;
const SC_MOVER_X_RIGHT: f32 = 1040.0;
const SC_ANIM_S: f32 = 0.280;
const SC_PANEL_X: f32 = 628.0;
const SC_PANEL_Y: f32 = 316.0;
const SC_PANEL_W: f32 = 584.0;
const SC_PANEL_H: f32 = 112.0;
const SC_SWATCH_X: f32 = 740.0;
const SC_SWATCH_Y: f32 = 448.0;
const SC_SWATCH_W: f32 = 96.0;
const SC_SWATCH_H: f32 = 64.0;
const SC_SWATCH_COLOR: u32 = 0xff5b79;
const TEXT_COLOR: u32 = 0xf2f6ff;

fn rgb(c: u32) -> Color32 {
    Color32::from_rgb((c >> 16) as u8, (c >> 8) as u8, c as u8)
}

fn mono_ms() -> u64 {
    let mut ts = libc::timespec { tv_sec: 0, tv_nsec: 0 };
    unsafe { libc::clock_gettime(libc::CLOCK_MONOTONIC, &mut ts) };
    ts.tv_sec as u64 * 1000 + ts.tv_nsec as u64 / 1_000_000
}

struct Log {
    count: u32,
}
impl Log {
    fn ev(&mut self, name: &str, extra: &str) {
        if self.count >= 40000 {
            return;
        }
        self.count += 1;
        println!("{{\"e\":\"{}\",\"t\":{}{}{}}}", name, mono_ms(), if extra.is_empty() { "" } else { "," }, extra);
    }
}

/// The scene's own state: what the Qt probe keeps in QML properties.
struct Scene {
    selected: bool,
    moved: bool,
    text: String,
    tile: Option<egui::TextureHandle>,
    taps: u32,
}

fn tile_image() -> egui::ColorImage {
    // The same 32x32 checker as tools/generate-qtquick-probe-tile.py.
    let mut px = Vec::with_capacity(32 * 32);
    for y in 0..32 {
        for x in 0..32 {
            px.push(if (x / 8 + y / 8) % 2 == 1 { Color32::from_rgb(255, 186, 93) } else { Color32::from_rgb(67, 136, 207) });
        }
    }
    egui::ColorImage::new([32, 32], px)
}

fn draw_scene(ctx: &egui::Context, s: &mut Scene) {
    if s.tile.is_none() {
        s.tile = Some(ctx.load_texture("tile", tile_image(), egui::TextureOptions::NEAREST));
    }
    let frame = egui::Frame::NONE.fill(rgb(SC_BG));
    egui::CentralPanel::default().frame(frame).show(ctx, |ui| {
        let painter = ui.painter().clone();
        // Header.
        painter.rect_filled(Rect::from_min_size(Pos2::ZERO, Vec2::new(SC_WIDTH as f32, SC_HEADER_H)), 0.0, rgb(SC_HEADER_COLOR));
        painter.text(
            Pos2::new(SC_WIDTH as f32 / 2.0, SC_HEADER_H / 2.0),
            Align2::CENTER_CENTER,
            "egui software probe",
            FontId::proportional(30.0),
            rgb(TEXT_COLOR),
        );
        // List.
        let list_rect = Rect::from_min_size(Pos2::new(SC_LIST_X, SC_LIST_Y), Vec2::new(SC_LIST_W, SC_LIST_H));
        let mut list_ui = ui.new_child(egui::UiBuilder::new().max_rect(list_rect));
        list_ui.set_clip_rect(list_rect);
        egui::ScrollArea::vertical().id_salt("list").auto_shrink([false, false]).scroll_bar_visibility(egui::scroll_area::ScrollBarVisibility::AlwaysHidden).show(&mut list_ui, |ui| {
            ui.spacing_mut().item_spacing.y = SC_ROW_SPACING;
            for i in 0..SC_ROW_COUNT {
                let (rect, resp) = ui.allocate_exact_size(Vec2::new(SC_LIST_W, SC_ROW_H), Sense::click());
                let color = if i == 0 && s.selected { SC_ROW_SELECTED } else { SC_ROW_COLOR };
                ui.painter().rect_filled(rect, 12.0, rgb(color));
                ui.painter().text(rect.center(), Align2::CENTER_CENTER, format!("Scroll row {}", i + 1), FontId::proportional(24.0), rgb(TEXT_COLOR));
                if resp.clicked() {
                    s.selected = !s.selected;
                    s.taps += 1;
                }
            }
        });
        // Editor.
        let editor = Rect::from_min_size(Pos2::new(SC_EDITOR_X, SC_EDITOR_Y), Vec2::new(SC_EDITOR_W, SC_EDITOR_H));
        painter.rect_filled(editor, 12.0, rgb(SC_ROW_COLOR));
        let mut ed_ui = ui.new_child(egui::UiBuilder::new().max_rect(editor.shrink(22.0)));
        ed_ui.visuals_mut().selection.bg_fill = Color32::from_rgb(0x79, 0xa8, 0xef);
        ed_ui.add_sized(
            editor.shrink(22.0).size(),
            egui::TextEdit::singleline(&mut s.text).frame(egui::Frame::NONE).font(FontId::proportional(27.0)).text_color(Color32::WHITE).vertical_align(egui::Align::Center),
        );
        // Mover: eased 280 ms retargetable animation of x and opacity.
        let t = ctx.animate_bool_with_time_and_easing(egui::Id::new("mover"), s.moved, SC_ANIM_S, egui::emath::easing::cubic_out);
        let x = SC_MOVER_X_LEFT + (SC_MOVER_X_RIGHT - SC_MOVER_X_LEFT) * t;
        let mover = Rect::from_min_size(Pos2::new(x, SC_MOVER_Y), Vec2::new(SC_MOVER_W, SC_MOVER_H));
        let (c0, c1) = ((0xf9u8, 0xc6u8, 0x7au8), (0x9bu8, 0xcfu8, 0xffu8));
        let mix = |a: u8, b: u8| (a as f32 + (b as f32 - a as f32) * t) as u8;
        let alpha = ((1.0 - 0.3 * t) * 255.0) as u8;
        let col = Color32::from_rgba_unmultiplied(mix(c0.0, c1.0), mix(c0.1, c1.1), mix(c0.2, c1.2), alpha);
        painter.rect_filled(mover, 14.0, col);
        painter.text(mover.center(), Align2::CENTER_CENTER, "Tap / retarget", FontId::proportional(19.0), Color32::from_rgb(0x18, 0x24, 0x3a));
        let hit = Rect::from_min_size(Pos2::new(x, SC_MOVER_Y), Vec2::new(SC_MOVER_W, SC_MOVER_H));
        if ui.interact(hit, egui::Id::new("mover-hit"), Sense::click()).clicked() {
            s.moved = !s.moved;
            s.taps += 1;
        }
        // Panel with the tile and caption, and the solid swatch.
        let panel = Rect::from_min_size(Pos2::new(SC_PANEL_X, SC_PANEL_Y), Vec2::new(SC_PANEL_W, SC_PANEL_H));
        painter.rect_filled(panel, 12.0, rgb(SC_ROW_COLOR));
        if let Some(tile) = &s.tile {
            let r = Rect::from_min_size(Pos2::new(SC_PANEL_X + 20.0, SC_PANEL_Y + (SC_PANEL_H - 64.0) / 2.0), Vec2::splat(64.0));
            painter.image(tile.id(), r, Rect::from_min_max(Pos2::ZERO, Pos2::new(1.0, 1.0)), Color32::WHITE);
        }
        painter.text(
            Pos2::new(SC_PANEL_X + 100.0, SC_PANEL_Y + SC_PANEL_H / 2.0),
            Align2::LEFT_CENTER,
            "Software-safe solid rectangle",
            FontId::proportional(19.0),
            rgb(TEXT_COLOR),
        );
        painter.rect_filled(Rect::from_min_size(Pos2::new(SC_SWATCH_X, SC_SWATCH_Y), Vec2::new(SC_SWATCH_W, SC_SWATCH_H)), 0.0, rgb(SC_SWATCH_COLOR));
        painter.rect_stroke(panel, 12.0, Stroke::NONE, egui::StrokeKind::Inside);
    });
}

struct Buffer {
    wl: wl_buffer::WlBuffer,
    ptr: *mut u8,
    busy: bool,
}

struct App {
    log: Log,
    compositor: Option<wl_compositor::WlCompositor>,
    shm: Option<wl_shm::WlShm>,
    wm: Option<xdg_wm_base::XdgWmBase>,
    seat: Option<wl_seat::WlSeat>,
    ti_mgr: Option<zwp_text_input_manager_v3::ZwpTextInputManagerV3>,
    ti: Option<zwp_text_input_v3::ZwpTextInputV3>,
    surface: Option<wl_surface::WlSurface>,
    xdg_surface: Option<xdg_surface::XdgSurface>,
    configured: bool,
    closing: bool,
    bufs: Vec<Buffer>,
    frame_cb: Option<wl_callback::WlCallback>,
    ctx: egui::Context,
    render: EguiSoftwareRender,
    scene: Scene,
    events: Vec<egui::Event>,
    start: Instant,
    want_draw: bool,
    first_logged: bool,
    ti_enabled: bool,
    ti_serial: u32,
    ptr_pos: Pos2,
    ptr_down: bool,
    touch_id: Option<i32>,
    commits: u32,
    ti_pending_commit: Option<String>,
    ti_pending_delete: u32,
    repaint_at: Option<Instant>,
    last_buf: usize,
}

impl App {
    fn input(&mut self, kind: &str) {
        self.log.ev("input", &format!("\"k\":\"{}\"", kind));
        self.want_draw = true;
    }

    fn get_buffer(&mut self, qh: &QueueHandle<App>) -> Option<usize> {
        if let Some(i) = self.bufs.iter().position(|b| !b.busy) {
            return Some(i);
        }
        if self.bufs.len() >= 3 {
            return None;
        }
        let size = (SC_WIDTH * SC_HEIGHT * 4) as usize;
        let fd = unsafe { libc::memfd_create(c"egui-software-probe".as_ptr(), libc::MFD_CLOEXEC) };
        if fd < 0 || unsafe { libc::ftruncate(fd, size as libc::off_t) } < 0 {
            return None;
        }
        let ptr = unsafe { libc::mmap(std::ptr::null_mut(), size, libc::PROT_READ | libc::PROT_WRITE, libc::MAP_SHARED, fd, 0) };
        if ptr == libc::MAP_FAILED {
            return None;
        }
        let owned = unsafe { std::os::fd::OwnedFd::from_raw_fd_compat(fd) };
        let pool = self.shm.as_ref()?.create_pool(owned.as_fd(), size as i32, qh, ());
        let wl = pool.create_buffer(0, SC_WIDTH, SC_HEIGHT, SC_WIDTH * 4, wl_shm::Format::Xrgb8888, qh, self.bufs.len());
        pool.destroy();
        self.bufs.push(Buffer { wl, ptr: ptr as *mut u8, busy: false });
        Some(self.bufs.len() - 1)
    }

    fn draw(&mut self, qh: &QueueHandle<App>) {
        if !self.configured || self.frame_cb.is_some() || self.surface.is_none() {
            return;
        }
        let Some(bi) = self.get_buffer(qh) else { return };
        let t0 = Instant::now();
        // Input events that piled up while a frame callback was pending are fed one
        // press/release at a time: egui needs to see a press in a pass of its own
        // before the matching release, or a short tap is lost.
        let mut batches: Vec<Vec<egui::Event>> = vec![Vec::new()];
        for ev in std::mem::take(&mut self.events) {
            let boundary = matches!(ev, egui::Event::PointerButton { .. });
            batches.last_mut().unwrap().push(ev);
            if boundary {
                batches.push(Vec::new());
            }
        }
        if batches.len() > 1 && batches.last().map_or(false, |b| b.is_empty()) {
            batches.pop();
        }
        let ctx = self.ctx.clone();
        let mut textures = egui::TexturesDelta::default();
        let mut out = None;
        for events in batches {
            let raw = egui::RawInput {
                screen_rect: Some(Rect::from_min_size(Pos2::ZERO, Vec2::new(SC_WIDTH as f32, SC_HEIGHT as f32))),
                time: Some(self.start.elapsed().as_secs_f64()),
                events,
                focused: true,
                ..Default::default()
            };
            let mut o = ctx.run(raw, |ctx| draw_scene(ctx, &mut self.scene));
            textures.append(std::mem::take(&mut o.textures_delta));
            out = Some(o);
        }
        let mut out = out.unwrap();
        out.textures_delta = textures;
        let prims = ctx.tessellate(out.shapes, out.pixels_per_point);
        let t1 = Instant::now();
        let data = unsafe { std::slice::from_raw_parts_mut(self.bufs[bi].ptr as *mut [u8; 4], (SC_WIDTH * SC_HEIGHT) as usize) };
        let mut buf = BufferMutRef::new(data, SC_WIDTH as usize, SC_HEIGHT as usize);
        self.render.render(&mut buf, &prims, &out.textures_delta, out.pixels_per_point);
        let t2 = Instant::now();
        // Text input follows egui's focus.
        let wants = ctx.egui_wants_keyboard_input();
        self.sync_text_input(wants);
        // Repaint scheduling from egui.
        let delay = out.viewport_output.values().next().map(|v| v.repaint_delay).unwrap_or(Duration::MAX);
        self.want_draw = delay.is_zero();
        self.repaint_at = if delay.is_zero() || delay == Duration::MAX { None } else { Some(Instant::now() + delay) };
        let surface = self.surface.as_ref().unwrap();
        surface.attach(Some(&self.bufs[bi].wl), 0, 0);
        surface.damage_buffer(0, 0, SC_WIDTH, SC_HEIGHT);
        self.frame_cb = Some(surface.frame(qh, ()));
        self.bufs[bi].busy = true;
        self.last_buf = bi;
        surface.commit();
        self.commits += 1;
        let run_us = (t1 - t0).as_micros();
        let rast_us = (t2 - t1).as_micros();
        self.log.ev("commit", &format!("\"r\":{},\"run\":{},\"rast\":{}", run_us + rast_us, run_us, rast_us));
        if !self.first_logged {
            self.first_logged = true;
            self.log.ev("first_frame", "");
        }
    }

    fn sync_text_input(&mut self, wants: bool) {
        let Some(ti) = &self.ti else { return };
        if wants != self.ti_enabled {
            if wants {
                ti.enable();
                ti.set_content_type(zwp_text_input_v3::ContentHint::None, zwp_text_input_v3::ContentPurpose::Normal);
                self.log.ev("text_input_enable", "");
            } else {
                ti.disable();
                self.log.ev("text_input_disable", "");
            }
            ti.commit();
            self.ti_serial += 1;
            self.ti_enabled = wants;
        }
    }

    fn pointer_event(&mut self, pos: Pos2, down: Option<bool>) {
        self.ptr_pos = pos;
        self.events.push(egui::Event::PointerMoved(pos));
        if let Some(d) = down {
            self.events.push(egui::Event::PointerButton {
                pos,
                button: egui::PointerButton::Primary,
                pressed: d,
                modifiers: egui::Modifiers::NONE,
            });
        }
    }
}

trait FromRawFdCompat {
    unsafe fn from_raw_fd_compat(fd: i32) -> Self;
}
impl FromRawFdCompat for std::os::fd::OwnedFd {
    unsafe fn from_raw_fd_compat(fd: i32) -> Self {
        use std::os::fd::FromRawFd;
        std::os::fd::OwnedFd::from_raw_fd(fd)
    }
}

impl Dispatch<wl_registry::WlRegistry, ()> for App {
    fn event(state: &mut Self, reg: &wl_registry::WlRegistry, event: wl_registry::Event, _: &(), _: &Connection, qh: &QueueHandle<Self>) {
        if let wl_registry::Event::Global { name, interface, version } = event {
            match interface.as_str() {
                "wl_compositor" => state.compositor = Some(reg.bind(name, version.min(4), qh, ())),
                "wl_shm" => state.shm = Some(reg.bind(name, 1, qh, ())),
                "xdg_wm_base" => state.wm = Some(reg.bind(name, version.min(2), qh, ())),
                "wl_seat" => state.seat = Some(reg.bind(name, version.min(5), qh, ())),
                "zwp_text_input_manager_v3" => state.ti_mgr = Some(reg.bind(name, 1, qh, ())),
                _ => {}
            }
        }
    }
}
delegate_noop!(App: ignore wl_compositor::WlCompositor);
delegate_noop!(App: ignore wl_shm::WlShm);
delegate_noop!(App: ignore wl_shm_pool::WlShmPool);
delegate_noop!(App: ignore wl_surface::WlSurface);
delegate_noop!(App: ignore zwp_text_input_manager_v3::ZwpTextInputManagerV3);

impl Dispatch<wl_buffer::WlBuffer, usize> for App {
    fn event(state: &mut Self, _: &wl_buffer::WlBuffer, event: wl_buffer::Event, idx: &usize, _: &Connection, _: &QueueHandle<Self>) {
        if let wl_buffer::Event::Release = event {
            if let Some(b) = state.bufs.get_mut(*idx) {
                b.busy = false;
            }
        }
    }
}
impl Dispatch<wl_callback::WlCallback, ()> for App {
    fn event(state: &mut Self, _: &wl_callback::WlCallback, event: wl_callback::Event, _: &(), _: &Connection, qh: &QueueHandle<Self>) {
        if let wl_callback::Event::Done { .. } = event {
            state.frame_cb = None;
            if state.want_draw {
                state.draw(qh);
            }
        }
    }
}
impl Dispatch<xdg_wm_base::XdgWmBase, ()> for App {
    fn event(_: &mut Self, wm: &xdg_wm_base::XdgWmBase, event: xdg_wm_base::Event, _: &(), _: &Connection, _: &QueueHandle<Self>) {
        if let xdg_wm_base::Event::Ping { serial } = event {
            wm.pong(serial);
        }
    }
}
impl Dispatch<xdg_surface::XdgSurface, ()> for App {
    fn event(state: &mut Self, s: &xdg_surface::XdgSurface, event: xdg_surface::Event, _: &(), _: &Connection, qh: &QueueHandle<Self>) {
        if let xdg_surface::Event::Configure { serial } = event {
            s.ack_configure(serial);
            if !state.configured {
                state.configured = true;
                state.log.ev("configured", "");
                state.want_draw = true;
                state.draw(qh);
            }
        }
    }
}
impl Dispatch<xdg_toplevel::XdgToplevel, ()> for App {
    fn event(state: &mut Self, _: &xdg_toplevel::XdgToplevel, event: xdg_toplevel::Event, _: &(), _: &Connection, _: &QueueHandle<Self>) {
        if let xdg_toplevel::Event::Close = event {
            state.closing = true;
        }
    }
}
impl Dispatch<wl_seat::WlSeat, ()> for App {
    fn event(state: &mut Self, seat: &wl_seat::WlSeat, event: wl_seat::Event, _: &(), _: &Connection, qh: &QueueHandle<Self>) {
        if let wl_seat::Event::Capabilities { capabilities: WEnum::Value(c) } = event {
            if c.contains(wl_seat::Capability::Pointer) {
                seat.get_pointer(qh, ());
            }
            if c.contains(wl_seat::Capability::Touch) {
                seat.get_touch(qh, ());
            }
        }
        let _ = state;
    }
}
impl Dispatch<wl_pointer::WlPointer, ()> for App {
    fn event(s: &mut Self, _: &wl_pointer::WlPointer, event: wl_pointer::Event, _: &(), _: &Connection, qh: &QueueHandle<Self>) {
        match event {
            wl_pointer::Event::Motion { surface_x, surface_y, .. } => {
                s.pointer_event(Pos2::new(surface_x as f32, surface_y as f32), None);
                if s.ptr_down {
                    s.input("move");
                } else {
                    s.want_draw = true;
                }
            }
            wl_pointer::Event::Enter { surface_x, surface_y, .. } => s.pointer_event(Pos2::new(surface_x as f32, surface_y as f32), None),
            wl_pointer::Event::Button { state: WEnum::Value(st), .. } => {
                let down = st == wl_pointer::ButtonState::Pressed;
                s.ptr_down = down;
                let pos = s.ptr_pos;
                s.pointer_event(pos, Some(down));
                s.input(if down { "press" } else { "release" });
            }
            _ => return,
        }
        s.draw(qh);
    }
}
impl Dispatch<wl_touch::WlTouch, ()> for App {
    fn event(s: &mut Self, _: &wl_touch::WlTouch, event: wl_touch::Event, _: &(), _: &Connection, qh: &QueueHandle<Self>) {
        match event {
            wl_touch::Event::Down { id, x, y, .. } if s.touch_id.is_none() => {
                s.touch_id = Some(id);
                s.pointer_event(Pos2::new(x as f32, y as f32), Some(true));
                s.input("press");
            }
            wl_touch::Event::Motion { id, x, y, .. } if s.touch_id == Some(id) => {
                s.pointer_event(Pos2::new(x as f32, y as f32), None);
                s.input("move");
            }
            wl_touch::Event::Up { id, .. } if s.touch_id == Some(id) => {
                s.touch_id = None;
                let pos = s.ptr_pos;
                s.pointer_event(pos, Some(false));
                s.events.push(egui::Event::PointerGone);
                s.input("release");
            }
            _ => return,
        }
        s.draw(qh);
    }
}
impl Dispatch<zwp_text_input_v3::ZwpTextInputV3, ()> for App {
    fn event(s: &mut Self, _: &zwp_text_input_v3::ZwpTextInputV3, event: zwp_text_input_v3::Event, _: &(), _: &Connection, qh: &QueueHandle<Self>) {
        match event {
            zwp_text_input_v3::Event::CommitString { text } => s.ti_pending_commit = text,
            zwp_text_input_v3::Event::DeleteSurroundingText { before_length, .. } => s.ti_pending_delete = before_length,
            zwp_text_input_v3::Event::Done { .. } => {
                for _ in 0..std::mem::take(&mut s.ti_pending_delete) {
                    for pressed in [true, false] {
                        s.events.push(egui::Event::Key {
                            key: egui::Key::Backspace,
                            physical_key: None,
                            pressed,
                            repeat: false,
                            modifiers: egui::Modifiers::NONE,
                        });
                    }
                }
                if let Some(t) = s.ti_pending_commit.take() {
                    s.events.push(egui::Event::Text(t));
                }
                s.input("key");
                s.draw(qh);
            }
            _ => {}
        }
    }
}

fn main() {
    let mut exit_after_ms: Option<u64> = None;
    let mut dump_ppm: Option<String> = None;
    let mut args = std::env::args().skip(1);
    while let Some(a) = args.next() {
        match a.as_str() {
            "--exit-after-ms" => exit_after_ms = args.next().and_then(|v| v.parse().ok()),
            // The software rasteriser has no shader effects; accepted so one command line fits all probes.
            "--negative-effect" => {}
            // Host fixture: write the last committed frame as a binary PPM on exit.
            "--dump-ppm" => dump_ppm = args.next(),
            _ => {
                eprintln!("usage: egui-software-probe [--exit-after-ms N] [--negative-effect] [--dump-ppm PATH]");
                std::process::exit(2);
            }
        }
    }
    let conn = Connection::connect_to_env().unwrap_or_else(|e| {
        eprintln!("no wayland display: {e}");
        std::process::exit(3);
    });
    let mut queue = conn.new_event_queue::<App>();
    let qh = queue.handle();
    let display = conn.display();
    display.get_registry(&qh, ());
    let ctx = egui::Context::default();
    ctx.set_visuals(egui::Visuals::dark());
    let mut app = App {
        log: Log { count: 0 },
        compositor: None,
        shm: None,
        wm: None,
        seat: None,
        ti_mgr: None,
        ti: None,
        surface: None,
        xdg_surface: None,
        configured: false,
        closing: false,
        bufs: Vec::new(),
        frame_cb: None,
        ctx,
        render: EguiSoftwareRender::new(ColorFieldOrder::Bgra),
        scene: Scene { selected: false, moved: false, text: "Tap to edit".into(), tile: None, taps: 0 },
        events: Vec::new(),
        start: Instant::now(),
        want_draw: false,
        first_logged: false,
        ti_enabled: false,
        ti_serial: 0,
        ptr_pos: Pos2::ZERO,
        ptr_down: false,
        touch_id: None,
        commits: 0,
        ti_pending_commit: None,
        ti_pending_delete: 0,
        repaint_at: None,
        last_buf: 0,
    };
    app.log.ev("start", &format!("\"toolkit\":\"egui {}\",\"backend\":\"egui_software_backend 0.0.3\",\"route\":\"cpu-wl_shm\"", env!("CARGO_PKG_VERSION")));
    queue.roundtrip(&mut app).unwrap();
    if app.compositor.is_none() || app.shm.is_none() || app.wm.is_none() {
        eprintln!("missing wl_compositor/wl_shm/xdg_wm_base");
        std::process::exit(3);
    }
    if let (Some(mgr), Some(seat)) = (&app.ti_mgr, &app.seat) {
        app.ti = Some(mgr.get_text_input(seat, &qh, ()));
    }
    let surface = app.compositor.as_ref().unwrap().create_surface(&qh, ());
    let xs = app.wm.as_ref().unwrap().get_xdg_surface(&surface, &qh, ());
    let top = xs.get_toplevel(&qh, ());
    top.set_title("egui software probe".into());
    top.set_app_id("egui-software-probe".into());
    surface.commit();
    app.surface = Some(surface);
    app.xdg_surface = Some(xs);
    let _top = top;
    let t_start = mono_ms();
    loop {
        if app.closing {
            break;
        }
        if let Some(limit) = exit_after_ms {
            if mono_ms() - t_start >= limit {
                break;
            }
        }
        queue.dispatch_pending(&mut app).unwrap();
        if app.want_draw && app.frame_cb.is_none() {
            app.draw(&qh);
        }
        if let Some(at) = app.repaint_at {
            if Instant::now() >= at {
                app.repaint_at = None;
                app.want_draw = true;
                app.draw(&qh);
            }
        }
        let _ = conn.flush();
        let Some(guard) = queue.prepare_read() else { continue };
        let timeout_ms: i32 = {
            let mut t = if app.want_draw { 4 } else { 250 };
            if let Some(at) = app.repaint_at {
                t = t.min(at.saturating_duration_since(Instant::now()).as_millis() as i32 + 1);
            }
            if let Some(limit) = exit_after_ms {
                t = t.min((limit.saturating_sub(mono_ms() - t_start)) as i32 + 1);
            }
            t
        };
        let mut pfd = libc::pollfd { fd: guard.connection_fd().as_raw_fd(), events: libc::POLLIN, revents: 0 };
        let n = unsafe { libc::poll(&mut pfd, 1, timeout_ms) };
        if n > 0 {
            let _ = guard.read();
        } else {
            drop(guard);
        }
    }
    app.log.ev("exit", &format!("\"commits\":{}", app.commits));
    use std::io::Write;
    let _ = std::io::stdout().flush();
    if let (Some(path), Some(b)) = (dump_ppm, app.bufs.get(app.last_buf)) {
        let px = unsafe { std::slice::from_raw_parts(b.ptr, (SC_WIDTH * SC_HEIGHT * 4) as usize) };
        let mut out = format!("P6\n{} {}\n255\n", SC_WIDTH, SC_HEIGHT).into_bytes();
        for p in px.chunks_exact(4) {
            out.extend_from_slice(&[p[2], p[1], p[0]]);
        }
        let _ = std::fs::write(path, out);
    }
}
