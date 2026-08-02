from __future__ import annotations

import json
from pathlib import Path
from typing import Any

PACKAGE_ROOT = Path(__file__).resolve().parents[2]
PROJECT_ROOT = PACKAGE_ROOT.parent


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def data_path(relative: str) -> Path:
    candidate = PROJECT_ROOT / "data" / relative
    if candidate.exists():
        return candidate
    # Installed-package fallback for editable and zipped use.
    fallback = Path.cwd() / "data" / relative
    return fallback


def load_source_registry() -> dict[str, Any]:
    return load_json(data_path("source_registry.json"))


def load_formula_registry() -> dict[str, Any]:
    return load_json(data_path("formula_registry.json"))


def load_priors() -> dict[str, Any]:
    return load_json(data_path("simulation_priors.json"))
