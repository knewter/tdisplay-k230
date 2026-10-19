//! Host renders for the vision option (task C.3): the same screens drawn
//! from real generations that `tools/theme_activate.py` prepared from one
//! theme at each text step, and with high contrast.
//!
//! usage: render_accessibility_scale_evidence <out-dir> <generations-root>
//!        <name>=<generation-id>...
use cairo::{Context, Format, ImageSurface};
use k230_shell_rust::{
    appearance::{AppearanceReceiver, AppearanceSnapshot},
    catalog::AppEntry,
    evidence_render::{fixture_notification_events, fixture_settings, fixture_theme_view, fixture_wifi},
    render::{self, RenderParams, RendererCache},
    service_data::NotificationSnapshot,
    service_ui::ServiceView,
    theme_catalog::VisionChoice,
    theme_ui::{ThemePage, ThemeView},
    home_grid::{self, HomeSlot},
    home_screen::HomeScreen,
    home_state::{FolderData, HomeItem, HomeLayout, WidgetKind},
    home_widgets::{
        battery::{read_details, BatteryState},
        weather::{ForecastEntry, WeatherDisplay, WeatherSnapshot},
    },
    icon::IconCache,
    Route,
};
use std::{env, fs, os::unix::fs::PermissionsExt, path::PathBuf};

fn snapshot(root: &PathBuf, sockets: &PathBuf, name: &str, id: &str) -> AppearanceSnapshot {
    let receiver = AppearanceReceiver::bind_with_roots(
        sockets.join(format!("{name}.sock")),
        Some(root.join(id)),
        root.clone(),
    )
    .expect("bind fixture receiver");
    receiver.active().cloned().expect("generation did not load")
}

/// The Wi-Fi pages, with the keyboard raised on the password page.
fn wifi_page(page: &str, wide: bool) -> Option<k230_shell_rust::wifi_ui::WifiPublic> {
    use k230_shell_rust::wifi_ui::Page;
    let keyboard = if wide { 240.0 } else { 440.0 };
    let long = "A Rather Long Network Name For The Neighbours Upstairs";
    Some(match page {
        "wifi-list" => fixture_wifi(Page::List, None, false, 0.0, None),
        "wifi-entry" => fixture_wifi(Page::Entry, Some(long), false, keyboard, Some("Wrong password or the network refused it")),
        "wifi-saved" => fixture_wifi(Page::Entry, Some("Home Network"), true, 0.0, None),
        "wifi-connecting" => fixture_wifi(Page::Connecting, Some(long), false, 0.0, Some("Connecting to the network")),
        "wifi-forget" => fixture_wifi(Page::ForgetConfirm, Some("Home Network"), true, 0.0, None),
        _ => return None,
    })
}

fn render(path: PathBuf, theme: &AppearanceSnapshot, vision: &VisionChoice, w: u32, h: u32, page: &str) {
    let mut cache = RendererCache::default();
    cache.set_appearance(Some(theme.clone()));
    cache.set_services(ServiceView {
        settings: Some(fixture_settings()),
        notifications: Some(NotificationSnapshot {
            count: 2,
            events: fixture_notification_events(2),
            preview: None,
        }),
        wifi: wifi_page(page, w > h),
        ..ServiceView::default()
    });
    let route = match page {
        "settings" | "vision" | "themes" | "wifi-list" | "wifi-entry" | "wifi-saved" | "wifi-connecting" | "wifi-forget" => Route::Settings,
        "shade" => Route::Shade,
        "help" => Route::Help,
        _ => Route::Drawer,
    };
    if page == "themes" {
        cache.set_theme_view(fixture_theme_view(7));
    }
    if page == "vision" {
        cache.set_theme_view(ThemeView {
            page: ThemePage::Vision,
            vision: vision.clone(),
            vision_loaded: true,
            message: Some("Applied to every theme".into()),
            ..ThemeView::default()
        });
    }
    let apps: Vec<AppEntry> = ["Terminal", "Files", "Video Player", "Settings", "Text Editor", "System Monitor", "Calculator", "Image Viewer"]
        .into_iter()
        .map(|name| AppEntry { id: format!("{name}.desktop"), name: name.into(), icon: None, path: PathBuf::new() })
        .collect();
    let mut pixels = vec![0; (w * h * 4) as usize];
    cache
        .draw(&mut pixels, RenderParams { width: w, height: h, route, progress: 1.0, scroll: 0.0 }, &apps)
        .expect("draw");
    let frame = ImageSurface::create_for_data(pixels, Format::ARgb32, w as i32, h as i32, (w * 4) as i32).unwrap();
    let target = ImageSurface::create(Format::ARgb32, w as i32, h as i32).unwrap();
    let cr = Context::new(&target).unwrap();
    cr.set_source_rgb(0.5, 0.5, 0.5);
    cr.paint().unwrap();
    cr.set_source_surface(&frame, 0.0, 0.0).unwrap();
    cr.paint().unwrap();
    drop(cr);
    target.write_to_png(&mut fs::File::create(path).unwrap()).unwrap();
}

