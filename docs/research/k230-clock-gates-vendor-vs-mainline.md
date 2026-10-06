# K230 clock gates: vendor tree versus mainline `clk-k230.c`

Compiled 2026-10-06 for `openspec/changes/the-mainline-shell-reaches-parity`
from the mainline 7.3.0-rc5 source (`drivers/clk/clk-k230.c`) and the vendor
6.6 tree (`arch/riscv/boot/dts/canaan/k230_clock_provider.dtsi`), matched by
register offset and bit. Read-only source comparison; no board involved.

## Recorded decisions

- `dphy_dft_gate` was wired to 0x100 bit 0 in mainline; the vendor
  `dphy_test_clk` gates at 0x104 bit 0. Fixed in `k230-clk-vpu-ddrcp2-dphy.patch`.
- `usb_480m_gate` and `usb_100m_gate` both use 0x100 bit 0. The vendor tree
  gates `usb_clk480` and `usb_clk100` on the same bit, so this is one hardware
  gate feeding two clocks, not a mainline aliasing bug. No change.
- The vendor `disp_clkext` gate (0x74 bit 5) has no mainline gate.
  Linux never writes the bit, U-Boot's setting stands, and the panel works
  (2026-10-06 full-shell evidence). Modelling it without a consumer would let
  unused-clock cleanup gate it, the failure class this work removed. Left
  unmodelled on purpose.
- `cpu1_*`, `ai_src`/`ai_axi` and `camera0/1/2` gates have no vendor composite
  node to compare against; they are unvalidated, not known-bad.
- The vendor driver never marks any gate critical and its display drivers do no
  clock management; the vendor kernel works because its composite clocks are
  not gated as unused. Mainline needs explicit consumers or `CLK_IS_CRITICAL`
  (see `docs/evidence/mainline-clock-ownership-2026-10-06/` and
  `docs/evidence/mainline-full-shell-2026-10-06/`).

## Full table

