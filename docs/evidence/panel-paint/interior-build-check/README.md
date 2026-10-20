# Cross-build warning correction — 2026-10-20 UTC

Source97178f9f successfully built wlroots, then the Sway adapter compilation
failed under `-Werror=misleading-indentation` at the new interior-prepare guard.
The exact command, timestamps/result and full failure log are adjacent.
Native pixel tests do not compile this Sway integration unit. No candidate
was activated or persisted. The correction adds explicit braces and matches
the surrounding indentation; selection and pixel behavior are unchanged.
A new exact-source build is required. Hardware/default/archive gates stay open.
