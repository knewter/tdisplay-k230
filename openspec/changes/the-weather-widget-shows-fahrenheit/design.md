## Context

The weather source and cache store explicit Celsius fields; the renderer currently draws those integers directly with a degree sign. Converting the cache would invalidate existing values and could cause double conversion.

## Decisions

Format Celsius as rounded Fahrenheit at the rendering boundary using C × 9/5 + 32. Include °F on every temperature label. Fresh and stale snapshots share the renderer, so cached offline weather changes immediately too. Keep unavailable placeholders unchanged.

Deploy the same coherent HDMI trial system profile with the Chicago timezone and proven touch/compositor selection preserved. Refresh shell-ui to run the installed Rust binary.

## Evidence

Cross-building proves the changed binary. An installed profile and board-native screenshot establish runtime deployment and displayed units separately; they do not establish new gesture or reboot acceptance.
