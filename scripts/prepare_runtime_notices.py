"""Retain installed runtime dependency licence files; no network or licence grants."""

import argparse
from importlib import metadata
import json
from pathlib import Path
import re
import site
import sys
import tomllib

ROOT = Path(__file__).resolve().parents[1]
for directory in (ROOT / ".dev-deps", ROOT / ".provider-deps"):
    if directory.is_dir():
        site.addsitedir(str(directory))
        sys.path.insert(0, str(directory))

from packaging.requirements import Requirement  # noqa: E402


def prepare():
    output = ROOT / "assets/licenses/runtime"
    output.mkdir(parents=True, exist_ok=True)
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    pending = list(project["project"]["dependencies"])
    records, processed_extras = {}, {}
    while pending:
        request = Requirement(pending.pop())
        if request.marker and not request.marker.evaluate({"extra": ""}):
            continue
        name = re.sub(r"[-_.]+", "-", request.name).lower()
        distribution = metadata.distribution(request.name)
        if distribution.version not in request.specifier:
            raise ValueError("Installed runtime dependency does not satisfy its requirement: " + name)
        extras = set(request.extras)
        if name in records and extras <= processed_extras[name]:
            continue
        processed_extras.setdefault(name, set()).update(extras)
        target = output / name
        target.mkdir(exist_ok=True)
        notices = []
        for item in distribution.files or ():
            label = item.name.casefold()
            if not (label.startswith(("license", "licence", "copying", "notice")) or "licenses" in item.parts):
                continue
            source = Path(distribution.locate_file(item))
            if not source.is_file() or source.suffix.casefold() not in {"", ".txt", ".md", ".rst"}:
                continue
            if source.stat().st_size > 2 * 1024 * 1024:
                raise ValueError("Unexpectedly large dependency notice: " + name)
            # Flatten RECORD paths; no package metadata path can escape this folder.
            filename = re.sub(r"[^A-Za-z0-9_.-]", "_", str(item))
            destination = target / filename
            if not destination.resolve().is_relative_to(output.resolve()):
                raise ValueError("Unsafe notice destination")
            destination.write_bytes(source.read_bytes())
            notices.append(destination.relative_to(output).as_posix())
        if name == "vosk" and not notices:
            # The wheel omits its licence file; retain the unmodified tagged upstream COPYING.
            source = ROOT / "assets/licenses/vosk-COPYING.txt"
            (target / "COPYING.txt").write_bytes(source.read_bytes())
            notices.append((target / "COPYING.txt").relative_to(output).as_posix())
        records[name] = {
            "name": distribution.metadata["Name"], "version": distribution.version,
            "declared_license": distribution.metadata.get("License-Expression")
                or distribution.metadata.get("License", "Unspecified"),
            "notice_files": sorted(notices),
            "review": "Owner must review applicable redistribution/source obligations",
        }
        for requirement in distribution.requires or ():
            child = Requirement(requirement)
            if child.marker and not any(
                child.marker.evaluate({"extra": extra}) for extra in {""} | processed_extras[name]
            ):
                continue
            child.marker = None  # Its marker has been evaluated in the parent extras context.
            pending.append(str(child))
    result = {"scope": "Installed default runtime requirement closure; excludes development extras",
              "not_a_license_grant": True, "packages": [records[name] for name in sorted(records)]}
    (output / "inventory.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return result


if __name__ == "__main__":
    argparse.ArgumentParser(description=__doc__).parse_args()
    inventory = prepare()
    print(json.dumps({"runtime_packages": len(inventory["packages"]),
                      "notice_files": sum(len(p["notice_files"]) for p in inventory["packages"]),
                      "without_notice_files": [p["name"] for p in inventory["packages"] if not p["notice_files"]]}))
