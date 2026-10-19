"""Build into a separate directory; preserve the existing distribution before promotion."""
import json
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
work = ROOT / ".packaging-work-permission-overhaul"
reports = ROOT / "docs/installer-overhaul"
reports.mkdir(parents=True, exist_ok=True)
command = [sys.executable, "scripts/dev.py", "build", "--noconfirm", "--workpath",
           str(work / "build"), "--distpath", str(work / "output"), "NEXIS.spec"]
with (reports / "build.log").open("w", encoding="utf-8") as log:
    result = subprocess.run(command, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT, timeout=1200)
(reports / "build-result.json").write_text(json.dumps({"exit_code": result.returncode}))
if result.returncode:
    raise SystemExit("Build failed. Inspect docs/installer-overhaul/build.log; previous distribution retained.")
source = (work / "output/NEXIS").resolve()
target = (ROOT / "dist/NEXIS").resolve()
backup = (work / "previous-NEXIS-1.3.1").resolve()
if not all(path.is_relative_to(ROOT.resolve()) for path in (source, target, backup)):
    raise SystemExit("Unsafe artifact path; promotion stopped.")
if not (source / "NEXIS.exe").is_file():
    raise SystemExit("Build did not produce the executable.")
if target.exists():
    if backup.exists():
        raise SystemExit("Previous build backup exists. Review it before promotion; nothing overwritten.")
    shutil.move(str(target), str(backup))
shutil.move(str(source), str(target))
for license_file in (ROOT / "assets/licenses").iterdir():
    destination = target / "_internal/licenses" / license_file.name
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(license_file, destination)
print("Build completed; previous distribution preserved. New executable: dist/NEXIS/NEXIS.exe")
