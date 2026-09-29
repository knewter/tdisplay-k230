//! Host render harness for `home-widget-design`'s evidence screenshots.
//!
//! Renders Home's widget cards (each clock style, battery present/absent,
//! weather, a mixed-widget overview, the widget picker, and two live drag
//! mechanics -- an edge-hold page-switch dwell and a "no room here" drop
//! target) offscreen via the same `render::paint_home` the real client
//! calls, into two synthetic themes (one dark, one light) built directly
//! from `appearance::AppearanceSnapshot`'s own public fields rather than a
//! real Omarchy IPC handshake, which this host has no compositor to run.
//! Round 2 (board review: "browse the web find dope clock widgets") also
//! composites over a real Omarchy theme background image, decoded through
//! the same `background_decode::BackgroundCache` the production wallpaper
//! layer uses (crop-to-cover, real bytes), rather than a flat color --
//! since widgets no longer paint a card behind themselves, a flat color
//! would not actually exercise the halo/glow legibility mechanism this
//! round adds.
//!
//! `cargo run --example render_widget_evidence -- <out-dir> <dark-wallpaper>
//! <light-wallpaper>` writes every PNG into `<out-dir>`; the two wallpaper
//! arguments are paths to real image files (e.g. two `nix build
//! .#handheld-theme-default` output backgrounds, one per theme).
use cairo::{Context, Format, ImageSurface};
use k230_shell_rust::{
    appearance::{AppearanceSnapshot, AppearanceToken, Brush, BrushStop, PaletteColor, PaletteValue},
    background_decode::{BackgroundCache, FitMode},
    catalog::AppEntry,
    home_grid::{self, HomeSlot},
    home_screen::{HomeScreen, WidgetPicker, WidgetPickerPage},
    home_state::{HomeItem, HomeLayout, WidgetKind},
    home_widgets::{
        battery::BatteryState,
        weather::{ForecastEntry, WeatherDisplay, WeatherSnapshot},
    },
    icon::IconCache,
    render,
};
use std::{collections::BTreeMap, env, fs, path::{Path, PathBuf}};

const WIDTH: u32 = 568;
const HEIGHT: u32 = 1232;

fn solid(argb: &str) -> Brush {
    Brush { stops: vec![BrushStop { offset: 0.0, argb: argb.to_string() }], angle_degrees: 0.0, alpha: 1.0 }
}

fn hex_channels(argb: &str) -> (u8, u8, u8, u8) {
    let hex = argb.trim_start_matches('#');
    let byte = |at: usize| u8::from_str_radix(&hex[at..at + 2], 16).unwrap_or(0);
    (byte(0), byte(2), byte(4), byte(6)) // (alpha, red, green, blue)
}

fn palette_color(argb: &str) -> PaletteColor {
    let (alpha, red, green, blue) = hex_channels(argb);
    PaletteColor { red, green, blue, alpha }
}

/// Builds a fully self-contained `AppearanceSnapshot` -- every brush/palette
/// key `render.rs`'s `visual_style`/`brush_rgb`/`service_card` reads for the
/// "launcher"/"controls" sections this Home surface uses, so nothing here
/// silently falls back to render.rs's own hardcoded default color instead
/// of the theme actually being exercised.
#[allow(clippy::too_many_arguments)]
fn build_theme(name: &str, background: &str, surface: &str, surface_selected: &str, text: &str, accent: &str, muted: &str, red: &str) -> AppearanceSnapshot {
    let mut launcher = BTreeMap::new();
    launcher.insert("background".to_string(), AppearanceToken::Brush(solid(surface)));
    launcher.insert("selected-background".to_string(), AppearanceToken::Brush(solid(surface_selected)));
    launcher.insert("text".to_string(), AppearanceToken::Brush(solid(text)));
    launcher.insert("selected-text".to_string(), AppearanceToken::Brush(solid(accent)));
    launcher.insert("border".to_string(), AppearanceToken::Brush(solid(muted)));

    let mut controls = BTreeMap::new();
    controls.insert("normal-color".to_string(), AppearanceToken::Brush(solid(text)));
    controls.insert("normal-fill-alpha".to_string(), AppearanceToken::Number(0.06));
    controls.insert("selected-fill-alpha".to_string(), AppearanceToken::Number(0.16));
    controls.insert("background".to_string(), AppearanceToken::Brush(solid(surface)));
    controls.insert("selected-background".to_string(), AppearanceToken::Brush(solid(surface_selected)));
    controls.insert("text".to_string(), AppearanceToken::Brush(solid(text)));

    let mut sections = BTreeMap::new();
    sections.insert("launcher".to_string(), launcher);
    sections.insert("controls".to_string(), controls);

    let mut palette = BTreeMap::new();
    palette.insert("foreground".to_string(), PaletteValue::Color(palette_color(text)));
    palette.insert("background".to_string(), PaletteValue::Color(palette_color(background)));
    palette.insert("accent".to_string(), PaletteValue::Color(palette_color(accent)));
    palette.insert("light_foreground".to_string(), PaletteValue::Color(palette_color(muted)));
    palette.insert("red".to_string(), PaletteValue::Color(palette_color(red)));

    AppearanceSnapshot {
        generation: name.to_string(),
        path: PathBuf::new(),
        icon_theme: None,
        background: None,
        selected_background: None,
        backgrounds: Vec::new(),
        palette,
        sections,
        applied: Vec::new(),
        unavailable: Vec::new(),
        unknown: Vec::new(),
    }
}

