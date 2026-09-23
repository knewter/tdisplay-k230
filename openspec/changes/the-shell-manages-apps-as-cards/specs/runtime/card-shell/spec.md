## Purpose

Defines a touch-first live-card surface that lets a handheld user see,
rearrange, resume, and safely close eligible running applications.

## ADDED Requirements

### Requirement: A person can manipulate a live application card deck

<!-- UNVERIFIED: no live-card composition path has yet been observed on this board. -->
The card shell SHALL present eligible running applications as live visual cards,
not title-only substitutes. Entering the card shell SHALL shrink the active
application into a card, keep a horizontal deck of eligible cards, move the
selected card with a single finger, and expand the tapped card back to the
active application.

#### Scenario: A person resumes another running application

- **WHEN** the card shell contains two eligible running applications and a
  person drags to and taps one card
- **THEN** that application's live card is visible during selection and the
  application expands to become active

### Requirement: The card shell handles unavailable and private content safely

<!-- UNVERIFIED: eligibility, protected-surface behavior, and privacy policy have not been implemented or tested on the board. -->
The card shell SHALL identify an application whose live surface is unavailable,
protected, or excluded by the session privacy policy without exposing its
content. It SHALL provide a clear non-live card state and a route back to the
existing Apps or Windows/Home controls.

#### Scenario: A live surface cannot be presented

- **WHEN** an application is not eligible for live card presentation
- **THEN** the person sees a non-live state rather than stale, unrelated, or
  private pixels and can leave the card shell through an existing control

### Requirement: An upward throw requests a recoverable close

<!-- UNVERIFIED: gesture thresholds, close protocol, refusal handling, and recovery have not been measured on the board. -->
The card shell SHALL treat an intentional upward throw of an eligible card as a
request for that application to close gracefully. If the application refuses,
times out, or fails to close, the shell SHALL retain or restore a usable card
and make an existing recovery route available; it SHALL NOT silently discard
application state.

#### Scenario: An application refuses to close

- **WHEN** a person throws a card upward and the application remains running
- **THEN** the card shell reports the unsuccessful close without losing the
  card or the Apps and Windows/Home recovery routes

### Requirement: Card interaction has an explicit measured budget decision

<!-- UNVERIFIED: card composition frame, input, and memory costs are unknown on the K230 panel. -->
The card shell SHALL record input-to-visible-update latency, frame/update cost,
and incremental memory use at the panel's native portrait mode on the default
Pixman path. If a declared interaction budget is missed, the implementation
SHALL record the result and select an explicit reduced behavior, optimization,
or rejection before it is accepted for the system.

#### Scenario: A card workload misses its declared budget

- **WHEN** a measured card interaction exceeds its declared frame, input, or
  memory budget
- **THEN** the evidence records the workload and measured result, and the
  implementation does not present the missed budget as accepted performance
