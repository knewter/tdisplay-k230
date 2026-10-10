# Deliberately opened Help and navigation aid

Task 1.5 of `the-handheld-presents-a-coherent-shell`; source starts from
`6adac5467ce152bbc7b043dac8067c6e67f3b005`, branch
`closeout/coherent-integration-2026-10-10`, worktree
`/home/jadams/tmp/k230-coherent-closeout-2026-10-10`.

All Apps now has a real Help target beside Search. Help explains the existing
bottom Home/Overview, drawer, top shade, panel-close and keyboard routes. Its
**Navigation buttons** action deliberately opens large labeled Home, All Apps,
Notifications and Settings controls. Return to Help closes the aid; Return to
All Apps closes Help. The aid resets on route change/unmap and creates no
persistent bar or saved preference. The separate `coherentShell = false` Nix
session still selects the old launcher as rollback; the ordinary image's
coherent selection was already changed by earlier work.

Only userspace Rust changes. The smaller search field and Help target share
paint/hit geometry. The app grid, filtering, scroll and compositor live-card
paths retain their established geometry. Home uses the existing `card_shell
home` request on a worker, with a two-second deadline and visible pending/failure
feedback. A stale reply cannot close another route after Help has been left.
The other buttons use existing shell routes; no universal Back key is sent to
an app. Settings opens its controls page rather than a retained theme subpage.

## Host proof

[Host tests](host-tests.log) record the full task group's command:

```sh
CARGO_TARGET_DIR=/home/jadams/tmp/k230-admission-host-target \
  cargo test --offline --locked --manifest-path nix/rust-shell-client/Cargo.toml
```

The new tests exercise deliberate opt-in, matched route targets at 300×600,
568×1232, 1920×1080 and 1080×1920, no Help/search/app-grid overlap, cancelled
movement/cross-button/nonfinite input, and successful/failed/timed-out Home
requests using an actual worker command fixture. The full existing suite also
covers released buffers, routes, cancellation, search, theme transactions,
background decode and pixel references. See [proof.json](proof.json) for totals,
input identities and hashes. The prior drawer reference changed intentionally
because Help is new; its fresh reviewed render is copied to
`docs/evidence/shell-responsive/drawer-568x1232.png`. Home, wallpaper and Settings
references pass unchanged.

[Dark Help](dark-help.png), [light Help](light-help.png),
[dark navigation buttons](dark-buttons.png), [light navigation buttons](light-buttons.png),
[dark drawer](dark-drawer.png), [light drawer](light-drawer.png),
[dark HDMI buttons](dark-buttons-hdmi.png) and [light HDMI buttons](light-buttons-hdmi.png)
are production **host Cairo/Pango renders**. They have no Wayland/compositor,
QEMU, physical panel, real finger, latency or installation provenance. The app
names are bounded nonsecret synthetic fixtures; appearances are the pinned
Catppuccin dark/light generations, validated with the production receiver.

Reproduction (preparation only; no activation):

```sh
python3 tools/theme_activate.py catppuccin --prepare-only \
  --state-root /home/jadams/tmp/k230-help-appearance \
  --builtins /nix/store/9c1i2zfliab82a80iv87929qkngn1ca0-handheld-theme-default-28ceaae7/share/omarchy/themes \
  --background backgrounds/2-waves.webp
python3 tools/theme_activate.py catppuccin-latte --prepare-only \
  --state-root /home/jadams/tmp/k230-help-appearance \
  --builtins /nix/store/9c1i2zfliab82a80iv87929qkngn1ca0-handheld-theme-default-28ceaae7/share/omarchy/themes \
  --background backgrounds/1-color-fade.webp
CARGO_TARGET_DIR=/home/jadams/tmp/k230-admission-host-target \
XDG_DATA_DIRS=/nix/store/in3nc21zx02xiz2rdp5bpq36719x3axd-handheld-theme-icons-25.10.3/share \
  cargo run --offline --locked --manifest-path nix/rust-shell-client/Cargo.toml \
  --example render_navigation_aid -- docs/evidence/coherent-shell/navigation-aid-2026-10-10 \
  /home/jadams/tmp/k230-help-appearance/generations/dacf0af8c897e6c51fe922de \
  /home/jadams/tmp/k230-help-appearance/generations/c448496d80fec3ae02a892bd
```

The generation paths/hashes and final render command are also recorded in
[proof.json](proof.json) and [render.log](render.log).

## Build and remaining physical gate