| Mainline name | ID | reg/bit | mainline flags | vendor node (reg/bit) | vendor read-only | vendor-gateable? | device |
|---|---|---|---|---|---|---|---|
| cpu0_src_gate | K230_CPU0_SRC_GATE | 0/0 | CRITICAL | cpu0_src (0x0/0) | 0 | yes (rw gate bit exists) | no DT consumer found (orphan in vendor too) |
| cpu0_plic_gate | K230_CPU0_PLIC_GATE | 0x0/9 | CRITICAL | cpu0_plic (0x0/9) | 0 | yes (rw gate bit exists) | no DT consumer found (orphan in vendor too) |
| cpu0_noc_ddrcp4_gate | K230_CPU0_NOC_DDRCP4_GATE | 0x60/7 | CRITICAL | cpu0_noc_ddrcp4 (0x60/7) | 0 | yes (rw gate bit exists) | no DT consumer found (orphan in vendor too) |
| cpu0_apb_gate | K230_CPU0_APB_GATE | 0x0/13 | CRITICAL | cpu0_pclk (0x0/13) | 0 | yes (rw gate bit exists) | no DT consumer found (orphan in vendor too) |
| cpu1_src_gate | K230_CPU1_SRC_GATE | 0x4/0 | CRITICAL | **NONE FOUND** (-) | - | n/a (no vendor node at this reg/bit) | - |
| cpu1_plic_gate | K230_CPU1_PLIC_GATE | 0x4/15 | CRITICAL | **NONE FOUND** (-) | - | n/a (no vendor node at this reg/bit) | - |
| cpu1_apb_gate | K230_CPU1_APB_GATE | 0x4/19 | CRITICAL | **NONE FOUND** (-) | - | n/a (no vendor node at this reg/bit) | - |
| hs_hclk_high_gate | K230_HS_HCLK_HIGH_GATE | 0x18/1 | - | hs_hclk_high (0x18/1) | 0 | yes (rw gate bit exists) | no DT consumer found (orphan in vendor too) |
| hs_hclk_gate | K230_HS_HCLK_GATE | 0x18/0 | - | hs_hclk_src (0x18/0) | 0 | yes (rw gate bit exists) | no DT consumer found (orphan in vendor too) |
| hs_sd0_ahb_gate | K230_HS_SD0_AHB_GATE | 0x18/2 | - | sd0_hclk_gate (0x18/2) | 0 | yes (rw gate bit exists) | no DT consumer found (orphan in vendor too) |
| hs_sd1_ahb_gate | K230_HS_SD1_AHB_GATE | 0x18/3 | - | sd1_hclk_gate (0x18/3) | 0 | yes (rw gate bit exists) | no DT consumer found (orphan in vendor too) |
| hs_ssi1_ahb_gate | K230_HS_SSI1_AHB_GATE | 0x18/7 | - | ssi1_hclk_gate (0x18/7) | 0 | yes (rw gate bit exists) | no DT consumer found (orphan in vendor too) |
| hs_ssi2_ahb_gate | K230_HS_SSI2_AHB_GATE | 0x18/8 | - | ssi2_hclk_gate (0x18/8) | 0 | yes (rw gate bit exists) | no DT consumer found (orphan in vendor too) |
| hs_usb0_ahb_gate | K230_HS_USB0_AHB_GATE | 0x18/4 | - | usb0_hclk_gate (0x18/4) | 0 | yes (rw gate bit exists) | no DT consumer found (orphan in vendor too) |
| hs_usb1_ahb_gate | K230_HS_USB1_AHB_GATE | 0x18/5 | - | usb1_hclk_gate (0x18/5) | 0 | yes (rw gate bit exists) | no DT consumer found (orphan in vendor too) |
| hs_ssi0_axi_gate | K230_HS_SSI0_AXI_GATE | 0x18/27 | - | ssi0_aclk (0x18/27) | 0 | yes (rw gate bit exists) | no DT consumer found (orphan in vendor too) |
| hs_ssi1_gate | K230_HS_SSI1_GATE | 0x18/25 | - | ssi1_clk (0x18/25) | 0 | yes (rw gate bit exists) | ssi1 (SPI1) |
| hs_ssi2_gate | K230_HS_SSI2_GATE | 0x18/26 | - | ssi2_clk (0x18/26) | 0 | yes (rw gate bit exists) | ssi2 (SPI2, status disabled by default) |
| hs_qspi_axi_src_gate | K230_HS_QSPI_AXI_SRC_GATE | 0x18/28 | - | qspi_aclk_src (0x18/28) | 0 | yes (rw gate bit exists) | no DT consumer found (orphan in vendor too) |
| hs_ssi1_axi_gate | K230_HS_SSI1_AXI_GATE | 0x18/29 | - | ssi1_aclk_gate (0x18/29) | 0 | yes (rw gate bit exists) | no DT consumer found (orphan in vendor too) |
| hs_ssi2_axi_gate | K230_HS_SSI2_AXI_GATE | 0x18/30 | - | ssi2_aclk_gate (0x18/30) | 0 | yes (rw gate bit exists) | no DT consumer found (orphan in vendor too) |
| hs_sd_card_src_gate | K230_HS_SD_CARD_SRC_GATE | 0x18/11 | - | sd_cclk_src (0x18/11) | 0 | yes (rw gate bit exists) | no DT consumer found (orphan in vendor too) |
| hs_sd0_card_gate | K230_HS_SD0_CARD_GATE | 0x18/15 | - | sd0_cclk_gate (0x18/15) | 0 | yes (rw gate bit exists) | sdio0 card-detect (board .dts, lcd variants only) |
| hs_sd1_card_gate | K230_HS_SD1_CARD_GATE | 0x18/19 | - | sd1_cclk_gate (0x18/19) | 0 | yes (rw gate bit exists) | no DT consumer found (orphan in vendor too) |
| hs_sd_axi_src_gate | K230_HS_SD_AXI_SRC_GATE | 0x18/9 | - | sd_aclk (0x18/9) | 0 | yes (rw gate bit exists) | no DT consumer found (orphan in vendor too) |
| hs_sd0_axi_gate | K230_HS_SD0_AXI_GATE | 0x18/13 | - | sd0_aclk_gate (0x18/13) | 0 | yes (rw gate bit exists) | no DT consumer found (orphan in vendor too) |
| hs_sd1_axi_gate | K230_HS_SD1_AXI_GATE | 0x18/17 | - | sd1_aclk_gate (0x18/17) | 0 | yes (rw gate bit exists) | no DT consumer found (orphan in vendor too) |
| hs_sd0_base_gate | K230_HS_SD0_BASE_GATE | 0x18/14 | - | sd0_bclk_gate (0x18/14) | 0 | yes (rw gate bit exists) | no DT consumer found (orphan in vendor too) |
| hs_sd1_base_gate | K230_HS_SD1_BASE_GATE | 0x18/18 | - | sd1_bclk_gate (0x18/18) | 0 | yes (rw gate bit exists) | no DT consumer found (orphan in vendor too) |
| hs_ssi0_gate | K230_HS_SSI0_GATE | 0x18/24 | IGNORE_UNUSED | ssi0_clk (0x18/24) | 0 | yes (rw gate bit exists) | ssi0@... (QSPI/NOR boot flash controller) |
| hs_sd0_timer_gate | K230_HS_SD0_TIMER_GATE | 0x18/16 | - | sd0_tmclk_gate (0x18/16) | 0 | yes (rw gate bit exists) | no DT consumer found (orphan in vendor too) |
| hs_sd1_timer_gate | K230_HS_SD1_TIMER_GATE | 0x18/20 | - | sd1_tmclk_gate (0x18/20) | 0 | yes (rw gate bit exists) | no DT consumer found (orphan in vendor too) |
| hs_usb0_ref_gate | K230_HS_USB0_REF_GATE | 0x18/21 | IGNORE_UNUSED | usb0_ref_clk (0x18/21) | 0 | yes (rw gate bit exists) | no DT consumer found (orphan in vendor too) |
| hs_usb1_ref_gate | K230_HS_USB1_REF_GATE | 0x18/22 | IGNORE_UNUSED | usb1_ref_clk (0x18/22) | 0 | yes (rw gate bit exists) | no DT consumer found (orphan in vendor too) |
| ls_apb_src_gate | K230_LS_APB_SRC_GATE | 0x24/0 | CRITICAL | ls_pclk_src (0x24/0) | 0 | yes (rw gate bit exists) | no DT consumer found (orphan in vendor too) |
| ls_uart0_apb_gate | K230_LS_UART0_APB_GATE | 0x24/1 | CRITICAL | uart0_pclk_gate (0x24/1) | 0 | yes (rw gate bit exists) | no DT consumer found (orphan in vendor too) |
| ls_uart1_apb_gate | K230_LS_UART1_APB_GATE | 0x24/2 | CRITICAL | uart1_pclk_gate (0x24/2) | 0 | yes (rw gate bit exists) | no DT consumer found (orphan in vendor too) |
| ls_uart2_apb_gate | K230_LS_UART2_APB_GATE | 0x24/3 | CRITICAL | uart2_pclk_gate (0x24/3) | 0 | yes (rw gate bit exists) | no DT consumer found (orphan in vendor too) |
| ls_uart3_apb_gate | K230_LS_UART3_APB_GATE | 0x24/4 | CRITICAL | uart3_pclk_gate (0x24/4) | 0 | yes (rw gate bit exists) | no DT consumer found (orphan in vendor too) |
| ls_uart4_apb_gate | K230_LS_UART4_APB_GATE | 0x24/5 | CRITICAL | uart4_pclk_gate (0x24/5) | 0 | yes (rw gate bit exists) | no DT consumer found (orphan in vendor too) |
| ls_i2c0_apb_gate | K230_LS_I2C0_APB_GATE | 0x24/6 | - | i2c0_pclk_gate (0x24/6) | 0 | yes (rw gate bit exists) | no DT consumer found (orphan in vendor too) |
| ls_i2c1_apb_gate | K230_LS_I2C1_APB_GATE | 0x24/7 | - | i2c1_pclk_gate (0x24/7) | 0 | yes (rw gate bit exists) | no DT consumer found (orphan in vendor too) |
| ls_i2c2_apb_gate | K230_LS_I2C2_APB_GATE | 0x24/8 | - | i2c2_pclk_gate (0x24/8) | 0 | yes (rw gate bit exists) | no DT consumer found (orphan in vendor too) |
| ls_i2c3_apb_gate | K230_LS_I2C3_APB_GATE | 0x24/9 | - | i2c3_pclk_gate (0x24/9) | 0 | yes (rw gate bit exists) | no DT consumer found (orphan in vendor too) |
| ls_i2c4_apb_gate | K230_LS_I2C4_APB_GATE | 0x24/10 | - | i2c4_pclk_gate (0x24/10) | 0 | yes (rw gate bit exists) | no DT consumer found (orphan in vendor too) |
| ls_gpio_apb_gate | K230_LS_GPIO_APB_GATE | 0x24/11 | - | gpio_pclk_gate (0x24/11) | 0 | yes (rw gate bit exists) | no DT consumer found (orphan in vendor too) |
| ls_pwm_apb_gate | K230_LS_PWM_APB_GATE | 0x24/12 | - | pwm_pclk_gate (0x24/12) | 0 | yes (rw gate bit exists) | pwm0@9140a000, pwm1@9140a040 (canaan,k230-pwm) |
| ls_jamlink0_apb_gate | K230_LS_JAMLINK0_APB_GATE | 0x28/4 | - | jamlink0_pclk_gate (0x28/4) | 0 | yes (rw gate bit exists) | no DT consumer found (orphan in vendor too) |
| ls_jamlink1_apb_gate | K230_LS_JAMLINK1_APB_GATE | 0x28/5 | - | jamlink1_pclk_gate (0x28/5) | 0 | yes (rw gate bit exists) | no DT consumer found (orphan in vendor too) |
| ls_jamlink2_apb_gate | K230_LS_JAMLINK2_APB_GATE | 0x28/6 | - | jamlink2_pclk_gate (0x28/6) | 0 | yes (rw gate bit exists) | no DT consumer found (orphan in vendor too) |
| ls_jamlink3_apb_gate | K230_LS_JAMLINK3_APB_GATE | 0x28/7 | - | jamlink3_pclk_gate (0x28/7) | 0 | yes (rw gate bit exists) | no DT consumer found (orphan in vendor too) |
| ls_audio_apb_gate | K230_LS_AUDIO_APB_GATE | 0x24/13 | - | audio_pclk_gate (0x24/13) | 0 | yes (rw gate bit exists) | no DT consumer found (orphan in vendor too) |
| ls_adc_apb_gate | K230_LS_ADC_APB_GATE | 0x24/15 | - | adc_pclk_gate (0x24/15) | 0 | yes (rw gate bit exists) | no DT consumer found (orphan in vendor too) |
| ls_codec_apb_gate | K230_LS_CODEC_APB_GATE | 0x24/14 | - | codec_pclk_gate (0x24/14) | 0 | yes (rw gate bit exists) | no DT consumer found (orphan in vendor too) |
| ls_i2c0_gate | K230_LS_I2C0_GATE | 0x24/21 | - | i2c0_clk (0x24/21) | 0 | yes (rw gate bit exists) | i2c0 |
| ls_i2c1_gate | K230_LS_I2C1_GATE | 0x24/22 | - | i2c1_clk (0x24/22) | 0 | yes (rw gate bit exists) | i2c1 |
| ls_i2c2_gate | K230_LS_I2C2_GATE | 0x24/23 | - | i2c2_clk (0x24/23) | 0 | yes (rw gate bit exists) | i2c2 |
| ls_i2c3_gate | K230_LS_I2C3_GATE | 0x24/24 | - | i2c3_clk (0x24/24) | 0 | yes (rw gate bit exists) | i2c3 |
| ls_i2c4_gate | K230_LS_I2C4_GATE | 0x24/25 | - | i2c4_clk (0x24/25) | 0 | yes (rw gate bit exists) | i2c4 |
| ls_codec_adc_gate | K230_LS_CODEC_ADC_GATE | 0x24/29 | - | codec_adc_mclk (0x24/29) | 0 | yes (rw gate bit exists) | inno_codec@0x9140e000 (adc) |
| ls_codec_dac_gate | K230_LS_CODEC_DAC_GATE | 0x24/30 | - | codec_dac_mclk (0x24/30) | 0 | yes (rw gate bit exists) | inno_codec@0x9140e000 (dac) |
| ls_audio_dev_gate | K230_LS_AUDIO_DEV_GATE | 0x24/28 | - | audio_dev_clk (0x24/28) | 0 | yes (rw gate bit exists) | i2s@0x9140f000 (designware-i2s) |
| ls_pdm_gate | K230_LS_PDM_GATE | 0x24/31 | - | pdm_clk (0x24/31) | 0 | yes (rw gate bit exists) | no DT consumer found (orphan in vendor too) |
| ls_adc_gate | K230_LS_ADC_GATE | 0x24/26 | - | adc_clk (0x24/26) | 0 | yes (rw gate bit exists) | adc@9140d000 |
| ls_uart0_gate | K230_LS_UART0_GATE | 0x24/16 | CRITICAL | uart0_clk (0x24/16) | 0 | yes (rw gate bit exists) | no DT consumer found (orphan in vendor too) |
| ls_uart1_gate | K230_LS_UART1_GATE | 0x24/17 | CRITICAL | uart1_clk (0x24/17) | 0 | yes (rw gate bit exists) | no DT consumer found (orphan in vendor too) |
| ls_uart2_gate | K230_LS_UART2_GATE | 0x24/18 | CRITICAL | uart2_clk (0x24/18) | 0 | yes (rw gate bit exists) | no DT consumer found (orphan in vendor too) |
| ls_uart3_gate | K230_LS_UART3_GATE | 0x24/19 | CRITICAL | uart3_clk (0x24/19) | 0 | yes (rw gate bit exists) | no DT consumer found (orphan in vendor too) |
| ls_uart4_gate | K230_LS_UART4_GATE | 0x24/20 | CRITICAL | uart4_clk (0x24/20) | 0 | yes (rw gate bit exists) | no DT consumer found (orphan in vendor too) |
| ls_jamlink0co_gate | K230_LS_JAMLINK0CO_GATE | 0x28/0 | - | jamlink0CO_gate (0x28/0) | 0 | yes (rw gate bit exists) | no DT consumer found (orphan in vendor too) |
| ls_jamlink1co_gate | K230_LS_JAMLINK1CO_GATE | 0x28/1 | - | jamlink1CO_gate (0x28/1) | 0 | yes (rw gate bit exists) | no DT consumer found (orphan in vendor too) |
| ls_jamlink2co_gate | K230_LS_JAMLINK2CO_GATE | 0x28/2 | - | jamlink2CO_gate (0x28/2) | 0 | yes (rw gate bit exists) | no DT consumer found (orphan in vendor too) |
| ls_jamlink3co_gate | K230_LS_JAMLINK3CO_GATE | 0x28/3 | - | jamlink3CO_gate (0x28/3) | 0 | yes (rw gate bit exists) | no DT consumer found (orphan in vendor too) |
| sysctl_wdt0_apb_gate | K230_SYSCTL_WDT0_APB_GATE | 0x50/1 | - | wdt0_pclk_gate (0x50/1) | 0 | yes (rw gate bit exists) | no DT consumer found (orphan in vendor too) |
| sysctl_wdt1_apb_gate | K230_SYSCTL_WDT1_APB_GATE | 0x50/2 | - | wdt1_pclk_gate (0x50/2) | 0 | yes (rw gate bit exists) | no DT consumer found (orphan in vendor too) |
| sysctl_timer_apb_gate | K230_SYSCTL_TIMER_APB_GATE | 0x50/3 | - | timer_pclk_gate (0x50/3) | 0 | yes (rw gate bit exists) | no DT consumer found (orphan in vendor too) |
| sysctl_iomux_apb_gate | K230_SYSCTL_IOMUX_APB_GATE | 0x50/20 | - | iomux_pclk_gate (0x50/20) | 0 | yes (rw gate bit exists) | no DT consumer found (orphan in vendor too) |
| sysctl_mailbox_apb_gate | K230_SYSCTL_MAILBOX_APB_GATE | 0x50/4 | - | mailbox_pclk_gate (0x50/4) | 0 | yes (rw gate bit exists) | no DT consumer found (orphan in vendor too) |
| sysctl_hdi_gate | K230_SYSCTL_HDI_GATE | 0x50/21 | - | hdi_clk (0x50/21) | 0 | yes (rw gate bit exists) | no DT consumer found (orphan in vendor too) |
| sysctl_time_stamp_gate | K230_SYSCTL_TIME_STAMP_GATE | 0x50/19 | CRITICAL | stc_clk (0x50/19) | 0 | yes (rw gate bit exists) | no DT consumer found (orphan in vendor too) |
| timer0_gate | K230_TIMER0_GATE | 0x50/13 | IGNORE_UNUSED | timer0_clk (0x50/13) | 0 | yes (rw gate bit exists) | no DT consumer found (orphan in vendor too) |
| timer1_gate | K230_TIMER1_GATE | 0x50/14 | IGNORE_UNUSED | timer1_clk (0x50/14) | 0 | yes (rw gate bit exists) | no DT consumer found (orphan in vendor too) |
| timer2_gate | K230_TIMER2_GATE | 0x50/15 | IGNORE_UNUSED | timer2_clk (0x50/15) | 0 | yes (rw gate bit exists) | no DT consumer found (orphan in vendor too) |
| timer3_gate | K230_TIMER3_GATE | 0x50/16 | IGNORE_UNUSED | timer3_clk (0x50/16) | 0 | yes (rw gate bit exists) | no DT consumer found (orphan in vendor too) |
| timer4_gate | K230_TIMER4_GATE | 0x50/17 | IGNORE_UNUSED | timer4_clk (0x50/17) | 0 | yes (rw gate bit exists) | no DT consumer found (orphan in vendor too) |
| timer5_gate | K230_TIMER5_GATE | 0x50/18 | IGNORE_UNUSED | timer5_clk (0x50/18) | 0 | yes (rw gate bit exists) | no DT consumer found (orphan in vendor too) |
| shrm_apb_gate | K230_SHRM_APB_GATE | 0x5C/0 | - | shrm_pclk (0x5C/0) | 0 | yes (rw gate bit exists) | no DT consumer found (orphan in vendor too) |
| shrm_sram_gate | K230_SHRM_SRAM_GATE | 0x5c/10 | IGNORE_UNUSED | shrm_src (0x5C/10) | 0 | yes (rw gate bit exists) | no DT consumer found (orphan in vendor too) |
| shrm_axi_slave_gate | K230_SHRM_AXI_SLAVE_GATE | 0x5C/11 | IGNORE_UNUSED | shrm_axis_clk_gate (0x5C/11) | 0 | yes (rw gate bit exists) | no DT consumer found (orphan in vendor too) |
| shrm_axi_gate | K230_SHRM_AXI_GATE | 0x5C/12 | - | shrm_axim_clk_gate (0x5C/12) | 0 | yes (rw gate bit exists) | no DT consumer found (orphan in vendor too) |
| shrm_nonai2d_axi_gate | K230_SHRM_NONAI2D_AXI_GATE | 0x5C/9 | - | nonai2d_aclk_gate (0x5C/9) | 0 | yes (rw gate bit exists) | no DT consumer found (orphan in vendor too) |
| shrm_decompress_axi_gate | K230_SHRM_DECOMPRESS_AXI_GATE | 0x5C/7 | IGNORE_UNUSED | decompress_aclk_gate (0x5C/7) | 0 | yes (rw gate bit exists) | no DT consumer found (orphan in vendor too) |
| shrm_sdma_axi_gate | K230_SHRM_SDMA_AXI_GATE | 0x5C/5 | - | gsdma_aclk_gate (0x5C/5) | 0 | yes (rw gate bit exists) | no DT consumer found (orphan in vendor too) |
| shrm_pdma_axi_gate | K230_SHRM_PDMA_AXI_GATE | 0x5C/3 | - | pdma_aclk_gate (0x5C/3) | 0 | yes (rw gate bit exists) | pdma@0x80804000 (canaan,k230-pdma) |
| ddrc_src_gate | K230_DDRC_SRC_GATE | 0x60/2 | IGNORE_UNUSED | ddrc_core_clk (0x60/2) | 0 | yes (rw gate bit exists) | no DT consumer found (orphan in vendor too) |
| ddrc_bypass_gate | K230_DDRC_BYPASS_GATE | 0x60/8 | - | ddrc_bypass_gate (0x60/8) | 0 | yes (rw gate bit exists) | no DT consumer found (orphan in vendor too) |
| ddrc_apb_gate | K230_DDRC_APB_GATE | 0x60/9 | - | ddrc_pclk (0x60/9) | 0 | yes (rw gate bit exists) | no DT consumer found (orphan in vendor too) |
| display_ahb_gate | K230_DISPLAY_AHB_GATE | 0x74/0 | - | disp_hclk (0x74/0) | 0 | yes (rw gate bit exists) | no DT consumer found (orphan in vendor too) |
| display_axi_gate | K230_DISPLAY_AXI_GATE | 0x74/1 | - | disp_aclk_gate (0x74/1) | 0 | yes (rw gate bit exists) | no DT consumer found (orphan in vendor too) |
| display_gpu_gate | K230_DISPLAY_GPU_GATE | 0x74/6 | - | disp_gpu (0x74/6) | 0 | yes (rw gate bit exists) | gpu@90800000 (verisilicon,gc8000ul / vglite 2.5D GPU -- NOT the VO pixel pipe) |
| display_dpip_gate | K230_DISPLAY_DPIP_GATE | 0x74/2 | - | dpipclk (0x74/2) | 0 | yes (rw gate bit exists) | no DT consumer found (orphan in vendor too) |
| display_cfg_gate | K230_DISPLAY_CFG_GATE | 0x74/4 | - | disp_cfgclk (0x74/4) | 0 | yes (rw gate bit exists) | no DT consumer found (orphan in vendor too) |
| vpu_src_gate | K230_VPU_SRC_GATE | 0xC/0 | - | vpu_src (0xC/0) | 0 | yes (rw gate bit exists) | vpu@0x90400000 (canaan,vpu) |
| vpu_axi_gate | K230_VPU_AXI_GATE | 0xC/5 | - | vpu_aclk (0xc/5) | 0 | yes (rw gate bit exists) | no DT consumer found (orphan in vendor too) |
| vpu_ddrcp2_gate | K230_VPU_DDRCP2_GATE | 0x60/5 | - | vpu_ddrcp2 (0x60/5) | 0 | yes (rw gate bit exists) | no DT consumer found (orphan in vendor too) |
| vpu_cfg_gate | K230_VPU_CFG_GATE | 0xC/10 | - | vpu_cfg (0xC/10) | 0 | yes (rw gate bit exists) | no DT consumer found (orphan in vendor too) |
| sec_apb_gate | K230_SEC_APB_GATE | 0x80/0 | - | sec_pclk (0x80/0) | 0 | yes (rw gate bit exists) | no DT consumer found (orphan in vendor too) |
| sec_fix_gate | K230_SEC_FIX_GATE | 0x80/5 | - | sec_fixclk (0x80/5) | 0 | yes (rw gate bit exists) | no DT consumer found (orphan in vendor too) |
| sec_axi_gate | K230_SEC_AXI_GATE | 0x80/4 | - | sec_aclk_gate (0x80/4) | 0 | yes (rw gate bit exists) | no DT consumer found (orphan in vendor too) |
| usb_480m_gate | K230_USB_480M_GATE | 0x100/0 | - | usb_clk480, usb_clk100 (0x100/0) | 0 | yes (rw gate bit exists) | no DT consumer found (orphan in vendor too) |
| usb_100m_gate | K230_USB_100M_GATE | 0x100/0 | - | usb_clk480, usb_clk100 (0x100/0) | 0 | yes (rw gate bit exists) | no DT consumer found (orphan in vendor too) |
| dphy_dft_gate | K230_DPHY_DFT_GATE | 0x100/0 | - | usb_clk480, usb_clk100 (0x100/0) | 0 | yes (rw gate bit exists) | no DT consumer found (orphan in vendor too) |
| spi2axi_gate | K230_SPI2AXI_GATE | 0x108/0 | - | spi2axi_aclk (0x108/0) | 0 | yes (rw gate bit exists) | no DT consumer found (orphan in vendor too) |
| ai_src_gate | K230_AI_SRC_GATE | 0x8/0 | IGNORE_UNUSED | **NONE FOUND** (-) | - | n/a (no vendor node at this reg/bit) | - |
| ai_axi_gate | K230_AI_AXI_GATE | 0x8/10 | - | **NONE FOUND** (-) | - | n/a (no vendor node at this reg/bit) | - |
| camera0_gate | K230_CAMERA0_GATE | 0x6C/0 | IGNORE_UNUSED | **NONE FOUND** (-) | - | n/a (no vendor node at this reg/bit) | - |
| camera1_gate | K230_CAMERA1_GATE | 0x6C/1 | IGNORE_UNUSED | **NONE FOUND** (-) | - | n/a (no vendor node at this reg/bit) | - |
| camera2_gate | K230_CAMERA2_GATE | 0x6C/2 | IGNORE_UNUSED | **NONE FOUND** (-) | - | n/a (no vendor node at this reg/bit) | - |
| pmu_apb_gate | K230_PMU_APB_GATE | 0x10/0 | - | pmu_pclk (0x10/0) | 0 | yes (rw gate bit exists) | no DT consumer found (orphan in vendor too) |
| hs_sd_timer_src_gate | K230_HS_SD_TIMER_SRC_GATE | 0x18/12 | - | sd_tmclk_src (0x18/12) | 0 | yes (rw gate bit exists) | no DT consumer found (orphan in vendor too) |
| ls_gpio_debounce_gate | K230_LS_GPIO_DEBOUNCE_GATE | 0x24/27 | - | gpio_dbclk (0x24/27) | 0 | yes (rw gate bit exists) | no DT consumer found (orphan in vendor too) |
| sysctl_wdt0_gate | K230_SYSCTL_WDT0_GATE | 0x50/5 | - | wdt0 (0x50/5) | 0 | yes (rw gate bit exists) | no DT consumer found (orphan in vendor too) |
| sysctl_wdt1_gate | K230_SYSCTL_WDT1_GATE | 0x50/6 | - | wdt1 (0x50/6) | 0 | yes (rw gate bit exists) | watchdog1@91106800 |
| display_ref_gate | K230_DISPLAY_REF_GATE | 0x74/3 | - | disp_refclk_gate (0x74/3) | 0 | yes (rw gate bit exists) | no DT consumer found (orphan in vendor too) |

