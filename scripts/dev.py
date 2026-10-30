"""Workspace-only launcher for the bundled runtime; ordinary installs use nexis."""

import runpy
import site
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[1]
site.addsitedir(str(root / ".provider-deps"))
site.addsitedir(str(root / ".dev-deps"))
sys.path[:0] = [str(root / ".provider-deps"), str(root / ".dev-deps"), str(root / "src")]
mode = sys.argv.pop(1) if len(sys.argv) > 1 else "run"
if mode in {"measure", "screenshot", "measure_hud"}:
    runpy.run_path(str(root / "scripts" / (mode + ".py")), run_name="__main__")
    raise SystemExit(0)
modules = {"run": "nexis.main", "test": "pytest", "lint": "ruff", "build": "PyInstaller"}
if mode not in modules:
    raise SystemExit("Choose run, test, lint or build")
if mode == "lint":
    sys.path.insert(0, str(root / ".tool-runtime"))
if mode == "build":
    import os

    # Optional isolated patched tooling; preserve historical dependency folders.
    secured = root / ".tool-deps/setuptools-secure"
    if secured.is_dir():
        sys.path.insert(0, str(secured))
    os.environ.setdefault("PYINSTALLER_CONFIG_DIR", str(root / ".packaging-cache"))
if mode == "test":
    sys.argv.extend(["-p", "pytestqt.plugin"])
    import os

    os.environ["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
runpy.run_module(modules[mode], run_name="__main__")
