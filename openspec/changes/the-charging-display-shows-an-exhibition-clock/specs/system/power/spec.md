## ADDED Requirements

### Requirement: An idle display on the charger shows an exhibition clock

*Grounding: injected board runs on build `3vk5qy3a…` (docs/evidence/clock-display/board/README.md). `bq25890-charger-0` (type USB) reads `online` 1 when docked and 0 on battery. Docked idle opens the clock at 70 s with the display on. On battery, or with the preference set to Sleep, it dims and turns off at 60 s with no card. Unplugging blanks the display in 9–11.5 s. The clock-only phase adds no measurable CPU over a no-card baseline. The idle steps are board-read (docs/evidence/idle-dim/).*
While the charger is connected and the preference "Idle on charger" is Clock (the default), the system SHALL, after 30 s without input, dim the panel as it does on battery and show a full-screen exhibition of the time and date, and SHALL NOT turn the display off at 60 s. With the preference Sleep, or with no charger, the idle steps SHALL behave as on battery. The exhibition SHALL redraw its clock at most once a minute, SHALL change the clock's position at each redraw within a bounded range, and about every five minutes SHALL play one text effect over the text K230 for at most 20 s before the clock returns.

#### Scenario: Docked and idle

- **WHEN** the charger is connected, the preference is Clock and no input arrives for 60 s
- **THEN** the panel is dim, a clock and date are shown, and `swaymsg -t get_outputs` still reports power true

#### Scenario: On battery

- **WHEN** no charger is connected and no input arrives for 60 s
- **THEN** the panel is dim at 30 s and off at 60 s, and no exhibition card exists

#### Scenario: Preference Sleep

- **WHEN** the charger is connected, the preference is Sleep and no input arrives for 60 s
- **THEN** the display dims and turns off as on battery

#### Scenario: The clock moves

- **WHEN** two consecutive minutes pass in the exhibition
- **THEN** the clock's position differs between them and stays entirely on the panel

### Requirement: Input leaves the exhibition without reaching an app

*Grounding: on the board, an injected tap and an injected key over Files closed the card without reaching Files, and Files (the prior card) returned in front. The operator's glass report agrees. Unplugging closed the card and turned the display off (docs/evidence/clock-display/board/README.md).*
<!-- UNVERIFIED: the two-hour cap is not run on the board; the keyboard-base key and the power key rest on operator reports. -->
A touch or key that arrives while the exhibition is shown SHALL be consumed by the exhibition, with the release of a touch, and SHALL close it, restore the prior brightness, and return to the card or Home that was in front. No application beneath it SHALL receive the touch or key. When the charger is disconnected, or after the exhibition has been up two hours, it SHALL close and the display SHALL turn off with the idle step's own command.

#### Scenario: Tap over an app button

- **WHEN** the exhibition is shown over an app and a person taps where that app has a button
- **THEN** the exhibition closes, the brightness is the prior value, and the button is not activated

#### Scenario: Unplugged while exhibiting

- **WHEN** the charger is disconnected while the exhibition is shown
- **THEN** the exhibition closes and the display turns off within 15 s

#### Scenario: Woken from dark

- **WHEN** the display was turned off with the power key while the exhibition was shown and is turned on again
- **THEN** the exhibition is not shown and the prior card or Home is
