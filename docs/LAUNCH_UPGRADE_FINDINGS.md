# Launch upgrade: pre-implementation findings — 19 October 2026

Baseline commit: b2a0cac595c48ee3e448660db7c5f4d4d5b458c8; local tree clean and remote main matched. A source archive is preserved locally under .verification-launch-v1.

Fresh baseline: **249 passed, 1 skipped** in 76.25 seconds. The skip requires Windows symlink privilege. Pytest also reported a local cache ACL warning; application tests passed. No owner data was used by tests.

## Architecture inspected

- scripts/entry.py → nexis.main.main: Qt application identity, per-user lock/data/logs, splash, SQLite, MainWindow, onboarding, then deferred services.
- MainWindow retains the Crimson HUD, page stack, cached QPainter reactor, settings, manual command workers, voice page and provider manager.
- VoicePage → VoiceWorker QThread → sounddevice/PortAudio mono int16 → cached Vosk model → transcript → OperatorWorker selected provider → SpeechService Windows SAPI COM apartment. Signals use turn generations; stopping discards late transcripts.
- Default model is the already bundled English vosk-model-small-en-us-0.15. Resource hashes/preflight and Windows installer/portable checks passed in the preceding milestone. This is not fresh microphone evidence.
- SQLite schema v3, parameterized storage, additive migration and DPAPI provider profiles remain. Tools are schema validated, scoped and permission checked. Ordinary installed-app classification was already repaired; preserve it.
- Inno is per-user, PyInstaller bundles Python, Qt, audio runtimes, model, artwork and notices. No always-on wake-word engine exists. No clean Windows machine without Python is available here.

## Reproduced findings

1. **Input processing gap (P0 investigation):** capture feeds all PCM to Vosk; there is no volume activation gate. There is also no calibration, sensitivity control, clipping feedback or bounded normalization. Code alone cannot establish why a user's normal speech is quiet. Actual selected-device levels and fresh speech are still required.
2. **Endpoint boundary risk:** the worker immediately stops on Vosk's first nonempty endpoint. Bundled model endpoint trailing-silence rules are 0.5/0.75/1 second. This can end a conversational turn at a natural pause; end-of-turn timing needs independent control. Capture currently includes initial audio, so no pre-roll loss has been demonstrated.
3. **Brand decoding reproduced:** two installed Windows voices synthesized “Hi NEXIS” into local WAV files without playback. Unmodified Vosk returned “hi nexus” for both; “Hi mate” remained “hi mate”, and two ordinary sentences decoded correctly. The actual vocabulary contains BOTH nexis and nexus. Therefore an out-of-vocabulary claim would be false. Grammar adaptation is supported, but replacing unrestricted recognition with a greeting-only grammar would break ordinary speech. Preserve raw results and guard any contextual greeting adaptation with acoustic decoder evidence and negative tests. The reported human “Hi mate” error has not been reproduced from a human recording.
4. **Session controls:** cancellation/state generations exist, but no latched Hard Mute or explicit sleep/wake control exists. Owned permission dialogs have no cancellation linkage. Add safe global stop behavior without enabling ambient capture.
5. **Performance:** native 1366×768 baseline: 1.495 s first window event excluding imports; about 100 MB working set without loaded ASR. Idle 14.57% of one CPU core, active 55.79%, mean reactor paint 12.57/14.00 ms. Reduced motion 1.03%, minimized 0%. These are this host, not an i3 benchmark. Expensive repeated arc drawing is a measured optimization candidate; retain artwork and reduced-motion behavior.
6. Provider streaming, context, endpoint validation, bounded IO, explicit switching and redaction already exist. No automatic transient retry/backoff exists. Do not retry ambiguous POST failures or partial streams and accidentally duplicate requests/tools.
7. SECURITY.md contains obsolete v1.1 statements claiming generative providers are absent. Update disclosures to match actual optional cloud text and DPAPI behavior.

## Verification boundary and priorities

First repair input diagnostics, bounded gain/noise handling, conversational endpoint timing, brand-context decoding, cancellation/Hard Mute and measured rendering cost. Then run negative/security regressions, controlled synthetic speech tests, final native package tests and source publication. Do not bump the existing 1.3.x version backward merely because this milestone is named “V1.0 launch”.

**Launch blocking until verified:** normal-volume human speech, representative “Hi NEXIS”, real selected-provider conversations, audible TTS and clean Windows 10/11 install/uninstall. Synthetic SAPI fixtures are reproducible engineering tests, not proof of human recognition accuracy. Hindi/Hinglish require a compatible validated model and representative audio; do not advertise them from the default English model. November 1 is a target, not an acceptance waiver.

Evidence remains local: .verification-launch-v1/baseline-tests.txt, baseline-performance.json, asr-baseline.json and synthetic WAV fixtures. No microphone was opened and no speaker played during this audit.
