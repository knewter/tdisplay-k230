## Purpose

Defines how a person reaches a prompt on the physical board.

## ADDED Requirements

### Requirement: The board presents a console over the CH342 bridge

The board SHALL present its console on the CH342 USB-UART bridge, on the
charging USB-C port, at 115200 8N1 with no flow control.

*Grounding: observed on this board. The bridge enumerates as `1a86:55d2`
"USB Dual_Serial" and is handled by the in-kernel `cdc-acm` driver with no
vendor driver installed, giving `/dev/ttyACM0` (CH342 channel 0, K230 UART0)
and `/dev/ttyACM1` (channel 1, UART3). `docs/rtsmart-boot-log.txt` was captured
this way.*

No vendor driver SHALL be required on the host. The CH342 is CDC-ACM
compliant, and installing WCH's `ch343ser` driver would displace `cdc-acm`
rather than help.

#### Scenario: The board is connected to a host

- **WHEN** the board is connected with a USB-C data cable and powered on
- **THEN** two CDC-ACM ports appear, and the system's console is reachable on the first at 115200 8N1

### Requirement: A cable fault is distinguishable from a dead board

The project SHALL record how a cable fault presents, because on this hardware
it is indistinguishable from failure by eye — the charge LED lights either way.

*Grounding: observed. A charge-only cable produces no kernel USB events
whatsoever. A marginal cable produces `device descriptor read/64, error -71`
followed by `unable to enumerate USB device`. A working cable enumerates
`1a86:55d2` cleanly.*

#### Scenario: The board does not appear on the host

- **WHEN** no console device appears
- **THEN** the documented procedure distinguishes a charge-only cable, a marginal cable, and a board that is not running, by what the kernel log shows