## Vendor gate-capable composite nodes with NO mainline gate at the same reg+bit

| vendor node | reg/bit | read-only | DT consumer | notes |
|---|---|---|---|---|
| disp_clkext | 0x74/5 | 0 | no DT consumer found | mainline's `display_clkext_rate` (K230_DISPLAY_CLKEXT_RATE) is parented straight off `pll0_div3.hw` with **no gate at all** -- mainline never defines any clk for 0x74 bit 5. This DISPLAY-register bit is completely unmanaged in mainline (left exactly as the bootloader set it). |
| dphy_test_clk | 0x104/0 | 0 | no DT consumer found | mainline's `dphy_dft_gate` (K230_DPHY_DFT_GATE) is wired to reg 0x100 bit 0 instead of the correct 0x104 bit 0 -- see mislabeled-gate finding below. mainline's own `dphy_dft_rate` divider register (0x104) is correct, only the GATE register/bit is wrong. |

## Mainline gates with NO vendor composite node at the same reg+bit (no vendor ground truth)

| mainline name | ID | reg/bit | likely reason |
|---|---|---|---|
| cpu1_src_gate | K230_CPU1_SRC_GATE | 0x4/0 | vendor `k230_clock_provider.dtsi` in this source drop has no CPU1 clock tree at all (cpu0 only) -- either a single-core snapshot or CPU1 clocks live in a file not present here. |
| cpu1_plic_gate | K230_CPU1_PLIC_GATE | 0x4/15 | vendor `k230_clock_provider.dtsi` in this source drop has no CPU1 clock tree at all (cpu0 only) -- either a single-core snapshot or CPU1 clocks live in a file not present here. |
| cpu1_apb_gate | K230_CPU1_APB_GATE | 0x4/19 | vendor `k230_clock_provider.dtsi` in this source drop has no CPU1 clock tree at all (cpu0 only) -- either a single-core snapshot or CPU1 clocks live in a file not present here. |
| ai_src_gate | K230_AI_SRC_GATE | 0x8/0 | vendor tree has no AI/KPU clock tree node at all under this compatible string. |
| ai_axi_gate | K230_AI_AXI_GATE | 0x8/10 | vendor tree has no AI/KPU clock tree node at all under this compatible string. |
| camera0_gate | K230_CAMERA0_GATE | 0x6C/0 | vendor tree has no camera0/1/2 clock tree node at all under this compatible string. |
| camera1_gate | K230_CAMERA1_GATE | 0x6C/1 | vendor tree has no camera0/1/2 clock tree node at all under this compatible string. |
| camera2_gate | K230_CAMERA2_GATE | 0x6C/2 | vendor tree has no camera0/1/2 clock tree node at all under this compatible string. |
## Answers