Source `9e4515ed32cc849bfcc56dbe60d02e877bee75a7` cross-build passed, selecting the actual coherent
configuration package set. [Package build](package-build.log) built exactly one
Rust derivation and fetched no dependencies. Target: `/nix/store/z4j8bc7iwz9m7pap376zy0j0z16295lr-k230-shell-rust-riscv64-unknown-linux-gnu-0.1.0/bin/k230-shell-rust: ELF 64-bit LSB pie executable, UCB RISC-V, RVC, double-float ABI, version 1 (SYSV), dynamically linked, interpreter /nix/store/syg6xw4x296w82267qnvrd3nn0cp6j31-glibc-riscv64-unknown-linux-gnu-2.42-84/lib/ld-linux-riscv64-lp64d.so.1, for GNU/Linux 4.15.0, not stripped`.
Output: `/nix/store/z4j8bc7iwz9m7pap376zy0j0z16295lr-k230-shell-rust-riscv64-unknown-linux-gnu-0.1.0`. [Repeat build plan](repeat-build.log) exits 0 with zero builds
and zero fetches. No kernel, compositor, theme helper or image was rebuilt.

```sh
flock -n /tmp/k230-nix-build.lock nix build --impure --expr \
  'let f = builtins.getFlake "git+file:///mnt/MediaVolume/home/jadams/src/gitlab.daringbit.com/josh/tdisplay-k230?rev=9e4515ed32cc849bfcc56dbe60d02e877bee75a7"; p = f.nixosConfigurations.k230-coherent-shell.pkgs; in p.callPackage (f.outPath + "/nix/rust-shell-client") {}' \
  --out-link /home/jadams/.local/state/tdisplay-k230/retained-builds/coherent-help-2026-10-10/candidate \
  --print-out-paths --max-jobs 1 --cores 2
```

[Retention](retention.json) records 10,405 valid store
paths, adding 3 to the prior verified Foot farm.
The durable candidate and `build-closure` GC roots preserve this output,
recursive sources and currently realized declared dependency outputs. The
link-farm uses explicit `builtins.storePath` references; every retained path
passed `nix-store --check-validity`, and this output's actual GC roots include
the new farm. Global GC policy remains unchanged (`keep-outputs=false`,
`keep-derivations=true`). Source edits still invalidate the Rust package and
can recompile its release crates; rooting dependency outputs cannot preserve
Cargo intermediates inside a changed derivation.
The exact [enumeration script](retain-inputs.py) and [store-reference recipe](retain.nix)
are preserved; their paths describe this host's retained build directory.
The graph read and retention commands were (enumeration/root creation ran
after the client build completed):

```sh
nix derivation show --recursive /nix/store/fk3w6gym9vd1fnybdp3ppmiqqpsjf03m-k230-shell-rust-riscv64-unknown-linux-gnu-0.1.0.drv \
  > /home/jadams/tmp/k230-help-derivations.json
python3 /home/jadams/tmp/k230-help-retain.py
flock -n /tmp/k230-nix-build.lock nix build --impure --expr \
  'import /home/jadams/.local/state/tdisplay-k230/retained-builds/coherent-help-2026-10-10/retain.nix' \
  --out-link /home/jadams/.local/state/tdisplay-k230/retained-builds/coherent-help-2026-10-10/build-closure \
  --print-out-paths --max-jobs 1 --cores 2
```

No board or serial port was reserved or
used for this work. A package build does not prove installation or discovery.
Task 5.3 remains unchecked: after coordinated candidate deployment, an operator
must open All Apps → Help → Navigation buttons, use the named routes and return,
and record the actual touch/discovery outcomes plus exact running artifact:

```sh
flock /tmp/k230-board.lock ./tools/console.py /dev/ttyACM0 --wait=3 \
  'readlink -f /run/current-system; pgrep -a k230-shell-rust; systemctl is-active shell shell-ui'
python3 tools/capture-feature.py coherent-gestures --provenance real-touch \
  --duration 60 --description 'Gesture ownership and drawer discovery on glass' \
  --output-dir docs/evidence/coherent-gestures
```

The operator must reserve the board for both commands and inspect camera plus
console evidence separately. Physical discovery/readability remains UNVERIFIED;
earlier general app-navigation acceptance does not identify this new candidate.

## Local site budget failure and owner

Coordinator `/root` owns the [failed host site build](site-build-host.log):
`python3 scripts/build_site.py` against committed source
`70e3fecdbf94a14590a7a16aab92103ceb9d5565`, exit 2, 680 pages,
18,138,424 bytes and 148.33 seconds against the unchanged 32 MiB / 120 second
budgets. Content, inventory and built-site assertions passed; only elapsed time
failed. Several unrelated Rust builds/emulators were concurrently active on this
host; this is an observation, not a proved attribution of the overrun. No other
operator's processes were stopped. The implementation and cross-build gate
remain complete. The coordinator must inspect the resulting CI site build and
exact published revision after landing; a local artifact is not Pages deployment
proof, and the elapsed-time budget was not increased or bypassed.
