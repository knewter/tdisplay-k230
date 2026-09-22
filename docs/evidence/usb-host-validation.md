# U-Boot host coexistence validation — 2026-09-22

The repaired candidate supports the onboard RTL8152 host and the J3 mass
storage gadget in the same U-Boot session. This proves controller binding
and device enumeration; no Ethernet packet test was performed.

`uboot-usb-host-coexist-v2.txt` records both DWC2 bindings, the Realtek USB
tree before and after UMS, host enumeration as `29f1:0230`, and the expected
249,872,384-sector card. Reading 380,911 bytes from its U-Boot slot produced
SHA-256 `4cb755ed0b0ac06fcccade582fcbc90f99ffb6f4c35cec65e3564804b5be6226`,
matching the source-built candidate. Linux returned; the separate
`usb-host-second-candidate-linux.txt` confirms the stock shell is active,
has no service drop-ins, and drives 568x1232 in the normal orientation.

That was the **initial narrow trial**: its installer changed only the U-Boot
slot, and the slot-backup/recovery-image statements apply to that session's
board state only. They are historical evidence, not a claim about the board
after later full-image flashing.

The repaired stage 1 was subsequently included in the source-built daily
image. [`daily-shell-image.md`](daily-shell-image.md) identifies the exact
image and stage-1 store paths, and
[`declarative-final/image-flash.txt`](shell-features/declarative-final/image-flash.txt)
records the complete 2,308,689,920-byte image written through UMS at
12.7 MB/s, U-Boot reset, and return to the Linux login prompt with status 0.
That transcript intentionally skipped a full readback, so it proves full-image
boot and recovery to Linux, not byte-for-byte post-write verification.

The first candidate's missing host remains recorded in
`uboot-usb-host-coexist.txt`. The helper now reports a separate host verdict:
a prompt alone cannot turn `No working controllers found` into a pass.
Its parser checks each driver against its own controller address and uses
status 4 for host failure after successful UMS and Linux recovery.

A further physical session using the updated helper is preserved in
`uboot-usb-host-verdict.txt`: host checks passed before and after UMS,
the card enumerated and its bootloader readback matched, Linux returned,
and the final line reports both UMS and USB host PASS with exit status 0.

Checks on the integrated changes:

- `python3 -m unittest -v tests/test_ums_target.py`: 16 passed, including
  wrong-controller binding and the physical candidate-2 fixture.
- `python3 -m py_compile tools/ums-session.py`: passed.
- `openspec validate --all`: 14 passed, zero failed.
- `python3 scripts/build_site.py`: passed, including evidence, binary
  inventory and rendered-site checks; 55 pages, 1,100,344 bytes, 12.63 s.

The existing Linux USB KFENCE warning remains unresolved; see
`usb-kfence-observation.md`. BootROM recovery characterization still needs
physical card/button/power operations. Neither limitation is hidden by this
host coexistence result.
