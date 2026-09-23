# Recovery-first storyboard

1. **Boot to first choice.** Splash gives way to a visible shell. The person
   sees Apps, Windows, Keyboard, and System before needing a gesture.
2. **Discover.** Apps opens named large cards, including Help; Previous, Back,
   and Next state where the person is. A failed optional launch stays in the
   shell and explains the next route.
3. **Work with the keyboard.** Keyboard changes the available viewport but
   keeps a visible escape route. Asymmetric typing is a separate physical
   acceptance test, not inferred from the layout.
4. **Switch or recover.** Windows shows named cards; a selection yields to the
   chosen app. Empty/stale/loading states expose Back/Apps/Home instead of a
   silent no-op. Home can recover Terminal.
5. **End a transient task.** Video Stop, Home, and EOF clean up into the shell.
   System action requires an action-named confirmation; Cancel leaves the
   session usable and reboot returns to shell.
6. **Future direct cards.** The card-composition/app-card owners add global
   entry, live shrinking content, finger-following deck, expansion and a
   graceful close/refusal path. Buttons, Back, and Home remain recovery routes.

This storyboard compares continuity and reversible navigation with the webOS
reference listed in [references.md](references.md); it does not assert shared
implementation, gesture grammar, or visual assets.
