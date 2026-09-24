# Direct live-app carousel: headless QEMU checkpoint

The exact opt-in card-shell source revision `7d1c2b43` cross-built as `/nix/store/4x4kpds8kvha9zpmr966lbsi8r2gnzma-k230-card-shell`; its unwrapped compositor is `/nix/store/lmgq4hj6fxc37vp98hy1x93wnz589iyn-sway-unwrapped-riscv64-unknown-linux-gnu-1.12/bin/sway`. The public client was `/nix/store/6nskh3ldk3ya7mwxbb258qszrxhw2i61-card-composition-probe-client-0.1/bin/card-composition-probe-client`. The headless fixture at test revision `54e21ed7` enabled the same `card_shell ordinary` marker used for ordinary full-panel apps in the coherent session. It injected synthetic touch through the compositor's native test input and captured the actual Pixman-composed Wayland output. The test was run twice through `tests/test_card_shell_two_axis_runtime.py`, then once with the persistent capture command below; all three passed. `python3 tests/test_card_shell_state.py` passed 28 native policy cases.

```sh
CARD_SHELL_SWAY=/nix/store/lmgq4hj6fxc37vp98hy1x93wnz589iyn-sway-unwrapped-riscv64-unknown-linux-gnu-1.12/bin/sway \
  python3 tests/test_card_shell_two_axis_runtime.py
python3 tests/card_shell_runtime.py \
  --sway /nix/store/lmgq4hj6fxc37vp98hy1x93wnz589iyn-sway-unwrapped-riscv64-unknown-linux-gnu-1.12/bin/sway \
  --client /nix/store/6nskh3ldk3ya7mwxbb258qszrxhw2i61-card-composition-probe-client-0.1/bin/card-composition-probe-client \
  --output /tmp/k230-direct-switch-qemu-proof3 --native-touch --touch-first --two-axis
```

The committed PNGs are unedited selections from that final run. A pure 100-pixel sideways drag translated the exposed app 100±7 pixels while held; a pause did not move it, and a 40-pixel reversal followed directly. The release frame still contained substantial live pixels from both apps at near-full height, and the selected app received focus without a card-sized overview or second expansion. The separate upward release shows the live app between held geometry and its deck slot, then the settled deck. Host policy tests verify an unchanged position at release, nonzero bounded release velocity, a fast upward spring near the deck without a hard clamp, and a fast reversal that cannot choose the opposite neighbor before crossing the source. The fixture also checked private-neighbor pixels, target disappearance, and opposite-direction return.

This is synthetic headless QEMU evidence. It does not establish real-finger feel, panel presentation timing, installed-image CPU/frame budgets, keyboard conflicts on glass, or the user's acceptance of the revised motion. The coherent-shell physical two-axis task and performance gates remain open. Video and transient containers are not normalized to the ordinary full-panel carousel frame; their own geometry remains in use through focus handoff.