/// The board's own gauge text from 2026-10-15, as in
/// `render_battery_details_evidence`.
const GAUGE: &str = "POWER_SUPPLY_TYPE=Battery\nPOWER_SUPPLY_STATUS=Full\nPOWER_SUPPLY_HEALTH=Good\nPOWER_SUPPLY_PRESENT=1\nPOWER_SUPPLY_CYCLE_COUNT=0\nPOWER_SUPPLY_VOLTAGE_NOW=4030000\nPOWER_SUPPLY_CURRENT_NOW=0\nPOWER_SUPPLY_POWER_AVG=0\nPOWER_SUPPLY_CHARGE_FULL_DESIGN=3000000\nPOWER_SUPPLY_CHARGE_FULL=2872000\nPOWER_SUPPLY_CHARGE_NOW=2872000\nPOWER_SUPPLY_CAPACITY=100\nPOWER_SUPPLY_TEMP=322\n";

/// Home with the Bubble clock and the battery details widget, as on the
/// operator's panel.
fn render_home(path: PathBuf, theme: &AppearanceSnapshot, w: u32, h: u32) {
    // `RendererCache::set_appearance` sets the layout step; do the same.
    let mut cache = RendererCache::default();
    cache.set_appearance(Some(theme.clone()));
    let dir = env::temp_dir().join(format!("k230-a11y-gauge-{}", std::process::id()));
    fs::create_dir_all(dir.join("bq27220-0")).unwrap();
    fs::write(dir.join("bq27220-0").join("uevent"), GAUGE).unwrap();
    let details = read_details(&dir).quantized();
    let _ = fs::remove_dir_all(&dir);
    let per_page = home_grid::apps_per_page(w, h);
    let mut layout = HomeLayout {
        columns: home_grid::columns_for_width(w),
        dock: vec![None; home_grid::DOCK_SLOTS],
        ..HomeLayout::default()
    };
    layout.place(HomeSlot::Grid { page: 0, slot: 0 }, HomeItem::Widget { widget: WidgetKind::Clock }, per_page, false);
    layout.place_first_fit(HomeItem::Widget { widget: WidgetKind::BatteryDetails }, per_page);
    let mut home = HomeScreen::new(layout, f64::from(w));
    home.battery_details = details;
    let target = ImageSurface::create(Format::ARgb32, w as i32, h as i32).unwrap();
    {
        let cr = Context::new(&target).unwrap();
        cr.set_source_rgb(0.12, 0.3, 0.3);
        cr.paint().unwrap();
        let content = ImageSurface::create(Format::ARgb32, w as i32, h as i32).unwrap();
        {
            let cc = Context::new(&content).unwrap();
            render::paint_home(&cc, w, h, Some(theme), &home, &[], &mut IconCache::new());
        }
        cr.set_source_surface(&content, 0.0, 0.0).unwrap();
        cr.paint().unwrap();
    }
    target.write_to_png(&mut fs::File::create(path).unwrap()).unwrap();
}

