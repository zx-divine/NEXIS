# Project Freedom — engineering build 1.3.6

This revision continues Project Ascension on `codex/project-ascension`. The original 1.3.4 launch candidate and verified 1.3.5 artifacts remain historical checkpoints. Nothing in this revision authorizes public distribution. The application licence, third-party compliance and owner release decision remain unresolved gates.

## Appearance

Open Settings Hub with the gear or Ctrl+comma, then select Desktop & Appearance. The six choices are OG Blood Red (new-install default), Midnight Black, Arctic White, Cyber Blue, Matrix Green and Custom Theme. The original red/black/gold HUD structure and reactor identity remain available.

Theme selection previews the running application, including painted navigation, charts, reactor, floating orb, menus and permission dialogs. Custom colors use six-digit hexadecimal values or a color picker. Text must achieve 4.5:1 contrast against the background and derived panels; primary/accent/status colors are adjusted for readability. Save appearance commits both theme preferences atomically. Revert restores the saved preference. Reset previews OG Blood Red; Save keeps the reset. General preferences do not accidentally save a theme draft.

Legacy `dark` and `light` settings continue to map to OG Blood Red and Arctic White respectively. Existing stored strings and unrelated preferences are preserved until deliberately saved. Missing custom preferences use validated defaults, with no destructive database migration. Theme colors contain no credentials; provider protection remains in the existing Windows DPAPI storage.

Reduced Motion remains in General and stops reactor, radar and hover animation timers. The appearance engine adds no timer or background renderer. Cached reactor textures are invalidated once per actual palette change, including when hidden or reduced motion is enabled. Qt controls retain keyboard navigation, focus indicators and normal DPI scaling. Independent voice diagnostics reads the saved appearance without migrating or writing the main profile when it starts. Its separate process does not receive live preview changes. Native Windows-owned dialogs and Settings retain Windows' own appearance.

## Why routine commands used to prompt

The former authorization rule was effectively `risk >= MEDIUM => ask`. Website resolution marked unfamiliar destinations as medium risk even when their HTTP(S) target was valid. The AI executor repeated that classification. Task Manager was grouped with sensitive launch names, and the utility wrapper was medium risk. AI multi-step plans and saved workflows added an enclosing approval before individual child approvals. Thus harmless requests could encounter prompts in several layers.

The new policy separates resolved operation risk, revocable category grants, the authorization decision, and Windows privileges. A manually typed request never grants blanket trust. All interfaces share the same command engine/tool executor and effect-boundary validation.

## Policy

| Operation | Default decision after category grants |
| --- | --- |
| Validated HTTP/HTTPS websites and domains | LOW; automatic. Explicit browser selection is preserved. |
| Fixed ordinary Windows applications and a recognized installed executable with verified PE, ordinary original identity, local Windows signature trust and acceptable manifest | LOW; automatic. Opening an app grants no permission for its later privileged actions. |
| Registered ordinary Store app | LOW after current Windows registration validation; sensitive identifiers retain review. |
| Unknown, unsigned/unverifiable, downloaded or sensitive executable | HIGH; fresh review or rejection. Location alone cannot establish trust. Renamed recognized script hosts/interpreters are rejected. |
| Existing approved ordinary document, approved folder, filename search, file metadata | LOW; automatic, with path, suffix and reparse-point checks. |
| Downloads, Documents, Desktop | LOW for validated Windows Known Folder navigation. This grants no search/content-inspection scope outside approved roots. |
| System information, PC Health, Task Manager, ordinary supported Settings pages | LOW; automatic. Opening a page changes no setting. |
| Explicit Wi-Fi/Bluetooth on/off | LOW after exact intent validation and system-settings grant; Windows access and readback still apply. |
| Bounded volume/mute, validated 1–10 website tabs, saved workflow envelope | MEDIUM operations explicitly allowed by policy. Workflow children still authorize independently. |
| Reading document contents into AI, clipboard writes through AI, creating/copying/moving/renaming data, installation-folder opening, consequential tab/window changes | Fresh approval where classified medium/high; approved roots and category grants still apply. |
| Security/account/authentication Settings pages, recycling an individual file, other sensitive supported operations | HIGH; fresh approval. Account/password/security changes themselves remain owner-completed in Windows or unsupported. |
| Critical destructive administration, formatting, bulk permanent deletion, disabling security, arbitrary script commands | No supported tool; blocked. CRITICAL decisions cannot be approved through the ordinary approval callback. |

The existing optional “Also confirm low-risk actions” preference remains user-controlled and preserved. It intentionally adds prompts, and dialogs explain that preference. There is no new remembered trust, universal allow-all setting, terminal execution capability or elevation bypass.

Approval dialogs show the operation, resolved resource, effect, risk, category, reason, reversibility and decline consequences. Approve and Deny are explicit, with Deny the default. Delegated wrappers prompt once. A workflow stops on denial/failure and retains earlier completed steps; it does not promise rollback. Nested workflows and arbitrary command chains are not accepted as saved workflow steps. Model plans validate every tool schema before execution.

## Windows radio controls

The on-demand bridge calls `Windows.Devices.Radios` through the Windows PowerShell .NET projection. Its program is fixed code; only validated radio/state enums and a generated cancellation-event name are substituted. It never evaluates a user command or accepts arbitrary script text. It runs with no profile, no visible console, no elevation and no idle helper. Local Windows code-signature checks likewise use native WinVerifyTrust with network retrieval disabled, not a new dependency.

An explicit single radio request is required. Model-generated radio changes unrelated to that request are refused. Voice recognition cannot alone authorize a radio change: review and send the recognized transcript. The same restriction propagates into a voice-triggered saved workflow. Hard Mute, cancellation, expiry and access revocation retain their existing effect. A named Windows cancellation event gates helper submissions, and a cancelled/timed-out helper is stopped. A Windows request already submitted before cancellation may have taken effect; NEXIS says to check the actual state instead of promising an undo.

Radio-off requests are blocked in detected standard RDP sessions with an explanation. Third-party remote-control software cannot be detected reliably; do not claim comprehensive remote-session detection. Hardware-disabled, absent, denied or disappearing radios fail honestly. Successful submission alone is insufficient: all selected radios must read back the requested state. Turning a radio on does not prove network connectivity or paired-device operation.

Microsoft references: [Radio access](https://learn.microsoft.com/en-us/uwp/api/windows.devices.radios.radio.requestaccessasync), [radio state changes](https://learn.microsoft.com/en-us/uwp/api/windows.devices.radios.radio.setstateasync), [WinVerifyTrust data and offline retrieval policy](https://learn.microsoft.com/en-us/windows/win32/api/wintrust/ns-wintrust-wintrust_data).

## Verification and operating limits

Use the current Freedom engineering results report for actual counts, artifacts and unresolved gates. Tests and mocked providers do not establish physical microphone/speaker operation, a live provider connection, clean-install compatibility or application licensing. Native radio “on while already on” readback is distinct from an off/on cycle, network reconnection, Bluetooth peripheral recovery or remote-session qualification.

Builds must use a fresh output directory and five passing independent regression processes of the same source fingerprint. Original distributions and the USB archive must not be overwritten or cleaned. The current development installer/portable artifacts are local review candidates, not a public release. No push or publication is authorized.
