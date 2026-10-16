//! Host render helpers shared by `examples/render_responsive_evidence.rs`
//! (produces `docs/evidence/shell-responsive/*.png`) and
//! `tests/responsive_pixel_identity.rs` (proves the 568x1232 renders those
//! helpers produce stay byte-for-byte identical to the committed evidence,
//! i.e. `feat/shell-responsive` never changed the native panel's own
//! output). One shared implementation so the evidence PNGs and the test
//! that guards them can never quietly drift apart from each other.
//!
//! Renders Home, the wallpaper background, the Drawer and Settings through
//! the exact same production paths (`render::paint_home`,
//! `render::RendererCache::draw_wallpaper`, `render::export_png`) the real
//! Wayland client calls -- never opens a Wayland connection itself, so this
//! proves render geometry only, not that the compositor hands this client
//! a whole-output configure at any given size (see `lib.rs`'s own
//! `is_whole_output`/`configure_preserves_aspect` tests for that).
use crate::{
    catalog::AppEntry,
    home_grid::{self, HomeSlot},
    home_screen::HomeScreen,
    home_state::{HomeItem, HomeLayout},
    icon::IconCache,
    render::{self, RendererCache},
    Route,
};
use cairo::{Context, Format, ImageSurface};
use std::path::{Path, PathBuf};

/// Enough synthetic apps to overflow a single Home page and a single
/// Drawer viewport at every target resolution, so a render at each size
/// visibly exercises more than one row -- 30 apps is comfortably past this
/// panel's own 20-per-page grid capacity (`home_grid::apps_per_page`) and
/// the drawer's per-viewport row count.
pub fn synthetic_apps(count: usize) -> Vec<AppEntry> {
    (0..count)
        .map(|index| AppEntry {
            id: format!("evidence.app{index}.desktop"),
            name: format!("App {index}"),
            icon: None,
            path: PathBuf::from(format!("/nonexistent/app{index}.desktop")),
        })
        .collect()
}

/// Fills the dock with the first `home_grid::dock_slots` apps and the grid
/// pages with the rest, via the same `HomeLayout::place`/`place_first_fit`
/// primitives a real drag uses -- unlike `home_state::seed_default`, which
/// only auto-pins a small curated list of well-known real desktop-entry
/// ids (`foot.desktop` and friends) and would seed nothing but the Clock
/// widget for this harness's synthetic `evidence.appN.desktop` ids.
pub fn seed_layout(apps: &[AppEntry], width: u32, height: u32) -> HomeLayout {
    let apps_per_page = home_grid::apps_per_page(width, height);
    let mut layout = HomeLayout {
        columns: home_grid::columns_for_width(width),
        dock: vec![None; home_grid::dock_slots(width, height)],
        ..HomeLayout::default()
    };
    let mut iter = apps.iter();
    for slot in 0..home_grid::dock_slots(width, height) {
        let Some(app) = iter.next() else { break };
        layout.set(HomeSlot::Dock { slot }, Some(HomeItem::app(app.id.clone())), apps_per_page);
    }
    for app in iter {
        layout.place_first_fit(HomeItem::app(app.id.clone()), apps_per_page);
    }
    layout
}

/// `render::paint_home` clears to a fully transparent canvas before
/// painting (real production compositing shows it over the separate,
/// always-opaque wallpaper layer beneath). Composite it over the same flat
/// backdrop [`render_wallpaper`] draws so light-on-transparent text (e.g.
/// the Clock widget) is legible in a standalone PNG instead of
/// disappearing into an image viewer's own white behind full alpha 0.
pub fn render_home(path: &Path, width: u32, height: u32, apps: &[AppEntry]) {
    let content = ImageSurface::create(Format::ARgb32, width as i32, height as i32).unwrap();
    {
        let cr = Context::new(&content).unwrap();
        let home_layout = seed_layout(apps, width, height);
        let home = HomeScreen::new(home_layout, f64::from(width));
        let mut icons = IconCache::new();
        render::paint_home(&cr, width, height, None, &home, apps, &mut icons);
    }
    let composited = ImageSurface::create(Format::ARgb32, width as i32, height as i32).unwrap();
    {
        let cr = Context::new(&composited).unwrap();
        cr.set_source_rgb(0x1e as f64 / 255.0, 0x1e as f64 / 255.0, 0x2e as f64 / 255.0);
        cr.paint().unwrap();
        cr.set_source_surface(&content, 0.0, 0.0).unwrap();
        cr.paint().unwrap();
    }
    let mut file = std::fs::File::create(path).unwrap();
    composited.write_to_png(&mut file).unwrap();
}

