## 1. Reproducible player configuration

- [x] 1.1 Add the pinned mpv/FFmpeg software playback derivations and the documented `wlshm`/software-H.264 profile to the Nix shell image; verify the narrow package evaluations and derivation paths succeed without private URLs or credentials.
- [x] 1.2 Add the public BBB test manifest, selected 480x270 baseline, explicit audio-disabled setting, and runtime URL boundary to the evidence/probe procedure without embedding a network secret; verify a source scan finds no protected-network material in source, desktop files, argv templates, or the Nix store.
- [x] 1.3 Build the affected riscv64 packages and image, record closure/path deltas and source hashes, and verify `nix build .#sdImage` plus the named package derivations succeed on the host.

## 2. Apps entry and recovery controls

- [ ] 2.1 Add a visible Terminal video desktop entry through the existing Apps/Foot bridge with the documented player profile; verify `k230-desktop-catalog list` discovers it and `launch ID` returns a successful process launch with the expected terminal environment.
- [x] 2.2 Define and implement stop, Back/Home return, EOF, network-error, and failed-decoder recovery without leaving an orphan player or runtime secret; verify launcher tests cover success, failure, return, and empty/error states.
- [ ] 2.3 Boot the resulting image and exercise launch, stop, Back/Home, and recovery with injected input; verify the existing Apps, Help, Keyboard, Terminal, Monitor, and System controls remain usable and record injected versus physical interaction explicitly.

## 3. Software playback baseline

- [x] 3.1 Run the 480x270 software BBB trial for at least 30 seconds and record manifest, representation, source frame rate, `wlshm`, audio state, decoder drops, video-output drops, cache, and player exit reason in `docs/evidence/`.
- [x] 3.2 Run the 640x360 comparison trial with the same software path and record its counters and network/cache behavior; verify the report distinguishes the comparison from an accepted smoothness claim.
- [x] 3.3 Capture CPU samples with verified `CLK_TCK` and page size, and calculate only clearly labeled interval estimates; verify raw `/proc` transcripts and the calculation method are committed with no secret or unrelated terminal data.
- [ ] 3.4 Capture a native decoded frame and a physical panel frame for the accepted software baseline; verify the report labels native screenshots, camera readability, decoder counters, and scanout/presentation evidence as separate claims.

## 4. MVX hardware decoder experiment

- [x] 4.1 Build or expose the MVX V4L2 probe/player path against the audited device interface; verify the device node, capabilities, negotiated H.264 format, and output format using a narrow board console probe before claiming decode.
- [ ] 4.2 Attempt the same bounded network representation through MVX and record whether frames decode and reach the existing output; verify a failed negotiation falls back to software and leaves the shell recoverable.
- [ ] 4.3 Compare software and MVX CPU, drop, cache, and presentation results over at least 30 seconds; verify the report names the actual decoder path and does not infer hardware acceleration from `/dev/video0` presence alone.

## 5. Presentation and audio acceptance

- [x] 5.1 Add a synchronized presentation-timing method that distinguishes decoded frames from actual compositor/panel presentation, then run it for at least 30 seconds at the selected source cadence; verify timestamps, sample count, and limitations are recorded and no current hardware counter is treated as valid without checking its reset/units behavior.
- [x] 5.2 Measure audio separately with an explicit enabled configuration, or record audio as unverified when the board path cannot establish physical output; verify video acceptance does not inherit an audio claim.
- [ ] 5.3 Run the final shell regression after playback and cleanup; verify serial access, touch/display services, keyboard, Apps/Back/Home, and removal of temporary player/network state.

## 6. Review and integration

- [x] 6.1 Run relevant launcher/player tests and `openspec validate the-shell-plays-network-video --strict`; verify every requirement has grounded evidence or an explicit `UNVERIFIED` marker.
- [ ] 6.2 Run `./scripts/build_site.py` and `./tools/blob-scan.py --no-vendor`; verify all committed screenshots, clips, logs, and any media test assets have provenance, attribution, hashes, and DATA inventory rows.

Initial completed tasks are grounded in `docs/evidence/big-buck-bunny/README.md`
and its committed 270p/360p logs and CPU sample. These are temporary-probe
results; package/image integration and presentation acceptance remain open.

Task 4.1: `docs/evidence/video-acceleration/v4l2-capabilities.txt` records the
live MVX H.264 capability; `mvx-decode-300.txt` proves real decoded frames.
MVX timing, automatic fallback and integrated controls remain unaccepted.

Task 5.1: `docs/evidence/network-video/README.md` and the software/MVX
presentation logs record >30-second hardware-signalled compositor feedback,
unique submitted/presented frame IDs, clock/sequence validation and limitations.
Final-image lifecycle regression remains separate.

Host integration proof: `docs/evidence/network-video/integration-host.md` and its
JSON record cover package/image builds, closure deltas, runtime source boundary
and lifecycle tests. They do not close the final-image board acceptance tasks.
