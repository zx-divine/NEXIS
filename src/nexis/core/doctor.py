"""On-demand diagnostics. No microphone, screen capture, cloud probes or repairs.

Reports contain fixed explanations and numeric aggregates, never raw settings,
paths, model IDs, device names, logs, credentials or conversation content.
"""

from datetime import datetime, timezone
import importlib
import json
import os
from pathlib import Path
import platform
import shutil
import sqlite3
import tempfile

from nexis import __version__, DISPLAY_VERSION
from nexis.core.access import require_access
from nexis.core.models import detect_model
from nexis.core.providers import validate_profile
from nexis.platform.system import SystemSampler
from nexis.storage.database import DEFAULTS

STATUSES = frozenset({"PASS", "FAIL", "WARNING", "NOT TESTED", "USER ACTION REQUIRED", "UNAVAILABLE"})


def check(category, title, status, detail):
    if status not in STATUSES:
        raise ValueError("Unknown diagnostic status.")
    return {"category": category, "check": title, "status": status, "detail": detail}


def collect(db, directory, cancel, *, profile=None, runtime=None):
    runtime = runtime or {}
    rows = []

    def add(category, title, status, detail):
        if cancel.is_set():
            raise ValueError("Diagnostics cancelled. Previous results were retained.")
        rows.append(check(category, title, status, detail))

    add("Application", "Startup", "PASS", "The application reached the diagnostics worker. This is not a clean-machine certification.")
    try:
        healthy = db.rows("PRAGMA quick_check(1)")[0]["quick_check"] == "ok"
        add("Application", "Database", "PASS" if healthy else "FAIL", "SQLite integrity check completed." if healthy else "Preserve the database and restore a verified backup; no repair was attempted.")
        invalid = 0
        for row in db.rows("SELECT key,value FROM settings"):
            if row["key"] in DEFAULTS:
                try:
                    value = json.loads(row["value"])
                    invalid += type(value) is not type(DEFAULTS[row["key"]])
                except (ValueError, TypeError):
                    invalid += 1
        add("Application", "Configuration", "WARNING" if invalid else "PASS",
            "Some stored values have invalid JSON/types; safe defaults are used. Preserve the database before editing settings." if invalid else "Stored known settings have valid JSON types. Semantic validation still occurs at use.")
    except sqlite3.Error:
        add("Application", "Database", "FAIL", "SQLite is unavailable or locked. Preserve existing files and retry after stopping active work.")
    try:
        with tempfile.TemporaryFile(prefix="nexis-doctor-", dir=directory) as stream:
            stream.write(b"NEXIS diagnostic write probe")
            stream.flush()
        add("Application", "Writable data storage", "PASS", "A temporary local write completed and was closed.")
    except OSError:
        add("Application", "Writable data storage", "FAIL", "The data directory could not accept a temporary file. Check free space and Windows folder permissions.")
    for module in ("PySide6.QtCore", "vosk", "sounddevice", "webrtcvad", "win32crypt"):
        try:
            imported = importlib.import_module(module)
            if module == "webrtcvad":
                imported.Vad(2)
            status, detail = "PASS", "Runtime import/initialization succeeded; physical operation is a separate test."
        except Exception:
            status, detail = "UNAVAILABLE", "Runtime component unavailable. Repair from the verified installer; no automatic installation was attempted."
        add("Application", "Dependency: " + module, status, detail)
    add("Application", "Workers", "NOT TESTED", "Running-thread counts do not prove responsiveness. Use cancellation and the owner checklist for active jobs.")
    add("Application", "Recent crashes", "NOT TESTED", "Private logs were not read or exported. Review the local log on this PC when investigating a crash.")

    model = detect_model(db.setting("voice_model_path"), directory)
    add("Voice", "Offline STT model", "PASS" if model else "UNAVAILABLE",
        "Required model files are present. Decoder integrity and speech accuracy require separate model/audio tests." if model else "Open Voice Studio to configure the verified English model. No model was downloaded.")
    try:
        import sounddevice as sd
        from nexis.platform.speech import default_input

        preference = db.setting("audio_input")
        devices = list(sd.query_devices())
        missing = bool(preference and not any(d["name"] == preference and d["max_input_channels"] > 0 for d in devices))
        default_input(sd, preference)
        add("Voice", "Microphone", "WARNING" if missing else "USER ACTION REQUIRED",
            "Saved microphone is missing; the voice engine can use Windows default. Reconnect or select a device, then test normal speech." if missing else "An input device is enumerated. Use Voice Studio to test permission, noise, levels, clipping and normal-volume transcription; no capture occurred.")
    except Exception:
        add("Voice", "Microphone", "UNAVAILABLE", "No usable input device could be enumerated. Check connection and Windows microphone privacy, then refresh Voice Studio.")
    voices = runtime.get("windows_voice_count", 0)
    add("Voice", "Speaker / TTS", "USER ACTION REQUIRED" if voices else "NOT TESTED",
        "Windows voice enumeration is available. Test the selected speaker and confirm the sentence is audible." if voices else "Open Voice Studio, initialize Windows speech, test the selected speaker and confirm actual audible output.")
    add("Voice", "Wake word", "USER ACTION REQUIRED" if db.setting('wake_word_enabled') else "NOT TESTED", "Local Vosk Hey NEXIS phrase listening is implemented and opt-in. Review Always Active, microphone permission, selected model and confidence; test real speech and false activations on this PC. Doctor does not start capture.")
    add("Voice", "Languages", "WARNING", "Bundled model targets English (US). Hindi/Hinglish STT and physical English accuracy are not qualified.")

    try:
        config = validate_profile(profile) if profile else None
        if config and not config.get("model", "").strip():
            config = None
    except (ValueError, TypeError, KeyError):
        config = None
    add("AI", "Selected configuration", "PASS" if config else "USER ACTION REQUIRED",
        "Selected provider configuration validates locally; this does not verify authentication, model availability or a live connection." if config else "Select a provider and model in AI & Models. Unreadable encrypted profiles are preserved.")
    add("AI", "Authentication / model / network", "NOT TESTED", "Use Test selected provider for one explicit inference request. No automatic network request or provider fallback occurred.")

    sample = SystemSampler().sample()
    metrics = {"logical_cpus": os.cpu_count(), "ram_total_mb": sample.total_memory_mb,
               "ram_percent": sample.memory}
    try:
        metrics["data_volume_free_mb"] = round(shutil.disk_usage(directory).free / 1048576, 1)
        add("System", "Disk space", "WARNING" if metrics["data_volume_free_mb"] < 512 else "PASS", "Free space on the application data volume was measured; no files were removed.")
    except OSError:
        add("System", "Disk space", "UNAVAILABLE", "Free disk space could not be measured.")
    add("System", "OS / RAM / CPU", "PASS" if sample.total_memory_mb is not None else "WARNING", "See numeric system metrics. CPU load requires a timed sample in PC Health; temperatures are not available here.")
    add("System", "Startup registration", runtime.get("startup_status", "NOT TESTED"),
        "The current Windows sign-in registration was compared with this executable; no registry setting was changed." if runtime.get("startup_status") == "PASS" else "Startup is disabled, unavailable or has not been checked. Review the separate General opt-in.")
    add("System", "Website opener", "PASS" if os.name == "nt" else "UNAVAILABLE", "Windows URL association and explicit browser discovery are implemented. Native launch and page loading need separate evidence.")

    muted = db.setting("microphone_muted")
    capturing = bool(runtime.get("capture_active"))
    add("Privacy", "Hard Mute", "FAIL" if muted and capturing else "PASS",
        "Mute is latched but a capture worker is still active; stop work and verify device release." if muted and capturing else "Mute preference and current capture snapshot are consistent. This snapshot does not certify cancellation races.")
    add("Privacy", "Microphone state", "WARNING" if capturing else "PASS", "Capture worker active from Talk/test or opted-in wake listening." if capturing else "No microphone capture worker is active at this snapshot.")
    add("Privacy", "Screen permission", "WARNING" if db.setting("screen_awareness_enabled") else "PASS", "Screen feature enabled; each image still needs capture, preview and separate transmission approval." if db.setting("screen_awareness_enabled") else "Screen feature disabled. No screen was captured by diagnostics.")
    add("Privacy", "Approved folders", "PASS", "Only the approved-folder count is exported; paths and indexed contents are excluded.")
    add("Privacy", "Local memory", "PASS", "Memory is enabled for explicit saves only; it is not automatically included in cloud context." if db.setting("memory_enabled") else "Memory is off; existing notes are preserved and new saves/imports are blocked.")
    try:
        require_access(db, "terminal_commands")
        enforced = False
    except ValueError:
        enforced = True
    add("Privacy", "Permission enforcement", "PASS" if enforced else "FAIL", "Arbitrary terminal execution is rejected by the capability gate; full security regressions are separate evidence.")
    return {"format": 1, "version": __version__, "display_version": DISPLAY_VERSION,
            "generated_utc": datetime.now(timezone.utc).isoformat(),
            "os": platform.system(), "architecture": platform.machine(), "checks": rows,
            "metrics": metrics, "approved_folder_count": len(db.setting("search_roots")),
            "network_requests_in_this_check": 0}


