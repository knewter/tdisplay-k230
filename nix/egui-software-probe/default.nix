{ lib, rustPlatform }:

# Opt-in egui client rasterised on the CPU (egui_software_backend) and
# presented through wl_shm. No GL, Vulkan, winit or softbuffer, and no
# native libraries: wayland-client's pure-Rust backend speaks the protocol.
rustPlatform.buildRustPackage {
  pname = "egui-software-probe";
  version = "0.1.0";
  src = lib.fileset.toSource {
    root = ./.;
    fileset = lib.fileset.unions [ ./Cargo.toml ./Cargo.lock ./src ];
  };
  cargoLock.lockFile = ./Cargo.lock;
  # A cross build cannot run a RISC-V test binary on the build host.
  doCheck = false;
  meta = {
    description = "Opt-in egui software-rendered Wayland probe matching the Qt Quick probe scene";
    license = lib.licenses.mit;
    mainProgram = "egui-software-probe";
    platforms = lib.platforms.linux;
  };
}
