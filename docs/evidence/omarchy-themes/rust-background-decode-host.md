# Rust still-wallpaper decode: host checkpoint

Observed 2026-09-24 from pushed base `0bef9cf4` in isolated branch
`implement/rust-background-decode`. The module is not yet linked into the
production Rust shell; the frontend owner retains Cargo/Nix, main/render,
the persistent `Layer::Background`, and real screen adoption. A standalone
test manifest pins `image` 0.25.10 with only PNG/JPEG/WebP/GIF/BMP features,
matching the still formats accepted by `tools/theme_activate.py`. This is a
pure-Rust decoder path and does not require a GdkPixbuf loader cache.

`BackgroundCache::render(path, width, height, mode)` returns opaque native
little-endian Cairo ARGB32 bytes (BGRA). `Crop` fills, `Fit` letterboxes black,
and `Center` uses native-size centered placement. The default is Crop. The
single-entry cache retains success or failure for identical immutable path,
geometry, and mode, so a frame does not repeat decode. `clear()` permits an
explicit retry when source state changes.

The module independently requires an absolute canonical regular file, uses
`O_NOFOLLOW|O_NONBLOCK`, caps compressed bytes at 32 MiB, checks image format
against the imported extension, caps each decoded edge at 8192 pixels and
total pixels at 16 Mi, and caps output at 1024×2048 (8 MiB). The `image`
reader is configured with a 128 MiB decoder allocation limit. The library
[documents](https://docs.rs/image/0.25.10/image/struct.Limits.html) that its
`max_alloc` limit is *non-strict* for some codecs; this checkpoint cannot claim
a hard process-wide peak RSS bound. The source/dimension/output checks are
explicit, and target memory use remains a physical/instrumented gate. Video
backgrounds are not decoded by this module and stay open in the theme scope.

```text
cd nix/rust-shell-client
CARGO_TARGET_DIR=/tmp/k230-background-test-target cargo test --offline \
  --manifest-path tests/background_decode_host/Cargo.toml \
  --test background_decode_module
  PASS 5 host tests
rustfmt --edition 2021 --check src/background_decode.rs tests/background_decode_module.rs
  PASS
```

The tests cover crop/fit/center geometry, Cairo byte order, all six imported
still extensions, repeated-frame cache and retry, source/output bounds,
symlink and format mismatch rejection, and an oversize decoded edge in a
small compressed image. No target cross-build, Wayland layer, camera, or real
panel result is claimed.