pub fn render_wallpaper(path: &Path, width: u32, height: u32) {
    let cache = RendererCache::default();
    let mut canvas = vec![0u8; (width as usize) * (height as usize) * 4];
    cache.draw_wallpaper(&mut canvas, width, height).unwrap();
    let surface = unsafe {
        ImageSurface::create_for_data_unsafe(
            canvas.as_mut_ptr(),
            Format::ARgb32,
            width as i32,
            height as i32,
            (width * 4) as i32,
        )
    }
    .unwrap();
    let mut file = std::fs::File::create(path).unwrap();
    surface.write_to_png(&mut file).unwrap();
}

pub fn render_route(path: &Path, width: u32, height: u32, route: Route, apps: &[AppEntry]) {
    render::export_png(path, width, height, route, apps).unwrap();
}

/// Renders `route` with the given service data through the same
/// `RendererCache::draw` path the live client uses (unlike [`render_route`],
/// which has no service data), so the shade and Settings show the battery and
/// Key backlight rows exactly when `view` carries them.
pub fn render_route_with_services(
    path: &Path,
    width: u32,
    height: u32,
    route: Route,
    view: crate::service_ui::ServiceView,
) {
    let mut renderer = RendererCache::default();
    renderer.set_services(view);
    let mut canvas = vec![0u8; (width as usize) * (height as usize) * 4];
    renderer
        .draw(
            &mut canvas,
            render::RenderParams { width, height, route, progress: 1.0, scroll: 0.0 },
            &[],
        )
        .unwrap();
    let surface = unsafe {
        ImageSurface::create_for_data_unsafe(
            canvas.as_mut_ptr(),
            Format::ARgb32,
            width as i32,
            height as i32,
            (width * 4) as i32,
        )
    }
    .unwrap();
    let mut file = std::fs::File::create(path).unwrap();
    surface.write_to_png(&mut file).unwrap();
}

/// A loaded Settings snapshot with every row readable, for fixtures.
pub fn fixture_settings() -> crate::service_data::SettingsSnapshot {
    use crate::service_data::{Control, ControlState, ControlValue, SettingsSnapshot};
    let control = |state, value, label: &str, detail: Option<&str>| Control {
        state,
        value,
        label: label.into(),
        detail: detail.map(Into::into),
        action: None,
    };
    SettingsSnapshot {
        network: control(ControlState::Action, None, "Wi-Fi", None),
        brightness: control(ControlState::Writable, Some(ControlValue::Percent(60)), "Brightness", None),
        keyboard: control(ControlState::Action, None, "On-screen keyboard", None),
        motion: control(ControlState::ReadOnly, Some(ControlValue::Text("Full".into())), "Motion", None),
        volume: crate::service_data::unknown_volume_placeholder(),
    }
}

/// Like [`render_route_with_services`] but also with a theme-chooser view,
/// for the Settings sub-pages that live under `Route::Settings`.
pub fn render_route_with_views(
    path: &Path,
    width: u32,
    height: u32,
    route: Route,
    view: crate::service_ui::ServiceView,
    chooser: Option<crate::theme_ui::ThemeView>,
) {
    let mut renderer = RendererCache::default();
    renderer.set_services(view);
    if let Some(chooser) = chooser {
        renderer.set_theme_view(chooser);
    }
    let mut canvas = vec![0u8; (width as usize) * (height as usize) * 4];
    renderer
        .draw(
            &mut canvas,
            render::RenderParams { width, height, route, progress: 1.0, scroll: 0.0 },
            &[],
        )
        .unwrap();
    let surface = unsafe {
        ImageSurface::create_for_data_unsafe(
            canvas.as_mut_ptr(),
            Format::ARgb32,
            width as i32,
            height as i32,
            (width * 4) as i32,
        )
    }
    .unwrap();
    let mut file = std::fs::File::create(path).unwrap();
    surface.write_to_png(&mut file).unwrap();
}

