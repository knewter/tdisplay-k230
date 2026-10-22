# Shipped 12 ms panel render allowance: installed trial, glass check, persistent boot

On 2026-10-21 the operator chose a 12 ms panel render allowance. At the old
8 ms, three live cards skip refreshes during a real-rate drag
([8 ms trial](../touch-rate-trial-8ms/README.md)). Source
`154225653e80df13868f11fc5651a44d60cb5a7f` changes only
`output DSI-1 … max_render_time 8` to `12` in `nix/shell.nix`. HDMI keeps its
own 8 ms hover-flicker fix. This directory holds the proof that the change is
installed, passes the card budget, does not bring back the bottom-band
flicker, and survives an ordinary reboot.

## 1. Build and live activation

```sh
nix build .#nixosConfigurations.k230-mainline-drm-shell-landscape-hdmi.config.system.build.toplevel
nix build .#kernelMainlineDrmShellLandscapeHdmiBootFiles --max-jobs 1 --cores 6
```

These produce system `/nix/store/8xkkpma4fvgw4fi6pl8qaz7d9d75kcdi-nixos-system-nixos-26.11.20260919.20b1ddd`
and bundle `/nix/store/d5664cphbs9l1jyd36zr0kpyqz17xymp-k230-coherent-shell-boot-files`.
The committed revision rebuilds the identical bundle. Against the previous
system `2igpibpw…`, 18 store paths (16 MB) were missing on the board: the
sway config, units, `/etc`, and shell packages. Image, initrd and logo are
byte-identical; DTB and bootargs differ only in the `init=` path. The shipped
compositor is the same `0v1q7r9g…-k230-card-shell-hdmi-trial` (ELF
`2778ed3c…`) used by every touch-rate trial. The closure was copied with
`nix copy --to ssh://k230`, and `switch-to-configuration test` activated it.
`swaymsg -t get_outputs` then reported DSI-1 `max_render_time: 12`,
`transform: 270`.

## 2. Paired real-rate card trial against the installed allowance

The run took place **2026-10-22 00:30:24Z–00:34:28Z** on the activated system.
It is the [touch-rate trial](../touch-rate-trial/README.md) controller, with
three checked differences in [prepare-host.py](prepare-host.py):

- The "before" assertion requires the installed `max_render_time` to be 12.
- The running system must be the new system. The boot profile was still
  `2igpibpw…` during this non-persistent activation, so profile equality
  was not required.
- Fresh owned names are used.

The controller's override swaps in the same compositor binary, only to route
stderr to the bounded file log. It does not change the allowance.

| Metric | Still, one | Still, three | Video, one | Video, three |
| --- | ---: | ---: | ---: | ---: |
| Frame-update CPU p95 | 4.394 ms | 7.288 ms | 4.139 ms | 6.804 ms |
| Render wall p95 (all committed) | 8.426 ms | 11.261 ms | 7.268 ms | 9.847 ms |
| Motion-to-submit p95 | 18.898 ms | 19.452 ms | 18.541 ms | 19.464 ms |
| Motion-to-present p95 | 27.900 ms | 25.890 ms | 28.087 ms | 26.132 ms |
| Frozen tracking interval p95 | 19.172 ms | 19.173 ms | 19.171 ms | 19.164 ms |
| Tracking interval maximum | 38.328 ms | 19.212 ms | 19.209 ms | 19.175 ms |
| Above-target tracking intervals | 1 / 215 | 0 / 216 | 0 / 218 | 0 / 216 |
| Incremental session memory | 6,512,640 B | 11,624,448 B | 5,779,456 B | 11,218,944 B |

**Every frozen numeric metric passes in all four arms.** No input pauses
were excluded, and each arm has 516 motions. The correlation audit finds no
mapping disagreements. The named background workload completes with
restoration passed. Exposed video mean CPU is 0.8886 cores against 0.0155
for still, and cover pauses the decoder. [final-audit.json](final-audit.json)
verifies that the run restored the activated system, the 12 ms allowance,
landscape, still wallpaper, exact preferences, fixture removal and an
inactive timer. The combined `budget-analysis.json` gate remains
`INCOMPLETE` only for its portrait 568x1232 observation. This board runs in
landscape at the operator's direction.

## 3. Real-glass flicker check

**Evidence class: real glass interaction, operator-reported.** On the
activated 12 ms system, the operator dragged cards and moved the drawers
while watching the panel's bottom edge, which is where the
[bottom-band flicker](../../../card-shell/bottom-band-flicker/max-render-time-fix.md) appeared before
the original allowance fix. The operator reported **"no flicker"**
(2026-10-22, about 00:40Z). There was no camera recording; the webcam was
not pointed at this panel.

## 4. Persistent selection and ordinary boot

[promote-system.py](promote-system.py) is the earlier candidate2 promotion
script with the new hashes and paths. It verified the staged files, kept
rollback copies and GC roots for both systems, and atomically replaced only
`k230-tdisplay.dtb` and `bootargs.txt`, leaving the other boot files
unchanged. It then set the system profile to `8xkkpma4…`
([promotion-receipt.json](promotion-receipt.json), `PERSISTENT_SELECTED`).
After an ordinary `systemctl reboot`, [ordinary-boot.json](ordinary-boot.json)
records a new boot ID, with booted, current and profile systems all
`8xkkpma4…`. Services are active, DSI-1 is at `max_render_time: 12` and
landscape, and a native capture shows the normal startup terminal.

The board's root filesystem was already at 100% use (25 MB free) before
this change.
