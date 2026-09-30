## ADDED Requirements

### Requirement: Home weather uses Fahrenheit

*Grounding: `docs/evidence/fahrenheit-weather/README.md`, `activation.log` and the cropped native capture establish physical-board deployment and Fahrenheit rendering. Finger and reboot proof are not claimed.*

The Home weather widget SHALL display current, daily high/low and hourly temperatures in rounded Fahrenheit with an explicit °F label. Fresh and stale Celsius cache snapshots SHALL retain their existing schema and receive the same display conversion.

#### Scenario: Weather data is available

- **WHEN** fresh or cached weather is displayed on Home
- **THEN** every displayed temperature is converted from Celsius to Fahrenheit and labeled °F

#### Scenario: Weather is unavailable

- **WHEN** there is no weather snapshot
- **THEN** the widget preserves its existing unavailable display without fabricating a temperature