/// Wi-Fi fixtures: a saved current network plus nearby ones, long names
/// included, so every page has realistic content.
pub fn fixture_wifi_snapshot() -> crate::wifi_settings::Snapshot {
    use crate::wifi_settings::{Network, Security, Snapshot};
    let net = |ssid: &str, security| Network { ssid: ssid.into(), security };
    Snapshot {
        networks: vec![
            net("Home Network", Security::Wpa2Psk),
            net("Guest (open)", Security::Open),
            net("A Rather Long Network Name For The Neighbours Upstairs", Security::Wpa2Psk),
            net("Cafe Free WiFi", Security::Open),
            net("Printer-Direct", Security::Unsupported),
            net("Office 5G", Security::Wpa2Psk),
            net("Garage", Security::Wpa2Psk),
        ],
        current: Some("Home Network".into()),
        saved: vec![net("Home Network", Security::Wpa2Psk), net("Office 5G", Security::Wpa2Psk)],
        error: None,
    }
}

/// A `WifiPublic` on `page` for the fixture snapshot; `selected` names a
/// network of `wifi_ui::all_networks(&snapshot)`.
pub fn fixture_wifi(
    page: crate::wifi_ui::Page,
    selected: Option<&str>,
    use_saved: bool,
    keyboard_inset: f64,
    message: Option<&str>,
) -> crate::wifi_ui::WifiPublic {
    let snapshot = fixture_wifi_snapshot();
    let selected = selected.and_then(|ssid| crate::wifi_ui::all_networks(&snapshot).into_iter().find(|n| n.ssid == ssid));
    crate::wifi_ui::WifiPublic {
        page,
        snapshot: Some(snapshot),
        selected,
        password_len: if use_saved { 0 } else { 9 },
        password_visible: false,
        use_saved,
        pending: false,
        message: message.map(Into::into),
        scroll: 0.0,
        keyboard_inset,
    }
}

/// A theme chooser with `themes` themes and five backgrounds on its List
/// page. No thumbnails are loaded, so the carousels draw their placeholders.
pub fn fixture_theme_view(themes: usize) -> crate::theme_ui::ThemeView {
    use crate::theme_catalog::{
        ActiveTheme, BackgroundChoice, BackgroundKind, Compatibility, ThemeEntry, ThemeList, ThemeOrigin,
        ThemePreview,
    };
    let id = |n: usize| format!("{:024x}", n + 1);
    let entry = |n: usize| ThemeEntry {
        id: id(n),
        name: format!("theme-{n}"),
        label: ["Catppuccin", "Tokyo Night", "Gruvbox", "Nord", "Rose Pine", "Everforest", "Kanagawa"][n % 7].into(),
        origin: if n % 3 == 2 { ThemeOrigin::User } else { ThemeOrigin::Builtin },
        preview_path: None,
    };
    let list = ThemeList {
        themes: (0..themes).map(entry).collect(),
        active: ActiveTheme { id: Some(id(1)), generation: None },
    };
    let background = |n: usize| BackgroundChoice {
        id: format!("{:024x}", 0x100 + n),
        label: format!("{:02}-background.png", n + 1),
        kind: if n == 3 { BackgroundKind::Video } else { BackgroundKind::Image },
        path: PathBuf::from(format!("/nonexistent/bg{n}.png")),
        selected: n == 1,
        decode_status: "unverified".into(),
    };
    let preview = ThemePreview {
        theme: entry(1),
        generation: id(0x200),
        appearance_path: PathBuf::from("/nonexistent/appearance.json"),
        palette: Default::default(),
        icon_theme: None,
        backgrounds: (0..5).map(background).collect(),
        compatibility: Compatibility { applied: vec![], adapted: vec![], unavailable: vec![], unknown: vec![] },
        activated: true,
        app_appearance: None,
    };
    crate::theme_ui::ThemeView {
        page: crate::theme_ui::ThemePage::List,
        list: Some(list),
        preview: Some(preview),
        theme_position: 1.0,
        background_position: 1.0,
        ..crate::theme_ui::ThemeView::default()
    }
}

