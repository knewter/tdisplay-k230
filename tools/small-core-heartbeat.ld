ENTRY(_start)
SECTIONS
{
  . = 0x07000000;
  .text : { *(.text*) }
  /DISCARD/ : { *(.comment) *(.note*) }
}
heartbeat_output = 0x07002000;
ASSERT(SIZEOF(.text) <= 0x1000, "heartbeat code exceeds first scratch page")