/// Catppuccin Mocha-derived: a real, well-known dark palette, not an
/// arbitrary guess -- this shell already loads Omarchy/Catppuccin themes,
/// so this reads as a plausible actual theme, not a synthetic test swatch.
/// The returned color is only a decode-failure fallback -- see
/// `paint_wallpaper`'s own doc; the real background is a genuine image path
/// passed on the command line.
fn dark_theme() -> (AppearanceSnapshot, &'static str) {
    (build_theme("mocha-evidence", "#FF1E1E2E", "#E6313244", "#E645475A", "#FFCDD6F4", "#FF89B4FA", "#FFA6ADC8", "#FFF38BA8"), "#FF1E1E2E")
}

/// Catppuccin Latte-derived: the same family's light counterpart. Same
/// fallback-only caveat as [`dark_theme`].
fn light_theme() -> (AppearanceSnapshot, &'static str) {
    (build_theme("latte-evidence", "#FFEFF1F5", "#E6FFFFFF", "#E6E6E9EF", "#FF4C4F69", "#FF1E66F5", "#FF6C6F85", "#FFD20F39"), "#FFEFF1F5")
}

fn fill_wallpaper(cr: &Context, argb: &str) {
    let (alpha, red, green, blue) = hex_channels(argb);
    cr.set_source_rgba(f64::from(red) / 255.0, f64::from(green) / 255.0, f64::from(blue) / 255.0, f64::from(alpha) / 255.0);
    let _ = cr.paint();
}

/// Paints a real theme wallpaper (a photo/gradient, not a flat swatch),
/// decoded and crop-to-cover fit through the same `BackgroundCache` the
/// production wallpaper layer uses -- exactly the point of round 2's own
/// evidence ask ("use actual Omarchy theme backgrounds... not flat
/// colour"): with no card behind any widget any more, a flat color would
/// never actually exercise the halo/glow legibility mechanism this round
/// adds. Falls back to a flat color only if the given path fails to decode
/// (e.g. an evidence re-run pointed at a stale/GC'd path), so this harness
/// still produces *something* rather than aborting the whole run.
fn paint_wallpaper(cr: &Context, cache: &mut BackgroundCache, path: &Path, fallback_argb: &str) {
    let pixels: Vec<u8> = match cache.render(path, None, WIDTH, HEIGHT, FitMode::Crop) {
        Ok(bytes) => bytes.to_vec(),
        Err(error) => {
            eprintln!("warning: could not decode wallpaper {}: {error} (falling back to a flat color)", path.display());
            fill_wallpaper(cr, fallback_argb);
            return;
        }
    };
    match ImageSurface::create_for_data(pixels, Format::ARgb32, WIDTH as i32, HEIGHT as i32, (WIDTH * 4) as i32) {
        Ok(surface) => {
            let _ = cr.set_source_surface(&surface, 0.0, 0.0);
            let _ = cr.paint();
        }
        Err(_) => fill_wallpaper(cr, fallback_argb),
    }
}

fn sample_apps() -> Vec<AppEntry> {
    vec![
        AppEntry { id: "org.k230.files".into(), name: "Files".into(), icon: None, path: PathBuf::new() },
        AppEntry { id: "org.k230.terminal".into(), name: "Terminal".into(), icon: None, path: PathBuf::new() },
        AppEntry { id: "org.k230.camera".into(), name: "Camera".into(), icon: None, path: PathBuf::new() },
    ]
}