### 1. Gates whose register offset/bit differs from the vendor tree (mislabeled gates)

**Confirmed bug: `dphy_dft_gate` (K230_DPHY_DFT_GATE).** Mainline wires its GATE to reg `0x100` bit `0`:

```c
K230_CLK_GATE_FORMAT(dphy_dft_gate, K230_DPHY_DFT_GATE, 0x100, 0, 0, 0, &pll0.hw);
```

That is the **exact same reg+bit as `usb_480m_gate` and `usb_100m_gate`**. The vendor's `dphy_test_clk` node gates at reg `0x104` bit `0` instead -- a different register entirely. Mainline's own rate divider for this clock (`dphy_dft_rate`) correctly uses `0x104` for its divider field, so only the GATE half of the definition is wrong; someone copy-pasted the `usb_100m_gate`/`usb_480m_gate` block and forgot to repoint the gate register to `0x104`. Practical effect: toggling mainline's `dphy_dft_gate` actually toggles the shared USB-480M/100M test-clock enable bit, while the real D-PHY test/DFT clock enable at `0x104` bit 0 is never touched by anything in the mainline driver -- it is an orphan bit, left exactly as the bootloader set it. This is a real, fixable driver bug independent of the display-blanking investigation, but it's not purely cosmetic: it means holding `dphy_dft_gate` "open" (as in the already-tried DDRC+SHRM+VPU_CFG+AI_AXI+DPHY_DFT combination) has *zero* effect on the real `0x104` bit, and silently duplicates whatever `usb_480m_gate`/`usb_100m_gate` already do to `0x100` bit 0.

