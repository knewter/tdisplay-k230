# Real-glass closeout feedback, 2026-09-30

The operator tested the installed panel shell during this session. Exact observed behavior is preserved below, separately from the requirements still awaiting their named proof. Sanitized identity from the same session: `/nix/store/r0knnb72k3p3mpmbsnfgrk66yg8gl144-nixos-system-nixos-26.11.20260919.20b1ddd`, Sway `/nix/store/g2yxx2jxas1nhivqcpxwrhsxpdi8367q-sway-unwrapped-riscv64-unknown-linux-gnu-1.12/bin/sway`, shell `/nix/store/lc0ll4ckkm2vif0s82w2phlwn398g0w1-k230-shell-rust-riscv64-unknown-linux-gnu-0.1.0/bin/k230-shell-rust`. Identity is available in `docs/evidence/card-shell/overview-home-bleed-through/board-2026-09-30/console.txt`.

| Area | Operator observation | Closeout implication |
| --- | --- | --- |
| Overview | “home icons don't appear behind the cards” | Physical re-check passed; matching native capture and panel photograph now committed in the overview evidence. That proposal was archived. |
| Home | “page swips seem to work fine” | Page behavior accepted on glass; full dark/light layout capture still pending. |
| Drawer-to-Home pin | Drag works but places in “next free opening left right top down” | Placement defect: dropped app must land in the intended cell. Keep Home open; an add action alone does not prove drop-position correctness. |
| Files | Both apps show icons; scrolling not tested yet | Icon visibility accepted. Resume folder/header taps and scrolling after the edge tap fix; task 5.3 remains incomplete. |
| App drawer | “drawer works fine. search works fine” | Real reversal/search acceptance reported in response to the coordinator's named checks. Timing proof still pending. |
| Keyboard | “standalone keyboasrd from foot worked great” | Positive real-glass report in response to show/type/slow hide-hold-reverse/committed hide/navigation instructions. No contemporaneous gesture video or workload measurement: tasks 3.2/3.3 remain incomplete. |
| Wi-Fi | “wifi seems perfect” | Positive real-glass flow acceptance. The report does not individually establish every 3.1 case or controlled reboot/Forget evidence in 3.2. |
| Password field | Requests show/hide eye to inspect typos | Source follow-up now explicitly tracked in the Wi-Fi proposal before final acceptance. |
| Edge taps | App header taps open notification shade; compact search-keyboard Backspace dismisses drawer | Reproduction report recorded in the mouse navigation change; source fix, simulation and physical retest are required. |

No credential, network identifier or address is included. These are real operator reports, not injected-input observations. Remaining named photographs, recordings, per-case checks and measurements are not silently marked complete. The next easy operator step after deployment of the tap fix is to retest app header and Backspace, then scroll folders in both Portfolio and Nautilus.

## Clock feedback

The operator additionally reported: **“clock survives a reboot seems fine fwiw, it's right now many reboots later.”** This confirms repeated-reboot time correctness at the observed shell. Task 4.2 of `the-clock-survives-a-reboot` specifically calls for full power removal or demonstrated RTC backup supply, with the RTC sampled before network synchronization/writeback. A correct clock after those services run cannot establish that additional retention property; keep the named power-removal gate open. No additional power test was requested or performed during the input deployment.
