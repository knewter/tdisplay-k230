//! Real production host paints with validated, pinned appearance generations.
//! Service values are explicitly synthetic; no Wayland, card compositor or board.
use cairo::{Context, Format, ImageSurface};
use k230_shell_rust::{
    appearance::{AppearanceReceiver, AppearanceSnapshot},
    background_decode::{BackgroundCache, FitMode},
    catalog::AppEntry,
    home_grid::{self, HomeSlot},
    home_screen::HomeScreen,
    home_state::{HomeItem, HomeLayout, WidgetKind},
    render::{RenderParams, RendererCache},
    service_data::*,
    service_ui::ServiceView,
    theme_catalog::*,
    theme_ui::{ThemePage, ThemeView},
    Route,
};
use std::{collections::BTreeMap, fs, os::unix::fs::PermissionsExt, path::PathBuf, time::Duration};
const W: u32 = 568;
const H: u32 = 1232;
fn surface(bytes: Vec<u8>) -> ImageSurface {
    ImageSurface::create_for_data(bytes, Format::ARgb32, W as i32, H as i32, (W * 4) as i32)
        .unwrap()
}
fn apps() -> Vec<AppEntry> {
    [
        ("Terminal", "utilities-terminal"),
        ("Files", "system-file-manager"),
        ("Settings", "preferences-system"),
        ("Video", "multimedia-video-player"),
        ("Monitor", "utilities-system-monitor"),
        ("Music", "multimedia-audio-player"),
        ("Web", "web-browser"),
        ("Notes", "accessories-text-editor"),
    ]
    .iter()
    .enumerate()
    .map(|(i, (name, icon))| AppEntry {
        id: format!("fixture-{i}"),
        name: name.to_string(),
        icon: Some(icon.to_string()),
        path: PathBuf::from("/nonexistent/fixture.desktop"),
    })
    .collect()
}
fn control(label: &str, value: &str, detail: &str, state: ControlState) -> Control {
    Control {
        state,
        value: Some(ControlValue::Text(value.into())),
        label: label.into(),
        detail: Some(detail.into()),
        action: None,
    }
}
fn services() -> ServiceView {
    let mut brightness = control("Brightness", "68%", "", ControlState::Writable);
    brightness.value = Some(ControlValue::Percent(68));
    ServiceView {
        settings: Some(SettingsSnapshot {
            network: control(
                "Wi-Fi",
                "Connected",
                "Wireless network",
                ControlState::Writable,
            ),
            brightness,
            keyboard: control(
                "Keyboard",
                "Hidden",
                "Use the bottom two-finger gesture",
                ControlState::Writable,
            ),
            motion: control(
                "Motion",
                "Full motion",
                "Follows your touch",
                ControlState::Writable,
            ),
            volume: unknown_volume_placeholder(),
        }),
        notifications: Some(NotificationSnapshot {
            count: 2,
            preview: None,
            events: vec![
                NotificationEvent {
                    id: 1,
                    source: "Files".into(),
                    icon: Some("system-file-manager".into()),
                    summary: "Copy complete".into(),
                    body: "Your files are ready".into(),
                    priority: Priority::Ordinary,
                    timestamp: 0,
                    error: None,
                    dismissible: true,
                    action_available: false,
                },
                NotificationEvent {
                    id: 2,
                    source: "System".into(),
                    icon: Some("preferences-system".into()),
                    summary: "Theme updated".into(),
                    body: "Appearance is applied across the shell".into(),
                    priority: Priority::Ordinary,
                    timestamp: 0,
                    error: None,
                    dismissible: true,
                    action_available: false,
                },
            ],
        }),
        audio: Some(k230_shell_rust::pipewire_ipc::GraphSnapshot {
            sinks: vec![k230_shell_rust::pipewire_ipc::Sink {
                id: 1,
                name: "fixture-output".into(),
                description: "Audio controller".into(),
                linear_volume: k230_shell_rust::volume::percent_to_linear(40),
                muted: false,
                is_default: true,
                route: None,
            }],
            streams: Vec::new(),
        }),
        ..ServiceView::default()
    }
}
fn theme_entry(theme: &AppearanceSnapshot) -> ThemeEntry {
    let report: serde_json::Value =
        serde_json::from_slice(&fs::read(theme.path.join("report.json")).unwrap()).unwrap();
    let source = PathBuf::from(report["source"].as_str().unwrap());
    ThemeEntry {
        id: theme.generation.clone(),
        name: report["name"].as_str().unwrap().into(),
        label: report["name"].as_str().unwrap().replace('-', " "),
        origin: ThemeOrigin::Builtin,
        preview_path: Some(source.join("preview.png")),
    }
}
fn chooser(theme: &AppearanceSnapshot, all: &[AppearanceSnapshot]) -> ThemeView {
    let entry = theme_entry(theme);
    let mut view = ThemeView::default();
    view.page = ThemePage::List;
    view.theme_position = all
        .iter()
        .position(|t| t.generation == theme.generation)
        .unwrap() as f64;
    view.list = Some(ThemeList {
        themes: all.iter().map(theme_entry).collect(),
        active: ActiveTheme {
            id: Some(entry.id.clone()),
            generation: Some(theme.generation.clone()),
        },
    });
    let selected = theme
        .backgrounds
        .iter()
        .position(|b| b.selected)
        .unwrap_or(0);
    view.background_position = selected as f64;
    view.preview = Some(ThemePreview {
        theme: entry,
        generation: theme.generation.clone(),
        appearance_path: theme.path.clone(),
        palette: BTreeMap::new(),
        icon_theme: theme.icon_theme.clone(),
        backgrounds: theme
            .backgrounds
            .iter()
            .enumerate()
            .map(|(i, b)| BackgroundChoice {
                id: format!("background-{i}"),
                label: b.relative.clone(),
                kind: BackgroundKind::Image,
                path: b.staged_path.clone(),
                selected: b.selected,
                decode_status: "host decode".into(),
            })
            .collect(),
        compatibility: Compatibility {
            adapted: vec![],
            applied: theme.applied.clone(),
            unavailable: theme.unavailable.clone(),
            unknown: theme.unknown.clone(),
        },
        activated: true,
        app_appearance: None,
    });
    view
}
fn main() -> Result<(), String> {
    let args: Vec<String> = std::env::args().skip(1).collect();
    if args.len() != 3 {
        return Err("usage: render_polish_evidence OUT DARK-GENERATION LIGHT-GENERATION".into());
    }
    let out = PathBuf::from(&args[0]);
    fs::create_dir_all(&out).map_err(|e| e.to_string())?;
    let runtime = std::env::temp_dir().join(format!("k230-polish-evidence-{}", std::process::id()));
    fs::create_dir(&runtime).map_err(|e| e.to_string())?;
    fs::set_permissions(&runtime, fs::Permissions::from_mode(0o700)).unwrap();
    let mut themes = Vec::new();
    for (i, path) in args[1..].iter().enumerate() {
        let receiver = AppearanceReceiver::bind_with_roots(
            runtime.join(format!("{i}.sock")),
            Some(PathBuf::from(path)),
            runtime.clone(),
        )?;
        themes.push(receiver.active().ok_or("no active appearance")?.clone());
    }
    let apps = apps();
    for (name, theme) in ["dark", "light"].iter().zip(themes.iter()) {
        let mut cache = RendererCache::default();
        cache.set_appearance(Some(theme.clone()));
        cache.set_services(services());
        let wallpaper = BackgroundCache::new()
            .render(
                theme
                    .selected_background
                    .as_deref()
                    .ok_or("no selected wallpaper")?,
                Some(&theme.path),
                W,
                H,
                FitMode::Crop,
            )?
            .to_vec();
        for kind in ["home", "drawer", "settings", "shade", "themes"] {
            let mut pixels = vec![0; (W * H * 4) as usize];
            if kind == "home" {
                let per_page = home_grid::apps_per_page(W, H);
                let mut layout = HomeLayout {
                    dock: vec![None; home_grid::DOCK_SLOTS],
                    ..HomeLayout::default()
                };
                layout.place(
                    HomeSlot::Grid { page: 0, slot: 0 },
                    HomeItem::Widget {
                        widget: WidgetKind::ClockMinimal,
                    },
                    per_page,
                    false,
                );
                for (i, app) in apps.iter().take(4).enumerate() {
                    layout.place(
                        HomeSlot::Dock { slot: i },
                        HomeItem::app(app.id.clone()),
                        4,
                        false,
                    );
                }
                for (i, app) in apps.iter().skip(4).enumerate() {
                    layout.place(
                        HomeSlot::Grid {
                            page: 0,
                            slot: 8 + i,
                        },
                        HomeItem::app(app.id.clone()),
                        per_page,
                        false,
                    );
                }
                cache.draw_home(&mut pixels, W, H, &apps, &HomeScreen::new(layout, W as f64))?;
            } else {
                if kind == "themes" {
                    cache.set_theme_view(chooser(theme, &themes));
                    // Real asynchronous thumbnail worker, bounded wait; fail on missing source.
                    for _ in 0..4500 {
                        cache.poll_theme_thumbnails(W);
                        if !cache.theme_thumbnails_pending(W) {
                            break;
                        }
                        std::thread::sleep(Duration::from_millis(10));
                    }
                    if cache.theme_thumbnails_pending(W) {
                        return Err("thumbnail worker did not finish within 45 seconds".into());
                    }
                }
                let route = match kind {
                    "drawer" => Route::Drawer,
                    "shade" => Route::Shade,
                    _ => Route::Settings,
                };
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
            let target = ImageSurface::create(Format::ARgb32, W as i32, H as i32).unwrap();
            let cr = Context::new(&target).unwrap();
            cr.set_source_surface(surface(wallpaper.clone()), 0.0, 0.0)
                .unwrap();
            cr.paint().unwrap();
            cr.set_source_surface(surface(pixels), 0.0, 0.0).unwrap();
            cr.paint().unwrap();
            drop(cr);
            let path = out.join(format!("{name}-{kind}.png"));
            target
                .write_to_png(&mut fs::File::create(&path).unwrap())
                .unwrap();
            println!("{}", path.display());
        }
    }
    fs::remove_dir_all(runtime).map_err(|e| e.to_string())?;
    Ok(())
}
