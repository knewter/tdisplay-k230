# T-Display-K230

Bring-up work for the LILYGO T-Display-K230 — a Kendryte K230D (dual RISC-V
C908 + KPU NPU) board with a 4.1" 568x1232 AMOLED, GT9895 touch, RTL8189FTV
Wi-Fi, and an SX1262/LR2021 LoRa radio.

Current goal: a usable **NixOS touchscreen handheld** with a Sway shell,
on-screen keyboard, installed-app launcher, persistent Wi-Fi, and reproducible
video playback. AtomVM and the Dozer core are later work.

See [work status and next steps](docs/work-status.md) and [the contribution and
landing workflow](AGENTS.md).

## Shell demonstrations

The [feature gallery](docs/evidence/shell-features/index.html) and
[evidence index](docs/evidence/shell-features/README.md) contain native screen
clips, screenshots, and FFmpeg camera recordings for ten shell workflows.
They distinguish injected touch events, IPC launches, and recorded physical
interaction. Accepted keyboard and Home checks are recorded with their
evidence; newly added interactions need their own proof. The
[handheld site](https://knewter.github.io/tdisplay-k230/handheld/) publishes
short device-focused demonstrations.

## Connecting to the board

The board has two USB-C ports. The one that also charges (`J2` on the
schematic) carries a **CH342 dual USB-UART bridge**, giving two CDC-ACM
consoles. No driver is needed — the in-kernel `cdc-acm` handles it.

| Device | CH342 ch | K230 UART | Purpose |
| --- | --- | --- | --- |
| `/dev/ttyACM0` | 0 | UART0 | U-Boot and NixOS console (RT-Thread `msh` on factory firmware) |
| `/dev/ttyACM1` | 1 | UART3 | Second console |

115200 8N1, no flow control. Enumerates as `1a86:55d2` "USB Dual_Serial".

**Use a known-good USB-C data cable.** A charge-only cable produces complete
silence (no kernel events at all); a marginal one produces `error -71`
enumeration failures. Both look identical from the board's side — the red
charge LED lights either way.

## Tools

| Script | Purpose |
| --- | --- |
| `tools/console.py` | Run serial-console commands and capture output |
| `tools/probe.py` | Passively sniff a serial port, optionally poke it with CR/LF |
| `tools/bootcap.py` | Send `reboot` and capture the full boot log |
| `tools/snap.sh` | Snapshot USB/serial/block state for diffing |
| `tools/capture-feature.py` | Record a finite, named V4L2 camera evidence clip or still with FFmpeg |
| `tools/watch.sh` | Poll for USB device changes (misses failed enumerations) |
| `tools/kwatch.sh` | Follow the kernel log for USB events **including** failures |

```sh
./tools/console.py /dev/ttyACM0 --wait=3 "uname -a"
```

### Camera evidence clips

Record one feature at a time from the host camera. The default is a 15-second
raw-orientation H.264 MP4 suitable for the site; a JSON manifest next to it
records the camera, timestamp, operator-declared touch provenance, description,
and exact FFmpeg command. That metadata does not prove a real touch happened.

```sh
./tools/capture-feature.py keyboard-show --provenance real-touch \
  --description 'Touch Keyboard, type a command, then dismiss it'

./tools/capture-feature.py system-confirm --duration 12 --provenance injected \
  --description 'Injected input opens System and cancels reboot'

./tools/capture-feature.py terminal-still --still --rotate180 \
  --description 'Terminal visible after boot; presentation rotation requested'
```

Use `--device /dev/videoN`, `--output-dir DIR`, and `--duration SECONDS` when
needed. `--rotate180` changes only the recorded presentation; omit it to keep
the camera's raw view. `--dry-run` writes only the manifest and prints the
command, without opening the camera.

### Sampled screen clips without a network link

When the board is reachable only through serial and U-Boot UMS,
`tools/sample-grim-frames.sh` records finite PNG samples on the board with
Grim's Wayland screencopy client. It writes actual boot-relative monotonic
start and end timestamps for every capture to `frames.tsv`; it does not assume
the requested sampling interval was achieved. Run it as the `shell` session
user, then copy the resulting directory off the board using the UMS volume.

```sh
./tools/sample-grim-frames.sh keyboard-show --duration 20 --interval 0.5 \
  --provenance injected --description 'Open and dismiss the on-screen keyboard'

./tools/encode-grim-samples.py grim-samples/20260922T000000Z-keyboard-show \
  --output docs/evidence/video/keyboard-show-sampled.mp4 --provenance injected \
  --description 'Sampled compositor output while the on-screen keyboard opens'
```

The host encoder gives each frame its measured interval through FFmpeg's concat
input and writes a manifest alongside the H.264 MP4. These clips show sampled
compositor output. They are not smoothness or performance evidence and their
provenance does not prove real touch.

## Planning

All planning goes through [OpenSpec](https://openspec.dev). Read
`.skills/k230-spec-change/SKILL.md` before proposing a change — it holds the
capability taxonomy, what may ground a requirement on this hardware, and why
a QEMU run and a hardware run are different claims.

```
openspec/specs/<group>/<capability>/spec.md   what this board does today
openspec/changes/<id>/                        one in-flight change
openspec validate --all                       check them
```

### Reading the specs

**<https://knewter.github.io/tdisplay-k230/>** — rebuilt from
`openspec/specs/` on every push to `master`, and its first line is how many
requirements are still unverified. Live.

To watch it being built rather than read the result:
**<https://github.com/knewter/tdisplay-k230/actions/workflows/spec-site.yml>**
— one run per push to `master`, each with the page count, byte size and the
render assertions. That build also runs `tools/blob-scan.py`, which fails it
if a binary file exists anywhere in the tree that `docs/blob-inventory.md`
does not account for.

Locally:

```sh
npm install --prefix site      # once
./scripts/build_site.py        # site/dist/, with the budgets enforced
npm run dev --prefix site      # or preview it at http://localhost:4321/
```

Every requirement is shown as **grounded** (something was observed on the
board, or vendor source was read and cited by path) or **unverified**, with
the reason. Citations under `docs/` become links to the committed boot log or
photograph, so the evidence behind a requirement is one click from it.

The build refuses to guess. A requirement carrying neither an
`<!-- UNVERIFIED -->` marker nor a `*Grounding: ...*` citation, or one citing
evidence that is not committed, is reported as a build defect: the site is
still written and shows the defect in its own colour, and the command exits
non-zero naming the file and the requirement. Generation time and output size
are budgeted in `scripts/build_site.py`, with the measurements behind those
numbers in
[`docs/evidence/spec-site-build.txt`](docs/evidence/spec-site-build.txt).

`scripts/render_specs.py` is the half that reads the specs — standard library
only, no npm needed — and `site/` is the Astro project that draws them.

```sh
python3 -m unittest discover -s tests -p 'test_render_specs.py'   # the data pass
./scripts/build_site.py                                           # + the built site
```

## Status

The shell, touch launcher, offline apps/Help, Wi-Fi with reboot persistence,
and U-Boot USB flashing work on the physical board. Application defaults,
including Foot, htop and Neofetch, are part of the repository/image. There is
no battery requirement for this USB-powered setup.

Video streaming and MVX hardware decoding have measured board evidence;
the installed player and recovery controls are still being integrated.
Sway uses Pixman. GPU probes do not yet accelerate the compositor. Linux
still has one CPU online; the second-core investigation records the gates
needed before attempting bring-up.

The experimental splash has improved warm-boot handoff evidence; full
power-on/geometry acceptance and the final default remain open. BootROM
recovery without a working bootloader is separate from proven U-Boot USB
flashing. Historical factory-firmware findings are in
[docs/findings.md](docs/findings.md); current work and evidence links are in
[docs/work-status.md](docs/work-status.md).

## Building

```sh
nix build .#checks.x86_64-linux.cross-hello     # smoke-test the cross toolchain
nix build .#nixosConfigurations.k230.config.system.build.toplevel
./tools/qemu-k230.sh                            # boot it under QEMU
CAPTURE=120 ./tools/qemu-k230.sh > boot.txt     # ...and record the boot

# The board device tree on its own -- seconds, no kernel rebuild.
nix build .#deviceTree

# Stage 1 -- U-Boot SPL, U-Boot 2022.10, OpenSBI 1.4 and the environment --
# built from source by the flake. nix/stage1.nix says how; nothing in it is
# a committed or downloaded binary except the 32 KiB of DDR training
# firmware that arrives as C, which docs/blob-inventory.md names.
nix build .#uboot-k230 .#opensbi-k230     # the two compilers' worth
nix build .#stage1                        # the five files the card carries

# The card image, carrying the stage 1 above. Booted on the board on
# 2026-09-22 (docs/evidence/stage1-from-source.txt).
nix build .#sdImage
./tools/flash-latest.sh          # the same build, then tools/flash.sh

# For bisecting only: the vendor-compiled stage 1 tools/gen-stage1.sh leaves
# in firmware/stage1/ (gitignored), selected by name.
K230_STAGE1=vendor ./tools/flash-latest.sh
```

Editing `nix/dts/` does **not** rebuild the kernel. The DTB is a separate
derivation (`nix/device-tree.nix`) compiled against the pinned kernel's
headers, so iterating on the panel init sequence costs about a second
instead of a twenty-minute cross-compile.

Everything cross-compiles from `x86_64-linux`; you do not need riscv64
hardware to build. Budget real time for a first build: the glibc cross
toolchain substitutes from the cache, but NixOS's initrd wants a static
busybox, so a **second, musl** GCC bootstrap compiles locally alongside the
kernel. That cost is one-time per nixpkgs pin.

`tools/qemu-k230.sh` defaults to `-machine virt`, not `k230`. Mainline Linux
ships no K230 device tree and no `SOC_CANAAN_K230`, so a stock kernel cannot
boot QEMU's `k230` machine at all; that needs the Xuantie kernel built with
`CONFIG_ERRATA_THEAD_PBMT=n`. See `docs/evidence/boot-path-differences.md`.
