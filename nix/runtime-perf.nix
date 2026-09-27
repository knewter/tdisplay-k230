{ lib, perf }:

# Diagnostic-only perf. Keep record/report/script and ELF/unwind support without
# bundling the optional TUI, embedded Python, CTF export or SystemTap probe tools.
# Symbol annotation/disassembly can use explicitly supplied host tools later.
(perf.override { withPython = false; }).overrideAttrs (old: {
  pname = "perf-k230-runtime";
  enableParallelBuilding = true;
  buildInputs = builtins.filter
    (package: !(builtins.elem (package.pname or (lib.getName package))
      [ "newt" "slang" "babeltrace" "binutils" "libopcodes" "systemtap" ]))
    old.buildInputs;
  makeFlags = old.makeFlags ++ [ "NO_SLANG=1" "NO_SDT=1" "NO_BABELTRACE2=1" ];
  # Upstream's wrapper adds target binutils and Python to PATH. Neither is
  # required for recording stacks or emitting text with `perf script`.
  preFixup = "";
})