/// Notification history rows for the shade: short and long text, a
/// critical row, ongoing/actionable ones.
pub fn fixture_notification_events(count: usize) -> Vec<crate::service_data::NotificationEvent> {
    use crate::service_data::{NotificationEvent, Priority};
    let rows = [
        ("Messages", "New message from Alex", "Are we still on for dinner tonight? I booked the table for 7:30 and can move it if that is too early for everyone.", Priority::Ordinary, true, true),
        ("System", "Battery low", "12% remaining. Connect the charger soon.", Priority::Critical, false, false),
        ("Updates", "An extremely long notification summary that cannot possibly fit on one line of the shade", "Body text of moderate length that goes on for a while so that it must wrap or be clipped by the row without spilling into its neighbours below.", Priority::Important, true, true),
        ("Mail", "3 new emails", "", Priority::Ordinary, true, false),
        ("Calendar", "Standup in 10 minutes", "Room 4 / video link", Priority::Ordinary, true, true),
        ("Downloads", "Download complete", "release-notes.pdf (2.4 MB)", Priority::Ordinary, true, false),
    ];
    (0..count)
        .map(|n| {
            let (source, summary, body, priority, dismissible, action) = rows[n % rows.len()];
            NotificationEvent {
                id: n as u64 + 1,
                source: source.into(),
                icon: None,
                summary: summary.into(),
                body: body.into(),
                priority,
                timestamp: 1_790_000_000 + n as i64 * 60,
                error: None,
                dismissible,
                action_available: action,
            }
        })
        .collect()
}

/// A Home page with a folder of `members` apps in its first grid cell,
/// opened (the overlay of task 5), rendered over the standard backdrop.
pub fn render_home_with_open_folder(path: &Path, width: u32, height: u32, apps: &[AppEntry], members: usize) {
    use crate::{home_screen::OpenFolder, home_state::FolderData};
    let apps_per_page = home_grid::apps_per_page(width, height);
    let mut layout = HomeLayout {
        columns: home_grid::columns_for_width(width),
        dock: vec![None; home_grid::dock_slots(width, height)],
        ..HomeLayout::default()
    };
    let (folder_apps, rest) = apps.split_at(members.min(apps.len()));
    let slot = layout.place_first_fit(
        HomeItem::Folder(FolderData { name: "Games and Fun".into(), apps: folder_apps.iter().map(|a| a.id.clone()).collect() }),
        apps_per_page,
    );
    for app in rest.iter().take(8) {
        layout.place_first_fit(HomeItem::app(app.id.clone()), apps_per_page);
    }
    let mut home = HomeScreen::new(layout, f64::from(width));
    home.open_folder = Some(OpenFolder { slot, editing_name: false, name_buffer: String::new() });
    let content = ImageSurface::create(Format::ARgb32, width as i32, height as i32).unwrap();
    {
        let cr = Context::new(&content).unwrap();
        let mut icons = IconCache::new();
        render::paint_home(&cr, width, height, None, &home, apps, &mut icons);
    }
    let composited = ImageSurface::create(Format::ARgb32, width as i32, height as i32).unwrap();
    {
        let cr = Context::new(&composited).unwrap();
        cr.set_source_rgb(0x1e as f64 / 255.0, 0x1e as f64 / 255.0, 0x2e as f64 / 255.0);
        cr.paint().unwrap();
        cr.set_source_surface(&content, 0.0, 0.0).unwrap();
        cr.paint().unwrap();
    }
    let mut file = std::fs::File::create(path).unwrap();
    composited.write_to_png(&mut file).unwrap();
}

/// Home with the widget picker open on `widgets` (the Widgets page) or the
/// Menu page, over a flat backdrop -- the picker's row geometry at a size.
pub fn render_home_with_widget_picker(path: &Path, width: u32, height: u32, apps: &[AppEntry], widgets: bool) {
    use crate::home_screen::{WidgetPicker, WidgetPickerPage};
    let mut home = HomeScreen::new(seed_layout(apps, width, height), f64::from(width));
    home.sync_columns(width, height);
    home.widget_picker = Some(WidgetPicker { page: if widgets { WidgetPickerPage::Widgets } else { WidgetPickerPage::Menu } });
    let content = ImageSurface::create(Format::ARgb32, width as i32, height as i32).unwrap();
    {
        let cr = Context::new(&content).unwrap();
        let mut icons = IconCache::new();
        render::paint_home(&cr, width, height, None, &home, apps, &mut icons);
    }
    let composited = ImageSurface::create(Format::ARgb32, width as i32, height as i32).unwrap();
    {
        let cr = Context::new(&composited).unwrap();
        cr.set_source_rgb(0x1e as f64 / 255.0, 0x1e as f64 / 255.0, 0x2e as f64 / 255.0);
        cr.paint().unwrap();
        cr.set_source_surface(&content, 0.0, 0.0).unwrap();
        cr.paint().unwrap();
    }
    let mut file = std::fs::File::create(path).unwrap();
    composited.write_to_png(&mut file).unwrap();
}
