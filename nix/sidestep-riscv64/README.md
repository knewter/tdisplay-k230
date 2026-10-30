# Sidestep on riscv64 (LP64D): patch overlay and reproduction

Sidestep (github.com/bitemyapp/sidestep, MIT/Apache-2.0) implements an
Objective-C runtime and Foundation/AppKit for Linux, with assembly and
calling-convention code for aarch64 and x86_64 only. These patches add
riscv64 (LP64D, `riscv64gc-unknown-linux-gnu`). They apply to Sidestep at
`626422b1fa52fc14af13976c5c90b4efd657b1d7` (2026-10-08); nothing here is
upstreamed.

- `sidestep-riscv64.patch`: the runtime port (`git apply` in the Sidestep
  checkout). About 500 added lines across `trampoline.rs`, `call.rs`,
  `forward.rs`, `msgsend.rs`, `block_imp.rs`, `message.rs`, plus conformance
  test cfg changes for the struct-return entry point.
- `objc2-encode-4.1.0-riscv64.patch`: a one-line change to the third-party
  `objc2-encode` crate (`long double` is 16 bytes on riscv64; the crate has no
  arm for it, so nothing compiles). Applied through `[patch.crates-io]`.

What the port does and does not do is in
`docs/evidence/egui-sidestep/sidestep-riscv64-assessment.md`. This is a source
overlay built outside Nix with a host cargo; it is not yet a pinned Nix
derivation, because Sidestep's objc2 overlay tool downloads and patches crates
at build time.

Reproduce (host, build slot not needed for a cargo build; the compiler wrapper
and glibc are the ones in the K230 cross closure):

```sh
git clone https://github.com/bitemyapp/sidestep && cd sidestep
git checkout 626422b1fa52fc14af13976c5c90b4efd657b1d7
git apply /path/to/sidestep-riscv64.patch
cargo run --release --manifest-path tools/objc2-overlay/Cargo.toml   # writes .objc2-overlay/
mkdir .rv-patch && cp -r ~/.cargo/registry/src/*/objc2-encode-4.1.0 .rv-patch/
(cd .rv-patch/objc2-encode-4.1.0 && patch -p1 < /path/to/objc2-encode-4.1.0-riscv64.patch)
echo 'objc2-encode = { path = ".rv-patch/objc2-encode-4.1.0" }' >> Cargo.toml   # under [patch.crates-io]
GCC=$(ls -d /nix/store/*riscv64-unknown-linux-gnu-gcc-wrapper-*/bin/riscv64-unknown-linux-gnu-gcc | head -1)
export CARGO_TARGET_RISCV64GC_UNKNOWN_LINUX_GNU_LINKER=$GCC CC_riscv64gc_unknown_linux_gnu=$GCC
export CARGO_TARGET_RISCV64GC_UNKNOWN_LINUX_GNU_RUNNER="qemu-riscv64-static -L /"
cargo +1.95.0 test --release --target riscv64gc-unknown-linux-gnu -p sidestep-runtime
cargo +1.95.0 test --release --target riscv64gc-unknown-linux-gnu -p sidestep-conformance --no-fail-fast
```

The conformance run needs a small font directory when run under QEMU user
mode (it scans every host font file, which is very slow when emulated); the
recorded run bind-mounted three DejaVu files over `/usr/share/fonts` in a user
namespace. Those fonts cause the `coregraphics` `fonts` and `rich_text`
`rtf_default_font` failures noted in the assessment.
