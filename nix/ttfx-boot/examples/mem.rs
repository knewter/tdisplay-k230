//! Peak heap per effect (counting allocator) and frame production time.
//! usage: mem <text file> <seed> <cols> <rows> <fps>
use std::alloc::{GlobalAlloc, Layout, System};
use std::sync::atomic::{AtomicUsize, Ordering::Relaxed};
struct Count;
static CUR: AtomicUsize = AtomicUsize::new(0);
static PEAK: AtomicUsize = AtomicUsize::new(0);
unsafe impl GlobalAlloc for Count {
    unsafe fn alloc(&self, l: Layout) -> *mut u8 {
        let c = CUR.fetch_add(l.size(), Relaxed) + l.size();
        PEAK.fetch_max(c, Relaxed);
        System.alloc(l)
    }
    unsafe fn dealloc(&self, p: *mut u8, l: Layout) { CUR.fetch_sub(l.size(), Relaxed); System.dealloc(p, l) }
    unsafe fn realloc(&self, p: *mut u8, l: Layout, n: usize) -> *mut u8 {
        if n > l.size() { let c = CUR.fetch_add(n - l.size(), Relaxed) + n - l.size(); PEAK.fetch_max(c, Relaxed); } else { CUR.fetch_sub(l.size() - n, Relaxed); }
        System.realloc(p, l, n)
    }
}
#[global_allocator] static A: Count = Count;
fn main() {
    let a: Vec<String> = std::env::args().collect();
    let text = std::fs::read_to_string(&a[1]).unwrap();
    println!("| effect | frames | peak heap KiB | live at end KiB | host ms |");
    println!("| --- | ---: | ---: | ---: | ---: |");
    for name in k230_ttfx_boot::EFFECT_NAMES {
        CUR.store(0, Relaxed); PEAK.store(0, Relaxed);
        let t = std::time::Instant::now();
        let mut run = k230_ttfx_boot::Run::new(name, &text, a[2].parse().unwrap(), a[3].parse().unwrap(), a[4].parse().unwrap(), a[5].parse().unwrap()).unwrap();
        let mut n = 0u32;
        while let Some(f) = run.next_frame() { run.recycle(f); n += 1; }
        let live = CUR.load(Relaxed);
        println!("| {name} | {n} | {} | {} | {:.0} |", PEAK.load(Relaxed) / 1024, live / 1024, t.elapsed().as_secs_f64() * 1000.0);
        drop(run);
    }
}
