# Run on Windows from the project root: python -m PyInstaller NEXIS.spec
from pathlib import Path
from importlib.util import find_spec
import json
import runpy
from PyInstaller.utils.hooks import collect_dynamic_libs, collect_data_files, copy_metadata

root = Path(SPECPATH)
# Default offline speech is mandatory in release builds. User-selected alternatives stay private.
prepare = runpy.run_path(str(root / "scripts/prepare_model.py"))
model_manifest = json.loads((root / "assets/models/manifest.json").read_text())
prepare["verify_model"](root / "assets/models" / model_manifest["model"]["id"], model_manifest)
voice_binaries = []
for package in ("webrtcvad", "_webrtcvad"):
    if find_spec(package) is None:
        raise RuntimeError("Required voice activity runtime missing: " + package)
for package in ("vosk", "_sounddevice_data"):
    if find_spec(package) is None:
        raise RuntimeError("Required audio runtime missing: " + package)
    voice_binaries.extend(collect_dynamic_libs(package))
a = Analysis([str(root / "scripts" / "entry.py")],
             pathex=[str(root / "src"), str(root / ".provider-deps"), str(root / ".dev-deps"), str(root / ".dev-deps/win32"), str(root / ".dev-deps/win32/lib")],
             binaries=voice_binaries, datas=[(str(root / "assets/models" / model_manifest["model"]["id"]), "nexis/assets/models/" + model_manifest["model"]["id"])] + [(str(root / "assets/models" / name), "nexis/assets/models") for name in ("manifest.json", "LICENSE-Apache-2.0.txt", "NOTICE.txt")] + copy_metadata("vosk") + copy_metadata("sounddevice") + copy_metadata("cffi") + copy_metadata("webrtcvad-wheels") + copy_metadata("PySide6-Essentials") + copy_metadata("shiboken6") + copy_metadata("pywin32") + copy_metadata("Send2Trash") + copy_metadata("websocket-client") + collect_data_files("google.genai") + copy_metadata("google-genai") + copy_metadata("google-auth") + [(str(root / "assets/THIRD_PARTY_NOTICES.txt"), "."), (str(root / "assets/licenses"), "licenses"), (str(root / "src/nexis/ui/theme.qss"), "nexis/ui"),
                 (str(root / "assets/branding/NEXIS_logo.png"), "nexis/assets/branding"),
                  (str(root / "assets/branding/NEXIS.ico"), "nexis/assets/branding"),
                  (str(root / "LICENSE"), "."),
                  (str(root / "assets/RELEASE_CHANNEL.txt"), ".")],
             hiddenimports=["webrtcvad", "_webrtcvad", "vosk", "sounddevice", "win32crypt", "pythoncom", "win32com.client", "win32gui", "win32process", "google.genai", "google.genai.client", "google.genai.models", "google.genai.types", "google.genai.errors", "send2trash", "websocket"], hookspath=[str(root / "scripts/pyinstaller_hooks")], runtime_hooks=[],
             excludes=["PyQt5", "PyQt6", "tkinter", "matplotlib", "numpy", "pandas", "openpyxl", "lxml", "PIL", "scipy", "sklearn", "torch", "IPython", "jupyter", "pytest", "setuptools", "pip", "wheel", "OpenSSL", "PySide6.QtWebEngineCore", "PySide6.QtWebEngineWidgets",
                       "PySide6.QtWebEngineQuick", "PySide6.QtQml", "PySide6.QtQuick", "PySide6.QtPdf", "__main__"], noarchive=False)
# Qt 6.12 uses Windows' ICU API. A development runtime's versioned ICU DLL
# can shadow the OS forwarder and cause "procedure not found" at QtCore import.
a.binaries = [entry for entry in a.binaries
              if Path(entry[0]).name.lower() not in {"icuuc.dll", "icudt78.dll"}]
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="NEXIS",
          debug=False, bootloader_ignore_signals=False, strip=False, upx=False,
          console=False, uac_admin=False, version=str(root / "scripts/version.txt"),
          icon=str(root / "assets/branding/NEXIS.ico"))
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name="NEXIS")
