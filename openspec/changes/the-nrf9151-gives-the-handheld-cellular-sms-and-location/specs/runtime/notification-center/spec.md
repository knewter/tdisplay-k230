## ADDED Requirements

### Requirement: An incoming text is a notification with a private preview

<!-- UNVERIFIED: depends on SMS reception, which has not been observed on this unit. -->
An SMS received by the modem service SHALL appear as a notification whose source is the sender's number. Following the existing privacy default, the preview SHALL hide the body. Opening the notification in history SHALL show the full text.

#### Scenario: A text arrives while typing

- **WHEN** a text arrives while a person types in the terminal
- **THEN** a preview shows the sender without the body and does not take focus, and the full message is readable in the shade's history

### Requirement: The shade shows cellular and location state while the modem is on

<!-- UNVERIFIED: depends on the modem service's state, which has not been observed. -->
While Cellular is on, the shade SHALL show a signal indicator matching the service's reported bars, or no service. While Location is on, the shade SHALL show a location indicator that distinguishes searching from a fix. While both are off, the shade SHALL show neither.

#### Scenario: Modem off

- **WHEN** both Cellular and Location are off
- **THEN** the shade shows no cellular or location indicator

#### Scenario: Searching for a fix

- **WHEN** Location is on without a fix
- **THEN** the shade's location indicator shows searching, and changes to a fix once `gpsd` reports one
