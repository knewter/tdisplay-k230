# Repeatable handheld UX review rubric

Use this rubric with a dated source identity and links to the evidence, not as
a numeric score. Record each observation as `observed`, `not observed`, or
`unavailable`; state whether it is host-render, native board capture, injected
board input, camera, or real-finger evidence.

| Dimension | Review question | Evidence needed to call a current behavior observed |
| --- | --- | --- |
| Discovery | Can a person identify the action and find a named app/surface? | Current-source image and stated catalog size; real-finger review for reach/reading claims. |
| Hierarchy and consistency | Do type, spacing, palette, icon role, and state labels form a legible whole across Home, drawer, settings, shade and deck? | Paired same-source frames; authored-theme host render may assess pixels, not physical readability. |
| Focus and feedback | Does selection/press/loading/error produce visible, timely feedback and preserve context? | Reproducible action and before/after native pixels or capture; host fixture only proves renderer output. |
| Motion and direct manipulation | Does the same object follow touch and settle predictably; are close/refusal routes recoverable? | Timestamped input and compositor/native capture; camera/finger footage for optical tracking. Static frames cannot prove trajectory. |
| Keyboard occlusion and recovery | When visible, what remains reachable, and can the person hide/recover the keyboard? | Current-source shown/hidden states and the actual action used. Keyboard command reveal is not gesture evidence. |
| Accessibility and reach | Are targets legible and reachable without relying on a gesture alone? | Target geometry plus actual interaction; camera framing/optical clarity and finger reach need physical review. |
| State/recovery language | Are empty, loading, stale, failed, denied and private states distinct, short, and actionable? | One artifact/fixture per state, with literal displayed text and route out. Do not infer missing states from a healthy screen. |
| Reference comparison | Does a webOS principle clarify an interaction while respecting this handheld’s different context? | Inspected primary reference and current artifact; label interpretation as comparison, not compatibility claim. |

Confidence labels: **high** = the named evidence directly shows the scoped
claim; **medium** = source or a proxy state supports a plausible issue, but
physical impact is not shown; **low** = hypothesis requiring a new observation.
Severity describes user impact only when the evidence shows a user-facing
problem. An absent capture is an evidence gap, not automatically a defect.

Review keyboard-hidden and keyboard-visible states separately. Reuse a prior
acceptance only for a behavior whose interaction contract and implementation
are unchanged; state the date and source. Do not count a described sequence,
host render, injected event, or previously accepted session as a newly walked
current-source journey. Preserve unknowns verbatim as `UNVERIFIED`.
