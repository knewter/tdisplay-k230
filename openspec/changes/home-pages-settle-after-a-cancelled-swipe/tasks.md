## 1. Implementation

- [x] 1.1 Settle a cancelled page drag (`HomePager::cancel`), and settle an
      at-rest pager that is between pages or past the last page
      (`HomePager::off_page`, `HomePager::tick`, `HomeScreen::is_animating`,
      `HomeScreen::tick`). Host tests: a cancelled drag at 0.44 settles to
      page 1; losing the last page settles back; removing the only widget on
      page 2 in rearrange mode returns Home to page 1.
      Proof (host): `cd nix/rust-shell-client && cargo test` -- 545 lib tests
      pass (2 ignored), and the other suites pass.

## 2. Board

- [x] 2.1 On HDMI, remove the only widget on the last page and capture with
      grim that Home returns to the previous page with its page dots.
      Evidence class: injected pointer + grim. Done 2026-10-15:
      `docs/evidence/home-screen/page-settle/README.md`.
- [ ] 2.2 The operator pages to page 2 with a two-finger trackpad swipe and
      removes or moves a widget there. Evidence class: operator observation.
