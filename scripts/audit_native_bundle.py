"""Check native imports and private-file exclusions in the built Windows folder."""
import json
import dis
import os
from pathlib import Path
import re
import site

ROOT = Path(__file__).resolve().parents[1]
site.addsitedir(str(ROOT / ".dev-deps"))
import pefile  # noqa: E402
from PyInstaller.archive.readers import CArchiveReader  # noqa: E402

folder = ROOT / "dist/NEXIS"
files = [p for p in folder.rglob("*") if p.is_file()]
by_name = {p.name.casefold() for p in files}
missing = []
imports = 0
for path in files:
    if path.suffix.lower() not in {".dll", ".pyd", ".exe"}:
        continue
    pe = pefile.PE(str(path), fast_load=True)
    pe.parse_data_directories(directories=[pefile.DIRECTORY_ENTRY["IMAGE_DIRECTORY_ENTRY_IMPORT"]])
    for entry in getattr(pe, "DIRECTORY_ENTRY_IMPORT", []):
        name = entry.dll.decode("ascii").casefold()
        imports += 1
        if name in by_name or name.startswith(("api-ms-", "ext-ms-")):
            continue
        system = Path(os.environ["SystemRoot"]) / "System32" / name
        redistributable = re.match(r"(?:msvcp|vcruntime|vcomp|concrt|libssl|libcrypto|libgcc|libstdc|qt6|python3|portaudio|libvosk)", name)
        if redistributable or not system.exists():
            missing.append({"importer": str(path.relative_to(folder)), "dependency": name})
    pe.close()
archive = CArchiveReader(str(folder / "NEXIS.exe"))
embedded = archive.open_embedded_archive("PYZ.pyz")
code = embedded.extract("nexis.core.tools")
instructions = list(dis.get_instructions(code))
start = next(i for i, item in enumerate(instructions) if item.opname == "LOAD_CONST" and item.argval == "app_directory")
end = next(i for i in range(start, len(instructions)) if instructions[i].opname == "POP_TOP")
folder_review = any(item.opname == "LOAD_ATTR" and item.argval == "MEDIUM" for item in instructions[start:end])
private = [str(p.relative_to(folder)) for p in files if p.suffix.lower() in {".dpapi", ".db", ".sqlite", ".wav", ".pfx", ".p12"} or p.name.startswith(".env")]
report = {"static_imports_checked": imports, "missing_dependencies": missing, "private_files": private, "compiled_installation_directory_requires_review": folder_review,
          "model_files": sum(p.is_file() for p in (folder / "_internal/nexis/assets/models/vosk-model-small-en-us-0.15").rglob("*")),
          "clean_machine_verified": False,
          "limitation": "Static PE imports plus this Windows host's OS DLL presence; not every delay-loaded DLL or clean Windows version."}
output = ROOT / "docs/installer-overhaul/native-bundle.json"
output.write_text(json.dumps(report, indent=2), encoding="utf-8")
print(json.dumps(report, indent=2))
raise SystemExit(1 if missing or private or not folder_review else 0)
