# First Launch Recovery and Living Particle Core

This 1.4.0 rebuild is a **development/test candidate**. Use its matching external
engineering report, test evidence and SHA-256 manifest. No public release is approved.

## Setup recovery

The acknowledgment page now checks the actual consent value rather than Qt's
mandatory-field comparison with the initial checkbox value. A previously saved
checked acknowledgment no longer disables Next. Unchecked consent gives explicit
feedback. Capability grants, microphone tests, speaker tests and provider tests
remain optional. At the provider step, explicitly choose Manual / Offline to skip
AI configuration. Settings remains accessible during setup.

Validated navigation saves a local setup checkpoint. Interrupted setup resumes
with a usable Back history. Draft grants never authorize tools. Completion and its
related preferences are committed together only after validation succeeds. Failed
saves show a retry message; repeated Finish activation cannot duplicate setup.
No schema downgrade or profile reset is performed.

## Living core

340 cached Fibonacci-distributed surface points rotate in perspective. Tiny
antialiased dot sprites are drawn from back to front with depth-dependent size
and opacity, restrained atmosphere and occasional theme-accent highlights. There
is no opaque ball or decorative reactor ring. The official logo and icon stay
unchanged. All six existing themes apply through centralized appearance settings.

Idle, listening, thinking (controller name PROCESSING), speaking, executing, muted,
offline, permission required (WAITING_PERMISSION) and error are implemented.
Existing SUCCESS feedback is retained. Permission review takes precedence over
nested callbacks. Hard mute prevents listening/speech visuals. Capture preparation
does not claim listening; SAPI requests waiting to start do not claim speaking.
Current worker identity, cancellation and voice generations reject stale callbacks.

Windows SAPI provides speaking status and completion events here, **not PCM/RMS**.
Speaking therefore uses a documented activity-state fallback with gentle movement;
it is **not speech-amplitude-synchronized**. There is no invented speech waveform.
Authorized existing microphone levels use attack/release smoothing and expire
after 300 ms without fresh data. No additional recording or external transmission
is introduced. Reduced motion renders a static formation. Hidden/minimized cores
stop their timers; idle is capped at 8 FPS and activity at 30 FPS.

## Safe candidate installation

When the build report specifies a side-by-side label, the actual installer has a
separate test registration, program directory and shortcut group. Keep that default
directory to preserve the older installed program. The app title remains NEXIS.
Normal installed and portable launches still use your existing account profile.
For independent onboarding checks use the documented `--smoke-test <new-directory>
--offline-smoke` option; it uses disposable fixture storage and outputs screenshots.

Read the engineering report for exact native, DPI, performance and packaging
results. Automated native control activation is not human acceptance testing.
Windows 11, physical microphone/audibility, extended AI/audio load and an exact
side-by-side comparison with the previous approved demonstration may remain
unverified. The installer is unsigned; licensing and wider product gates remain.
