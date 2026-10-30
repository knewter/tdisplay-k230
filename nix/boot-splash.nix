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

  # the-boot-shows-a-computational-game-of-life: the Game of Life state record
  # lives INSIDE the existing reservation, after the 568x1232x4 scanout
  # (2 799 104 bytes = 0x2ab600; the offset below is the next 4 KiB boundary).
  # No new reserved-memory node and no new RAM claim: the kernel already may
  # not touch 0x10000000..0x10400000.  The window is 8 KiB; the record is
  # 5 584 bytes (src/game_of_life.h GOL_RECORD_BYTES).
  # tools/check-boot-life-memory.py reads these values.
  lifeRecordOffset = "0x002ac000";
  # Absolute form of framebufferAddress + lifeRecordOffset (Nix cannot add
  # hex strings); tools/check-boot-life-memory.py rejects a mismatch.
  lifeRecordAddress = "0x102ac000";
  lifeRecordWindow = "0x00002000";
}
