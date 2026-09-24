import data from "../data/specs.json";

export type Status = "grounded" | "unverified" | "undeclared";

export interface Tally {
  grounded: number;
  unverified: number;
  undeclared: number;
}

export interface Evidence {
  path: string;
  slug: string;
  href: string;
}

export interface Requirement {
  name: string;
  slug: string;
  status: Status;
  reason: string;
  proseHtml: string;
  evidence: Evidence[];
  scenarios: { title: string; bodyHtml: string }[];
}

export interface Capability {
  group: string;
  name: string;
  slug: string;
  ident: string;
  source: string;
  blurb: string;
  purposeHtml: string;
  purposeFirst: string;
  tally: Tally;
  requirements: Requirement[];
}

export interface EvidenceFile {
  path: string;
  slug: string;
  name: string;
  bytes: number;
  kind: "text" | "image" | "video";
  text?: string;
  asset?: string;
  mediaUrl?: string;
  /**
   * Whether a requirement in the ledger rests on this file, or only a
   * hand-authored note. The distinction is the site's whole subject and is
   * never collapsed: a note's evidence is real, and it is still not a
   * requirement anyone has archived.
   */
  citedBy: "requirement" | "note";
}

export interface Specs {
  sourceRevision: string;
  generated: string;
  tally: Tally;
  total: number;
  groups: { name: string; blurb: string; slugs: string[] }[];
  capabilities: Capability[];
  evidence: EvidenceFile[];
  defects: { kind: string; source: string; requirement: string; detail: string }[];
}

export const specs = data as unknown as Specs;

export const STATUS_ORDER: Status[] = ["grounded", "unverified", "undeclared"];

export const STATUS_LABEL: Record<Status, string> = {
  grounded: "grounded",
  unverified: "unverified",
  undeclared: "no status declared",
};

/** The data pass does not know where the site is served from. */
export function resolveBase(html: string): string {
  return html.replaceAll("@@BASE@@", import.meta.env.BASE_URL);
}

export function url(path: string): string {
  const base = import.meta.env.BASE_URL;
  return base.endsWith("/") ? base + path : `${base}/${path}`;
}

export function kib(bytes: number): string {
  return `${(bytes / 1024).toFixed(1)} KiB`;
}

export function unproven(t: Tally): number {
  return t.unverified + t.undeclared;
}

export function total(t: Tally): number {
  return t.grounded + t.unverified + t.undeclared;
}

/** The evidence entry for a committed path, or a build-time failure.
 *
 * `scripts/render_specs.py` renders every `docs/...` path it finds in this
 * directory's `.astro` sources, so a path spelled here is a path that got a
 * page -- unless it is misspelled or the file is gone, and then the build
 * says so rather than emitting a dead link.
 */
export function evidenceFile(path: string): EvidenceFile {
  const hit = specs.evidence.find((e) => e.path === path);
  if (!hit) {
    throw new Error(
      `${path} is cited by a hand-authored page but was not rendered. ` +
        `Check the spelling, and that the file is committed.`,
    );
  }
  return hit;
}

/** The page rendering a committed evidence file. */
export function evidenceUrl(path: string): string {
  return url(`evidence/${evidenceFile(path).slug}/`);
}

/** The copied image for a committed photograph. */
export function evidenceAsset(path: string): string {
  const file = evidenceFile(path);
  if (file.kind !== "image" || !file.asset) {
    throw new Error(`${path} is not an image; it has no asset to show.`);
  }
  return url(file.asset);
}

/** Evidence files of one kind of citation, in path order. */
export function evidenceCitedBy(by: "requirement" | "note"): EvidenceFile[] {
  return specs.evidence.filter((e) => e.citedBy === by);
}
