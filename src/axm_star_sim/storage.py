from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any


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