fn sample_weather(forecast_len: usize) -> WeatherDisplay {
    let forecast = [("3pm", 23, "Partly cloudy"), ("6pm", 19, "Overcast"), ("9pm", 16, "Clear"), ("12am", 13, "Clear"), ("3am", 12, "Light rain")]
        .into_iter()
        .take(forecast_len)
        .map(|(label, temp_c, condition)| ForecastEntry { label: label.to_string(), temp_c, condition: condition.to_string() })
        .collect();
    WeatherDisplay::Fresh(WeatherSnapshot {
        location: "Boston".to_string(),
        condition: "Partly cloudy".to_string(),
        temperature_c: 21,
        feels_like_c: 20,
        high_c: 24,
        low_c: 15,
        forecast,
        fetched_unix_secs: 0,
    })
}

/// `HomeLayout::default()` leaves `dock` as a zero-length `Vec` (the real
/// `dock_slots`-sized allocation happens in the private `HomeLayout::empty`
/// constructor this harness cannot call) -- every layout below needs this
/// so `HomeSlot::Dock` placements actually have slots to land in.
fn layout_with_dock() -> HomeLayout {
    HomeLayout { dock: vec![None; home_grid::DOCK_SLOTS], ..HomeLayout::default() }
}

/// One widget, alone on an otherwise empty Home page plus a populated dock
/// -- the composition every "widget style" screenshot shares.
fn single_widget_layout(kind: WidgetKind, apps: &[AppEntry]) -> HomeLayout {
    let apps_per_page = home_grid::apps_per_page(WIDTH, HEIGHT);
    let mut layout = layout_with_dock();
    layout.place(HomeSlot::Grid { page: 0, slot: 0 }, HomeItem::Widget { widget: kind }, apps_per_page, false);
    for (index, app) in apps.iter().enumerate() {
        layout.place(HomeSlot::Dock { slot: index }, HomeItem::app(app.id.clone()), 4, false);
    }
    layout
}

struct Frame {
    file_name: String,
    layout: HomeLayout,
    battery: BatteryState,
    weather: WeatherDisplay,
    widget_picker: Option<WidgetPicker>,
    /// A pre-armed live drag, driven through `HomeScreen`'s own public
    /// down/motion/tick API before rendering -- not faked by poking private
    /// fields -- to demonstrate the cross-page-drag mechanics (task 1)
    /// honestly, from the real state machine.
    drag_demo: Option<fn(&mut HomeScreen)>,
}

fn edge_hold_partial_dwell(home: &mut HomeScreen) {
    // Near the right edge, partway through the dwell before a page turns --
    // the arrow/highlight should read as "growing in", not yet complete.
    // The finger sits well above the panel's vertical center so the lifted
    // icon does not visually cover the edge arrow, which is always drawn at
    // mid-height -- purely a demo-legibility choice, not a behavior change.
    home.layout.place(HomeSlot::Grid { page: 0, slot: 0 }, HomeItem::app("org.k230.files"), home_grid::apps_per_page(WIDTH, HEIGHT), false);
    home.begin_external_drag("org.k230.files".to_string(), (f64::from(WIDTH) - 10.0, 260.0));
    home.external_drag_motion((f64::from(WIDTH) - 10.0, 260.0), 0, WIDTH, HEIGHT);
    for _ in 0..8 {
        home.tick(30); // 240ms of a 380ms first-dwell threshold
    }
}

fn no_room_drop_target(home: &mut HomeScreen) {
    // A Weather widget (2x2), already pinned, long-pressed and dragged over
    // the Clock's own 4x2 span -- nowhere in that span has room for it.
    let apps_per_page = home_grid::apps_per_page(WIDTH, HEIGHT);
    home.layout.place(HomeSlot::Grid { page: 0, slot: 0 }, HomeItem::Widget { widget: WidgetKind::Clock }, apps_per_page, false);
    home.layout.place(HomeSlot::Grid { page: 0, slot: 8 }, HomeItem::Widget { widget: WidgetKind::Weather }, apps_per_page, false);
    // `home_grid::slot_at` hit-tests each *single* cell's own `tile_rect`,
    // not a widget's merged `spanned_tile_rect` -- picking the anchor
    // cell's own single-tile center (rather than the spanned card's visual
    // center, which sits in the gap between four individual cells) is what
    // a real touch anywhere on the widget's anchor cell would also resolve
    // to, since `HomeLayout::anchor_at` maps any covered cell back to slot
    // 8 identically either way.
    let (wx, wy, ww, wh) = home_grid::tile_rect(WIDTH, HEIGHT, 8, home_grid::COLUMNS);
    let weather_center = (wx + ww / 2.0, wy + wh / 2.0);
    home.down(1, weather_center, 0, WIDTH, HEIGHT);
    for _ in 0..40 {
        home.tick(20); // clears the 500ms long-press threshold
    }
    let (cx, cy, cw, ch) = home_grid::tile_rect(WIDTH, HEIGHT, 0, home_grid::COLUMNS);
    let clock_center = (cx + cw / 2.0, cy + ch / 2.0);
    home.motion(1, clock_center, 900, WIDTH, HEIGHT);
}

