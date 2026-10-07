"""Content mode for tools that work on the client's files — US-86 · UC-8604.

On a remote transport the server never reads or writes a path the client
names (threat model §8, rule 3). These tools still have to work there, so the
client sends the files a tool needs as ``files_content`` — ``{relpath: text}``
— and the tool runs its usual code over a :class:`MemoryWorkspace`: an
in-memory tree with the subset of :class:`pathlib.Path` those modules use. No
file is read from or written to the server's disk.

The answer tells the client what to do in its repository:

* ``files_changed`` — full content of every file the tool wrote;
* ``files_deleted`` — files it removed;
* ``files_appended`` — text appended to logs (``.jsonl``) the tool only
  appends to, so the client appends it instead of overwriting its history;
* ``files_requested`` — files the tool looked for and the client did not send.
  Sending them (when they exist) gives the same answer as a local server.

A :class:`VirtualPath` has no ``__fspath__``: anything that tries to reach the
real filesystem with it fails instead of touching the disk.
"""

from __future__ import annotations

import fnmatch
import io
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from pathlib import Path, PurePosixPath
from typing import Any


class WorkspacePathError(ValueError):
    """A path that is not a plain relative path inside the workspace."""


def normalize_relpath(relpath: Any) -> str:
    """``a/b/c`` for a relative POSIX path inside the workspace, else raise."""
    if not isinstance(relpath, str) or not relpath.strip():
        raise WorkspacePathError("empty path")
    if "\\" in relpath or "\x00" in relpath or relpath.startswith("/") or ":" in relpath.split("/")[0]:
        raise WorkspacePathError(f"{relpath!r} is not a relative path")
    parts = [p for p in PurePosixPath(relpath).parts if p not in ("", ".")]
    if not parts or ".." in parts:
        raise WorkspacePathError(f"{relpath!r} leaves the workspace")
    return "/".join(parts)


class MemoryWorkspace:
    """An in-memory tree of the files a client sent."""

    def __init__(self, files: Mapping[str, str] | None) -> None:
        self._files: dict[str, str] = {}
        for relpath, content in (files or {}).items():
            if not isinstance(content, str):
                raise WorkspacePathError(f"{relpath!r}: content must be text")
            self._files[normalize_relpath(relpath)] = content
        self._original = dict(self._files)
        self._dirs: set[str] = set()
        self._written: set[str] = set()
        self._appended: dict[str, str] = {}
        self._requested: set[str] = set()

    @property
    def root(self) -> VirtualPath:
        return VirtualPath(self, ())

    # ── state used by VirtualPath ────────────────────────────────────

    def _is_dir(self, key: str) -> bool:
        if key == "":
            return True
        prefix = key + "/"
        return key in self._dirs or any(f.startswith(prefix) for f in self._files)

    def _children(self, key: str) -> list[str]:
        prefix = "" if key == "" else key + "/"
        names: set[str] = set()
        for item in list(self._files) + list(self._dirs):
            if item.startswith(prefix) and item != key:
                names.add(item[len(prefix):].split("/", 1)[0])
        return sorted(names)

    def _descendants(self, key: str) -> list[str]:
        prefix = "" if key == "" else key + "/"
        return sorted(f for f in self._files if f.startswith(prefix))

    def _request(self, key: str) -> None:
        if key and key not in self._original:
            self._requested.add(key)

    # ── what the client applies ──────────────────────────────────────

    def report(self) -> dict[str, Any]:
        changed = {
            k: self._files[k]
            for k in sorted(self._written)
            if k in self._files and self._files[k] != self._original.get(k)
        }
        deleted = sorted(k for k in self._original if k not in self._files)
        appended = {k: v for k, v in sorted(self._appended.items()) if k not in self._written}
        requested = sorted(k for k in self._requested if k not in self._files)
        return {
            "files_changed": changed,
            "files_deleted": deleted,
            "files_appended": appended,
            "files_requested": requested,
        }


