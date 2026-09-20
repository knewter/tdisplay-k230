# Tasks

This change needs no hardware. Every command below runs on the build host.

## 1. Read the specs

- [ ] 1.1 Parse `openspec/specs/` into capabilities and requirements, classifying each as grounded or unverified, and failing on any requirement that cannot be classified. Verify with a unit test covering a grounded requirement, an `UNVERIFIED` one, and one that is neither — asserting the third raises
- [ ] 1.2 Extract `docs/evidence/` citations from requirement prose and check each path exists, failing with the requirement name and the missing path. Verify with a unit test for a present path and an absent one

## 2. Render

- [ ] 2.1 Render one page per capability, showing each requirement's status and its reason where unverified. Verify by running the renderer over the current tree and confirming a page exists for every `openspec/specs/**/spec.md`
- [ ] 2.2 Render a landing page stating the unverified count before any capability prose. Verify by asserting in a test that the count appears before the first capability heading in the generated HTML
- [ ] 2.3 Turn evidence citations into working links. Verify by generating the site and confirming every `docs/evidence/` link resolves to a committed file
- [ ] 2.4 Confirm nothing from `openspec/changes/` appears in the output. Verify with a test that greps the generated tree for the id of an in-flight change and expects no match

## 3. Budgets

- [ ] 3.1 Measure generation time and output size on the current tree, and set budgets above both with the measured values recorded. Verify by committing the measurements alongside the budgets and noting the date and machine
- [ ] 3.2 Fail the build when either budget is exceeded, reporting measured against budget. Verify with a test that forces a breach and asserts the failure names both numbers

## 4. Make it runnable

- [ ] 4.1 Add `markdown` to the development shell and expose the renderer as one command. Verify by running it from a clean shell with no network
- [ ] 4.2 Gitignore the output directory and document the command in `README.md`. Verify with `git status` clean after a build, and by following the README's instruction from scratch
- [ ] 4.3 Resolve the `UNVERIFIED` markers in `docs/spec-site` against the working renderer. Verify with `openspec validate --all`
