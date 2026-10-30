//! A boot-time ttfx run: `no_std` + `alloc`, deterministic, one frame at a time.
//!
//! The effect is chosen by name, the text by the caller, and the run by a
//! seed, so a boot can pick all three. Frames are the same ANSI text
//! `ttfx --parity-dump` prints (SGR 0 and 38;2 only), which
//! `textfx_parse_frame` in the boot renderer already understands.
#![cfg_attr(not(feature = "hosted"), no_std)]
extern crate alloc;

use alloc::boxed::Box;
use alloc::string::String;
use ttfx::engine::canvas::Anchor;
use ttfx::engine::ctx::{Clock, EngineCtx};
use ttfx::engine::effect::Effect;
use ttfx::engine::error::EngineError;
use ttfx::engine::terminal::TerminalConfig;
use ttfx::utils::rng::Rng;

pub use ttfx::effects::NAMES as EFFECT_NAMES;

#[cfg(feature = "capi")]
pub mod capi;
#[cfg(feature = "fw")]
mod fw;

#[derive(Debug)]
pub enum Error {
    UnknownEffect,
    Engine(EngineError),
}

pub struct Run {
    ctx: EngineCtx,
    effect: Box<dyn Effect>,
    frames: u32,
}

impl Run {
    /// `cols` x `rows` is the canvas, anchored at the centre; `fps` only sets
    /// the virtual clock the clock-driven effects (matrix, thunderstorm) read.
    pub fn new(effect: &str, text: &str, seed: u64, cols: i64, rows: i64, fps: i64) -> Result<Run, Error> {
        let mut effect = ttfx::effects::build_default(effect).ok_or(Error::UnknownEffect)?;
        let config = TerminalConfig {
            frame_rate: fps,
            canvas_width: cols,
            canvas_height: rows,
            anchor_canvas: Anchor::C,
            anchor_text: Anchor::C,
            ignore_terminal_dimensions: true,
            ..TerminalConfig::default()
        };
        let mut ctx = EngineCtx::new(text, config, Rng::seeded(seed), Clock::virtual_with_frame_rate(fps))
            .map_err(Error::Engine)?;
        effect.build(&mut ctx).map_err(Error::Engine)?;
        Ok(Run { ctx, effect, frames: 0 })
    }

    /// The next frame, or None when the effect is complete.
    pub fn next_frame(&mut self) -> Option<String> {
        let f = self.effect.next_frame(&mut self.ctx)?;
        self.frames += 1;
        Some(f)
    }

    pub fn frames(&self) -> u32 {
        self.frames
    }

    /// Give a frame's buffer back so the next one reuses it.
    pub fn recycle(&mut self, frame: String) {
        self.ctx.terminal.recycle_output_string(frame);
    }
}
