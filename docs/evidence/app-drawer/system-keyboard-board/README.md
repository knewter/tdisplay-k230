# Standard Search keyboard installed on the board

Installed and tested 30 September 2026 America/Chicago (1 October UTC). Matching source and userspace/executable identities are in [result.json](result.json). The Rust UI, compositor, keyboard service and touch relay were active after activation. The userspace update used a seven-minute rollback timer, canceled after the matching executable and successful input/capture checks. The booted kernel remains 6.6.36; the existing boot-selection path is unchanged by this runtime activation.

[Focused field, visible caret and system keyboard](focused.jpg), [typed q](typed-q.jpg), [Backspace correction](corrected.jpg), [Enter hides the keyboard](dismissed.jpg), [tap reopens it](reopened.jpg), [unfocused field](unfocused.jpg). The focused and corrected JPEGs are byte-identical: actual wvkbd Backspace returned the search to its empty placeholder and restored the app list. The typed query visibly reads `q` and filters to no matches. These native captures were visually inspected. [Camera view](panel.jpg) records the illuminated panel and drawer; its oblique, partly framed and blurry view cannot establish text legibility or finger behavior.

## Commands and evidence class

[probe.py](probe.py) creates the existing named uinput gesture-test source, injects taps at native 568×1232 coordinates, routes the actual live Rust shell, queries Sway mapping state and captures through grim. The board's configured 400px keyboard plus 56px gesture grip is retained. No credentials or network selection are exercised.

```sh
python3 tools/console.py /dev/ttyACM0 --wait=3 'readlink -f /run/current-system'
python3 tools/push-file.py --src docs/evidence/app-drawer/system-keyboard-board/probe.py --dest /root/tmp/k230-deployment/search-board-check.py
python3 tools/console.py /dev/ttyACM0 --wait=12 '/nix/store/v189xydz6qkcd4cbkixcmv91w8hbc560-python3-riscv64-unknown-linux-gnu-3.14.7/bin/python3 /root/tmp/k230-deployment/search-board-check.py >/root/tmp/k230-deployment/search-board-check.log 2>&1'
```

The probe result and six original JPEGs were collected by framed, validated base64 over the single reserved serial port. The original camera image was captured with `ffmpeg -hide_banner -loglevel error -f v4l2 -i /dev/video0 -frames:v 1 -y <private-camera-path>`.

PASS, board-injected: actual wvkbd text/correction, drawer preserved, Enter keyboard-only dismissal, Search tap reopens keyboard. QEMU separately proves filtered desktop-entry launch and app key focus. [Operator acceptance](operator-feedback.md) confirms real-finger Search, typing, Backspace correction, Enter dismissal, tap-to-reopen and filtered launch on this build. [Pages deployment proof](deployment.json) records successful CI build/deploy and HTTP inspection of the dashboard at exact revision `7eda7f36`, including the installed screenshot and Search acceptance text. The additional keyboard-handle/drawer-dismiss gesture check remains pending; task 6.3 is open for that part. Scroll frame measurements (5.2) and the conditional follow-up (5.4) remain open. This is a userspace deployment, not a flash or reboot proof.

The site was built using the flake’s locked Nixpkgs Node 22: `nix shell --inputs-from . nixpkgs#nodejs_22 --command python3 scripts/build_site.py`. Initial dependency installation on this host uses `SHARP_IGNORE_GLOBAL_LIBVIPS=1 npm ci --prefix site` inside that same Nix environment, preventing Sharp from attempting a local build against unrelated globally installed libvips. The final build and site assertions passed: 421 pages, 13,428,507 bytes, 22.49 seconds within the configured budgets.
