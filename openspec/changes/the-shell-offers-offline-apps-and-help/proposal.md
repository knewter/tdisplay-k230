## Why

The launcher now proves the shell can discover and start installed desktop entries, but a fresh image still offers too little useful offline software and no in-device explanation of the controls. The next increment should give a person a small, predictable set of portrait-friendly tools and a Help page without turning the shell into a general desktop or adding a network-dependent installer.

## What Changes

- Add a small offline application set selected from packages already appropriate for the K230 shell, with Terminal and Help always available.
- Add a readable Help surface reachable from the launcher or persistent shell controls, covering Apps, Keyboard, Windows/Home, System, Back, and paging.
- Keep application discovery through visible desktop entries and GLib launch semantics; do not add a second launcher/catalog implementation.
- Define package and closure checks so each candidate is evaluated before inclusion.
- Verify startup and the touch workflow with injected input; keep physical-finger and reboot evidence separate.
- Exclude network installers, AtomVM/Dozer integration, broad theming, and a general desktop environment.

## Capabilities

### New Capabilities

- None.

### Modified Capabilities

- `runtime/shell`: Adds a bounded offline app set and keyboard-free Help surface to the portrait shell.

## Impact

The change affects the shell Nix package set, desktop-entry exposure, launcher cards, and evidence tasks. Candidate packages must work with the pinned riscv64 cross build, 568x1232 portrait layout, Pixman rendering, 1 GiB RAM, and existing Foot terminal profile. The board is needed for physical touch and reboot evidence; package closure, desktop discovery, startup, and injected touch checks can run on the host or in the existing shell image workflow.
