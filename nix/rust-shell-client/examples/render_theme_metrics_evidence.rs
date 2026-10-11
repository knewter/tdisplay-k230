//! Render a pinned theme's Settings screen before/after temporary font and
//! spacing overrides. Overrides exist only in this example's private fixture.
use cairo::{Context, Format, ImageSurface};
use k230_shell_rust::{
    appearance::{AppearanceReceiver, AppearanceSnapshot},
    render::{RenderParams, RendererCache},
    service_data::{
        unknown_volume_placeholder, Control, ControlState, ControlValue, SettingsSnapshot,
    },
    service_ui::{DrawerSearch, ServiceView},
    catalog::AppEntry,
    app_actions::{ActionRow, AppAction, AppMenu},
    home_screen::HomeScreen,
    home_state::HomeLayout,
    Route,
};
use serde_json::Value;
use std::{fs, os::unix::fs::PermissionsExt, path::PathBuf};

const W: u32 = 568;
const H: u32 = 1232;
const BASELINE_ID: &str = "0123456789abcdef01234567";
const ADAPTED_ID: &str = "89abcdef0123456701234567";

fn control(label: &str, value: &str, detail: &str) -> Control {
    Control {
        state: ControlState::Unavailable,
        value: Some(ControlValue::Text(value.into())),
        label: label.into(),
        detail: Some(detail.into()),
        action: None,
    }
}

fn services() -> ServiceView {
    ServiceView {
        settings: Some(SettingsSnapshot {
            network: control("Wi-Fi", "Connected", "Wireless network"),
            brightness: control("Brightness", "68%", "Screen brightness"),
            keyboard: control("Keyboard", "Hidden", "Two fingers up at bottom to show"),
            motion: control("Motion", "Full motion", "Follows your touch"),
            volume: unknown_volume_placeholder(),
        }),
        ..ServiceView::default()
    }
}

fn snapshot(root: &PathBuf, adapted: bool) -> Result<AppearanceSnapshot, String> {
    let id = if adapted { ADAPTED_ID } else { BASELINE_ID };
    let source = PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("../../nix/handheld-theme-default");
    let mut report: Value = serde_json::from_slice(
        &fs::read(source.join("default-report.json")).map_err(|e| e.to_string())?,
    )
    .map_err(|e| e.to_string())?;
    let mut appearance: Value = serde_json::from_slice(
        &fs::read(source.join("default-appearance.json")).map_err(|e| e.to_string())?,
    )
    .map_err(|e| e.to_string())?;
    report["generation"] = id.into();
    appearance["generation"] = id.into();
    if adapted {
        appearance["sections"]["font"]["base-size"]["value"] = 15.0.into();
        appearance["sections"]["font"]["caption"] =
            serde_json::json!({"kind":"number","value":13.0});
        appearance["sections"]["spacing"]["scale"]["value"] = 1.25.into();
    }
    let generation = root.join(id);
    fs::create_dir_all(&generation).map_err(|e| e.to_string())?;
    fs::write(
        generation.join("report.json"),
        serde_json::to_vec(&report).unwrap(),
    )
    .map_err(|e| e.to_string())?;
    fs::write(
        generation.join("appearance.json"),
        serde_json::to_vec(&appearance).unwrap(),
    )
    .map_err(|e| e.to_string())?;
    let receiver = AppearanceReceiver::bind_with_roots(
        root.join(if adapted {
            "adapted.sock"
        } else {
            "baseline.sock"
        }),
        Some(generation),
        root.clone(),
    )?;
    receiver
        .active()
        .cloned()
        .ok_or_else(|| "fixture did not load".into())
}

fn render(path: PathBuf, theme: AppearanceSnapshot, route: Route, mode: &str) -> Result<(), String> {
    let mut cache = RendererCache::default();
    cache.set_appearance(Some(theme));
    cache.set_services(services());
    if mode == "hover" { cache.set_pointer(Some((80.0, 220.0)), false); }
    if mode == "focus" {
        let mut search = DrawerSearch::default();
        search.focus();
        cache.set_drawer_search(search);
    }
    let apps: Vec<AppEntry> = ["Terminal", "Files", "Video", "Settings"].into_iter().map(|name| AppEntry {
        id: format!("{name}.desktop"), name: name.into(), icon: None, path: PathBuf::new(),
    }).collect();
    let mut pixels = vec![0; (W * H * 4) as usize];
    if mode == "menu" {
        let mut menu = AppMenu::new(apps[0].clone(), true, 1);
        menu.ready = true;
        menu.rows = vec![ActionRow { label: "Open".into(), action: AppAction::Activate },
                         ActionRow { label: "New Window".into(), action: AppAction::NewWindow(None) }];
        cache.draw_app_menu(&mut pixels, W, H, &menu)?;
    } else if mode == "home" {
        let home = HomeScreen::new(HomeLayout::seed(&apps, 4, 12), f64::from(W));
        cache.draw_home(&mut pixels, W, H, &apps, &home)?;
    } else {
    cache.draw(
        &mut pixels,
        RenderParams {
            width: W,
            height: H,
            route,
            progress: 1.0,
            scroll: 0.0,
        },
        &apps,
    )?;
    }
    let frame =
        ImageSurface::create_for_data(pixels, Format::ARgb32, W as i32, H as i32, (W * 4) as i32)
            .map_err(|e| e.to_string())?;
    let target =
        ImageSurface::create(Format::ARgb32, W as i32, H as i32).map_err(|e| e.to_string())?;
    let cr = Context::new(&target).map_err(|e| e.to_string())?;
    cr.set_source_rgb(30.0 / 255.0, 30.0 / 255.0, 46.0 / 255.0);
    cr.paint().map_err(|e| e.to_string())?;
    cr.set_source_surface(&frame, 0.0, 0.0)
        .map_err(|e| e.to_string())?;
    cr.paint().map_err(|e| e.to_string())?;
    drop(cr);
    target
        .write_to_png(&mut fs::File::create(path).map_err(|e| e.to_string())?)
        .map_err(|e| e.to_string())
}

fn main() -> Result<(), String> {
    let out = std::env::args()
        .nth(1)
        .ok_or("usage: render_theme_metrics_evidence OUT")?;
    let out = PathBuf::from(out);
    fs::create_dir_all(&out).map_err(|e| e.to_string())?;
    let runtime = out.join("private-runtime");
    fs::create_dir(&runtime).map_err(|e| e.to_string())?;
    fs::set_permissions(&runtime, fs::Permissions::from_mode(0o700)).map_err(|e| e.to_string())?;
    render(out.join("baseline.png"), snapshot(&runtime, false)?, Route::Settings, "idle")?;
    render(
        out.join("font-spacing-adapted.png"),
        snapshot(&runtime, true)?, Route::Settings, "idle",
    )?;
    for (name, route, mode) in [
        ("settings-hover", Route::Settings, "hover"),
        ("drawer-focus", Route::Drawer, "focus"),
        ("home", Route::Hide, "home"),
        ("help", Route::Help, "idle"),
        ("app-menu", Route::Hide, "menu"),
    ] {
        for adapted in [false, true] {
            let label = if adapted { "adapted" } else { "baseline" };
            render(out.join(format!("{name}-{label}.png")), snapshot(&runtime, adapted)?, route, mode)?;
        }
    }
    fs::remove_dir_all(runtime).map_err(|e| e.to_string())?;
    Ok(())
}
