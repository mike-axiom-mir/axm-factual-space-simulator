from __future__ import annotations

from typing import Any

from .contact_horizon import validate_contact_horizon_registry
from .technology_core import validate_technology_registry

ALLOWED_TRUTH_TYPES = {
    "catalog_fact",
    "derived",
    "simulation_prior",
    "observation",
    "hypothesis",
    "speculation",
}


class ValidationError(ValueError):
    pass


def _validate_evidence(path: str, evidence: dict[str, Any], known_sources: set[str]) -> None:
    truth = evidence.get("truth_type")
    if truth not in ALLOWED_TRUTH_TYPES:
        raise ValidationError(f"{path}: invalid truth type {truth!r}")
    if truth == "catalog_fact" and not evidence.get("source_ids"):
        raise ValidationError(f"{path}: catalog facts require a source")
    unknown_sources = set(evidence.get("source_ids", [])) - known_sources
    if unknown_sources:
        raise ValidationError(f"{path}: unknown source IDs {sorted(unknown_sources)}")
    if truth == "derived" and not evidence.get("formula_id"):
        raise ValidationError(f"{path}: derived values require a formula ID")
    if truth in {"hypothesis", "speculation"} and not evidence.get("notes"):
        raise ValidationError(f"{path}: uncertain claims require an explanation")


def validate_system(data: dict[str, Any]) -> list[str]:
    warnings: list[str] = []
    if not data.get("master_seed"):
        raise ValidationError("master_seed is required")
    if not data.get("seed_manifest"):
        raise ValidationError("seed_manifest is required")

    known_sources = set(data.get("source_registry", {}).get("sources", {}))
    for key, evidence in data["star"].items():
        _validate_evidence(f"star.{key}", evidence, known_sources)

    last_axis = 0.0
    for index, planet in enumerate(data["planets"]):
        for key, evidence in planet["facts"].items():
            _validate_evidence(f"planets[{index}].facts.{key}", evidence, known_sources)
        axis = float(planet["facts"]["semi_major_axis"]["value"])
        if axis <= last_axis:
            raise ValidationError("planet semi-major axes must increase")
        last_axis = axis
        eccentricity = float(planet["facts"]["eccentricity"]["value"])
        if not 0 <= eccentricity < 1:
            raise ValidationError("eccentricity must be in [0, 1)")

    ship = data.get("ship", {})
    technology = ship.get("technology_core")
    if not technology:
        raise ValidationError("ship.technology_core is required")
    try:
        warnings.extend(validate_technology_registry())
        warnings.extend(validate_contact_horizon_registry())
    except ValueError as exc:
        raise ValidationError(f"technology registry invalid: {exc}") from exc
    receipt = technology.get("selection_receipt", {})
    if receipt.get("manual_technology_choice") is not False:
        raise ValidationError("technology core selection must not be manually chosen")
    if technology.get("selected_core_id") not in receipt.get("eligible_core_ids", []):
        raise ValidationError("selected technology core is not in the eligible source-pinned catalog")
    if not technology.get("truth_contract", {}).get("unknown_values_remain_unknown"):
        raise ValidationError("technology core must preserve unknown values")

    if len(data["planets"]) < 1:
        warnings.append("system has no planets")
    return warnings
