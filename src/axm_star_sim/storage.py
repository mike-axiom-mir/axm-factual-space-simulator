from __future__ import annotations

import json
import os
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator


OUTPUT_MUTATION_LOCK_NAME = ".runtime_mutation.lock"


class OutputMutationBusy(RuntimeError):
    """Raised when another local process owns the output mutation boundary."""


def _try_lock(handle) -> None:
    handle.seek(0)
    if os.name == "nt":
        import msvcrt

        msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        return

    import fcntl

    fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)


def _unlock(handle) -> None:
    handle.seek(0)
    if os.name == "nt":
        import msvcrt

        msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
        return

    import fcntl

    fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


@contextmanager
def output_mutation_lock(output: Path) -> Iterator[None]:
    """Admit one local output mutation process, with crash-safe OS ownership."""
    output.mkdir(parents=True, exist_ok=True)
    path = output / OUTPUT_MUTATION_LOCK_NAME
    handle = path.open("a+b")
    try:
        handle.seek(0, os.SEEK_END)
        if handle.tell() == 0:
            handle.write(b"\0")
            handle.flush()
        try:
            _try_lock(handle)
        except OSError as exc:
            raise OutputMutationBusy(
                "another local process is already mutating this adventure output"
            ) from exc
        try:
            yield
        finally:
            _unlock(handle)
    finally:
        handle.close()


def sync_directory(path: Path) -> None:
    """Best-effort directory sync; unsupported on some Windows filesystems."""
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
    try:
        descriptor = os.open(path, flags)
    except OSError:
        return
    try:
        try:
            os.fsync(descriptor)
        except OSError:
            return
    finally:
        os.close(descriptor)


def atomic_write_text(path: Path, value: str) -> None:
    """Replace one file only after its complete contents have reached storage."""
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(value)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        sync_directory(path.parent)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise


def atomic_write_json(path: Path, value: Any) -> None:
    atomic_write_text(path, json.dumps(value, indent=2, ensure_ascii=False) + "\n")


def remove_file(path: Path) -> None:
    if path.exists():
        path.unlink()
        sync_directory(path.parent)