class _Writer(io.StringIO):
    def __init__(self, path: VirtualPath, append: bool) -> None:
        super().__init__()
        self._path = path
        self._append = append

    def close(self) -> None:
        if not self.closed:
            ws, key, text = self._path._ws, self._path._key, self.getvalue()
            if self._append:
                ws._files[key] = ws._files.get(key, "") + text
                ws._appended[key] = ws._appended.get(key, "") + text
            else:
                ws._files[key] = text
                ws._written.add(key)
        super().close()


class VirtualPath:
    """The subset of :class:`pathlib.Path` the app_docs modules use, in memory."""

    __slots__ = ("_ws", "_parts")

    def __init__(self, ws: MemoryWorkspace, parts: tuple[str, ...]) -> None:
        self._ws = ws
        self._parts = parts

    @property
    def _key(self) -> str:
        return "/".join(self._parts)

    # ── pure path operations ─────────────────────────────────────────

    def __truediv__(self, other: Any) -> VirtualPath:
        text = str(other)
        if isinstance(other, VirtualPath):
            text = other._key
        if not text or text == ".":
            return self
        rel = normalize_relpath(text)
        return VirtualPath(self._ws, self._parts + tuple(rel.split("/")))

    def joinpath(self, *others: Any) -> VirtualPath:
        path = self
        for other in others:
            path = path / other
        return path

    def __str__(self) -> str:
        return self._key or "."

    def __repr__(self) -> str:
        return f"VirtualPath({str(self)!r})"

    def __eq__(self, other: object) -> bool:
        return isinstance(other, VirtualPath) and other._ws is self._ws and other._parts == self._parts

    def __hash__(self) -> int:
        return hash((id(self._ws), self._parts))

    def __lt__(self, other: VirtualPath) -> bool:
        return self._parts < other._parts

    @property
    def parts(self) -> tuple[str, ...]:
        return self._parts

    @property
    def name(self) -> str:
        return self._parts[-1] if self._parts else ""

    @property
    def suffix(self) -> str:
        return PurePosixPath(self.name).suffix

    @property
    def stem(self) -> str:
        return PurePosixPath(self.name).stem

    @property
    def parent(self) -> VirtualPath:
        return VirtualPath(self._ws, self._parts[:-1])

    def with_name(self, name: str) -> VirtualPath:
        return self.parent / name

    def with_suffix(self, suffix: str) -> VirtualPath:
        return self.parent / (self.stem + suffix)

    def relative_to(self, other: VirtualPath) -> PurePosixPath:
        n = len(other._parts)
        if self._parts[:n] != other._parts:
            raise ValueError(f"{self} is not under {other}")
        return PurePosixPath(*self._parts[n:]) if self._parts[n:] else PurePosixPath(".")

    def resolve(self, strict: bool = False) -> VirtualPath:
        return self

    def absolute(self) -> VirtualPath:
        return self

    def expanduser(self) -> VirtualPath:
        return self

    # ── queries ──────────────────────────────────────────────────────

    def exists(self) -> bool:
        found = self._key in self._ws._files or self._ws._is_dir(self._key)
        if not found:
            self._ws._request(self._key)
        return found

    def is_file(self) -> bool:
        found = self._key in self._ws._files
        if not found and not self._ws._is_dir(self._key):
            self._ws._request(self._key)
        return found

    def is_dir(self) -> bool:
        return self._ws._is_dir(self._key)

    def iterdir(self) -> Iterator[VirtualPath]:
        for name in self._ws._children(self._key):
            yield self / name

    def glob(self, pattern: str) -> Iterator[VirtualPath]:
        matched = False
        if "/" not in pattern and "**" not in pattern:
            for name in self._ws._children(self._key):
                if fnmatch.fnmatch(name, pattern):
                    matched = True
                    yield self / name
        else:
            base = len(self._parts)
            for key in self._ws._descendants(self._key):
                rel = "/".join(key.split("/")[base:])
                if PurePosixPath(rel).match(pattern.replace("**/", "")) or fnmatch.fnmatch(rel, pattern):
                    matched = True
                    yield VirtualPath(self._ws, tuple(key.split("/")))
        if not matched:
            self._ws._request(f"{self._key}/{pattern}" if self._key else pattern)

    def rglob(self, pattern: str) -> Iterator[VirtualPath]:
        found = False
        for key in self._ws._descendants(self._key):
            if fnmatch.fnmatch(key.rsplit("/", 1)[-1], pattern):
                found = True
                yield VirtualPath(self._ws, tuple(key.split("/")))
        if not found:
            self._ws._request(f"{self._key}/**/{pattern}" if self._key else f"**/{pattern}")

    # ── reads and writes ─────────────────────────────────────────────

    def read_text(self, encoding: str | None = None, errors: str | None = None) -> str:
        try:
            return self._ws._files[self._key]
        except KeyError:
            self._ws._request(self._key)
            raise FileNotFoundError(f"{self} (not sent in files_content)") from None

    def read_bytes(self) -> bytes:
        return self.read_text().encode("utf-8")

    def write_text(self, data: str, encoding: str | None = None, errors: str | None = None, newline: str | None = None) -> int:
        self._ws._files[self._key] = data
        self._ws._written.add(self._key)
        return len(data)

    def write_bytes(self, data: bytes) -> int:
        return self.write_text(data.decode("utf-8"))

    def mkdir(self, mode: int = 0o777, parents: bool = False, exist_ok: bool = False) -> None:
        for i in range(1, len(self._parts) + 1):
            self._ws._dirs.add("/".join(self._parts[:i]))

    def touch(self, mode: int = 0o666, exist_ok: bool = True) -> None:
        if self._key not in self._ws._files:
            self.write_text("")

    def unlink(self, missing_ok: bool = False) -> None:
        if self._key in self._ws._files:
            del self._ws._files[self._key]
        elif not missing_ok:
            raise FileNotFoundError(str(self))

    def open(self, mode: str = "r", buffering: int = -1, encoding: str | None = None, errors: str | None = None, newline: str | None = None):  # noqa: A003
        if "r" in mode and "+" not in mode:
            return io.StringIO(self.read_text())
        if "a" in mode:
            return _Writer(self, append=True)
        if "w" in mode:
            return _Writer(self, append=False)
        raise ValueError(f"mode {mode!r} is not supported in content mode")


