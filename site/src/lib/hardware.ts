/** The hand-authored hardware notes.
 *
 * These pages are NOT produced by `scripts/render_specs.py`. They are written
 * and maintained by hand under `site/src/pages/hardware/`, and the repository
 * is their only home -- they began as published Claude artifacts and were
 * ported here so that a correction lands in one place. Where a note and the
 * repository disagree, the repository wins; where something is still
 * unverified, the page says so.
 *
 * This list is the single source of truth for the set: the landing page and
 * the cross-links at the foot of each note both read it, and both group it by
 * `kind`. That split is the honest one on this project -- a note written from
 * a console transcript carries a different weight from a note written from a
 * device tree, and the reader should not have to guess which they are holding.
 */

export type NoteKind = "observed" | "read";

export interface HardwareNote {
  slug: string;
  title: string;
  /** Where the note's facts came from. Drives the grouping. */
  kind: NoteKind;
  /** One line, used on the ledger and in the cross-links. */
  blurb: string;
}

export const NOTE_GROUPS: { kind: NoteKind; name: string; blurb: string }[] = [
  {
    kind: "observed",
    name: "Observed on the board",
    blurb:
      "Written from console transcripts. The board did these things and they were captured.",
  },
  {
    kind: "read",
    name: "Read out of the files",
    blurb:
      "Written from the device trees, the schematic and the vendor BSP. Correct descriptions of source, which is not the same as working hardware.",
  },
];

export const HARDWARE_NOTES: HardwareNote[] = [
  {
    slug: "first-boot",
    title: "First boot",
    kind: "observed",
    blurb:
      "2026-09-20: NixOS reached a root shell on the silicon. The transcript, what each line proves, and why Linux gets exactly one hart.",
  },
  {
    slug: "boot-chain",
    title: "Boot chain",
    kind: "observed",
    blurb:
      "Our DTB carried the right kernel command line and U-Boot threw it away. One `if` in the vendor source, and the two-line fix that beat it.",
  },
  {
    slug: "thermal",
    title: "Thermal",
    kind: "read",
    blurb:
      "The temperature is readable and nothing acts on it. A tripless zone, no thermal-zones node, no cpufreq driver — a characterised gap with four ordered steps out of it.",
  },
  {
    slug: "silicon-map",
    title: "Silicon map",
    kind: "read",
    blurb:
      "Every subsystem on the board traced to the device-tree node that turns it on, and where the CanMV v3 reference describes a board that is not ours.",
  },
  {
    slug: "overlay-anatomy",
    title: "Overlay anatomy",
    kind: "read",
    blurb:
      "What k230.dtsi declares, how a board file reaches back into it by label, and the seven kinds of edit a board file is capable of making.",
  },
  {
    slug: "panel-contract",
    title: "Panel contract",
    kind: "read",
    blurb:
      "Property by property, what panel-canaan-universal reads out of a .dtsi — and the 20-command init sequence the RM69A10 needs.",
  },
];

/** The notes of one kind, in list order. */
export function notesOfKind(kind: NoteKind): HardwareNote[] {
  return HARDWARE_NOTES.filter((n) => n.kind === kind);
}
