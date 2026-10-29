## ADDED Requirements

### Requirement: A file opens in its default app and another app can be chosen

*Grounding (2026-10-28, board, injected): opening `open-test.png` and the PDF from Files started Viewnior and Zathura, and Open With listed the alternative handler (`docs/evidence/open-with/board/README.md`). On glass, 2026-10-29, build `ql630glm…`, the operator opened a photo and a PDF and switched handler once: "it all worked" (`docs/evidence/glass-checklist-2026-10-29/operator-report.md`).*
*Grounding: `nix/shell.nix` sets MIME defaults only for `text/plain`, `text/markdown` and `text/x-markdown`, and records that no `xdg-desktop-portal` runs on the image; `nix/handheld-desktop-entries.nix` gives Viewnior the image types and both file managers `inode/directory`. Source read at cff47b1e.*

The system SHALL ship a default application, from the image and not from a person's home directory, for images, PDF documents, folders and plain text. Opening a file of one of those types from Files, or with `xdg-open`, SHALL start that application on that file. Where a second installed application declares the file's type, Files SHALL offer it through its Open With dialog, and choosing it SHALL open the file in that application for that one open. A person's own association SHALL take precedence over the image's. The system SHALL NOT run a desktop portal to do this.

#### Scenario: A photo opens in the image viewer

- **WHEN** a person taps a PNG in Files
- **THEN** Viewnior opens that image

#### Scenario: A folder opens in Files

- **WHEN** a person taps a folder in Files, or `xdg-open` is given a folder
- **THEN** the one Files entry opens it, not the hidden Portfolio

#### Scenario: A fresh home still has defaults

- **WHEN** the shell user's home directory has no `mimeapps.list`
- **THEN** a PDF opens in Zathura

#### Scenario: Another app is chosen

- **WHEN** a person opens the Open With dialog for a file that two installed apps can open and picks the second
- **THEN** the file opens in the second app and the default is unchanged

#### Scenario: No handler

- **WHEN** a person opens a file whose type no installed app declares
- **THEN** no app starts and Files stays in front, with the dialog listing no application for it
