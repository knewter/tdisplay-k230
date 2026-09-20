## Purpose

Names every opaque binary this project ships, executes during a build, or is
one configuration line away from pulling in — with what it is, what would
remove it, and what it says about the next board — so that a blob we keep is
one we chose rather than one nobody noticed.

## ADDED Requirements

### Requirement: Every opaque binary this project depends on is listed before it ships

The project SHALL maintain a single inventory naming every binary it ships,
executes during a build, or would acquire by enabling a vendor package that
its chosen board configuration already sets. Each entry SHALL carry the
binary's sha256, its size, and where it came from. The inventory SHALL cover
binaries that are *not* on the current path as well as those that are, marked
as such, because the cost of a blob is paid when someone enables it rather
than when it is written down.

*Grounding: `docs/blob-inventory.md` is that inventory. It records 33 entries
covering roughly 330 individual files: three committed under
`firmware/stage1/`, two byte ranges embedded inside one of those, 121 in the
Kendryte Linux SDK, about 203 in the LilyGO RT-Smart clone, one downloaded
toolchain, and the BootROM. Every sha256 in it was computed from the tree
`firmware/stage1/PROVENANCE.txt` describes.*

#### Scenario: Someone asks what unauditable code this board runs

- **WHEN** a reader wants to know what on this device they cannot read the source of
- **THEN** one document answers it, by name and by hash, and says which entries are on the live boot path and which are dormant in a vendor checkout

#### Scenario: A vendor package is enabled that was previously off

- **WHEN** a defconfig line turns on a package that carries firmware images
- **THEN** those images are already described in the inventory, so enabling them is a decision rather than a discovery

### Requirement: A binary that is not in the inventory fails the build

The build SHALL refuse to complete when a binary file exists in the tree, or
in a vendor checkout the scan is pointed at, that the inventory does not
account for. The check SHALL be "every binary is accounted for", not "there
are no binaries" — an entry may record that a blob is permanent and that is a
passing state.

<!-- UNVERIFIED: tools/blob-scan.py does not exist yet. Grounded once it is
committed and docs/evidence/blob-scan.txt records a run that both passes on
the current tree and fails on a planted unlisted binary. -->

#### Scenario: A new firmware file appears in the tree

- **WHEN** someone adds or vendors a binary without adding it to the inventory
- **THEN** the build fails and names the file, rather than the binary entering the project silently

#### Scenario: A listed blob changes content

- **WHEN** a blob's bytes change but its inventory entry does not
- **THEN** the recorded sha256 no longer matches and the build fails, so a swapped vendor artifact cannot pass unnoticed

### Requirement: Each listed binary records what would remove it and what it says about the next board

Every inventory entry SHALL name the concrete event that would make the binary
unnecessary — an upstream publishing source, a driver reaching mainline, a
different boot mode, or "none, this is work rather than waiting" — so that a
future reader can check whether it has happened without re-deriving the
analysis. Every entry SHALL also say whether the binary is a property of the
silicon, of this vendor's process, of this board's parts, or near-universal
across modern systems-on-chip.

*Grounding: `docs/blob-inventory.md` carries both for each entry, and section
F distils them into the questions worth asking before buying hardware. The
distinction it draws is load-bearing: the DDR PMU training firmware is marked
industry-wide and permanent, while being made to execute a renamed GNU gzip to
produce a bootable image is marked as this vendor's choice and removable
today.*

#### Scenario: Someone revisits the inventory two years later

- **WHEN** a reader asks whether a blob can be dropped yet
- **THEN** the entry names the specific thing to check, rather than requiring the original investigation to be repeated

#### Scenario: Someone is choosing the next board

- **WHEN** a reader asks which of these problems follow the chip and which follow the vendor
- **THEN** each entry says which, and the inventory ends with the checks that separate them

### Requirement: The inventory is published with the specs

The inventory SHALL be reachable from the specification site rather than only
from the repository, because the people most affected by what a device runs
are the least likely to clone it.

*Grounding: `scripts/render_specs.py` copies any `docs/` path cited from a
`*Grounding:*` line into the site and serves it at `/evidence/<slug>/`, and
`scripts/build_site.py` fails when a cited evidence file is missing. Citing
`docs/blob-inventory.md` from a requirement therefore publishes it and keeps
it published, with no new rendering code.*

#### Scenario: The inventory is deleted or renamed

- **WHEN** the file a requirement cites is no longer there
- **THEN** `./scripts/build_site.py` fails rather than publishing a site that silently drops it
