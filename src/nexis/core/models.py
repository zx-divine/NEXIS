"""Consent-driven, pinned offline model provisioning. No executable downloads."""

import hashlib
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import sys
import tempfile
import urllib.request
import zipfile
from uuid import uuid4

MODEL = {
    "id": "vosk-model-small-en-us-0.15",
    "language": "English (United States)",
    "size": 41205931,
    "sha256": "30f26242c4eb449f948e42cb302dd7a686cb29a3423a8367f99ff41780942498",
    "url": "https://alphacephei.com/vosk/models/vosk-model-small-en-us-0.15.zip",
    "license": "Apache-2.0",
}


class Cancelled(ValueError):
    pass


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError("Download redirected away from the approved source. Retry later.")


def valid_model(path):
    path = Path(path)
    return all(
        (path / p).is_file()
        for p in ("am/final.mdl", "conf/model.conf", "graph/HCLr.fst", "graph/Gr.fst")
    )


def detect_model(saved, directory):
    if saved and valid_model(saved):
        return str(Path(saved).resolve())
    bundled = Path(__file__).resolve().parents[1] / "assets/models" / MODEL["id"]
    managed = Path(directory) / "models" / MODEL["id"]
    candidates = [bundled, managed]
    if not getattr(sys, "frozen", False):
        candidates.append(Path(__file__).resolve().parents[3] / "assets/models" / MODEL["id"])
    for path in candidates:
        if valid_model(path):
            return str(path.resolve())
    return ""


def validate_model(path):
    from vosk import Model, SetLogLevel

    SetLogLevel(-1)
    model = Model(str(path))
    del model


def safe_extract(archive, destination, cancel):
    destination = Path(destination).resolve()
    with zipfile.ZipFile(archive) as source:
        infos = source.infolist()
        if len(infos) > 10000 or sum(i.file_size for i in infos) > 512 * 1024 * 1024:
            raise ValueError("Speech archive is too large or malformed.")
        for info in infos:
            path = PurePosixPath(info.filename)
            mode = info.external_attr >> 16
            reserved = {
                "con",
                "prn",
                "aux",
                "nul",
                *("com" + str(n) for n in range(1, 10)),
                *("lpt" + str(n) for n in range(1, 10)),
            }
            if (
                not path.parts
                or path.is_absolute()
                or ".." in path.parts
                or "\\" in info.filename
                or ":" in info.filename
                or "\0" in info.filename
                or stat.S_ISLNK(mode)
                or info.flag_bits & 1
                or any(p.split(".")[0].casefold() in reserved for p in path.parts)
                or any(p.rstrip(" .") != p for p in path.parts)
            ):
                raise ValueError("Unsafe path in speech archive.")
            target = destination.joinpath(*path.parts).resolve()
            if not target.is_relative_to(destination):
                raise ValueError("Archive path escaped the model directory.")
        for info in infos:
            if cancel.is_set():
                raise Cancelled("Speech setup cancelled. Download can be retried.")
            target = destination.joinpath(*PurePosixPath(info.filename).parts)
            if info.is_dir():
                target.mkdir(parents=True, exist_ok=True)
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            with source.open(info) as src, target.open("xb") as dst:
                while chunk := src.read(256 * 1024):
                    if cancel.is_set():
                        raise Cancelled("Speech setup cancelled. Retry when ready.")
                    dst.write(chunk)


def install_model(directory, cancel, progress=lambda text: None, *, consent=False, opener=None):
    if not consent:
        raise ValueError("Consent is required before downloading the speech model.")
    base = Path(directory).resolve()
    models = base / "models"
    models.mkdir(parents=True, exist_ok=True)
    target = models / MODEL["id"]
    if valid_model(target):
        return str(target)
    if target.exists():
        quarantine = models / (MODEL["id"] + ".invalid-" + uuid4().hex)
        if (
            target.is_symlink()
            or getattr(target, "is_junction", lambda: False)()
            or not target.resolve().is_relative_to(models.resolve())
            or not quarantine.resolve().is_relative_to(models.resolve())
        ):
            raise ValueError("Unsafe managed model path. Setup stopped.")
        os.replace(target, quarantine)
        progress("An incomplete model was preserved for recovery. Retrying setup…")
    cache = base / "model-downloads"
    cache.mkdir(parents=True, exist_ok=True)
    part = cache / (MODEL["id"] + ".zip.part")
    if part.is_symlink() or getattr(part, "is_junction", lambda: False)():
        raise ValueError("Unsafe download cache path.")
    offset = part.stat().st_size if part.exists() else 0
    if offset > MODEL["size"]:
        part.unlink()
        offset = 0
    if shutil.disk_usage(base).free < 512 * 1024 * 1024:
        raise ValueError("Speech setup needs at least 512 MB of free disk space.")
    if cancel.is_set():
        raise Cancelled("Speech setup cancelled.")
    if offset < MODEL["size"]:
        request = urllib.request.Request(
            MODEL["url"],
            headers={"Range": f"bytes={offset}-", "User-Agent": "NEXIS-Desktop/1.3"}
            if offset
            else {"User-Agent": "NEXIS-Desktop/1.3"},
        )
        open_request = opener or urllib.request.build_opener(NoRedirect()).open
        with open_request(request, timeout=10) as response:
            if response.geturl() != MODEL["url"]:
                raise ValueError("Unapproved model download source.")
            if offset and response.status == 206:
                match = re.fullmatch(
                    r"bytes (\d+)-(\d+)/(\d+)", response.headers.get("Content-Range", "")
                )
                if not match or int(match[1]) != offset or int(match[3]) != MODEL["size"]:
                    raise ValueError("Resume information was invalid. Retry the download.")
            elif response.status == 200:
                offset = 0
            else:
                raise ValueError("Speech download was not accepted by the approved source.")
            with part.open("ab" if offset else "wb") as output:
                reader = getattr(response, "read1", response.read)
                while chunk := reader(128 * 1024):
                    if cancel.is_set():
                        raise Cancelled("Speech setup paused. Retry to resume the download.")
                    offset += len(chunk)
                    if offset > MODEL["size"]:
                        raise ValueError("Speech download exceeded its expected size.")
                    output.write(chunk)
                    progress(f"Downloading {MODEL['language']}: {offset * 100 // MODEL['size']}%")
    with part.open("rb") as downloaded:
        digest = hashlib.file_digest(downloaded, "sha256").hexdigest()
    if part.stat().st_size != MODEL["size"] or digest != MODEL["sha256"]:
        part.unlink(missing_ok=True)
        raise ValueError("Model integrity check failed. Retry to download a fresh copy.")
    progress("Verified download. Preparing offline speech…")
    staging = Path(tempfile.mkdtemp(prefix=".speech-", dir=models)).resolve()
    try:
        safe_extract(part, staging, cancel)
        extracted = staging / MODEL["id"]
        if not valid_model(extracted):
            raise ValueError("The archive does not contain a compatible speech model.")
        progress("Checking that the offline recognition engine can load the model…")
        validate_model(extracted)
        if cancel.is_set():
            raise Cancelled("Speech setup cancelled before activation.")
        os.replace(extracted, target)
        part.unlink(missing_ok=True)
        return str(target)
    finally:
        if staging.is_relative_to(models.resolve()) and staging.name.startswith(".speech-"):
            shutil.rmtree(staging)
