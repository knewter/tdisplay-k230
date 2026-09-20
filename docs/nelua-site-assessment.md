# Replacing the spec site's renderer with Nelua

An effort assessment, not an implementation. Written 2026-09-20 against
`openspec/specs/docs/spec-site/spec.md` as the requirements baseline.

**Bottom line up front.** 8–15 focused days for the full replacement, at
medium-low confidence, to arrive at something functionally identical to and
operationally worse than what exists. The single biggest blocker is not
Markdown: it is that Nelua's standard library **cannot list a directory or
create one**, and the site's first requirement is to walk
`openspec/specs/**/spec.md`. The recommendation is a scoped middle path —
port only the parser, keep the JSON seam that already exists — at 3–5 days,
with a clean revert.

---

## 0. What is actually being replaced

The premise in the question ("replace the Astro static site") is slightly off,
and the correction matters a great deal to the estimate.

The site is **already two programs with a data seam between them**:

| Piece | What it is | Size |
| --- | --- | --- |
| `scripts/render_specs.py` | Parses `openspec/specs/**/spec.md`, classifies every requirement, resolves evidence citations, enforces budgets, emits `site/src/data/specs.json` | 728 lines, CPython stdlib only |
| `site/src/data/specs.json` | The seam | 19.5 KB |
| `site/src/**` | Astro reads the JSON and renders HTML | 1,069 lines, of which **547 are CSS** |
| `tests/test_render_specs.py` | Contract tests over the parser | 314 lines |

Output today: 84 KB `dist/`, parser runs in 0.017 s over a staged tree of every
capability the open proposals will add (`docs/evidence/spec-site-build.txt`).

Three consequences:

1. **The "middle path" the question asks about is already the architecture.**
   "Nelua for the spec parser emitting JSON, with something else rendering" is
   the shape of the system right now, with Python in the Nelua slot. That makes
   the Nelua experiment far cheaper and far safer than a from-scratch SSG.
2. **Half the Astro side is CSS**, which is language-independent and carries
   over unchanged to any renderer. Any estimate that counts those 547 lines as
   work to redo is wrong.
3. **The parser already has an oracle.** Anything replacing it can be validated
   by diffing its `specs.json` against Python's, byte for byte. This is the best
   possible circumstance in which to write an alpha language.

---

## 1. What Nelua actually is today

Confirmed: statically typed, compiles to C, then invokes a C compiler (GCC,
Clang, or TCC) to produce native code. Lua 5.4 syntax and semantics, with types.
Optional garbage collector (`nogc` pragma disables it). MIT licensed. The killer
feature is the **preprocessor: a full Lua 5.4 interpreter running inside the
compiler at compile time**, with the complete Lua standard library, able to read
files, generate code, and — per the manual — "modify or inject code into the
compiler itself."

### Project health, bluntly

| Signal | Value |
| --- | --- |
| Stars | 2,424 |
| Forks / watchers | 89 / 53 |
| Open issues | 27 |
| First commit | 2017-10-28 |
| **Last push to master** | **2025-06-24** |
| **Tagged releases** | **Zero.** One rolling `latest` tag, created 2021-09-05, rebuilt per commit |
| Commit velocity (last 20 commits) | 2024-06-11 → 2025-06-24, i.e. ~1.5/month |
| Contributors | Effectively one: `edubart` |
| Stated status | README: "The language is in alpha state and still evolving" |
| nixpkgs | Present, as `nelua-0-unstable-2025-06-24` |

Read those together. Nine years old, never cut a version number, and as of today
**15 months since the last commit**. The nixpkgs version string —
`0-unstable-2025-06-24` — is the whole story in one token: there is no release
to pin, so the distro pins a date.

The last six commits, all on 2025-06-24, were a maintenance burst: Windows/Clang
fixes, a GCC-compat fix, CI bumps, and — notably —
`Fix string.gsub when replacing with functions, fixes #299`. That is a core
string operation, it was broken, it was fixed in the final burst of activity,
and nothing has been merged since. That cuts both ways: the maintainer does fix
real bugs, and you are about to depend on the state of the tree the moment he
stopped.

