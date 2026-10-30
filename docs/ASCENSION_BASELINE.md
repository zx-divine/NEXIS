# Project Ascension baseline — 24 October 2026

ASH owns product and release decisions. This mission continues the existing application; no rebuild from scratch or website work is authorized.

## Pre-flight

Repository remote is the existing `zx-divine/nexis`. Initial branch `main`, commit `ae27bf8650548077e83e6fd5722df88c18aac135`, clean staged/unstaged/untracked status, one worktree. Enhancement branch: `codex/project-ascension`. No active robocopy/xcopy/archive/NEXIS/Python copy process was detected during initial inspection. No original environment, database, credential file, archive, release candidate or Git history was removed.

The 1.3.4 candidate, previous builds, NEXIS LAUNCH directory and private release verification reports were inspected. File hashes are retained privately for preservation checks. The intended USB destination `E:\NEXIS` is absent. The private archive continuation report identifies an alternative existing archive. Its recorded full read-back passed for captured bytes, but its verdict is **INCOMPLETE** because ten source fixtures were absent and a cache directory was inaccessible. Windows reports the USB Healthy/OK; this is not a reason to delete originals. No archive write or new claim of complete restoration was made.

## Fresh test baseline

Initial suite: **395 passed, 1 skipped, 1 failed**, 195.85 seconds. The failure was a five-second shutdown wait in `test_startup_never_prechecks_network_or_opens_microphone`, involving startup speech worker completion. The skip requires Windows symlink privilege. Original log is retained privately. This was not recorded as a clean baseline PASS. Later engineering adds early speech initialization cancellation checks and guards queued UI payload/playback delivery; final evidence is in the handoff.

## Targeted architecture inventory

| Subsystem | Baseline status | Evidence and boundary |
|---|---|---|
| Qt entry/HUD/startup/shutdown | Implemented, shutdown reliability issue | Existing native startup evidence; fresh timeout above |
| Chat and provider adapters | Implemented; live service dependent | Encrypted profiles, compatible/Gemini adapters, context, streaming and bounded IO; mocks do not certify credentials |
| Voice capture/STT/VAD/Voice Studio | Implemented; human verification required | Explicit capture, device calibration, dBFS/clipping, cached Vosk; no physical accuracy claim |
| Offline resources | Implemented in preserved packages | Prior audit verified all 14 English model files, VAD/native runtimes; SAPI voices/drivers remain Windows components |
| Wake word | Missing | No trained detector/assets; honest standby/PTT is the appropriate fallback |
| Hard Mute | Implemented; delivery boundary needs hardening | Persistent latch/cancel generations/approval rejection already present; queued UI delivery reviewed |
| Website opening | Partial | Curated names/full HTTPS/default browser only; bare domains and explicit browsers missing |
| Settings | Implemented but scattered | Long page with provider/voice/privacy elsewhere; no dedicated gear/central hub |
| NEXIS Doctor | Missing as a full feature | About exports limited aggregates; no categorized evidence-based diagnostic page |
| Orb/tray | Implemented, optional | Existing drag/clamp/reduced-motion/fullscreen logic; physical multi-monitor/lock testing pending |
| Memory/schema | Implemented | Schema 4, local explicit drafts/saves/export/import; no automatic provider context; on/off missing |
| File Finder/index | Implemented within bounds | Approved-root metadata search and optional bounded UTF-8 txt/md index; no PDF/Office support |
| Workflows | Implemented, experimental authoring | Editable drafts/dry-run/explicit save/run/pause/cancel; scheduling missing |
| Screen Awareness | Implemented, live vision unverified | Permission, opt-in, capture preview, destination consent; no automatic capture/transmission |
| PC Health | Implemented | Read-only OS metrics outside GUI thread; temperature unavailable |
| Permissions/security | Implemented | Schemas, DPAPI, approved roots, risk-based approvals, bounded cancellation; review is not proof of all bugs absent |
| Packages | Existing 1.3.4 current-host evidence | Preserve originals; new source requires new isolated packages and fresh evidence |

Priority: P0 diagnostics, settings access, safe website launch and cancellation first. Existing voice/productivity implementations are retained. Hardware, clean Windows, licensing and account-dependent live checks remain separate release gates. The November 10 target is not an acceptance waiver.