fn frames() -> Vec<Frame> {
    let apps = sample_apps();
    let apps_per_page = home_grid::apps_per_page(WIDTH, HEIGHT);
    let mut overview = layout_with_dock();
    overview.place(HomeSlot::Grid { page: 0, slot: 0 }, HomeItem::Widget { widget: WidgetKind::Clock }, apps_per_page, false);
    overview.place(HomeSlot::Grid { page: 0, slot: 8 }, HomeItem::Widget { widget: WidgetKind::Battery }, apps_per_page, false);
    overview.place(HomeSlot::Grid { page: 0, slot: 10 }, HomeItem::Widget { widget: WidgetKind::Weather }, apps_per_page, false);
    for (index, app) in apps.iter().enumerate() {
        overview.place(HomeSlot::Dock { slot: index }, HomeItem::app(app.id.clone()), 4, false);
    }

    vec![
        Frame {
            file_name: "clock-bubble.png".into(),
            layout: single_widget_layout(WidgetKind::Clock, &apps),
            battery: BatteryState::Absent,
            weather: WeatherDisplay::Unavailable,
            widget_picker: None,
            drag_demo: None,
        },
        Frame {
            file_name: "clock-thin.png".into(),
            layout: single_widget_layout(WidgetKind::ClockMinimal, &apps),
            battery: BatteryState::Absent,
            weather: WeatherDisplay::Unavailable,
            widget_picker: None,
            drag_demo: None,
        },
        Frame {
            file_name: "clock-analog.png".into(),
            layout: single_widget_layout(WidgetKind::ClockAnalog, &apps),
            battery: BatteryState::Absent,
            weather: WeatherDisplay::Unavailable,
            widget_picker: None,
            drag_demo: None,
        },
        Frame {
            file_name: "clock-dotmatrix.png".into(),
            layout: single_widget_layout(WidgetKind::ClockDotMatrix, &apps),
            battery: BatteryState::Absent,
            weather: WeatherDisplay::Unavailable,
            widget_picker: None,
            drag_demo: None,
        },
        Frame {
            file_name: "battery-present.png".into(),
            layout: single_widget_layout(WidgetKind::Battery, &apps),
            battery: BatteryState::Present { percent: 72, status: "Charging".into() },
            weather: WeatherDisplay::Unavailable,
            widget_picker: None,
            drag_demo: None,
        },
        Frame {
            file_name: "battery-absent.png".into(),
            layout: single_widget_layout(WidgetKind::Battery, &apps),
            battery: BatteryState::Absent,
            weather: WeatherDisplay::Unavailable,
            widget_picker: None,
            drag_demo: None,
        },
        Frame {
            file_name: "weather.png".into(),
            layout: single_widget_layout(WidgetKind::Weather, &apps),
            battery: BatteryState::Absent,
            weather: sample_weather(3),
            widget_picker: None,
            drag_demo: None,
        },
        Frame {
            file_name: "overview.png".into(),
            layout: overview,
            battery: BatteryState::Present { percent: 54, status: "Discharging".into() },
            weather: sample_weather(3),
            widget_picker: None,
            drag_demo: None,
        },
        Frame {
            file_name: "widget-picker.png".into(),
            layout: single_widget_layout(WidgetKind::Clock, &apps),
            battery: BatteryState::Present { percent: 90, status: "Not charging".into() },
            weather: sample_weather(3),
            widget_picker: Some(WidgetPicker { page: WidgetPickerPage::Widgets }),
            drag_demo: None,
        },
        Frame {
            file_name: "drag-edge-indicator.png".into(),
            layout: HomeLayout::default(),
            battery: BatteryState::Absent,
            weather: WeatherDisplay::Unavailable,
            widget_picker: None,
            drag_demo: Some(edge_hold_partial_dwell),
        },
        Frame {
            file_name: "drag-no-room.png".into(),
            layout: HomeLayout::default(),
            battery: BatteryState::Absent,
            weather: WeatherDisplay::Unavailable,
            widget_picker: None,
            drag_demo: Some(no_room_drop_target),
        },
    ]
}

