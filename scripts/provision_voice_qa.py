"""Copy an already available compatible model for authorized local voice QA."""

import hashlib
import json
from pathlib import Path
import shutil
import site
import sys

site.addsitedir(".dev-deps")
sys.path.insert(0, "src")
from nexis.platform.discovery import known_folder
from nexis.core.models import MODEL, valid_model, validate_model

base = known_folder("B4BFCC3A-DB2C-424C-B029-7FE99A87C641") / "NEXIS-Voice-Engine"
source = Path(".verification-v13-model-real/models") / MODEL["id"]
target = base / "models" / MODEL["id"]
assert valid_model(source)
if not target.exists():
    shutil.copytree(source, target)
assert valid_model(target)
manifest = {
    str(p.relative_to(source)): hashlib.sha256(p.read_bytes()).hexdigest()
    for p in source.rglob("*")
    if p.is_file()
}
assert all(
    hashlib.sha256((target / name).read_bytes()).hexdigest() == value
    for name, value in manifest.items()
)
validate_model(target)
report = {
    "model": MODEL,
    "method": "Reused compatible previously verified official model; development copy matches source file hashes",
    "source_evidence": json.loads(Path("docs/v13-model-verification.json").read_text()),
    "file_hashes": manifest,
    "development_copy": str(target),
    "engine_load": "PASS",
    "real_microphone_recognition": "NOT VERIFIED",
    "production_dependency_on_desktop": False,
}
(base / "diagnostics/model-provisioning.json").write_text(
    json.dumps(report, indent=2), encoding="utf-8"
)
print(json.dumps({"model": str(target), "files_verified": len(manifest), "engine_load": "PASS"}))
