import os
import stat
import math
from time import monotonic
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
    metadata: dict = field(default_factory=dict)

    def ranked(self, query):
        needle = query.casefold()
        self.paths.sort(key=lambda raw: (Path(raw).name.casefold() != needle,
                         not Path(raw).name.casefold().startswith(needle),
                         -self.metadata.get(raw, {}).get("modified", 0), raw.casefold()))
        return self


@dataclass(frozen=True)
class SearchFilters:
    min_bytes: int = 0
    max_bytes: int | None = None
    modified_after: float | None = None
    modified_before: float | None = None

    def __post_init__(self):
        if type(self.min_bytes) is not int or self.min_bytes < 0 or (self.max_bytes is not None and (type(self.max_bytes) is not int or self.max_bytes < self.min_bytes)):
            raise ValueError("File size bounds must be non-negative bytes, minimum no greater than maximum.")
        for value in (self.modified_after, self.modified_before):
            if value is not None and (type(value) not in (int, float) or not math.isfinite(value)):
                raise ValueError("Modified dates must be finite timestamps.")
        if self.modified_after is not None and self.modified_before is not None and self.modified_after > self.modified_before:
            raise ValueError("The beginning date must be no later than the ending date.")

    def matches(self, info):
        return (info.st_size >= self.min_bytes and (self.max_bytes is None or info.st_size <= self.max_bytes)
                and (self.modified_after is None or info.st_mtime >= self.modified_after)
                and (self.modified_before is None or info.st_mtime <= self.modified_before))


def search(
    roots: list[str],
    query: str,
    extension: str = "",
    cancel: Event | None = None,
    progress=lambda count: None,
    limit=1000,
    *, filters=None, access_check=lambda: None,
) -> SearchReport:
    if not query.strip() or len(query) > 255 or any(c in query for c in "/\\"):
        raise ValueError("Search by filename, without path separators.")
    if extension and (not extension.startswith(".") or not extension[1:].isalnum()):
        raise ValueError("Use an extension such as .pdf, or leave it empty.")
    cancel = cancel or Event()
    report = SearchReport()
    filters = filters or SearchFilters()
    deadline = monotonic() + 30
    seen = set()
    for raw in roots:
        try:
            root = approved_root(raw)
        except (OSError, ValueError):
            report.inaccessible += 1
            continue
        stack = [root]
        while stack:
            access_check()
            if cancel.is_set():
                report.cancelled = True
                return report.ranked(query)
            if monotonic() >= deadline or report.visited >= 50000:
                report.limited = True
                return report.ranked(query)
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
                        access_check()
                        if cancel.is_set():
                            report.cancelled = True
                            return report.ranked(query)
                        if monotonic() >= deadline or report.visited >= 50000:
                            report.limited = True
                            return report.ranked(query)
                        path = Path(item.path)
                        try:
                            if is_link(path):
                                continue
                            if item.is_dir(follow_symlinks=False):
                                stack.append(path)
                            elif item.is_file(follow_symlinks=False):
                                report.visited += 1
                                if (
                                    (query == "*" or query.casefold() in item.name.casefold())
                                    and (
                                        not extension
                                        or path.suffix.casefold() == extension.casefold()
                                    )
                                    and path.resolve(strict=True).is_relative_to(root)
                                ):
                                    info = item.stat(follow_symlinks=False)
                                    if not filters.matches(info):
                                        continue
                                    report.paths.append(str(path))
                                    report.metadata[str(path)] = {"bytes": info.st_size, "modified": info.st_mtime}
                                    if len(report.paths) >= limit:
                                        report.limited = True
                                        return report.ranked(query)
                                if report.visited % 100 == 0:
                                    progress(report.visited)
                        except OSError:
                            report.inaccessible += 1
            except OSError:
                report.inaccessible += 1
    return report.ranked(query)
