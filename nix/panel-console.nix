{ lib, ... }:
{
  options.k230.panelConsole = lib.mkOption {
    type = lib.types.bool;
    default = false;
    description = ''
      Show the Linux console on the panel and omit the U-Boot splash asset
      from the SD image. The serial console remains available in either mode.
    '';
  };
}
