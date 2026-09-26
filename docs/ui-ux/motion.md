# Interface motion

## Scope and gate

The owner requested purposeful motion throughout the existing interface on
2026-09-26. Motion supports feedback, spatial consistency and state indication;
it does not change financial values, API calls, validation or commit behavior.

| Surface | Frequency and purpose | Implementation |
| --- | --- | --- |
| Operation, account, category, fund and scheduling forms; calendar day dialog | Occasional; spatial consistency | Backdrop opacity and centered card opacity/scale, 240 ms |
| Add-operation menu and entity search results | Pointer entry only; spatial consistency | Opacity/scale from the trigger edge, 180 ms |
| Native More menus in directories, fund actions and calendar | Occasional; state indication | Symmetric opacity transition on native details content, 180 ms |
| Submit, close, add-operation, menu-toggle, page primary actions and button links | Frequent; subtle feedback | Press/release scale 0.97, 120 ms |
| Operation and report disclosure arrows | Frequent; subtle state indication | Rotation retargeted by CSS transition, 120 ms |

Amounts, graph coordinates, chart data, ledger rows, page navigation, active
filters and typing do not animate. There are no decorative scroll reveals,
staggers of financial data, counters, springs or new runtime dependencies.

## Shared implementation

`frontend/src/motion.css` extends the root tokens with `--ease-out`
(`cubic-bezier(0.23, 1, 0.32, 1)`), `--ease-in-out`
(`cubic-bezier(0.77, 0, 0.175, 1)`) and the three durations above. Press and
indicator feedback use CSS transitions. No new hover movement is introduced.
Native details uses progressive enhancement; engines without details-content
transition support retain instant open/close behavior.

`UiMotion` uses the Web Animations API with Angular's enter/leave callbacks for
surfaces that require removal coordination. Menus originate at their trigger
edge, while dialogs stay centered. Exit starts at the current computed opacity
and transform, so closing during entry does not jump to the fully open state.
An outgoing surface is inert and hidden from accessibility immediately. A fast
reopen completes any stale exit first. Both cancellation and completion release
the Angular callback exactly once; destruction cleans up listeners and motion.

## Keyboard and reduced motion

A captured pointer event enables motion; any keydown switches back to instant
interaction and completes in-flight motion. Keyboard-opened surfaces, typing,
shortcuts and Escape therefore do not wait for animation. Existing menu focus
behavior and form handlers are retained.

With reduced motion enabled, pointer-opened surfaces fade without scaling;
press movement and arrow transitions are disabled. Native More menus retain
opacity feedback. The existing loading indicator remains static under reduced
motion. No information depends on movement.

## Verification and acceptance

Unit tests cover keyboard bypass, switching modality mid-animation, reduced-motion
keyframes, interrupted entry, inert exits and rapid reopening. Browser checks
exercise the operation menu, composer entry/exit, native More-menu transition,
entity-list origin and keyboard menu navigation without posting data. Build, lint and typing checks cover every integrated
surface; not every form variation was individually played in the browser.

Timing is intentionally short, but subjective motion quality still requires
owner feel-check on the actual device: open/close a composer, reverse quickly,
then repeat using only the keyboard and the OS reduced-motion setting. A static
screenshot shows the final layout, not animation quality.
