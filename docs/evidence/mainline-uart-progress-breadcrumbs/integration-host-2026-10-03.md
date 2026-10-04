# Integrated bounded worker markers and controller

The coordinator reviewed source checkpoint `071086bc` and controller checkpoint
`c88af531`, integrating them on `integrate/mainline-probe-path` in
`/home/jadams/tmp/k230-mainline-probe-integration`, based on `8e66e299`.
Owned integration paths are the reviewed additive source/Nix/flake, controller,
new focused tests, CI step, host evidence and narrow group 5g task notes.
No board/UART/camera was accessed for this host integration.

Native patched worker fixtures (13), original native source fixtures (12), new
controller fixtures (17 initially, 18 after the correction below), original
controller fixtures (20) and existing trial discovery (214) passed. Commands:

```sh
python3 tests/test_mainline_uart_progress_breadcrumbs.py
python3 tests/test_mainline_uart_progress.py
python3 tests/test_mainline_uart_progress_breadcrumbs_controller.py
python3 tests/test_mainline_uart_progress_controller.py
python3 -m unittest discover -s tests -p 'test_mainline_drm*trial.py'
openspec validate the-board-runs-a-mainline-kernel --strict
git diff --check
```

The coordinator found a concrete malformed-byte case: shared terminal cleanup
removed embedded CR, turning `worker-\rentry` into a valid worker-entry marker.
Only the explicit new mode now permits conventional CRLF framing while retaining
embedded CR for rejection. Its added actual-pump fixture rejects two corrupted
lines without stimulus and accepts conventional CRLF. The old mode retains its
existing terminal cleanup. Focused new/original controller suites were rerun
after this correction; existing trial discovery tested the merged controller
before that new-mode-only correction. CI now runs both new focused files.

The reviewed source-only evaluation proves all 91 preexisting package identities
and ten exposed kernel source/config pairs unchanged, as recorded in the
[source receipt](source-host/README.md). The [controller host note](controller/README.md)
records actual cached rejection of the legacy configured reporter and the
reviewed worker hash plus compiled Image marker/gate requirements. Both exact
runtime gates remain required; the same six delayed samples are retained, with
at most two extra worker-only SBI attempts. No IRQ/TTY/PID1 marker, retry,
priority/affinity change or candidate reboot is added.

A fresh matching bundle/dev build, exact configured object/layout proof,
positive actual controller preparation, physical markers/receipt and protected
recovery remain UNVERIFIED. Tasks 5g.2–6 and ordinary-root/panel/glass task5b.5
stay open. Root owns the shared build slot next and will freeze this integration
revision before its matching build. Review/merge/push and CI/publication are
coordinator actions; successful host tests are not deployment or board proof.