/// Renders onto two *separate* surfaces and composites them, exactly
/// mirroring the real client's own layering (`main.rs`'s Wayland
/// `Layer::Bottom` wallpaper surface underneath `home_surface`'s own
/// `Layer::Bottom` Home layer): `render::paint_home` always clears its own
/// surface to transparent first (`Operator::Source`, so a real Wayland
/// compositor can show the separate wallpaper surface through it) --
/// painting the wallpaper onto the *same* surface before calling it would
/// just have that clear wipe the wallpaper out again before a single pixel
/// of Home content is drawn.
fn render_frame(frame: &Frame, theme: &AppearanceSnapshot, wallpaper: &Path, fallback_argb: &str, cache: &mut BackgroundCache) -> ImageSurface {
    let wallpaper_surface = ImageSurface::create(Format::ARgb32, WIDTH as i32, HEIGHT as i32).expect("wallpaper surface");
    {
        let cr = Context::new(&wallpaper_surface).expect("wallpaper context");
        paint_wallpaper(&cr, cache, wallpaper, fallback_argb);
    }

    let home_surface = ImageSurface::create(Format::ARgb32, WIDTH as i32, HEIGHT as i32).expect("home surface");
    {
        let cr = Context::new(&home_surface).expect("home context");
        let mut home = HomeScreen::new(frame.layout.clone(), f64::from(WIDTH));
        home.battery = frame.battery.clone();
        home.weather = frame.weather.clone();
        home.widget_picker = frame.widget_picker;
        if let Some(demo) = frame.drag_demo {
            demo(&mut home);
        }
        let apps = sample_apps();
        let mut icons = IconCache::new();
        render::paint_home(&cr, WIDTH, HEIGHT, Some(theme), &home, &apps, &mut icons);
    }

    let composed = ImageSurface::create(Format::ARgb32, WIDTH as i32, HEIGHT as i32).expect("composed surface");
    let cr = Context::new(&composed).expect("composed context");
    let _ = cr.set_source_surface(&wallpaper_surface, 0.0, 0.0);
    let _ = cr.paint();
    let _ = cr.set_source_surface(&home_surface, 0.0, 0.0);
    let _ = cr.paint();
    drop(cr);
    composed
}

fn main() -> Result<(), String> {
    let mut args = env::args().skip(1);
    let out_dir = PathBuf::from(args.next().ok_or("expected an output directory")?);
    let dark_wallpaper = PathBuf::from(args.next().ok_or("expected a dark-theme wallpaper path")?);
    let light_wallpaper = PathBuf::from(args.next().ok_or("expected a light-theme wallpaper path")?);
    fs::create_dir_all(&out_dir).map_err(|error| error.to_string())?;

    // The fallback flat colors here are only ever used if a wallpaper path
    // fails to decode (see `paint_wallpaper`'s own doc) -- the real
    // evidence run always supplies two genuine Omarchy background images.
    let themes: [(&str, AppearanceSnapshot, PathBuf, &str); 2] = {
        let (dark, dark_fallback) = dark_theme();
        let (light, light_fallback) = light_theme();
        [("dark", dark, dark_wallpaper, dark_fallback), ("light", light, light_wallpaper, light_fallback)]
    };

    let all_frames = frames();
    let mechanic_frame_names = ["drag-edge-indicator.png", "drag-no-room.png"];
    let mut cache = BackgroundCache::new();
    let mut written = Vec::new();
    for (theme_name, theme, wallpaper, fallback_argb) in &themes {
        for frame in &all_frames {
            // The two live-drag mechanic demos are theme-independent
            // mechanics, not a widget style comparison -- rendered once
            // (in the dark theme) rather than duplicated per theme.
            if mechanic_frame_names.contains(&frame.file_name.as_str()) && *theme_name != "dark" {
                continue;
            }
            let surface = render_frame(frame, theme, wallpaper, fallback_argb, &mut cache);
            let file_name = format!("{theme_name}-{}", frame.file_name);
            let path = out_dir.join(&file_name);
            let mut file = fs::File::create(&path).map_err(|error| error.to_string())?;
            surface.write_to_png(&mut file).map_err(|error| error.to_string())?;
            written.push(file_name);
        }
    }
    for name in &written {
        println!("wrote {name}");
    }
    Ok(())
}
