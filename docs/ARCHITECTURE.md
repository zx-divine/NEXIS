# Architecture

## Data flow

UI command input -> parser -> registry -> target validation -> Permissions.authorise
-> handler -> typed Result -> UI presentation. Qt widgets never execute raw shell input.

Core code has no Qt dependency. The engine accepts an injected platform adapter
and permission provider. Tests substitute a fake adapter, preventing real application
launches and startup changes.

Commands declare identifier, description, argument requirements, risk, permission,
confirmation policy, handler and shared validator. Engine.prepare resolves the
resource target and validates it before authorisation. Engine.dispatch implements
the registered handlers. Adding a registry record alone does not enable execution;
the dispatcher still fails closed.

## Concurrency

CommandWorker is a QThread. Permission requests are Qt signals to the main thread;
the worker waits on an Event, with cancellation polling. Worker results and clipboard
payloads return via queued signals; only the UI thread touches the clipboard.
SearchWorker traverses directories independently with an Event for cancellation
and throttled progress every 100 inspected files. There is one command worker and
one search worker at a time. Shutdown refuses to destroy running workers and requests
cancellation. No background service or timer polling is required while idle.

Workflows validate every definition before running, revalidate each step, stop at
the first failure/cancellation and never recursively run other workflows. Sensitive
workflow preview is followed by per-step risk checks. Already completed launches
cannot be rolled back.

## Persistence

Database uses SQLite with a five-second busy timeout, a shared connection protected
by RLock, parameterised values, startup quick_check and PRAGMA user_version migrations.
Version zero installs schema version one; newer schemas are rejected. Existing
corrupt files are preserved with an actionable startup error. Settings with malformed
JSON or an incorrect type fall back to conservative defaults. SQLite failure is
reported rather than silently dropping data. Data is never automatically replaced.

Repository owns validated CRUD for snippets, shortcuts and workflows. Settings
validation restricts approved roots, theme, history retention and booleans. No
pickle, arbitrary deserialisation, plug-in loading or expression evaluation is used.

## Platform boundary

platform/windows.py owns Windows process launching and current-user startup registry
changes. Custom paths must be local absolute .exe paths and cannot name known script
hosts. Websites use the standard browser module after HTTPS validation. Search is
platform-independent but checks Windows reparse attributes as well as symbolic links.

## File map

- core/results.py: Request, Preview, Risk and Result data types.
- core/management.py: core-enforced approvals for data controls, startup and root approval.
- diagnostics.py: opt-in isolated packaged smoke check.
- core/parser.py, commands.py, permissions.py, router.py: input and execution policy.
- actions/files.py: approved-root containment and cancellable filename search.
- storage/database.py: schema, settings, history and export/reset.
- storage/repository.py: validated resource operations and workflow structure checks.
- platform/windows.py: process, browser, Explorer and startup integration.
- ui/main_window.py: shell, navigation, command results, diagnostics and lifecycle.
- ui/pages.py: resource editors, search and history; settings_page.py: preferences/data controls.
- ui/workers.py, dialogs.py, theme.qss: background execution, confirmations, visual styling.
- main.py: application-data location, single-instance lock and bootstrap.

The optional --smoke-test OUTPUT_DIRECTORY launch mode uses temporary storage,
visits every page, writes a rendered image and aggregate JSON, and exits without
normal application data or OS launch actions. It is used to verify the frozen build.

The proposed folder structure was consolidated where small modules would only forward
calls: commands/workflow handlers stay in the core engine, resource CRUD in one repository,
and related simple UI pages share pages.py.

## v1.1 Crimson Command additions

ui/reactor.py paints six concentric visual layers. Static marks are cached per logical size/device pixel ratio, and the radial core glow is cached per accent. Dynamic arcs/ticks use elapsed time. The timer targets 8 FPS at idle and 10–30 FPS in active states; reduced motion, hidden pages and minimized windows stop it. No expensive blur effect, GPU renderer or image wallpaper is used.

ui/hud_widgets.py implements angular panels, segmented meters, bounded sixty-sample real-data graphs and an activity visualization. Only actual command events create dots; the sweep is decorative. platform/system.py reads GetSystemTimes, GlobalMemoryStatusEx and GetTickCount64 at one-second intervals. Missing data remains None/N/A. Polling stops when minimized.

ui/command_deck.py paints accessible QPushButton subclasses with short on-demand hover transitions. ui/conversation.py owns text and voice views. core/assistant.py maps a small explicit phrase set to registered requests. Manual, Chat and reviewed voice requests all call MainWindow.submit -> CommandWorker -> Engine. An optional core phase observer reports PROCESSING before validation and EXECUTING only after permission/cancellation checks; the security decisions do not depend on that observer.

core/voice.py lazily loads optional Vosk/sounddevice only after explicit activation. A QThread loads the selected local model, opens mono PCM capture, processes a bounded queue and emits real RMS levels/transcripts. Stop/navigation/minimize/shutdown cancel capture; a second cancellation check precedes stream creation after model loading. Capture is bounded to thirty seconds, with no audio files and no network calls. Transcripts require review/execution separately. No TTS backend is configured.

Preferences are additive defaults in the existing schema-v1 settings table: reduced_motion, animation_fps, start_maximized and voice_model_path. Missing keys fall back without rewriting old rows or replacing databases. The application/organization names and LocalAppData location stay unchanged. Chat stays in memory (200-message cap). Full personal-data export includes the selected model path; safe diagnostics do not.

Default packaging has no optional voice library requirement; when installed, the spec collects optional voice native libraries but never a user model. The known Qt/ICU packaging exclusion is retained.
