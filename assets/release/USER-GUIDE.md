# Using this NEXIS V1 candidate

## First run and modes

Enter your preferred name, read the capability disclosure, choose permissions and
screen assistance, and optionally test the microphone/speaker and provider. Setup
offers six appearance choices with live Launch/Orb/Chat/Voice previews. The Settings
gear remains visible. Completing setup is saved; normal launches do not repeat it.
Skipped physical/provider tests are not marked passed. Name entry is required.
The API page requires either a saved default provider/model or an explicit
Manual / Offline choice. You can configure AI later in Settings. The chosen name
is supplied as data to configured AI conversations; “What is my name?” can also
be answered locally. Keys are never bundled or shown after saving.

The welcome page offers Voice, Chat and Manual / Offline. Header controls switch
modes without restarting or discarding chat context. Leaving Voice stops capture.
Home returns to the welcome page. Tools opens the secondary page list.

## Chat and AI providers

Use AI Providers to configure an account/endpoint/model, explicitly save/select it,
refresh models and test inference. Supported protocols include compatible gateways
(OpenAI-compatible, OpenRouter and OmniRoute), native Gemini and explicit Ollama
configuration. You supply authorized credentials; none are included. Streaming,
timeouts and advanced API controls depend on the selected provider/model.

Ollama requires an existing server and suitable model. NEXIS never installs or
starts one silently. Some Ollama configurations route to cloud models; localhost
does not alone prove offline inference. There is no automatic provider fallback.

Chat messages stay in memory until **Save conversation**. A reviewed title saves
the completed chat locally as private plaintext. Saved conversations can be searched,
previewed, explicitly reopened, exported with personal data and deleted after
confirmation. **New conversation** clears the current draft/context and preserves
saved chats. Keep credentials and sensitive material out of saved chats.

## Voice

Press Talk, wait for the visible listening state and speak. Stop and transcribe
finishes a turn; Cancel discards capture. The default English Vosk model is local.
Provider conversation requires the configured connection. Windows supplies the
default SAPI voice; advanced device/voice choices and diagnostics are in Settings.
Interruption uses the explicit interrupt/stop controls in this candidate.

Hard mute stops capture/speech and cancels pending work. Waking the microphone
does not record automatically. The setup phrase test is local input verification;
it does not itself enable wake listening. Target-app dictation and automatic
barge-in remain incomplete.

## Always Active and “Hey NEXIS”

Open Always Active in the header, enable standby/orb/tray, and separately select
local Hey NEXIS listening. Also grant Microphone access in Settings > Permissions.
These choices are offered in first-run setup and are off by default. No capture
starts inside onboarding. Windows sign-in startup is a separate General setting.

Say **“Hey NEXIS”**, pause until the listening indicator appears, then speak your
command. The local phrase detector requires both words with configurable minimum
confidence. Standby audio stays local in memory and is discarded. Only speech
captured after activation enters the existing command/provider pipeline. That
pipeline keeps its permissions and sensitive-action approvals. For radio changes,
review the transcript and press Retry / send transcript yourself.

Minimize to keep NEXIS available in the tray; Close or Exit NEXIS shuts it down.
Hard mute stops the listener and discards queued commands. Wake resumes listening
only if you previously opted in. Tray controls also let you pause wake listening.
Listening pauses during other speech/capture/command tasks and Windows busy,
fullscreen, locked or unavailable states. Errors stop automatic retries; correct
the device/model/permission and click Retry wake listening. No audio is saved.

This is local Vosk phrase spotting, not a custom trained neural wake model. Use
the bundled English model. A pause after the wake phrase is required; speaking
the whole command in one uninterrupted sentence is not supported in this candidate.
There is no speech barge-in during replies. Test your room, normal voice and false
activations before relying on it; synthetic tests do not certify live accuracy.

## Manual tools and permissions

Open Manual to use registered commands. `help` lists supported commands. Examples
include `open notepad` and `open https://www.youtube.com`, subject to capability
grants and risk checks. Files searches only approved folders. Other tools include
supported window/volume/settings integrations, local memory, history and workflows.
Typed or AI requests share the execution layer's validation and authorization.

Routine approved low-risk actions avoid repeated confirmation. Destructive or
sensitive actions retain fresh review. Arbitrary shell/script execution, purchases
and automatic message sending are not available. NEXIS never bypasses Windows UAC
or authentication. Screen assistance requires its own permission, capture preview,
configured vision support and explicit transmission approval.

## Settings, launcher and background use

General includes preferred name, launch mode and a global command launcher.
Ctrl+Space is the default; alternative supported combinations are selectable.
Registration conflicts are reported and Ctrl+K remains available inside NEXIS.
The launcher opens the command interface and never executes input by itself.

The eight Settings categories organize existing controls. Integrations that have
not been built are labeled as unavailable. Optional companion/tray controls expose
Open, Talk, mute, pause/wake and exit behavior within the current implementation.
Local opt-in wake listening is described above. Reduce motion or lower active animation
FPS for lower resource use. Normal Windows cursor behavior is preserved.

NEXIS Doctor runs explicit local diagnostics and can export redacted results.
Device enumeration or synthesized completion does not prove audibility or speech
accuracy; perform the manual checks before relying on voice.
# Living Particle Core and setup recovery

See `LIVING-CORE-CANDIDATE.md` for the new particle core, interrupted-setup recovery,
optional permissions, Manual / Offline setup and side-by-side candidate details.
Settings → Appearance selects all six themes and reduced motion. Hard mute stops
microphone-driven movement. Speaking follows Windows speech activity; its movement
does not measure the loudness of your speakers.