This is not abandonware — it's a well-made one-person project resting. But for a
dependency in a build whose *entire product* is a trustworthy number, "resting"
and "abandoned" are the same risk until proven otherwise. Which is, note, this
repository's own house rule applied to itself: a README claiming the language
works is a datasheet, not grounding.

### Who uses it

Games, almost exclusively. The curated `awesome-nelua` list is: raylib bindings,
an SDL2 game library (`nene`), a 2048 clone, a Tetris clone, a ray tracer, a
Celeste recreation, a Game of Life for Arduino, a profiler for raylib, a package
manager, a Sublime syntax file, and one WebSocket demo. No production users are
named anywhere. No text-processing, web, or tooling use to draw on.

That is a coherent niche and Nelua is genuinely good at it: a fast native game
loop with Lua ergonomics and no GC. It is precisely orthogonal to this job.

---

## 2. Ecosystem reality check

Asked directly, and answered directly.

| Need | Exists? | Detail |
| --- | --- | --- |
| Markdown parser | **No** | Nothing in stdlib, nothing in `awesome-nelua`, nothing in `nelua-decl` |
| Templating | **No** | Nothing. `stringbuilder` + `string.format` is the whole toolkit |
| HTML escaping | **No** | ~15 lines to write; the cost is that it must be right, and the site renders raw boot-log bytes |
| JSON | **No** | No encoder, no decoder |
| Date handling | **Yes** | `os.date`, `os.time`, `os.clock`, `os.now`, `os.difftime`, `timedesc` record |
| Test framework | **No** | `awesome-nelua` lists Lester, but Lester is a **Lua** framework written to test the Nelua *compiler* (which is itself Lua). It does not test Nelua programs |
| Pattern matching | **Yes** | Full Lua patterns: `find`, `match`, `gmatch`, `gsub`, `gsub` with a function callback |
| Containers | **Yes** | `vector`, `sequence`, `list`, `hashmap`, `span`, `stringbuilder` |
| **Directory listing** | **No** | See below |
| **Directory creation** | **No** | See below |
| Sorting | **No** | See below |

Three of those deserve expansion, because they are the ones that actually hurt.

### `os` has no `readdir` and no `mkdir`

The full `os` module is: `execute`, `exit`, `setenv`, `getenv`, `remove`,
`rename`, `setlocale`, `tmpname`, `date`, `clock`, `difftime`, `time`,
`realtime`, `now`, `sleep`. The full `io` module is `open`, `popen`, `close`,
`flush`, `input`, `output`, `tmpfile`, `read`, `write`, `writef`, `printf`,
`print`, `type`, `lines`.

There is no way to enumerate a directory and no way to create one. `lib/C/`
binds ctype, errno, locale, math, signal, stdarg, stdatomic, stdio, stdlib,
string, threads, time — C11 only, and C11 has neither `dirent.h` nor `mkdir`.

The spec's first requirement is *"generated from `openspec/specs/`"* — a tree
walk. The budget requirement is *"the output SHALL stay within a recorded size
budget"* — measuring a generated tree, another walk. Evidence copying writes
into nested output directories — `mkdir -p`. Three of five requirements touch
the one thing the stdlib cannot do.

This is not fatal. It is worth naming clearly because it sets the character of
the whole project: **the first thing you write in Nelua is not spec parsing, it
is filesystem plumbing that every other language in the running gives you for
free.**

### There is no `table.sort`, and the reason is instructive

`lib/table.nelua` exists. It is 21 lines. In its entirety it is a
`static_error 'tables are not implement yet'` followed by a commented-out list
of the functions it does not provide, `table.sort` among them. Requiring it is a
compile error by design.

The renderer sorts capabilities by a custom group rank (`GROUP_ORDER`) and sorts
requirements within them. You write your own sort, or bind C `qsort` and hand it
a function pointer. Fine, 40 lines — but it is a fair sample of what "alpha
standard library" means in practice.

