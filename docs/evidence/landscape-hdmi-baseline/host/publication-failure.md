# Tooling-only work-board publication correction

The plan35e9fdca passed OpenSpec strict validation but CI39371311915 failed
in `scripts/build_site.py` at `scripts/render_work_board.py`:

```
work board error: missing delta specification for the-landscape-hdmi-shell-has-a-reproducible-motion-baseline
```

The renderer had no support for OpenSpec's explicit `skip_specs: true` metadata.
This change adds support for the top-level literal while preserving rejection
of absent, false, quoted, nested or repeated markers, and conflicting deltas.
No requirement was invented to bypass this guard. Twenty-five work-board tests
and the complete working-tree work-data render pass after the correction.
The superseded tooling checkpointe8caf598 has the same publication blocker.
