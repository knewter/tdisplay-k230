//! C ABI over `Run` (declared in nix/ttfx-boot/ttfx_boot.h).
//!
//! The caller supplies the global allocator and panic handler; the `fw` feature
//! does (allocator over a caller-supplied arena, panic hook) for U-Boot.

use alloc::boxed::Box;
use alloc::string::String;
use crate::Run;

pub struct Handle { run: Run, frame: Option<String> }

/// Start a run. `effect` and `text` are NUL-free byte strings with explicit
/// lengths. Returns an opaque handle or null (unknown effect, bad text, no memory).
#[no_mangle]
pub unsafe extern "C" fn ttfx_fw_new(effect: *const u8, effect_len: usize, text: *const u8, text_len: usize,
                                     seed: u64, cols: i32, rows: i32, fps: i32) -> *mut Handle {
    let e = core::slice::from_raw_parts(effect, effect_len);
    let t = core::slice::from_raw_parts(text, text_len);
    let (Ok(e), Ok(t)) = (core::str::from_utf8(e), core::str::from_utf8(t)) else { return core::ptr::null_mut() };
    match Run::new(e, t, seed, cols as i64, rows as i64, fps as i64) {
        Ok(run) => Box::into_raw(Box::new(Handle { run, frame: None })),
        Err(_) => core::ptr::null_mut(),
    }
}

/// Produce the next frame. Returns its byte length (> 0) and sets `*out` to its
/// bytes, valid until the next call; returns 0 when the effect is complete.
#[no_mangle]
pub unsafe extern "C" fn ttfx_fw_next(h: *mut Handle, out: *mut *const u8) -> isize {
    let h = &mut *h;
    if let Some(old) = h.frame.take() { h.run.recycle(old); }
    match h.run.next_frame() {
        Some(f) => {
            *out = f.as_ptr();
            let n = f.len() as isize;
            h.frame = Some(f);
            n
        }
        None => 0,
    }
}

#[no_mangle]
pub unsafe extern "C" fn ttfx_fw_frames(h: *const Handle) -> u32 { (*h).run.frames() }

#[no_mangle]
pub unsafe extern "C" fn ttfx_fw_free(h: *mut Handle) { drop(Box::from_raw(h)); }
