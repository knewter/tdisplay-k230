# Archive publication correction

Archive commit `36f57cd4476bf891d47f702061bbb7cf9d884512` failed the
[site build](https://github.com/knewter/tdisplay-k230/actions/runs/39366761992)
on 2026-10-20 at 03:57:29 UTC. The local owner is the panel-paint change.
The requirement used an HTML `Grounded:` comment, while
`scripts/render_specs.py` requires a visible `Grounding:` paragraph.
The log reports `runtime/card-shell ... 1 undeclared`,
`82 of 290 requirements unverified, 1 undeclared`, and exit2.

The same change was reopened only to correct that marker and use full
repository-relative evidence paths. OpenSpec archive/sync applied one MODIFIED
requirement to the existing capability and rearchived all seven completed
tasks. No source, pixel, budget, camera or installation result was changed.
The earlier qualified evidence publication at `2d8142d4` remains successful.

Narrow verification after correction:

```sh
python3 scripts/render_specs.py --json /tmp/panel-paint-specs.json --assets /tmp/panel-paint-spec-assets
```

The executed command used the session handoff directory for outputs. It
exits0, reports `82 of 290 requirements unverified` and no undeclared
requirements. This checks the exact classifier that rejected the archive.
Corrective CI/Pages publication is checked after the correction is pushed.
