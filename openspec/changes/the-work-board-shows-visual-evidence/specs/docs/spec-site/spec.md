## ADDED Requirements

### Requirement: Work cards expose their visual evidence
<!-- UNVERIFIED: implementation and published-page checks remain pending. -->
The work board SHALL discover committed images and videos associated with a change's cited evidence, show a representative visual cover when available, and present the discovered media inside that card's detail view. Videos SHALL provide playback controls without autoplay. Captions and evidence-class labels SHALL not imply physical validation from mockups or automated captures. Changes without visual evidence SHALL remain readable text cards.

#### Scenario: Screenshot and video arrive during implementation
- **WHEN** screenshot or video evidence is committed for an open change and the site publishes that revision
- **THEN** the card and detail view expose the new media without waiting for task completion or archive

#### Scenario: A reader opens a card
- **WHEN** the reader clicks the card outside its evidence links or activates its primary link by keyboard
- **THEN** the existing inline detail view opens with its media and documents, without a separate View details button

#### Scenario: Enlarge media while reading a card
- **WHEN** the reader activates an image or the enlarge action for a video in the card detail
- **THEN** a gallery modal displays that media at the largest size that fits the viewport while preserving its aspect ratio, supports adjacent-media navigation by touch swipe and arrow keys, and returns to the same card position when closed

### Requirement: Card headers expose related evidence records
<!-- UNVERIFIED: implementation and published-page checks remain pending. -->
Each work card with related evidence SHALL expose directly usable evidence links from its header area, including reports, logs, screenshots and videos. Those links SHALL identify their artifacts, refer to the published revision, and remain separately usable from the primary whole-card action. Discovery SHALL exclude uncommitted, missing, unsafe and unrelated paths.

#### Scenario: Open a report from a card header
- **WHEN** the reader activates a report or log in the card's header evidence menu
- **THEN** the named evidence opens directly, without first searching through proposal documents
