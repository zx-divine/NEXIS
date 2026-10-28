"""On-demand WinRT radio bridge through Windows PowerShell's built-in .NET projection.

Only fixed enums enter the program. No user text, file, adapter name or shell command
is evaluated. A named cancellation event gates every state submission. Windows owns
access approval; requests never elevate. No helper runs at idle.
"""
import base64
import ctypes
from ctypes import wintypes
import json
import os
from pathlib import Path
import subprocess
from time import monotonic
from uuid import uuid4

_access_allowed = False
PROGRAM = r"""
$ErrorActionPreference = 'Stop'
$OutputEncoding = [Console]::OutputEncoding = [Text.UTF8Encoding]::new($false)
$cancel = [Threading.EventWaitHandle]::OpenExisting('__EVENT__')
try {
 Add-Type -AssemblyName System.Runtime.WindowsRuntime
 $null = [Windows.Devices.Radios.Radio,Windows.System.Devices,ContentType=WindowsRuntime]
 $method = [System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object {
   $_.Name -eq 'AsTask' -and $_.IsGenericMethodDefinition -and $_.GetParameters().Count -eq 1 -and
   $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1'
 } | Select-Object -First 1
 function Await($operation, $type) {
   $task = $method.MakeGenericMethod($type).Invoke($null, @($operation))
   while (-not $task.Wait(80)) { if ($cancel.WaitOne(0)) { throw 'Cancelled' } }
   if ($cancel.WaitOne(0)) { throw 'Cancelled' }
   return $task.Result
 }
 $radios = @(Await ([Windows.Devices.Radios.Radio]::GetRadiosAsync()) ([Collections.Generic.IReadOnlyList[Windows.Devices.Radios.Radio]]))
 $selected = @($radios | Where-Object { $_.Kind.ToString().ToLowerInvariant() -eq '__KIND__' })
 if ($selected.Count -eq 0) { throw 'Unsupported or unavailable radio hardware' }
 $access = 'ReadOnly'
 if ('__STATE__' -ne 'read') {
   $access = '__ACCESS__'
   if ($access -ne 'Allowed') { $access = (Await ([Windows.Devices.Radios.Radio]::RequestAccessAsync()) ([Windows.Devices.Radios.RadioAccessStatus])).ToString() }
   if ($access -ne 'Allowed') { throw ('Windows radio access: ' + $access) }
   foreach ($radio in $selected) {
     if ($cancel.WaitOne(0)) { throw 'Cancelled before state submission' }
     $result = Await ($radio.SetStateAsync([Windows.Devices.Radios.RadioState]::__STATE__)) ([Windows.Devices.Radios.RadioAccessStatus])
     if ($result.ToString() -ne 'Allowed') { throw ('Windows radio state request: ' + $result.ToString()) }
   }
   $until = [DateTime]::UtcNow.AddSeconds(5)
   do {
     if ($cancel.WaitOne(0)) { throw 'Cancelled after state submission; check Windows radio state' }
     $pending = @($selected | Where-Object { $_.State.ToString().ToLowerInvariant() -ne '__STATE__' })
     if ($pending.Count -eq 0) { break }
     Start-Sleep -Milliseconds 100
   } while ([DateTime]::UtcNow -lt $until)
 }
 $states = @($selected | ForEach-Object { $_.State.ToString().ToLowerInvariant() })
 @{ states=$states; access=$access; verified=('__STATE__' -eq 'read' -or @($states | Where-Object { $_ -ne '__STATE__' }).Count -eq 0) } | ConvertTo-Json -Compress
} catch {
 @{ verified=$false; message=$_.Exception.Message } | ConvertTo-Json -Compress
} finally { $cancel.Dispose() }
"""


def remote_session():
    if os.name != "nt":
        return False
    # SM_REMOTESESSION detects standard RDP; third-party remote tools cannot be inferred.
    return bool(ctypes.windll.user32.GetSystemMetrics(0x1000))


def set_state(kind, state, cancel):
    if kind not in {"wifi", "bluetooth"} or state not in {"on", "off", "read"}:
        raise ValueError("Choose wifi or bluetooth and on or off.")
    if os.name != "nt":
        raise ValueError("Radio control is available only on Windows.")
    if cancel.is_set():
        raise ValueError("Radio request cancelled before starting.")
    if state == "off" and remote_session():
        raise ValueError("Turning this radio off could disconnect the active remote session or its input devices. Use Windows locally to change it; no radio request was submitted.")
    global _access_allowed
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.CreateEventW.argtypes = [ctypes.c_void_p, wintypes.BOOL, wintypes.BOOL, wintypes.LPCWSTR]
    kernel.CreateEventW.restype = wintypes.HANDLE
    kernel.SetEvent.argtypes = [wintypes.HANDLE]
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    event_name = "Local\\NEXIS-Radio-" + uuid4().hex
    handle = kernel.CreateEventW(None, True, False, event_name)
    if not handle:
        raise OSError("Windows cancellation event is unavailable.")
    helper = None
    try:
        program = PROGRAM.replace("__EVENT__", event_name).replace("__KIND__", kind).replace("__STATE__", state)
        program = program.replace("__ACCESS__", "Allowed" if _access_allowed else "Request")
        command = Path(os.environ.get("SystemRoot", "C:/Windows")) / "System32/WindowsPowerShell/v1.0/powershell.exe"
        if not command.is_file():
            raise ValueError("Windows PowerShell WinRT support is unavailable. Use Windows Settings.")
        if cancel.is_set():
            raise ValueError("Radio request cancelled before helper launch.")
        helper = subprocess.Popen([str(command), "-NoLogo", "-NoProfile", "-NonInteractive", "-EncodedCommand",
                                   base64.b64encode(program.encode("utf-16le")).decode("ascii")],
                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=False,
                                  creationflags=subprocess.CREATE_NO_WINDOW)
        deadline = monotonic() + 25
        while True:
            if cancel.is_set() or monotonic() >= deadline:
                kernel.SetEvent(handle)
                helper.kill()
                helper.communicate(timeout=3)
                raise ValueError("Radio operation cancelled or timed out. An already submitted Windows request may have taken effect; check Windows Settings.")
            try:
                stdout, _ = helper.communicate(timeout=.08)
                break
            except subprocess.TimeoutExpired:
                continue
        try:
            result = json.loads(stdout.decode("utf-8-sig"))
        except (ValueError, UnicodeError):
            raise ValueError("Windows radio API could not return a readable result. No completion is claimed.") from None
        _access_allowed = result.get("access") == "Allowed"
        if not result.get("verified"):
            # OS error text stays local and is not persisted in audit logs.
            raise ValueError("Radio state was not verified. " + result.get("message", "Hardware or Windows policy may prevent this change."))
        result.update(kind=kind, requested_state=state, message="Windows radio state verified by readback.")
        return result
    finally:
        kernel.SetEvent(handle)
        if helper is not None and helper.poll() is None:
            helper.kill()
            helper.communicate(timeout=3)
        kernel.CloseHandle(handle)
