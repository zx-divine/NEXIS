# Milestone 1 — foundation implementation checkpoint

27 October 2026. **Implemented but partially verified. Full NEXIS V1: NOT READY.**
This report closes the foundation implementation checkpoint, not public-release
acceptance. See NEXIS_V1_PLAN.md for all 25 feature statuses and remaining milestones.

## Implemented

- Main native window and onboarding title: exactly **NEXIS**. Native Windows
  frame retained. Approved logo/icon files were not changed. The original logo
  SHA-256 remains `cee617446391da8bf0f3d348f96e0f629e11aa8c9dc9e30356c577d721794b4c`.
- Personalized welcome with exactly three primary mode choices; persistent Home,
  Voice, Chat, Manual and Settings navigation. Existing page instances and session
  context survive mode changes. Leaving Voice requests capture cancellation.
- Validated local preferred name and launch mode. Additive defaults preserve the
  current schema and user-data location. Names accept multilingual ordinary text,
  reject controls/bidi overrides and render as plain text.
- Eight Settings categories, a keyboard accessible category list, existing
  controls, name/default mode editing and honest unavailable integration status.
- Onboarding: preferred name, capability acknowledgement, administrator/UAC
  explanation, screen choice/disclosure, explicit local phrase test and level/
  transcript feedback, Windows speaker test, retained provider configuration,
  six live themes and launch/orb/chat/voice previews. Its Settings gear is visible
  throughout. No microphone or network test starts just from opening setup.
- Permission, muted and unavailable-AI-connection reactor states driven by actual
  events. Authentication errors remain errors, not false claims of lost internet.
  Mute and offline reactors stop their motion. Delayed visual callbacks no longer
  read potentially closed storage; shutdown rejects late state changes.
- Smaller-window chat controls now use two rows, removing horizontal clipping.
  Theme names match the V1 brief; reduced motion and hidden/minimized suspension
  remain active. Existing command, privacy and execution boundaries are retained.
- Owner-selected proprietary copyright notices and a proposed EULA for review.
  Third-party notices preserve applicable LGPL rights. No final free-use grant,
  legal publisher, trademark registration or permission to distribute is invented.
- Removed the existing pointing-hand cursor override. No system cursor setting,
  cursor resource or global override was changed.

## Fresh verification

Runtime: bundled Windows Python with the project's development/provider dependencies.
Commands use `scripts/dev.py`; tests create isolated profiles and fake platform
adapters where appropriate. They do not exercise real destructive operations.

| Check | Actual result |
|---|---|
| Unmodified baseline, isolated temp directory | 554 passed, 1 skipped; 165.26 seconds |
| Focused early foundation/provider/branding/HUD checks | 50 passed; 48.20 seconds |
| First broad changed-source run | 570 passed, 1 skipped, 1 failed; 202.78 seconds. Windows denied an existing model-activation directory rename. Isolated retry passed. This failure was retained, not reported as a pass. |
| Next broad run | 570 passed, 1 skipped, 1 failed; 463.72 seconds. Exposed a late visual callback reading a closed DB. Fixed with cached mute state and shutdown guards; regression coverage added. |
| Final foundation full suite | **572 passed, 1 skipped; 377.95 seconds** |
| Ruff across src, tests and new verification script | All checks passed |
| Actual widget renders | 21 captures per run at 100%; separate 21 at 150% DPI. Welcome, Chat, Voice, Manual, Settings, six themes and onboarding pages. Inspected small/large welcome, small chat/settings/voice, appearance and white theme. |
| Native window discovery | Exactly one isolated preview window returned with title NEXIS |
| Native screenshot/accessibility interaction | **Unverified**. Two Windows helper capture attempts timed out; no input was attempted and no success was inferred. Preview exited through its five-minute timer. |

Final regression command:

```text
<bundled-python> scripts/dev.py test -q --basetemp=.verification-v1-m1-qualified --tb=short
```

Private local evidence: `.verification-v1-m1-qualified.txt`,
`.verification-v1-m1-qualified/`, `.verification-v1-m1-qualified-renders/`,
`.verification-v1-renders-fonts/` and `.verification-v1-renders-150/`.
Earlier failed runs remain available. Generated screenshots are real Qt widget
renders, not designed illustrations or claims of hardware/live-service success.
These machine-specific outputs are ignored by Git and are not release inputs.

## Performance observation

Measured during concurrent regression activity on this host, using an isolated
offscreen window and no loaded AI model. This is not reference-i3 qualification.

| State | One-core process CPU | Working set | Paints / approx. 3 seconds | Reactor / sensor timers |
|---|---:|---:|---:|---|
| Idle | 14.34% | 95.75 MB | 20 | on / on |
| Active | 15.37% | 95.80 MB | 23 | on / on |
| Reduced motion | 0.52% | 95.81 MB | 0 | off / on |
| Minimized | 0.00% | 96.10 MB | 0 | off / off |

Construction through first event, excluding imports: 8.366 seconds in that run.
Mean active paint wall time was 72.23 ms. These numbers warrant standalone native
profiling and optimization; do not claim the low-end performance requirement is
met. Hidden-page and minimized work suspension was observed. Streaming/audio/model
resource usage and long-session behavior remain unmeasured here.

## Outstanding issues and acceptance limits

- Full native keyboard/screen-reader, taskbar/Alt+Tab, multi-monitor, Windows 10/11,
  clean-install and user design acceptance remain outstanding.
- Physical microphone phrase recognition, speaker audibility, permissions/hot-plug,
  live provider/vision and automatic barge-in remain unqualified. The setup test
  is implemented; creating the control is not a claim that a physical test passed.
- The model-activation access-denial did not repeat in its isolated retry or the
  final full suite. Its cause is not proven; qualify actual first-run provisioning
  and file-lock recovery during voice/release work.
- Current startup/render performance needs optimization and repeat measurement
  without a concurrent regression workload. Native UI scaling works in actual
  100%/150% widget renders; that does not certify physical per-monitor behavior.
- Settings can expose existing capabilities and clear missing-feature status.
  Language engines, notification services, advanced font/orb controls, plugins and
  integrations still require their later milestone implementations.
- The EULA remains a draft awaiting owner review. Actual contracting rights holder,
  final consumer-law terms and complete dependency/source obligations remain
  release gates. No new binary, installer, portable ZIP or Release Nexis artifact
  was created from this foundation checkpoint.
- USB archive separation was confirmed read-only. The inspected transfer report
  still says NO-GO/incomplete; no full-backup verification or archive modification
  was performed. Keep all originals.

## Next required work

Milestone 2: preserve current passing foundation, add explicit Ollama/local-model
configuration, persistent searchable conversations with privacy controls and a
conflict-aware global launcher; implement target-bound dictation and optional
local wake-word lifecycle with properly licensed resources. Qualify actual voice,
interruption and model provisioning. Later milestones in the plan remain required;
the full-feature public release is not authorized or ready.

## Subsequent native verification during Milestone 2

Read-only hardware discovery subsequently confirmed that this host matches the
requested reference: i3-6100U, 8 GB class RAM, Intel HD 520, Windows 10 build 19045.
A separate native Qt/Win32 probe verified the NEXIS title, normal frame/control
style, nonzero Windows icon handle, and actual minimize/maximize/restore states.
It produced 47 real widget captures, including the full six-theme/four-preview
matrix. This supplements the earlier helper timeouts; it does not certify manual
accessibility, taskbar grouping, clean installation or Windows 11. Standalone
native performance numbers and current source verification belong in the
Milestone 2 report; the concurrent offscreen measurements above remain unchanged
as a record of that earlier run.