def as_path(project_path: Any) -> Any:
    """A :class:`VirtualPath` as is; anything else as a real :class:`Path`."""
    return project_path if isinstance(project_path, VirtualPath) else Path(project_path)


@contextmanager
def tool_root(project_path: str, files_content: Mapping[str, str] | None) -> Iterator[tuple[Any, MemoryWorkspace | None]]:
    """``(root, workspace)``: the in-memory tree when the client sent files, else the path."""
    if files_content is None:
        yield project_path, None
        return
    workspace = MemoryWorkspace(files_content)
    yield workspace.root, workspace


def with_report(result: Any, workspace: MemoryWorkspace | None) -> Any:
    """``result`` plus what the client must apply, in content mode."""
    if workspace is None or not isinstance(result, dict):
        return result
    return {**result, **workspace.report()}


def invalid_content_envelope(exc: WorkspacePathError) -> dict[str, Any]:
    return {"error": f"files_content: {exc}", "code": "INVALID_FILES_CONTENT"}


def run_in_root(project_path: str, files_content: Mapping[str, str] | None, fn: Any) -> Any:
    """``fn(root)`` on the client's path, or on the files it sent plus the report."""
    if files_content is None:
        return fn(project_path)
    try:
        workspace = MemoryWorkspace(files_content)
    except WorkspacePathError as exc:
        return invalid_content_envelope(exc)
    return with_report(fn(workspace.root), workspace)
