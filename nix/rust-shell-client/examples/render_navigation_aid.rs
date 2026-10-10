//! Production Cairo/Pango host renders. No compositor, board, or finger input.
use cairo::{Format, ImageSurface};
use k230_shell_rust::{
    appearance::{AppearanceReceiver, AppearanceSnapshot},
    evidence_render,
    render::{RenderParams, RendererCache},
    service_ui::ServiceView,
    Route,
};
use std::os::unix::fs::PermissionsExt;
use std::{
    env, fs,
    path::{Path, PathBuf},
};

fn render(out: &Path, theme: Option<&AppearanceSnapshot>, route: Route, aid: bool, w: u32, h: u32) {
    let mut cache = RendererCache::default();
    if let Some(theme) = theme {
        cache.set_appearance(Some(theme.clone()));
    }
    cache.set_services(ServiceView {
        navigation_aid: aid,
        keyboard_gesture_hint: true,
        ..ServiceView::default()
    });
    let mut bytes = vec![0; (w * h * 4) as usize];
    cache
        .draw(
            &mut bytes,
            RenderParams {
                width: w,
                height: h,
                route,
                progress: 1.0,
                scroll: 0.0,
            },
            &evidence_render::synthetic_apps(30),
        )
        .unwrap();
    let surface =
        ImageSurface::create_for_data(bytes, Format::ARgb32, w as i32, h as i32, (w * 4) as i32)
            .unwrap();
    surface
        .write_to_png(&mut fs::File::create(out).unwrap())
        .unwrap();
}
fn main() {
    let args: Vec<_> = env::args().skip(1).collect();
    assert_eq!(
        args.len(),
        3,
        "render_navigation_aid OUT DARK-GENERATION LIGHT-GENERATION"
    );
    let out = PathBuf::from(&args[0]);
    fs::create_dir_all(&out).unwrap();
    let runtime = env::temp_dir().join(format!("k230-help-render-{}", std::process::id()));
    fs::create_dir(&runtime).unwrap();
    fs::set_permissions(&runtime, fs::Permissions::from_mode(0o700)).unwrap();
    for (label, path) in [("dark", &args[1]), ("light", &args[2])] {
        let receiver = AppearanceReceiver::bind_with_roots(
            runtime.join(format!("{label}.sock")),
            Some(PathBuf::from(path)),
            runtime.clone(),
        )
        .unwrap();
        let theme = receiver.active().unwrap().clone();
        for (name, route, aid) in [
            ("drawer", Route::Drawer, false),
            ("help", Route::Help, false),
            ("buttons", Route::Help, true),
        ] {
            render(
                &out.join(format!("{label}-{name}.png")),
                Some(&theme),
                route,
                aid,
                568,
                1232,
            );
        }
        render(
            &out.join(format!("{label}-buttons-hdmi.png")),
            Some(&theme),
            Route::Help,
            true,
            1920,
            1080,
        );
    }
    fs::remove_dir_all(runtime).unwrap();
    evidence_render::render_route(
        &out.join("drawer-568x1232.png"),
        568,
        1232,
        Route::Drawer,
        &evidence_render::synthetic_apps(30),
    );
}
