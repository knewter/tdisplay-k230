# T-Display-K230

Bring-up work for the LILYGO T-Display-K230 — a Kendryte K230D (dual RISC-V
C908 + KPU NPU) board with a 4.1" 568x1232 AMOLED, GT9895 touch, RTL8189FTV
Wi-Fi, and an SX1262/LR2021 LoRa radio.

Goal: replace the shipped RT-Smart firmware with **NixOS** on riscv64, then run
[AtomVM](https://www.atomvm.net/) and the Dozer core on top.

## Connecting to the board

The board has two USB-C ports. The one that also charges (`J2` on the
schematic) carries a **CH342 dual USB-UART bridge**, giving two CDC-ACM
consoles. No driver is needed — the in-kernel `cdc-acm` handles it.

| Device | CH342 ch | K230 UART | Purpose |
| --- | --- | --- | --- |
| `/dev/ttyACM0` | 0 | UART0 | RT-Thread `msh` console |
| `/dev/ttyACM1` | 1 | UART3 | Second console |

115200 8N1, no flow control. Enumerates as `1a86:55d2` "USB Dual_Serial".

**Use a known-good USB-C data cable.** A charge-only cable produces complete
silence (no kernel events at all); a marginal one produces `error -71`
enumeration failures. Both look identical from the board's side — the red
charge LED lights either way.

## Tools

| Script | Purpose |
| --- | --- |
| `tools/console.py` | Run commands on the RT-Thread `msh` console and capture output |
| `tools/probe.py` | Passively sniff a serial port, optionally poke it with CR/LF |
| `tools/bootcap.py` | Send `reboot` and capture the full boot log |
| `tools/snap.sh` | Snapshot USB/serial/block state for diffing |
| `tools/watch.sh` | Poll for USB device changes (misses failed enumerations) |
| `tools/kwatch.sh` | Follow the kernel log for USB events **including** failures |

```sh
./tools/console.py /dev/ttyACM0 --wait=3 "wifi scan" "ifconfig"
```

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
`openspec/specs/` on every push to `main`, and its first line is how many
requirements are still unverified. Live.

To watch it being built rather than read the result:
**<https://github.com/knewter/tdisplay-k230/actions/workflows/spec-site.yml>**
— one run per push to `main`, each with the page count, byte size and the
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

See [docs/findings.md](docs/findings.md).

- Serial console working
- Shipped RT-Smart firmware boots; display and touch work
- **Wi-Fi is broken in the shipped firmware** — a LilyGO defect, see findings
- NixOS port under way — the cross toolchain works and the closure builds;
  see `docs/evidence/cross-build.txt`

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

# The card image. Pure builds carry the stage 1 above. Until a stage 1 this
# flake compiled has been booted (docs/evidence/stage1-from-source.txt will
# say), the known-good card was written from the vendor-compiled binaries
# tools/gen-stage1.sh leaves in firmware/stage1/, selected like this:
K230_STAGE1_DIR="$PWD/firmware/stage1" nix build --impure .#sdImage
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
