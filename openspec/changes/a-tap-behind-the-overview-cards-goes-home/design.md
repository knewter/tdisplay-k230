## Context

Overview is the C card shell (`nix/card-shell/adapter.c`) driving the pure
policy in `nix/card-shell-policy/card-shell-policy.c`. `cs_down` hit-tests
the cards; a miss inside the content rect sets `blocked_until_up`, which
swallows that contact's motion and release. In touch-first mode the
adapter routes a touch in the footer band to its own Home gesture
(`home_begin`), whose tap ends in `home_settle(true)`.

## Decisions

- **Layer: userspace, the policy.** A miss in `CS_DECK` mode keeps the
  existing swallow but also records a backdrop tap candidate (contact id
  and down point). Movement past `tap_slop`, a second contact or a cancel
  drops the candidate. If that contact lifts while still a candidate and
  the deck is still showing, `cs_up` returns a new `CS_HOME` action.
- **The adapter** answers `CS_HOME` with the footer's own path,
  `home_settle(true)`, so Home looks and behaves exactly as after a footer
  tap, including keeping app windows in Overview.
- The title band counts as backdrop; its Close button is hit-tested
  before the policy and keeps its meaning.

## Rejected

- Starting the adapter's Home swipe from any backdrop touch: an upward or
  sideways drag from beside a card would then pull Home, which nobody
  asked for and which would fight the card throw.
- Treating the tap on release position alone: a drag that ends back
  where it started would count as a tap. The slop test uses the whole
  path.
