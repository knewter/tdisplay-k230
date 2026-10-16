## ADDED Requirements

### Requirement: The Clock widget's date is readable at every text step

<!-- UNVERIFIED -->

Every Clock widget style SHALL draw its date line at no less than 26 px on
the panel at the 100% text step. The size SHALL grow in proportion to the
Vision text step. The date line SHALL fit within the widget's cell without
ellipsizing, shrinking only to fit the cell's width. The time SHALL NOT
overlap the date at any step.

#### Scenario: The date at the default step

- **WHEN** Home shows a Clock widget at the 100% text step
- **THEN** its date line is at least 26 px tall in font size and is shown in
  full

#### Scenario: The date at the largest step

- **WHEN** Home shows a Clock widget at the 200% text step
- **THEN** its date line is larger than at 100%, unless the cell's width
  limits it, and neither the date nor the time is clipped or overlapped
