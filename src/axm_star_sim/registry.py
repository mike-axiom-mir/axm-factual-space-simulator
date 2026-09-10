from __future__ import annotations

import json
from importlib import resources
from importlib.resources.abc import Traversable
from pathlib import Path
from typing import Any

PACKAGE_ROOT = Path(__file__).resolve().parents[2]
SOURCE_DATA_ROOT = PACKAGE_ROOT / "data"


def load_json(path: Path | Traversable) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def data_path(relative: str) -> Path | Traversable:
    requested = Path(relative)
    if requested.is_absolute() or ".." in requested.parts:
        raise ValueError("registry resource paths must stay inside the data root")

    source_candidate = SOURCE_DATA_ROOT.joinpath(*requested.parts)
    if source_candidate.is_file():
        return source_candidate

    try:
        packaged_candidate = resources.files("axm_star_sim.data").joinpath(*requested.parts)
    except ModuleNotFoundError:
        packaged_candidate = None
    if packaged_candidate is not None and packaged_candidate.is_file():
        return packaged_candidate

    # Preserve data-adjacent unpacked launches without allowing caller files to
    # override source-tree or installed canonical registries.
    return Path.cwd().joinpath("data", *requested.parts)


def load_source_registry() -> dict[str, Any]:
    return load_json(data_path("source_registry.json"))


def load_formula_registry() -> dict[str, Any]:
    return load_json(data_path("formula_registry.json"))


def load_priors() -> dict[str, Any]:
    return load_json(data_path("simulation_priors.json"))
