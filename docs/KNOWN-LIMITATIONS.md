# Known limitations and current feature status

**NOT READY for full-feature public NEXIS V1.** This candidate is for personal
testing. Status applies to the capability's full requested scope; a control or
fixture result is not proof of a working live integration.

| Feature | Current status | Scope and outstanding work |
|---|---|---|
| Identity, window, welcome, setup, mode switching | Verified working | Automated UI/native checks on this Windows 10 host; manual accessibility and clean-machine checks remain. |
| Settings, six themes, orb and measured HUD | Verified working | Existing controls and previews; advanced fonts/language/notification/integration settings are incomplete. |
| 1. Hey NEXIS wake word | Partially working | Local Vosk phrase listener, confidence control, hard mute, permissions and command handoff implemented. Say wake phrase, pause for indicator, then speak. Two synthetic voices and negative fixtures are tested; real-room accuracy, false activation rate and long sessions require qualification. No custom trained wake model or one-sentence command capture. |
| 2. Natural voice | Partially working | Local STT/backend, VAD, SAPI and explicit interruption exist. Physical input/output, device recovery and automatic barge-in are unqualified/incomplete. |
| 3. Chat and launcher | Partially working | Chat/provider pipeline, explicit saved searchable chats and native hotkey lifecycle verified; live inference/physical keypress and broader history policies remain. |
| 4. Long-term memory | Partially working | Explicit local notes/edit/search/delete/export; no unapproved automatic sensitive memory or complete automatic personalization. |
| 5. Context awareness | Partially working | Supported visible-window tools and approved resources; full task/document context not built. Titles never establish file contents. |
| 6. System control | Partially working | Supported app/website/window/volume/radio/settings integrations; hardware-specific brightness/power/elevation coverage incomplete. |
| 7. File management | Partially working | Approved-root search and supported reviewed operations; broader document summaries and all filesystem/race cases require qualification. |
| 8. Screen understanding | Partially working | Capture/preview/consent/adapter workflow; actual vision analysis blocked until an authorized capable provider/model is configured and tested. |
| 9. Calendar/reminders/alarms | Not implemented | No durable reminder scheduler or calendar adapters. |
| 10. Email/messages | Not implemented | No authenticated inbox/message integration or sending workflow. |
| 11. Web search with citations | Partially working | Browser search/opening only; source-returning search/citations/freshness pipeline absent. |
| 12. Smart home/IoT | Not implemented | No paired Home Assistant/device adapter. |
| 13. Task automation | Partially working | Bounded validated workflows, editor/dry-run/pause/cancel and logs; scheduling/briefing actions absent. |
| 14. Code assistant | Partially working | Configured AI can discuss/generate code; project execution/isolated approved scripts not built. Arbitrary shell is denied. |
| 15. Notification digest | Not implemented | Live weather/news/calendar/app-notification digest absent. |
| 16. Multilingual | Partially working | Unicode/provider text supported; default recognition is English. Hindi/Hinglish STT resources and physical qualification incomplete. |
| 17. Document tools | Partially working | Bounded UTF-8 txt/md index; PDF/DOCX read/write toolset absent. |
| 18. Media | Partially working | Volume and website opening; transport/player integration coverage incomplete. |
| 19. Focus mode | Not implemented | No focus sessions, breaks or restriction engine. |
| 20. Futuristic HUD | Verified working | Actual state/CPU/RAM rendering and reduced-motion/minimize suspension; full voice/model workload profiling remains. |
| 21. Privacy | Partially working | Hard mute, capture consent, protected credentials, explicit memory/chat, export/deletion and risk checks; full release security/retention qualification incomplete. |
| 22. Plugins/skills | Not implemented | Internal typed registry exists; no safe external plugin discovery/install/host. |
| 23. Cross-device sync | Not implemented | No mobile companion, pairing server, encrypted sync or revocation implementation. |
| 24. Smart permissions | Verified working | Tested execution-layer controls for implemented tools; unsupported/new tools cannot inherit blanket authorization. No absolute security certification is claimed. |
| 25. Offline mode | Partially working | Supported local manual commands/files/STT/TTS; no full offline AI without a functional local model. Reminders absent. |
| Voice-to-typing dictation | Not implemented | No target-bound, password-safe insertion engine. Clipboard copying is not dictation. |
| Clusters/multi-agent orchestration | Not implemented | Existing sequential workflows do not constitute specialized agent clusters. |
| NEXIS Doctor | Partially working | Explicit local checks/redacted export; real hardware/provider and future subsystems need independent qualification. |
| Background/tray operation | Partially working | Optional companion/tray lifecycle; lock/suspend, long-running capture and physical device cases remain unqualified. |
| Real cloud/local AI inference | Blocked for qualification | Requires an authorized working account/endpoint/model or installed local server/model. None is bundled with credentials. |

Saved chats are plaintext and bounded to 100 chats, 200 completed messages and
64,000 text characters per chat. Secret-pattern rejection is not comprehensive
data-loss prevention. Exports/backups may retain deleted data. DPAPI credentials
are bound to the Windows account; another account may need reconnection.

This is a source-only snapshot. No installer, launcher, portable archive or runtime
is included. Physical voice, live provider reliability, remaining mandatory features
and final licensing/security qualification are still open.
