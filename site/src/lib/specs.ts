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
  kind: "text" | "image";
  text?: string;
  asset?: string;
}

export interface Specs {
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
