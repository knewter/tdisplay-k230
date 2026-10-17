//! Writes the shell's stroked icon set as one sheet: every glyph at the row
//! size (48 px) and the drawer size (64 px), on a dark and a light ground.
//!
//!     cargo run --example render_glyph_evidence -- <out.png>
use cairo::{Context, Format, ImageSurface};
use k230_shell_rust::glyph::{self, Glyph};

fn main() {
    let out = std::env::args().nth(1).expect("output path");
    let cell = 88.0;
    let cols = Glyph::ALL.len() as f64;
    let (w, h) = ((cols * cell + 16.0) as i32, (4.0 * cell) as i32);
    let surface = ImageSurface::create(Format::Rgb24, w, h).unwrap();
    let cr = Context::new(&surface).unwrap();
    // Rows: dark 48, dark 64, light 48, light 64 (catppuccin base/text).
    for (row, (ground, ink, size)) in [
        (0x1e1e2e, 0xcdd6f4, glyph::ROW),
        (0x1e1e2e, 0xcdd6f4, glyph::DRAWER),
        (0xeff1f5, 0x4c4f69, glyph::ROW),
        (0xeff1f5, 0x4c4f69, glyph::DRAWER),
    ]
    .into_iter()
    .enumerate()
    {
        let y = row as f64 * cell;
        let rgb = |v: u32, shift: u32| f64::from((v >> shift) & 0xff) / 255.0;
        cr.set_source_rgb(rgb(ground, 16), rgb(ground, 8), rgb(ground, 0));
        cr.rectangle(0.0, y, f64::from(w), cell);
        let _ = cr.fill();
        for (col, item) in Glyph::ALL.iter().enumerate() {
            let x = 8.0 + col as f64 * cell + (cell - size) / 2.0;
            glyph::paint(&cr, *item, x, y + (cell - size) / 2.0, size, ink, 1.0);
        }
    }
    drop(cr);
    surface.write_to_png(&mut std::fs::File::create(out).unwrap()).unwrap();
}