/// Home with the Battery and Weather widgets, a folder and apps with stock
/// names, for the labels and widget captions on the type roles.
fn render_home_small(path: PathBuf, theme: &AppearanceSnapshot, w: u32, h: u32) {
    let mut cache = RendererCache::default();
    cache.set_appearance(Some(theme.clone()));
    let names = ["Terminal", "Settings", "Video", "Files", "Calculator", "System Monitor"];
    let apps: Vec<AppEntry> = names
        .iter()
        .map(|name| AppEntry { id: format!("{name}.desktop"), name: (*name).into(), icon: None, path: PathBuf::new() })
        .collect();
    let per_page = home_grid::apps_per_page(w, h);
    let mut layout = HomeLayout {
        columns: home_grid::columns_for_width(w),
        dock: vec![None; home_grid::DOCK_SLOTS],
        ..HomeLayout::default()
    };
    layout.place(HomeSlot::Grid { page: 0, slot: 0 }, HomeItem::Widget { widget: WidgetKind::Battery }, per_page, false);
    layout.place_first_fit(HomeItem::Widget { widget: WidgetKind::Weather }, per_page);
    for app in &apps {
        layout.place_first_fit(HomeItem::app(app.id.clone()), per_page);
    }
    layout.place_first_fit(
        HomeItem::Folder(FolderData { name: "Games".into(), apps: vec![apps[2].id.clone(), apps[3].id.clone()] }),
        per_page,
    );
    let mut home = HomeScreen::new(layout, f64::from(w));
    home.battery = BatteryState::Present { percent: 87, status: "Discharging".into() };
    let forecast = [("9pm", 16, "Clear"), ("12am", 13, "Clear"), ("3am", 12, "Light rain")]
        .into_iter()
        .map(|(label, temp_c, condition)| ForecastEntry { label: label.into(), temp_c, condition: condition.into() })
        .collect();
    home.weather = WeatherDisplay::Fresh(WeatherSnapshot {
        location: "Boston".into(),
        condition: "Partly cloudy".into(),
        temperature_c: 21,
        feels_like_c: 20,
        high_c: 24,
        low_c: 15,
        forecast,
        fetched_unix_secs: 0,
    });
    let target = ImageSurface::create(Format::ARgb32, w as i32, h as i32).unwrap();
    {
        let cr = Context::new(&target).unwrap();
        cr.set_source_rgb(0.12, 0.3, 0.3);
        cr.paint().unwrap();
        render::paint_home(&cr, w, h, Some(theme), &home, &apps, &mut IconCache::new());
    }
    target.write_to_png(&mut fs::File::create(path).unwrap()).unwrap();
}

fn main() {
    let mut args = env::args().skip(1);
    let out = PathBuf::from(args.next().expect("out dir"));
    let root = PathBuf::from(args.next().expect("generations root"));
    fs::create_dir_all(&out).unwrap();
    let sockets = env::temp_dir().join(format!("k230-a11y-evidence-{}", std::process::id()));
    fs::create_dir_all(&sockets).unwrap();
    fs::set_permissions(&sockets, fs::Permissions::from_mode(0o700)).unwrap();
    for pair in args {
        let (name, id) = pair.split_once('=').expect("name=generation");
        let theme = snapshot(&root, &sockets, name, id);
        // `<step>` or `<step>-high`, where step is a TEXT_SCALE_NAMES entry.
        let step = name.split('-').next().unwrap_or("default");
        let vision = VisionChoice {
            text_scale: step.into(),
            contrast: if name.ends_with("high") { "high" } else { "standard" }.into(),
        };
        for (w, h) in [(568u32, 1232u32), (1232, 568)] {
            for page in ["settings", "vision", "shade", "drawer", "help", "themes", "wifi-list", "wifi-entry", "wifi-saved", "wifi-connecting", "wifi-forget"] {
                render(out.join(format!("{name}-{page}-{w}x{h}.png")), &theme, &vision, w, h, page);
            }
            render_home(out.join(format!("{name}-home-{w}x{h}.png")), &theme, w, h);
            render_home_small(out.join(format!("{name}-home-small-{w}x{h}.png")), &theme, w, h);
        }
        println!("rendered {name}");
    }
    let _ = fs::remove_dir_all(&sockets);
}
