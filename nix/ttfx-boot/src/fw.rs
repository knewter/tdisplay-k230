//! C ABI for the stage 1 boot animation (freestanding riscv64imac, soft-float).
//!
//! The host supplies memory: `ttfx_fw_init(arena, len)` hands over a region
//! the allocator owns, so the Rust side never calls U-Boot's malloc and its
//! peak (1-13 MiB depending on the effect) cannot starve U-Boot's own heap.
//! Nothing here unwinds; a panic calls `ttfx_fw_panic` (the host's hook) and
//! then spins.
use core::alloc::{GlobalAlloc, Layout};
use core::cell::UnsafeCell;

// ---------------------------------------------------------------- allocator
// A first-fit free list with coalescing over the arena. Blocks carry a
// 16-byte header (size, next-free offset is kept in free blocks only).
const ALIGN: usize = 16;
const HDR: usize = 16;

struct Arena {
    base: usize,
    len: usize,
    free_head: usize, // address of first free block or 0
}
struct Heap(UnsafeCell<Arena>);
unsafe impl Sync for Heap {}
#[global_allocator]
static HEAP: Heap = Heap(UnsafeCell::new(Arena { base: 0, len: 0, free_head: 0 }));

#[inline]
fn up(n: usize, a: usize) -> usize { (n + a - 1) & !(a - 1) }

// free block layout at address p: [size: usize][next: usize]; allocated block: [size][pad]
unsafe fn rd(p: usize) -> usize { *(p as *const usize) }
unsafe fn wr(p: usize, v: usize) { *(p as *mut usize) = v }

unsafe impl GlobalAlloc for Heap {
    unsafe fn alloc(&self, l: Layout) -> *mut u8 {
        let a = &mut *self.0.get();
        let align = l.align().max(ALIGN);
        let need = up(l.size().max(1) + HDR, ALIGN);
        let mut prev = 0usize;
        let mut cur = a.free_head;
        while cur != 0 {
            let size = rd(cur);
            // payload address must be aligned: payload = cur + HDR (cur is ALIGN-aligned)
            let payload = cur + HDR;
            let aligned = up(payload, align);
            let waste = aligned - payload;
            if waste == 0 && size >= need {
                let rest = size - need;
                let next = rd(cur + 8);
                if rest >= 2 * ALIGN {
                    let nb = cur + need;
                    wr(nb, rest);
                    wr(nb + 8, next);
                    wr(cur, need);
                    if prev == 0 { a.free_head = nb } else { wr(prev + 8, nb) }
                } else if prev == 0 { a.free_head = next } else { wr(prev + 8, next) }
                return (cur + HDR) as *mut u8;
            }
            prev = cur;
            cur = rd(cur + 8);
        }
        // Over-aligned requests (> 16) are not used by this crate's dependencies;
        // refuse rather than guess.
        core::ptr::null_mut()
    }
    unsafe fn dealloc(&self, p: *mut u8, _l: Layout) {
        let a = &mut *self.0.get();
        let blk = p as usize - HDR;
        // insert in address order, coalescing neighbours
        let mut prev = 0usize;
        let mut cur = a.free_head;
        while cur != 0 && cur < blk { prev = cur; cur = rd(cur + 8); }
        wr(blk + 8, cur);
        if prev == 0 { a.free_head = blk } else { wr(prev + 8, blk) }
        if cur != 0 && blk + rd(blk) == cur {
            wr(blk, rd(blk) + rd(cur));
            wr(blk + 8, rd(cur + 8));
        }
        if prev != 0 && prev + rd(prev) == blk {
            wr(prev, rd(prev) + rd(blk));
            wr(prev + 8, rd(blk + 8));
        }
    }
}

/// Hand the allocator its arena (16-byte aligned, `len` >= 64 KiB). Returns 0 on success.
#[no_mangle]
pub unsafe extern "C" fn ttfx_fw_init(arena: *mut u8, len: usize) -> i32 {
    let base = up(arena as usize, ALIGN);
    let len = (len - (base - arena as usize)) & !(ALIGN - 1);
    if len < 64 * 1024 { return -1; }
    let a = &mut *HEAP.0.get();
    a.base = base;
    a.len = len;
    a.free_head = base;
    wr(base, len);
    wr(base + 8, 0);
    0
}

// ------------------------------------------------------------------ panics
extern "C" {
    /// Host hook: report a fatal Rust panic (no return expected).
    fn ttfx_fw_panic(msg: *const u8, len: usize);
}
#[panic_handler]
fn panic(info: &core::panic::PanicInfo) -> ! {
    use core::fmt::Write;
    let mut buf = heapless_buf::Buf::new();
    let _ = write!(buf, "{info}");
    unsafe { ttfx_fw_panic(buf.as_ptr(), buf.len()) };
    loop {}
}
mod heapless_buf {
    pub struct Buf { b: [u8; 160], n: usize }
    impl Buf {
        pub fn new() -> Self { Buf { b: [0; 160], n: 0 } }
        pub fn as_ptr(&self) -> *const u8 { self.b.as_ptr() }
        pub fn len(&self) -> usize { self.n }
    }
    impl core::fmt::Write for Buf {
        fn write_str(&mut self, s: &str) -> core::fmt::Result {
            let k = s.len().min(self.b.len() - self.n);
            self.b[self.n..self.n + k].copy_from_slice(&s.as_bytes()[..k]);
            self.n += k;
            Ok(())
        }
    }
}

