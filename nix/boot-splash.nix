# Shared stage-1 scanout reservation.  The U-Boot Kconfig fragment and the
# Linux DT preprocessor both consume these values.
let
  framebufferAddress = "0x10000000";
in
{
  inherit framebufferAddress;
  framebufferSize = "0x00400000";
  framebufferUnitAddress =
    builtins.substring 2 ((builtins.stringLength framebufferAddress) - 2)
      framebufferAddress;
}
