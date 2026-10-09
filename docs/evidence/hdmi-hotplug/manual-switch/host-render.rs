//! Host-only production Settings paint; synthetic controls, no board/Wayland.
use cairo::{Context, Format, ImageSurface};
use k230_shell_rust::{
    render::{RenderParams, RendererCache},
    service_data::{Control, ControlState, ControlValue, PowerAction, SettingsSnapshot},
    service_ui::{Confirmation, ServiceView}, Route,
};
use std::{fs, path::PathBuf, time::{Duration, Instant}};
fn control(label: &str, value: &str) -> Control {
    Control { label: label.into(), value: Some(ControlValue::Text(value.into())),
        state: ControlState::ReadOnly, detail: None, action: None }
}
fn main() -> Result<(), Box<dyn std::error::Error>> {
    let directory = PathBuf::from(std::env::args().nth(1).ok_or("output directory required")?);
    fs::create_dir_all(&directory)?;
    for (width, height) in [(568u32, 1232u32), (800, 1280), (1920, 1080)] {
        for confirmed in [false, true] {
            let mut display = control("Display", "Next boot: AMOLED");
            display.state = ControlState::Action;
            display.action = Some("hdmi".into());
            display.detail = Some("Tap for HDMI once; reboot returns to AMOLED".into());
            let view = ServiceView { settings: Some(SettingsSnapshot {
                network: control("Network", "Link available"), brightness: control("Brightness", "50%"),
                keyboard: control("Keyboard", "Toggle keyboard"), motion: control("Motion", "Off"),
                volume: control("Volume", "Unavailable"), display: Some(display),
            }), confirmation: confirmed.then(|| Confirmation { token: "a".repeat(32), action: PowerAction::Hdmi,
                label: "Restart on HDMI for one boot?".into(), expires_at: Instant::now() + Duration::from_secs(30) }),
                ..ServiceView::default() };
            let mut cache = RendererCache::default();
            cache.set_services(view);
            let mut pixels = vec![0; (width * height * 4) as usize];
            cache.draw(&mut pixels, RenderParams { width, height, route: Route::Settings, progress: 1.0, scroll: 0.0 }, &[])?;
            let frame = ImageSurface::create_for_data(pixels, Format::ARgb32, width as i32, height as i32, (width * 4) as i32)?;
            let target = ImageSurface::create(Format::ARgb32, width as i32, height as i32)?;
            let cr = Context::new(&target)?;
            cr.set_source_rgb(30.0/255.0, 30.0/255.0, 46.0/255.0);
            cr.paint()?;
            cr.set_source_surface(&frame, 0.0, 0.0)?;
            cr.paint()?;
            drop(cr);
            let state = if confirmed { "confirm" } else { "settings" };
            target.write_to_png(&mut fs::File::create(directory.join(format!("host-{state}-{width}x{height}.png")))?)?;
        }
    }
    Ok(())
}
