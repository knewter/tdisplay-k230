## ADDED Requirements

### Requirement: SD storage under mainline runs at the vendor kernel's card clock
Under the mainline kernel, the SD card and the SDIO radio SHALL be clocked at the
same card-clock rate the vendor kernel uses (High-Speed, 50 MHz actual), and
every SD controller clock gate SHALL stay claimed by its driver.

#### Scenario: Sequential reads match vendor throughput
- **WHEN** an operator runs `dd if=/dev/mmcblk1 of=/dev/null bs=4M count=32 iflag=direct` on the installed mainline system
- **THEN** `/sys/kernel/debug/mmc1/ios` reports an actual clock of 50000000 Hz and the read rate is within 15% of the vendor kernel's 23.3 MB/s on the same card
<!-- UNVERIFIED: clock fix not yet built or booted -->

#### Scenario: Wi-Fi still associates over SDIO
- **WHEN** the mainline system with the new SD clocks boots and Wi-Fi is enabled
- **THEN** the RTL8189FTV interface associates and obtains an address
<!-- UNVERIFIED -->