def export_report(report, target, directory):
    target = Path(target)
    if target.suffix.casefold() != ".json" or target.resolve().is_relative_to(Path(directory).resolve()):
        raise ValueError("Choose a .json report outside the application data directory.")
    if target.exists():
        raise ValueError("Choose a new filename; existing files are not overwritten.")
    # The report originates only from collect()/fixed provider-test results. No log
    # text or arbitrary profile dictionary is appended by the GUI.
    with target.open("x", encoding="utf-8") as stream:
        json.dump(report, stream, indent=2)


def provider_test(db, profile, cancel):
    """One user-initiated inference, never tools, memory or conversation history."""
    from nexis.core.provider_manager import generate
    from nexis.core.providers import ProviderError

    require_access(db, "network_actions")
    try:
        value = generate(validate_profile(profile), [{"role": "user", "content": "Reply with exactly: NEXIS diagnostic test OK."}], cancel)
        if cancel.is_set():
            raise ValueError("Provider diagnostic cancelled; a submitted remote request cannot be recalled.")
        status = "PASS" if value.get("text", "").strip() else "FAIL"
        return check("AI", "Explicit inference", status, "Selected endpoint returned a non-empty response. This proves this request only; no upstream provider identity or future availability is certified." if status == "PASS" else "The selected endpoint returned no text. Review model and protocol settings.")
    except ProviderError as exc:
        # Category is controlled by our adapter, never an upstream body/message.
        allowed = {"authentication", "rate_limit", "timeout", "connection", "network", "model", "server", "empty_response", "endpoint", "tls", "dns"}
        category = exc.category.lower() if exc.category.lower() in allowed else "provider"
        return check("AI", "Explicit inference", "FAIL", "Selected provider request failed (" + category + "). Review AI & Models and retry explicitly; no fallback occurred.")
