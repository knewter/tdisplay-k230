## Context

See proposal.md — Why. What shapes the approach:

- `../truck` solves this already with `scripts/render-specs.py` and a
  `task spec-site` target rendering into `public/`. It is 742 lines and imports
  a journey atlas, a design review gallery, a product story workbench and
  marketing research — all Dozer concerns. It also carries measured budgets
  (`MAX_CLEAN_GENERATION_SECONDS = 8.0`, a size ceiling raised deliberately
  once) that are worth copying as a habit.
- This project has six capability groups and will have on the order of fifteen
  capabilities. That is a different problem from truck's eighty-one.
- The verification conventions are prose conventions, established in
  `.skills/k230-spec-change/SKILL.md`, not structured data. Anything reading
  them is coupled to them.

## Goals / Non-Goals

**Goals:**

- A reader learns what is unproven before anything else.
- Evidence is one click from the requirement it grounds.
- The renderer is small enough to read in one sitting.

**Non-Goals:**

- Feature parity with truck's renderer.
- Publishing or hosting.
- Search, or navigation beyond a capability index.

## Decisions

**Write a small renderer here rather than porting truck's.** Truck's is
coupled to five Dozer-specific modules and would arrive mostly as dead code.
Copying its *habits* — budgets enforced in the build, per-capability pages,
`UNVERIFIED` surfaced as a first-class thing — is the valuable part. Revisit
if this one grows past a few hundred lines.

**Parse the conventions, and fail when they do not parse.** The alternative,
treating an unrecognised requirement as grounded, was rejected: the unverified
count is the site's entire product, and a count that silently under-reports is
worse than no site. Failing loudly also makes the coupling to the skill
document visible the moment someone changes the convention.

**Validate evidence links at build time.** A dead link to a boot log is a
requirement claiming grounding it does not have. That is exactly the error
this project is trying not to make, so the build refuses it.

**Render `specs/` only.** Publishing `changes/` would put proposals in front
of readers as though they were decided. Truck makes the same split.

**Budgets from the first commit, set above current output.** Truck's history
shows the alternative: a budget set at what the tree happened to produce goes
red on ordinary growth and gets raised reflexively until it means nothing.

## Risks / Trade-offs

- **The renderer's convention parsing drifts from the skill document.** →
  Failing loudly rather than defaulting turns the drift into a build error on
  the next run instead of a quietly wrong number.
- **`UNVERIFIED` markers are added faster than they are resolved, and the
  landing page becomes noise.** → Accepted. A large honest number is the
  correct output for a project at this stage, and hiding it would defeat the
  purpose.
- **Nobody reads it.** → Possible. Mitigated by making the build trivially
  runnable on a laptop, so it can serve one reader — the person who wrote the
  specs and has forgotten what is proven.

## Open Questions

- Whether to render evidence files themselves into the site or link to them in
  the repository. Links are simpler and sufficient to start; the answer does
  not change the specs or the approach.