**Structural gap, not a mislabeling, but display-relevant: `K230_DISPLAY_CLKEXT_RATE`.** The vendor's `disp_clkext` composite node (comment: "display clkext DIV & GATE") gates at reg `0x74` bit `5`, parented from `pll0_div3` (the same PLL tap that also feeds `disp_gpu`/display_gpu at bit 6 of the same register). Mainline has **no gate at all** for this: `display_clkext_rate` is wired straight to `&pll0_div3.hw` with no intervening `K230_CLK_GATE_FORMAT`, and there is no `K230_DISPLAY_CLKEXT_GATE` ID in `canaan,k230-clk.h` at all. So bit 5 of the DISPLAY control register (`0x74`) -- sitting between `display_dpip_gate` (bit 2) and `display_gpu_gate` (bit 6), inside the same register as the already-held `display_ahb/axi/dpip/cfg/ref` gates -- is completely unmanaged by the mainline clk driver. It is whatever the bootloader left it as, and the "already held" display gates do not cover it.

No other reg/bit mismatches were found; every other matched pair lines up exactly (see full table). `usb_480m_gate`/`usb_100m_gate` sharing `0x100` bit 0 is **not** a mainline bug -- the vendor DT does the same thing (`usb_clk480`/`usb_clk100` both gate at `0x100`/`0`), so that's an inherited vendor quirk (shared USB PHY test-clock enable), faithfully copied.

