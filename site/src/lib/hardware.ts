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
 * the cross-links at the foot of each note both read it.
 */

export interface HardwareNote {
  slug: string;
  title: string;
  /** One line, used on the ledger and in the cross-links. */
  blurb: string;
}

export const HARDWARE_NOTES: HardwareNote[] = [
  {
    slug: "silicon-map",
    title: "Silicon map",
    blurb:
      "Every subsystem on the board traced to the device-tree node that turns it on, and where the CanMV v3 reference describes a board that is not ours.",
  },
  {
    slug: "overlay-anatomy",
    title: "Overlay anatomy",
    blurb:
      "What k230.dtsi declares, how a board file reaches back into it by label, and the seven kinds of edit a board file is capable of making.",
  },
  {
    slug: "panel-contract",
    title: "Panel contract",
    blurb:
      "Property by property, what panel-canaan-universal reads out of a .dtsi -- and the 20-command init sequence the RM69A10 needs.",
  },
];
