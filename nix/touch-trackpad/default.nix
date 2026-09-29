{ rustPlatform, lib }:

rustPlatform.buildRustPackage {
  pname = "k230-touch-trackpad";
  version = "0.1.0";
  src = ./.;
  cargoLock.lockFile = ./Cargo.lock;
  # Cargo unit tests (relay/mode/devsearch/uinput's ioctl-number and
  # struct-size checks, plus a live /dev/uinput create/destroy) run
  # natively on the host, same as nix/rust-shell-client/default.nix's own
  # `doCheck = false` -- the cross package build cannot execute a RISC-V
  # test binary on the x86_64 build host, and the live uinput test would
  # need a real /dev/uinput inside the (sandboxed) build anyway.
  doCheck = false;

  meta = {
    description = "Re-emits the K230's GT9895 touchscreen as a virtual uinput touchpad while HDMI is the active output, so libinput natively drives pointer motion, tap-to-click, two-finger scroll, and pinch/swipe gestures on it";
    license = lib.licenses.mit;
    platforms = [ "riscv64-linux" ];
    mainProgram = "k230-touch-trackpad";
  };
}
