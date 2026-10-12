/* Link script for the CPU0 echo/ping payload (tools/small-core-echo.S).
 * PAYLOAD_BASE is the ONLY place the load address is chosen. The assembler
 * source holds no absolute address; it reaches the slot page through the
 * echo_page symbol below. To move the image, give the linker an extra
 * one-line script BEFORE this one (-Wl,-T,base.ld -Wl,-T,this.ld) containing
 *   PAYLOAD_BASE = 0x...;
 * (lld ignores --defsym for symbols this script provides). The default is
 * the vendor bare-metal scratch window U-Boot leaves free under U-Boot. */
ENTRY(_start)
PROVIDE(PAYLOAD_BASE = 0x07000000);
SECTIONS
{
  . = PAYLOAD_BASE;
  .text : { *(.text*) }
  /DISCARD/ : { *(.comment) *(.note*) }
}
/* Slot page: second 4 KiB page after the code page. Layout is documented in
 * tools/small-core-echo.S and docs/evidence/second-core/echo-runbook.md. */
echo_page = PAYLOAD_BASE + 0x2000;
ASSERT(SIZEOF(.text) <= 0x1000, "echo code exceeds the first 4 KiB page")
