# Native fixed-argv fixture

`cli_hush-v2022.10.c` is the entire unmodified U-Boot v2022.10 file from
[the official source](https://github.com/u-boot/u-boot/blob/v2022.10/common/cli_hush.c).
SHA-256: `954771b8638977d12955c4da3c540a3929d47e4431a092c079192155b2d60011`.
The source retains its GPL-2.0+ notice, Larry Doolittle copyright and original
credits. `COPYING` supplies GPL version 2. The project U-Boot configuration
uses the old Hush parser, `CONFIG_SYS_CBSIZE=1024`, `CONFIG_SYS_MAXARGS=16`;
the host headers select those values and the real `__U_BOOT__` source branch.
No replacement lexer, quote parser or variable parser is used.

`hush-native.c` includes the whole parser and calls `u_boot_hush_start` and
`parse_string_outer`. Hardware/interactive callbacks abort or return inert
values. The actual Hush execution engine reaches the capture-only `cmd_process`
hook. That hook records commands and stores the bootargs bytes; it does not
execute a U-Boot command handler, persistent environment writer or target code.
An exact-input check can reject altered commands before invoking the parser.
Its expected vector is a trusted test argument, not an authorization API for
arbitrary callers. Only the typed controller may construct candidate commands.
The ordinary one `env_get("IFS")` is distinguished from script-variable lookups.
The unchanged upstream parser has signed/unsigned comparison warnings; only
that upstream warning category is suppressed for Hush. Other compiler output
fails the tests. No target architecture or installed firmware ABI is proved.

`linux-selected-functions.h` contains byte-exact functions from the immutable
selected source recorded in `linux-source.json`, based on Linux commit
`72d3fcf802c45d00b300f25b848a93c3a2bd7c7e` plus the project's optional patches.
`init/main.c` copyright: Linus Torvalds, GPL-2.0-only;
`lib/cmdline.c` credits code from init/main.c and arch/i386/kernel/setup.c,
GPL-2.0-only; `kernel/params.c` copyright Rusty Russell, GPL-2.0-or-later.
Per-file and exact-function SHA-256/line receipts are included. The test verifies
those functions' byte digests, and their equality to the immutable source when
that source is present. This excerpt combination is GPL-2.0-only.

`linux-native.c` executes the actual `next_arg`, `parse_args`, `init_setup`,
`rdinit_setup`, `repair_env_string` and `set_init_arg` code. Its `parse_one` adapter
dispatches the two actual setup handlers before `--` (as their kernel `__setup`
registrations do), invokes the actual unknown callback after `--`, and leaves
other prefix handlers inert. IRQ/logging macros and globals are host stubs.
This proves the selected tokenizer, setup resets and argv append path; it does
not execute all kernel boot handlers, exec an ELF, or simulate a boot.

The independent `*.expected` files preserve the reviewed scout's exact raw
bytes, with no final newline: script 154, bootargs 477, transport 503. A 32-byte
lowercase hexadecimal nonce is the only substitution. Python orchestrates host
compilation/execution and exact byte comparisons; it does not parse shell or
kernel syntax. No `shlex` or Python lexer is used.
