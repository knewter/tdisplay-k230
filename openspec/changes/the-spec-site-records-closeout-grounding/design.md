## Context

The site parser intentionally requires a Grounding citation or an UNVERIFIED marker. Its failed CI log identifies the malformed closeout citations.

## Decisions

Use existing committed proof and the parser’s established Markdown Grounding format. Apply MODIFIED deltas through OpenSpec archive; never hand-edit accepted main specs. Keep operator, injected board, QEMU and unavailable-battery evidence limits explicit.

## Risks

A documentation fix must not turn an unmeasured timing or unavailable attached-battery result into a new claim. Existing wording and limits are retained.

## Validation

Strict OpenSpec, render_specs, render_work_board and site build; exact master deployment is verified separately.