### 2. Gates plausibly on the VO memory-fetch path (0x90840000 reading DDR over AXI)

Working backwards from the vendor DT and driver:

- **No DT consumer anywhere ties any of the "remaining 34" gates (USB ref/480m/100m, hs_sd0_*, ls_* audio/codec/adc/i2c/jamlink/pdm/pwm/gpio_debounce) to the display subsystem.** The vendor's own `vo@90840000` and `dsi@90850000` nodes carry **no `clocks` property at all** -- power for the DISP domain is handled purely by `sysctl_power`'s `K230_PM_DOMAIN_DISP` bit-banger (`drivers/soc/canaan/k230-power-domains.c`), not by clk consumers. `disp_gpu` is the only display-register clock with any consumer, and it feeds the `gc8000ul` 2.5D GPU (`vglite`), not the VO pixel pipe. `ls_pwm_apb_gate`/`pwm_pclk_gate` feeds `pwm0`/`pwm1`, but none of the vendor reference LCD boards (`k230-canmv-lcd.dts`, `-lckfb-lcd.dts`, `-v3-lcd.dts`, `-01studio-lcd.dts`) wire backlight to PWM -- they all use a plain `backlight_gpio-gpios` GPIO line instead. `jamlink*` has zero consumers anywhere in this tree (camera serial link, unrelated to VO). So the "ls_pwm for backlight" and "jamlink" hypotheses are **not supported** by this vendor source drop.
- **The two concrete register bugs above are the most display-register-proximate candidates and worth testing first**, in this order:
  1. Hold the real `0x74` bit 5 (vendor's `disp_clkext`) open -- mainline has no clk node for it, so this requires a direct register poke/new clk entry, not an existing gate name. This is the one bit in the DISPLAY control register that is provably never touched by mainline, sitting right next to the bits that already are held.
  2. Hold `0x104` bit 0 (the real D-PHY DFT/test clock) open directly -- separately from `dphy_dft_gate`, which (per the bug above) never reaches it.
- Beyond those two, nothing in the vendor DT/driver gives a principled reason to expect any single gate among USB/SD0/LS-peripheral clocks to sit on the VO-DDR path. A more likely explanation for "all 68 works, two ~half-sized subsets don't" is a **shared-register/interconnect side effect** rather than one functionally-wired clock: every vendor composite clock (including PLLs) has `clk_hw.init.flags = CLK_IS_BASIC` only -- never `CLK_IGNORE_UNUSED`/`CLK_IS_CRITICAL` -- and almost none of the ~150 composite nodes have a DT consumer (see table). The vendor VO/DSI drivers do no clk management whatsoever. That means, read literally, even the vendor kernel's generic `clk_disable_unused()` should prune nearly everything including the display pipeline; it evidently doesn't in practice, which means something outside this source tree (U-Boot/SPL bootargs, or BootROM/firmware register state) is what's actually keeping the real hardware alive. If so, "holding all 68" may simply be the easiest way from Linux to reproduce that unknown external state, without any one gate in the list being individually load-bearing for display.

### 3. Gates the vendor DT marks read-only, or that the vendor driver never registers

- **Read-only:** none. Every node checked across the ~150-entry `k230_clock_provider.dtsi` (PLLs, composites, fixed-factor) has `read-only = <0>` and `status = "okay"`. The vendor driver's `read-only`/`composite_read_only` machinery exists in code (`k230_clk_composite_{enable,disable,set_rate}` all check it and refuse with `pr_err("...is read-only!")` if set) but is never actually invoked by any shipped `.dtsi` value in this tree.
- **Never registered by the vendor driver:** `cpu1_src/plic/apb_gate` (reg `0x4`), `ai_src/ai_axi_gate` (reg `0x8`), and `camera0/1/2_gate` (reg `0x6C`) have **no corresponding `canaan,k230-clk-composite` node anywhere** in `k230_clock_provider.dtsi` -- mainline added clk support for these with no vendor ground truth to validate the reg/bit choices against in this source drop. Either this vendor tree snapshot is for a configuration without a second CPU/AI/camera clock domain, or those trees live in a file not present here; either way, mainline's reg/bit values for those IDs cannot be cross-checked.
