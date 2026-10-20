"""Approved-folder file operations with no overwrite or shell execution."""

import hashlib
import os
from pathlib import Path

from nexis.actions.files import scoped, is_link, search, SearchFilters
from nexis.utils.validation import approved_root

TEXT_SUFFIXES = {".txt", ".md", ".csv", ".json", ".log", ".rtf"}
OPEN_SUFFIXES = TEXT_SUFFIXES | {
    ".pdf",
    ".docx",
    ".xlsx",
    ".pptx",
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".bmp",
    ".wav",
    ".mp3",
    ".mp4",
}
RESERVED = {
    "con",
    "prn",
    "aux",
    "nul",
    *("com" + str(i) for i in range(1, 10)),
    *("lpt" + str(i) for i in range(1, 10)),
}


def safe_path(value, roots, *, new=False, data_dir=None):
    raw = Path(value)
    if not raw.is_absolute() or str(raw).startswith(("\\\\", "//")) or ".." in raw.parts:
        raise ValueError("Choose an absolute local path inside an approved folder.")
    if any(
        ":" in p or p.rstrip(" .") != p or p.split(".")[0].casefold() in RESERVED
        for p in raw.parts[1:]
    ):
        raise ValueError("Unsafe or reserved Windows path component.")
    resolved = raw.resolve(strict=not new)
    allowed = next(
        (approved_root(r) for r in roots if resolved.is_relative_to(approved_root(r))), None
    )
    if allowed is None:
        raise ValueError("This path is outside approved folders.")
    for index in range(len(raw.parts), 1, -1):
        ancestor = Path(*raw.parts[:index])
        if ancestor.exists() and is_link(ancestor):
            raise ValueError("Links and reparse points are not supported for file operations.")
    protected = [
        Path(os.environ.get(name, "C:/Windows"))
        for name in ("SystemRoot", "ProgramFiles", "ProgramFiles(x86)", "ProgramData")
        if os.environ.get(name)
    ]
    if data_dir:
        protected.append(Path(data_dir))
    for path in protected:
        if resolved.is_relative_to(path.resolve()):
            raise ValueError(
                "Protected application or system files cannot be modified by these tools."
            )
    if new:
        scoped(resolved.parent, roots)
        if not resolved.parent.is_dir():
            raise ValueError("The destination parent folder must already exist.")
        if resolved.exists():
            raise ValueError("Destination already exists. NEXIS will not overwrite it.")
    return resolved


def properties(path):
    stat = path.stat()
    return {
        "path": str(path),
        "is_folder": path.is_dir(),
        "bytes": stat.st_size,
        "modified_ns": stat.st_mtime_ns,
    }


def copy_exclusive(source, destination, cancel):
    source_hash = hashlib.sha256()
    created = False
    try:
        with source.open("rb") as src, destination.open("xb") as dst:
            created = True
            while chunk := src.read(256 * 1024):
                if cancel.is_set():
                    raise ValueError("File copy cancelled.")
                source_hash.update(chunk)
                dst.write(chunk)
            dst.flush()
            os.fsync(dst.fileno())
        with destination.open("rb") as copied:
            actual = hashlib.file_digest(copied, "sha256").hexdigest()
        if actual != source_hash.hexdigest():
            raise ValueError("Copied file did not pass integrity verification.")
        return {"path": str(destination), "verified": True, "sha256": actual}
    except Exception:
        if created:
            destination.unlink(missing_ok=True)
        raise


def perform(operation, args, roots, cancel, data_dir):
    if cancel.is_set():
        raise ValueError("File operation cancelled.")
    if operation == "search":
        filters = SearchFilters(**{key: args[key] for key in ("min_bytes", "max_bytes", "modified_after", "modified_before") if key in args})
        report = search(roots, args["query"], args.get("extension", ""), cancel, limit=100, filters=filters)
        return {"paths": report.paths, "metadata": report.metadata, "limited": report.limited, "cancelled": report.cancelled}
    new = operation in {"create_folder", "create_text"}
    path = safe_path(args["path"], roots, new=new, data_dir=data_dir)
    if operation == "properties":
        return properties(path)
    if operation == "open_location":
        from nexis.platform.windows import Windows

        Windows().folder(path if path.is_dir() else path.parent)
        return {"request_accepted": True, "location": str(path if path.is_dir() else path.parent)}
    if operation == "open":
        if not path.is_file() or path.suffix.casefold() not in OPEN_SUFFIXES:
            raise ValueError(
                "Only supported documents/media can be opened; executable and script launch is not allowed here."
            )
        os.startfile(str(path))
        return {"request_accepted": True, "path": str(path)}
    if operation == "preview":
        if (
            not path.is_file()
            or path.suffix.casefold() not in TEXT_SUFFIXES
            or path.stat().st_size > 256 * 1024
        ):
            raise ValueError("Preview supports text documents up to 256 KB.")
        return {"text": path.read_text(encoding="utf-8")[:16000], "path": str(path)}
    if operation == "create_folder":
        path.mkdir()
        return {"path": str(path), "verified": path.is_dir()}
    if operation == "create_text":
        if path.suffix.casefold() not in TEXT_SUFFIXES:
            raise ValueError("Create a .txt, .md, .csv, .json, .log or .rtf document.")
        with path.open("x", encoding="utf-8") as output:
            output.write(args.get("text", ""))
        return {
            "path": str(path),
            "verified": path.read_text(encoding="utf-8") == args.get("text", ""),
        }
    if operation in {"copy", "move", "rename"}:
        if not path.is_file():
            raise ValueError(
                "Copy/move/rename operate on individual files. Preview and plan folder organization as separate file steps."
            )
        destination = safe_path(args["destination"], roots, new=True, data_dir=data_dir)
        if path.suffix.casefold() != destination.suffix.casefold():
            raise ValueError("Changing a file's type is not supported.")
        if operation == "rename" and destination.parent != path.parent:
            raise ValueError("Rename must keep the file in the same folder; use move otherwise.")
        if operation == "copy":
            return copy_exclusive(path, destination, cancel)
        if path.stat().st_dev == destination.parent.stat().st_dev:
            os.rename(path, destination)
        else:
            copy_exclusive(path, destination, cancel)
            if cancel.is_set():
                return {
                    "verified": False,
                    "message": "Copy completed; move cancelled before original deletion. Both files were retained.",
                }
            path.unlink()
        return {"path": str(destination), "verified": destination.is_file() and not path.exists()}
    if operation == "recycle":
        if not path.is_file():
            raise ValueError(
                "Only individual files can be sent to the Recycle Bin; recursive deletion is not supported."
            )
        from send2trash import send2trash

        send2trash(str(path))
        return {"verified": not path.exists(), "recycle_bin_requested": True}
    raise ValueError("Unsupported file operation.")
