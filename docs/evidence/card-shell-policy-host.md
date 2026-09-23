# Product card policy: coordinator host review

On 2026-09-23 the coordinator reviewed the actual C policy in
`nix/card-shell-policy/card-shell-policy.c` and its integration contract.
Source commits `237be7b` and `c2ece6a` were integrated as `1755cb3` and
`8f21cf3`. The adapter compiles this shared source; there is no independent
Python state model. Adapter integration remains a separate task.

Command run from the integration worktree:

```sh
python3 tests/test_card_shell_state.py
openspec validate the-shell-manages-apps-as-cards --strict
```

Both exited zero. All 21 scenarios passed with AddressSanitizer and
UndefinedBehaviorSanitizer. They exercise dynamic snapshots, horizontal
tracking, adjacent-card identity, private/unavailable states and transitions,
graceful close, refusal, timeout, source removal, edge entry, multiple contacts,
button equivalents, keyboard geometry and reduced-motion outcomes. A 257-card
fixture avoids baking the two-app architecture probe into the product policy.

Review found that locally cancelling a gesture and ending a complete touch
stream need different semantics. Waiting for an up event after compositor
cancellation or device removal can swallow future input indefinitely. The
correction adds `cs_stream_cancel`, which clears all held contacts immediately;
locally rejected gestures still consume their remaining releases. Tests cancel
without any later up and then complete a fresh gesture, including after a
multiple-contact abort. The adapter owner received this API requirement.

This closes only the host policy task. Actual scene buffers, privacy pixels,
surface lifetimes, UI routes, keyboard focus, live rendering, physical touch,
performance and image integration remain **UNVERIFIED** by this evidence.
