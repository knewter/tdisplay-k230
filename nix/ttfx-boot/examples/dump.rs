//! Host harness: print frames in `ttfx --parity-dump` format.
//! usage: dump <effect> <text file> <seed> <cols> <rows> <fps> [max frames]
use std::io::Write;
fn main() {
    let a: Vec<String> = std::env::args().collect();
    let text = std::fs::read_to_string(&a[2]).unwrap();
    let mut run = k230_ttfx_boot::Run::new(&a[1], &text, a[3].parse().unwrap(), a[4].parse().unwrap(),
        a[5].parse().unwrap(), a[6].parse().unwrap()).unwrap_or_else(|e| { eprintln!("{e:?}"); std::process::exit(1) });
    let max: u64 = a.get(7).map_or(u64::MAX, |v| v.parse().unwrap());
    let out = std::io::stdout();
    let mut out = out.lock();
    let mut n = 0u64;
    while let Some(f) = run.next_frame() {
        writeln!(out, "{}", f.len()).unwrap();
        out.write_all(f.as_bytes()).unwrap();
        out.write_all(b"\n").unwrap();
        run.recycle(f);
        n += 1;
        if n >= max { break; }
    }
    eprintln!("frames={n}");
}
