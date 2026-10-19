## 1. Policy and adapter

- [x] 1.1 `cs_down` records a backdrop tap candidate on a card miss in the
  deck; `cs_motion`, extra contacts and `cs_cancel` clear it; `cs_up`
  returns `CS_HOME` for a still-candidate release. Driver cases for a
  backdrop tap, a backdrop drag, a backdrop tap joined by a second
  contact, and an unchanged card tap. Verify with
  `python3 -m unittest tests.test_card_shell_state`. Host class.
- [x] 1.2 The adapter answers `CS_HOME` with `home_settle(true)`. Verify
  with `nix build .#kernelMainlineDrmShellLandscapeHdmiBootFiles`. Build
  class.

## 2. Board

- [x] 2.1 On the landscape panel, an injected tap on the Overview backdrop
  above the card shows Home, and Overview still lists the open app
  afterwards. Native `grim` captures before and after, in
  `docs/evidence/overview-backdrop-tap/`. Board class (injected input).
- [x] 2.2 The operator taps behind the card on glass. Board class; stays
  open until the operator has tried it.

Proof for 1.1, 1.2 and 2.1: `docs/evidence/overview-backdrop-tap/README.md`
and `board-checks.log`. Source `90ac21db`; landscape panel, injected
absolute pointer and native `grim`, not an operator glass test.
The board was left at Home with Terminal still open.

Task 2.2: operator glass confirmation on 2026-10-19,
`docs/evidence/overview-backdrop-tap/operator-signoff.md`.
