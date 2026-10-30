# Testing

Use an isolated Python environment (3.12.14 verified for v1.3.2) and requirements-dev.txt; install the project
editable, then run python -m pytest -q and python -m ruff check src tests scripts.
Qt tests can run headlessly with QT_QPA_PLATFORM=offscreen. On this bundled runtime,
use scripts/dev.py test -q, which explicitly loads pytest-qt.

Tests use temporary SQLite databases and search folders. OS launches and registry
changes are injected fakes. Clipboard tests deliberately write a test string to the
clipboard and clear it afterward; headless Qt isolates it from the native desktop.
No tests start real external apps, browse websites or alter user documents.

Unit coverage: parser, URLs, names, executable restrictions, permission decisions and
workflow definitions. Integration: storage migration/restart, corruption, settings,
retention, snippets, shortcut persistence, routing, workflows and stop-on-failure.
Security: shell input, SQL payloads, dangerous URLs, invalid persisted actions, approval
enforcement, path traversal, search scope, symlinks, subprocess arrays, history and logs.
UI: creation, navigation, sizes, Enter submission, errors, clipboard, cancellation
dialog, permission denial, settings and asynchronous search.

A symlink test may skip on Windows if developer mode/privilege is unavailable. That
is reported as unverified, never counted as passed. Qt's offscreen renderer verifies
widgets and interactions; it is not full native accessibility or screen-reader validation.

Manual release checks: actual built-in launches, configured signed application,
default browser dispatch, inaccessible folders, removable disks, workflow stop,
Windows startup opt-in/out, data export/delete, no-Python clean-machine startup,
DPI 100/125/150/200%, Windows high contrast and screen reader.

Run scripts/measure.py with the installed environment for startup-to-first-events and
idle working-set measurements after three seconds. Hardware and cache conditions
matter; compare against the baseline machine before making performance promises.

## v1.1 additions

Historical v1.1 counts remain in local reports. Current v1.3.2 results are summarized in INSTALLER_PERMISSION_OVERHAUL.md. The expanded suite
checks reactor states/timers/reduced motion, real-counter sensor calculations, all three
HUD resolutions, deck/drawer behavior, deterministic conversation, both entry points
against permission denial and shell input, schema-v1 compatibility and worker shutdown.
Voice capture tests inject backends and PCM; they never open real microphones or assert
real recognition accuracy. scripts/measure_hud.py measures render events and process CPU
with a native Qt event loop; the direct state stimuli are benchmark-only.
