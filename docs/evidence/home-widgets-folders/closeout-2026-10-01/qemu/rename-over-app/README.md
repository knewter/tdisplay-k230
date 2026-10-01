# Rename keeps Home above an ordinary app

`unshare -Ur python3 tests/rust_home_screen_qemu.py --rename-only --rename-client <native-card-client> --sway <Sway in result.json> --rust <Rust in result.json> --theme-bundle <existing theme bundle> --icons <existing icon bundle> --output <private output>` passed. A real mapped Wayland app is beneath Home during the rename; a real virtual-keyboard connection types the new name. The persisted name is checked and the compositor must still report `home_selected=1` after the editor releases focus.

The former empty-session test missed app focus restoration. Source now retains workspace focus when Home's exclusive editor finishes, and excludes layer focus from ordinary app selection. Home selection belongs to the output, not the transient card-gesture seat (which is cleared after exiting overview). The coherent cross-build passed, producing `/nix/store/k01nc2m16qqbncn0hb7y0z8cz7i8rya3-nixos-system-nixos-26.11.20260919.20b1ddd`.

This is headless emulation and native Wayland keyboard/app proof, not a physical finger test. The first broad repeat reached this check successfully but failed a later fluid-fling check; the narrow run above verifies this focus fix independently. Physical Home acceptance is recorded separately.
