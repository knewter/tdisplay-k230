# the-boot-shows-a-computational-game-of-life: Linux continues the stage-1
# Game of Life from the state record in the splash reservation (validated
# against /chosen/canaan,life-instance; any failure draws the deterministic
# default).  Off by default; the static logo owner is unchanged without it.
{ lib, ... }:
{
  options.k230.bootLife.enable = lib.mkEnableOption "the early-Linux Game of Life continuation in the splash owner";
}
