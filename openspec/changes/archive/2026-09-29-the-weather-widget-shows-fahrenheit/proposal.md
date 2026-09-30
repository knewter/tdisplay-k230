## Why

The operator reports that the Home weather widget shows Celsius and wants Fahrenheit. The unit must be an image default, including existing cached weather.

## What Changes

- Convert temperatures at display time and label them °F.
- Apply the same unit to current conditions, daily high/low and the hourly strip.
- Deploy the built shell to the physical board and record verification.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `runtime/shell`: Home weather presents Fahrenheit.

## Impact

`nix/rust-shell-client/src/home_widgets.rs` and `src/render.rs`. Cache fields and network fetches retain Celsius. The separate terminal weather app and a unit-picker UI are outside this change.
