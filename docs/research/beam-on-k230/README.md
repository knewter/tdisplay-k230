# Erlang/OTP and Elixir running natively on the K230

**Evidence class: board, over SSH.** Measured on 2026-10-23 on the boot-default
system (`pb5l6lmb`, mainline 7.3.0-rc5 with this repository's forward ports),
boot ID `69d72d47…`. Linux had one online CPU, the 1.6 GHz core. The shell and
compositor stayed running but idle. Nothing was installed into the system
configuration.

This answers whether Elixos's runtime could run on the board's big core under
the kernel this project already boots. It does not test Elixos itself (an
Alpine/musl image built with melange, on OTP 29), AtomVM, or the little core.

## Build

[`beam.nix`](beam.nix.txt) cross-builds OTP 28.5.0.6 and Elixir 1.18.5 from
the flake's nixpkgs (`beam_minimal`, glibc), with three fixes:

- OTP's cross build stops at `cross_check_erl` unless a same-release
  build-machine OTP is on `PATH`, so the host `beam_minimal` OTP was added to
  `nativeBuildInputs`.
- OTP's build-machine helper `utils/find_cross_ycf` has a `/usr/bin/env`
  shebang that the sandbox lacks. It is patched before the build.
- Elixir compiles its bytecode with `erlc`, so the host OTP is on its
  `PATH` too. `.beam` files do not depend on the architecture.

The plain cross OTP closure was 254 MiB beyond what the board already had.
122 MiB of that was the x86-64 host OTP, kept alive by paths that yecc writes
into generated parser sources. `erlangSlim` instead removes:

- `src/`, `doc/` and `examples/`;
- the wx, megaco, snmp, diameter, et, debugger, observer, reltool,
  common_test, odbc, jinterface and erl_interface apps;
- the host references.

That leaves 43.1 MiB of OTP and 13.1 MiB of Elixir to copy. `nix copy` with
SSH compression took 14 s.

```sh
nix build --impure --expr '(import ./beam.nix { flake = builtins.getFlake (toString ./.); }).elixir'
```

## Results

[`measure.sh`](measure.sh.txt) ran as root under the board lock
([output](board-run.txt)):

| Measurement | Result |
| --- | --- |
| `erlang:system_info(emu_flavor)` | `emu`: the interpreter, since the BEAM JIT has no RISC-V backend |
| OTP / ERTS / Elixir | 28 / 16.4.0.6 / 1.18.5 |
| Schedulers | 1 |
| `erl -noshell -eval 'halt().'` | 0.87–0.90 s (4 runs) |
| `elixir -e ':ok'` | 1.39–1.41 s (4 runs) |
| `iex` start, evaluate one line, halt (through `script`) | 1.75–1.93 s (3 runs) |
| `:erlang.memory(:total)` in an `elixir -e` VM | 33 MiB |
| VmRSS of that VM | 46 MiB |
| `fib(25)`, naive recursion | 12 ms |
| `Enum.reduce(1..1_000_000, 0, &+/2)` | 168 ms |
| Spawn 10,000 processes | 317 ms |

Two short-name nodes on the board, with a shared cookie and the board's
`epmd`, connected (`Node.ping` → `:pong`). An `:erpc.call` returned the remote
node's `riscv64-unknown-linux-gnu`; the whole client run took 1.69 s
([output](board-dist.txt)). Afterwards the leftover `epmd` was stopped, and no
BEAM process or temporary file remained.

## What this means for Elixos

- The BEAM runs on the big core today, on the interpreter. Starting a VM
  takes about 0.9 s, and Elixir adds about 0.5 s. An idle VM uses tens of
  MiB, out of 927 MiB.
- Two nodes speak distribution on the device. The AtomVM link would use the
  same handshake; its OTP 29 compatibility is a separate question.
- The kernel question is unchanged. This ran on mainline plus this project's
  forward-ported K230 drivers (SD/MMC, GPIO, display, audio and others; see
  `nix/kernel-mainline.nix`). Under an "unmodified mainline" rule the board
  has no SD root or display at this pin.

## Limits

- glibc nixpkgs OTP 28, not Elixos's musl OTP 29.
- Timings are wall-clock, from single short loops on a board whose shell was
  idle but running.
- The `iex` timing goes through a pseudo-terminal from `script`. It is not a
  person waiting at a prompt.
- The closure stays on the board, rooted at
  `/var/lib/k230/beam-trial-20261023/elixir`. Remove that root and collect
  garbage to delete it.
