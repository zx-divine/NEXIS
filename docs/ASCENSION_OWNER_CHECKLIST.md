# Owner verification — ASH

Candidate: engineering **1.3.5**, **Development**. Record the artifact SHA-256, date, Windows build, device names locally, exact steps, expected result, actual result and PASS/FAIL/NOT TESTED for each item. Do not put credentials, recordings, private screenshots or conversation text in Git. Automated fixtures do not satisfy these steps.

## Voice Studio and microphone

- [ ] Open Settings with gear and Ctrl+,. Select the actual microphone in Voice; inspect devices after unplug/reconnect.
- [ ] Calibrate in ordinary background noise: remain silent for two seconds, speak at normal volume, inspect RMS/clipping/noise and recognized text, adjust sensitivity and save.
- [ ] Test **Hi NEXIS** and **Hi mate** separately; preserve both raw/recognized outcomes. Unrelated greetings must not be forced to NEXIS.
- [ ] Separately test **Open YouTube**, **Open GitHub in Chrome**, **What time is it?**, **Go to sleep**, **Stop listening**, ordinary conversation, low volume and noise-only input. A failed phrase is a failure, not a pass by manual replacement.
- [ ] Hard Mute during capture, transcription, provider thinking and an approval dialog. Confirm actual device release, obvious muted display, no late desktop action or speech and no later queued replay.
- [ ] Wake without Talk: microphone remains off. Change pages/hide/minimize during calibration/listening: capture stops.
- [ ] Repeat three standalone speech cycles in fresh processes and five complete source/restart/executable/installed/portable conversation cycles; record real outcomes.
- [ ] Test lock, sleep/resume, audio-device disconnect/reconnect and missing selected devices. No automatic hidden capture may resume.

## Speaker and conversation

- [ ] Select actual SAPI speaker/voice; Test Windows voice and explicitly confirm hearing the full sentence.
- [ ] Cancel long output, interrupt with explicit Talk, switch outputs, change Windows default device and repeat conversations. Confirm no delayed utterance after Hard Mute/Exit.
- [ ] Test follow-ups only after deliberately opting into the existing visible hands-free feature. It is not a wake detector.
- [ ] Record whether Windows supplied the SAPI voice/driver. Test a clean machine with missing voice resources for an actionable unavailable message.
- [ ] Do not advertise Hindi/Hinglish STT. A compatible optional model and separate real-language evidence are required before qualification.

## AI and diagnostics

- [ ] Configure your own valid provider/model; discover models, test inference and send/receive ordinary chat plus follow-ups.
- [ ] Test invalid/expired key, wrong model, unreachable endpoint, timeout, rate limit, interrupted stream, cancellation and provider switching. Confirm safe messages and no automatic paid-provider fallback/replayed tool actions.
- [ ] Check model identity identifies configured selection without inventing upstream attribution or active availability.
- [ ] Run Doctor local checks offline: no audio, screen or provider request starts. Review all WARNING/FAIL/NOT TESTED/USER ACTION REQUIRED entries.
- [ ] Run explicit Doctor provider test; confirm disclosed destination and separate capability gate. Export a fresh report and inspect for absence of keys, device names, paths, private logs, memories and chat.
- [ ] Save/edit/delete/export a local memory, turn memory off, restart and confirm old notes remain while saves/imports are blocked. A later AI request must not receive local memory commands through history.

## Windows and everyday work

- [ ] Open a controlled site using Windows default; change the actual Windows default and repeat. NEXIS must honor the current association.
- [ ] Test installed Chrome, Edge, Firefox, Brave, Opera as available and one missing browser. Missing browser must explain failure and offer an explicit alternative without opening it silently.
- [ ] Test deliberate HTTP, bare domains, paths/query strings, internationalized domains, offline network and rejected local/script schemes. A launch request is not proof of page load.
- [ ] Test app launching, approved folders, file filters/cancel/revocation, workflow preview/dry-run/run/pause/stop/failure and PC Health. No side effects during dry-run.
- [ ] Enable Always Active; drag/reopen orb, use tray controls and Exit, hide/show, test fullscreen/game focus and multiple monitors. Test optional always-on-top behavior where available; never assume eligibility checks cover every application.
- [ ] Enable minimize-to-tray separately; unavailable tray must leave the main window accessible. Test sign-in startup separately and disable it afterward if unwanted.
- [ ] Test screen permission → local preview → disclosed destination → transmission approval; cancel at each boundary. No hidden capture or tool action may accompany an explanation.
- [ ] Check 820×600 and 1366×768, keyboard navigation/focus, 100%/150% actual Windows scaling and reduced motion. Toolkit scaling screenshots alone are not physical display certification.

## Installation and final approval

- [ ] Verify new installer/ZIP SHA-256 against the manifest. Record unsigned Authenticode status; never bypass SmartScreen/UAC/antivirus.
- [ ] Clean Windows 10 build 19045+ x64 without Python: install, start offline, discover bundled model and run real audio/chat as configured.
- [ ] Repeat on clean Windows 11 x64. Extract portable ZIP into a new folder away from source; keep `_internal` adjacent and launch offline without source/Python PATH dependencies.
- [ ] Upgrade a disposable copy of existing data; verify memories, workflows, voice preferences, keys and settings. Test uninstall and explicitly confirm retained/deleted data policy. Preserve originals throughout.
- [ ] Review application licence decision, all third-party notices and Qt corresponding-source/replacement obligations. Included texts do not decide the application's licence or certify compliance.
- [ ] Review unresolved failures and candidate source fingerprint/five serial regressions. Any runtime change requires affected verification again.
- [ ] Give separate explicit approval before a public GitHub Release, binary upload, website download or deployment. An engineering build is not release approval.

Current result: **NOT READY — RELEASE BLOCKED** until licensing and mandatory owner evidence are resolved.


Project Freedom continues this checkpoint as engineering build 1.3.6. See ASCENSION_FREEDOM_GUIDE.md for the new theme and authorization policy, and ASCENSION_FREEDOM_RESULTS.md for its separate verification evidence. The 1.3.5 artifacts and results remain historical; their passing checks do not qualify 1.3.6. All unresolved owner release gates still apply.