### Lua patterns are not regex, and the gap lands exactly on the hard part

This is the most under-appreciated cost, so here is the actual code.
`scripts/render_specs.py` has this, and it is load-bearing for emphasis parsing:

```python
out = re.sub(r"(?<!\*)\*([^*]+?)\*(?!\*)", r"<em>\1</em>", out, flags=re.S)
```

Lua patterns have **no lookbehind, no lookahead, no alternation, no bounded
quantifiers, and no `\b`**. Every one of those appears in the current parser:

| Python | Lua patterns |
| --- | --- |
| `(?<!\*)...(?!\*)` (em vs. strong) | Impossible. Hand-roll a character scanner |
| `\*{0,2}Grounding\b` | No `{0,2}`, no `\b`. Branch manually |
| `\bdocs/[A-Za-z0-9_./@+-]*...` | No `\b`; `-` inside a class needs escaping and `-` is also the lazy quantifier |
| `re.split(r"\n\s*\n", ...)` | No split at all. Write it |
| `(.*?)` with `re.S` | `(.-)` works. This one is fine |
| `re.sub(pat, func, s)` | `gsub` with a function works — and was broken until the last commit ever merged |

The emphasis scanner alone is the difference between one line and eighty.

---

## 3. What you would have to write from scratch

Itemised, with rough sizes. "Nelua LOC" is new code; the Python column is what
it replaces, for calibration.

