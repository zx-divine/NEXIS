import os
import stat
from dataclasses import dataclass, field
from pathlib import Path
from threading import Event

from nexis.utils.validation import approved_root


def is_link(path: Path) -> bool:
    info = path.lstat()
    return path.is_symlink() or bool(
        getattr(info, "st_file_attributes", 0)
        & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    )


def scoped(path: Path, roots: list[str]) -> Path:
    resolved = path.resolve(strict=True)
    for root in roots:
        try:
            allowed = approved_root(root)
        except (ValueError, OSError):
            continue
        if resolved.is_relative_to(allowed):
            return resolved
    raise ValueError("This path is outside approved search folders.")


@dataclass
class SearchReport:
    paths: list[str] = field(default_factory=list)
    visited: int = 0
    inaccessible: int = 0
    cancelled: bool = False
    limited: bool = False


def search(
    roots: list[str],
    query: str,
    extension: str = "",
    cancel: Event | None = None,
    progress=lambda count: None,
    limit=1000,
) -> SearchReport:
    if not query.strip() or len(query) > 255 or any(c in query for c in "/\\"):
        raise ValueError("Search by filename, without path separators.")
    if extension and (not extension.startswith(".") or not extension[1:].isalnum()):
        raise ValueError("Use an extension such as .pdf, or leave it empty.")
    cancel = cancel or Event()
    report = SearchReport()
    seen = set()
    for raw in roots:
        try:
            root = approved_root(raw)
        except (OSError, ValueError):
            report.inaccessible += 1
            continue
        stack = [root]
        while stack:
            if cancel.is_set():
                report.cancelled = True
                return report
            directory = stack.pop()
            try:
                # Recheck containment and reparse attributes immediately before enumeration.
                if is_link(directory) or not directory.resolve(strict=True).is_relative_to(root):
                    continue
                if directory in seen:
                    continue
                seen.add(directory)
                with os.scandir(directory) as entries:
                    for item in entries:
                        if cancel.is_set():
                            report.cancelled = True
                            return report
                        path = Path(item.path)
                        try:
                            if is_link(path):
                                continue
                            if item.is_dir(follow_symlinks=False):
                                stack.append(path)
                            elif item.is_file(follow_symlinks=False):
                                report.visited += 1
                                if (
                                    query.casefold() in item.name.casefold()
                                    and (
                                        not extension
                                        or path.suffix.casefold() == extension.casefold()
                                    )
                                    and path.resolve(strict=True).is_relative_to(root)
                                ):
                                    report.paths.append(str(path))
                                    if len(report.paths) >= limit:
                                        report.limited = True
                                        return report
                                if report.visited % 100 == 0:
                                    progress(report.visited)
                        except OSError:
                            report.inaccessible += 1
            except OSError:
                report.inaccessible += 1
    return report