| # | Component | Python LOC | Nelua LOC | Notes |
| --- | --- | ---: | ---: | --- |
| 1 | Recursive directory walk | ~10 | 40–120 | `io.popen("find")`, or bind `dirent.h`, or compile-time Lua. See §4 |
| 2 | `mkdir -p` | ~1 | 20–40 | `os.execute`, or bind `sys/stat.h` |
| 3 | File copy incl. binary evidence | ~5 | 30 | No `shutil` |
| 4 | Split into requirements/scenarios/sections | ~40 | 120 | Mechanical; Lua patterns are pleasant here |
| 5 | Classifier (`UNVERIFIED` / `Grounding` / defect) | ~50 | 150 | The interesting part. Must fail loudly, per spec |
| 6 | Code-span masking + citation extraction | ~40 | 120 | `mask_code`, `code_spans`, `citations` |
| 7 | Inline Markdown (code, bold, em, autolink) | ~45 | 180–300 | **Hand-rolled emphasis scanner.** The single largest item |
| 8 | Block Markdown (paras, lists, Grounding callout) | ~35 | 120 | |
| 9 | HTML escaping | ~3 | 15 | Trivial, must be correct |
| 10 | Control-picture translation for boot-log bytes | ~8 | 30 | `utf8` module exists; encode U+2400–U+241F |
| 11 | Slugify / first-sentence / tally | ~30 | 80 | |
| 12 | Sort (custom group rank) | ~5 | 40 | No `table.sort` |
| 13 | Linker + evidence existence check | ~35 | 90 | |
| 14 | JSON emitter (if keeping the seam) | ~3 | 100 | No JSON library. Escaping is the whole job |
| 15 | Budget enforcement (time + output size) | ~25 | 60 | Time is easy; size needs the walk from #1 |
| 16 | Test harness | *(pytest)* | 60 | Assert-and-count `main`, no framework |
| 17 | Port the 314 lines of contract tests | 314 | 350–450 | Needs `mkdir` (#2) for staged trees |
| 18 | Templating layer + four page types | *(Astro, 522 LOC)* | 250–400 | **Only if replacing Astro too** |
| 19 | Nix packaging, flake integration, CI, re-capture evidence | — | ~80 + config | |
| | **Parser only (#1–17, 19)** | **1,042** | **~1,600–2,000** | |
| | **Parser + renderer (all)** | **1,564** | **~1,850–2,400** | 547 lines of CSS carry over unchanged |

Roughly a 2× line-count multiplier over Python for the same behaviour, which is
about what you would expect moving from a batteries-included scripting language
to a systems language with no batteries. The multiplier is not the problem; the
items with no library at all are.

---

## 4. The C escape hatch

Nelua's C interop is genuinely good, and this is the strongest argument in the
proposal's favour. The mechanism is three annotations —
`<cimport>` / `<cinclude>` / `linklib` — declared in a preprocessor block:

```lua
##[[ cinclude '<md4c.h>'; linklib 'md4c' ]]
```

`nelua-decl` is a binding generator (GCC plugin, Linux-only) with existing
bindings for SQLite3, curl, SDL2, raylib, blend2d, lexbor, MIR. So binding a C
library is a solved, demonstrated workflow, not an adventure.

### Does cmark or md4c make this tractable?

**md4c** is the better candidate: one `.c` and one `.h`, no dependencies, MIT,
SAX-style callback API, in nixpkgs. The binding is ~30–60 lines.
**cmark** gives you a walkable AST, which is nicer, but a CMake build with
generated headers.

And yet — **this helps much less than it looks like it should**, because the
renderer is not a CommonMark renderer. Look at what it actually does:

- Split on `### Requirement:` / `#### Scenario:`. CommonMark gives you headings,
  so this is a genuine win.
- Find `<!-- UNVERIFIED ... -->`. CommonMark treats HTML comments as raw HTML
  blocks or passes them through inline. You are post-processing regardless.
- Detect `*Grounding: ...*` — an emphasis-wrapped paragraph that must become a
  `<div class="grounding">` with the tag split out. Outside CommonMark
  semantics. Post-processing again.
- Rewrite bare `docs/…` paths and code spans into links **resolved against a
  linker that fails the build on a missing file**. Not a Markdown feature at all.
- Render NUL bytes from a serial capture as Unicode control pictures. Actively
  hostile to a parser that assumes valid text.

So md4c would hand you an event stream you then drive a stateful machine over —
across an FFI boundary, in an alpha language, with `MD_CHAR*` slices that are
**not NUL-terminated**, callback function pointers from C back into Nelua, and
GC interaction with C-held pointers. That machine is *harder* to write and much
harder to debug than the 90 lines of Python regex it replaces. You would be
trading a known-easy problem for an unknown-hard one to avoid writing an
emphasis scanner.

### What it costs

- The flake gains a C library dependency. This repo cross-builds RISC-V NixOS
  closures; it is entirely fluent in this. Not scary, but not free.
- The spec says rendering "SHALL be a single command that needs no network and
  no CI." Today that command needs CPython's stdlib and nothing else. After:
  a Nelua compiler, a C compiler, and md4c — all pinned in the flake, so the
  requirement still holds, but the floor under it is much thicker.

### Does it undermine the point?

Partly, and it is worth being honest about which part. If Markdown goes to md4c,
HTML escaping goes to a snippet, the directory walk goes to `dirent.h` or
`popen("find")`, and the ergonomic parts go to the compile-time Lua
preprocessor, then the Nelua you actually wrote is glue between C libraries.

More to the point: Nelua's reasons to exist — static types with Lua syntax, no
GC, zero-cost abstractions, native speed — are *all irrelevant here*. The
current build is **0.017 seconds over 20 KB of Markdown producing 78 KB of
output**. There is no performance problem to solve. Nelua's advantages sit
entirely off the critical path; its disadvantages sit entirely on it.

### The preprocessor trapdoor, which is the real finding

Nelua's preprocessor is Lua 5.4 with the full standard library, running at
compile time, and `nelua run foo.nelua` compiles on every invocation. So the
compile-time environment is available on every run.

Which means the path of least resistance for **every** blocker above is: do it
in the preprocessor. Directory walk? `io.popen` in Lua at compile time, emit a
static array of paths. Need a data structure Nelua lacks? Build it in Lua and
generate code. Need `table.sort`? Lua has it.

That works. It is also the trap: **follow it and you have written a Lua program
inside a Nelua file, with extra steps.** If the goal is to write Nelua, the
preprocessor is how you end up not writing Nelua while believing that you are.
Worth deciding up front where the line is.

---

## 5. Effort estimate

Against the Astro baseline, which exists and works.

### Full replacement (Nelua SSG, no Astro)

| Phase | Days |
| --- | --- |
| Spike: install via flake, hello world, prove the directory walk works | 0.5–1 |
| Filesystem plumbing (walk, mkdir, copy, size measurement) | 0.5–1 |
| Markdown subset incl. hand-rolled emphasis scanner | 1.5–3 |
| Templating layer + four page types (CSS carries over) | 1–2 |
| Classifier, linker, defects, budgets | 1–1.5 |
| Test harness + porting 314 lines of contract tests | 1–2 |
| Nix packaging, flake, CI, re-capture `spec-site-build.txt` | 0.5–1 |
| **Alpha-compiler tax** — miscompiles, GC/FFI edges, errors that point at generated C rather than your source, no Stack Overflow answers, 15-month-old unmerged fixes | **1–3** |
| **Total** | **7–14.5** |

Call it **8–15 focused days**. Say 1.5–3 weeks of evenings, or 1–2 weeks
full-time.

**Confidence: medium-low, and asymmetric.** I would give ~70% to "lands
somewhere in 8–15 days." The lower bound is fairly solid — the work is
well-understood and the oracle makes it verifiable. The *upper* bound is the
soft one. The tail risk is a compiler bug you cannot route around, in a project
with one maintainer who has not pushed in 15 months, where filing an issue is
not a plan. That scenario costs a week on its own or kills the effort.

### Middle path (Nelua parser, keep the JSON seam and Astro)

| Phase | Days |
| --- | --- |
| Spike + filesystem plumbing | 1–1.5 |
| Parsing, classifier, linker, budgets | 1.5–2 |
| JSON emitter | 0.5 |
| Golden-file validation against Python's `specs.json` + test harness | 0.5–1 |
| Flake/CI | 0.5 |
| **Total** | **4–5.5** |

Call it **3–5 days**, at meaningfully higher confidence (~80%), because the
oracle removes most of the specification risk and the whole of items #7–10 and
#18 (Markdown-to-HTML, escaping, templating) disappears — the JSON carries raw
Markdown and Astro renders it.

### The baseline, for comparison

The Astro version is being built in a single session on top of a parser that
already existed. Realistically **~1 day** of human-equivalent work for the
rendering layer, of which 547 lines of CSS — the "good visual design, light and
dark" requirement, and the part a reader actually notices — is the bulk.

So: **8–15 days to arrive at feature parity with roughly 1 day of work.**

### What you win and lose

**Win:** a single self-contained native binary, no runtime dependency; drop 246
npm packages from `site/node_modules`; a genuinely uncommon artifact; a real
excuse to learn the language.

**Lose:** Astro's dev server and HMR; scoped CSS and component composition;
someone else maintaining the HTML pipeline; CPython's stdlib guarantee. Gain a
build dependency on an alpha language with one maintainer and no releases, in
service of a build that already completes in 17 ms.

---

## 6. Recommendation

**This is a fun idea, not a good idea, and it is not quite a bad idea.** Those
are three different claims and all three are true.

**Why it is not a good idea.** The site exists because the unverified count must
be trustworthy — that is the stated reason to build it at all, and the reason
the renderer is required to fail loudly rather than guess. Putting that count
behind an alpha compiler with no tagged release and 15 months of silence is in
direct tension with the epistemics this repository is built on. The house rule
is that a datasheet grounds nothing and only observation counts. Right now,
"Nelua handles this fine" is a datasheet claim. It also inverts the cost profile
exactly: the ecosystem gaps (no readdir, no mkdir, no Markdown, no templating,
no test framework) land squarely on the critical path, while Nelua's genuine
strengths (native speed, no GC, C interop, static types over Lua syntax) are
irrelevant to a 17 ms build over 20 KB of text.

**Why it is not a bad idea either.** Nelua is well-made, MIT, in nixpkgs, and
its C interop is real and demonstrated. The failure mode is bounded: the
existing Python renderer is 728 lines in one file and reverting is one
`git revert`. There is a byte-exact oracle to develop against, which is the
single best circumstance for writing an alpha language. And "Josh wants to write
Nelua" is a legitimate reason to do something — it just is not an engineering
one, and the two should not be dressed up as each other.

### The middle path, and it is already half-built

**Replace `scripts/render_specs.py` with `scripts/render_specs.nelua`, emitting
the identical `site/src/data/specs.json`. Leave Astro alone.**

This is the right shape for five reasons:

1. **3–5 days, not 8–15.** No templating, no HTML escaping, no CSS, no
   Markdown-to-HTML — the JSON carries raw Markdown and Astro renders it.
2. **A golden-file oracle.** Diff the Nelua output against Python's `specs.json`
   byte for byte. You will know immediately and unambiguously when you are done,
   and when the alpha compiler has miscompiled something.
3. **It keeps the interesting part** — the `UNVERIFIED` / `Grounding` classifier
   — which is exactly where Lua patterns are genuinely pleasant, and exactly
   where the repository's conventions live.
4. **It drops the worst blockers** — templating, escaping, the emphasis scanner
   — while leaving the one that is unavoidable and actually instructive: the
   directory walk.
5. **Clean exit.** One file, one revert, Python still in history.

Do it behind a flag first: run both renderers, diff the JSON, promote Nelua only
when the diff is empty over the full capability tree. That is the same
discipline this repo applies to hardware — do not believe the claim, observe the
output.

The honest caveat even on the middle path: it makes the build depend on a Nelua
toolchain and a C compiler to replace something that currently depends on
nothing but CPython's stdlib. That is strictly more fragile for zero functional
gain. It is worth doing because you want to write Nelua. That is a fine reason.
It is not a technical one, and the proposal should say so out loud rather than
manufacture a performance or dependency-hygiene argument that does not survive
contact with a 17 ms build.

### One alternative worth naming

If the appeal is "a Lua-flavoured language that compiles to something fast," and
the job is text munging, **plain Lua or LuaJIT beats Nelua at this specific
task** on every axis that matters here. Same patterns, same feel, plus a real
ecosystem: `lpeg` (a proper parsing library, and genuinely the *better* tool for
a convention-carrying Markdown dialect than either regex or md4c), `lua-cjson`,
`luafilesystem` for the readdir you are missing, `busted` for tests. All in
nixpkgs. Probably **2–3 days**, less than the Nelua middle path, with a lower
tail risk.

Nelua is the right tool for a game loop. This is not a game loop. If the real
goal is "something unusual in this repo," an LPeg grammar for the spec dialect
is more unusual-and-good than Nelua-with-no-libraries — it would replace the
regex pile with an actual grammar, which is a legible improvement on the current
design rather than a lateral move.

---

## Sources

- [nelua.io](https://nelua.io/) · [edubart/nelua-lang](https://github.com/edubart/nelua-lang)
- [Nelua standard libraries](https://github.com/edubart/nelua-lang/blob/master/docs/pages/libraries.md) · [C libraries / cimport](https://github.com/edubart/nelua-lang/blob/master/docs/pages/clibraries.md)
- [`lib/table.nelua`](https://raw.githubusercontent.com/edubart/nelua-lang/master/lib/table.nelua) — 21 lines, `static_error 'tables are not implement yet'`
- [Andre-LA/awesome-nelua](https://github.com/Andre-LA/awesome-nelua) · [edubart/nelua-decl](https://github.com/edubart/nelua-decl) · [edubart/lester](https://github.com/edubart/lester)
- [mity/md4c](https://github.com/mity/md4c)
- GitHub API, `repos/edubart/nelua-lang`, retrieved 2026-09-20: `pushed_at` 2025-06-24, 2,424 stars, 27 open issues, 1 release (`latest`, 2021-09-05)
- nixpkgs-unstable: `nelua.version` = `0-unstable-2025-06-24`
- This repo: `scripts/render_specs.py`, `site/src/**`, `tests/test_render_specs.py`, `docs/evidence/spec-site-build.txt`
