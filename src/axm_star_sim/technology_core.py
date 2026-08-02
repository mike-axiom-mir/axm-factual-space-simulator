from __future__ import annotations

import copy
import hashlib
from typing import Any, Iterable

from .registry import data_path, load_formula_registry, load_json, load_source_registry
from .seed import SeedBranch

TECHNOLOGY_SCHEMA = "axm.ship-technology-profile.v1"
SELECTION_ALGORITHM = "sha256_named_branch_sorted_equal_catalog_index_v1"


class TechnologyCoreError(ValueError):
    """Raised when a technology core breaks the no-invention contract."""


def load_technology_core_registry() -> dict[str, Any]:
    return load_json(data_path("technology_core_registry.json"))


def load_exploration_function_map() -> dict[str, Any]:
    return load_json(data_path("exploration_function_map.json"))


def eligible_core_ids(
    registry: dict[str, Any] | None = None,
    *,
    horizon_year: int = 2027,
) -> list[str]:
    registry = registry or load_technology_core_registry()
    result: list[str] = []
    for core_id, core in registry["cores"].items():
        selection = core.get("selection", {})
        if not selection.get("eligible_for_2027_reference_ship", False):
            continue
        schedule = core.get("schedule", {})
        not_before = schedule.get("not_before_year")
        reference = schedule.get("reference_year")
        if not_before is not None and int(not_before) > horizon_year:
            continue
        if reference is not None and int(reference) > horizon_year:
            continue
        result.append(core_id)
    return sorted(result)


def _catalog_index(master_seed: str, eligible: list[str]) -> tuple[int, str]:
    if not eligible:
        raise TechnologyCoreError("no technology cores are eligible for the requested planning horizon")
    branch = SeedBranch(master_seed, "ship/technology-core")
    index = int(branch.digest[:16], 16) % len(eligible)
    return index, branch.digest


def select_technology_core(
    master_seed: str,
    registry: dict[str, Any] | None = None,
    *,
    horizon_year: int = 2027,
) -> tuple[str, dict[str, Any], dict[str, Any]]:
    registry = registry or load_technology_core_registry()
    eligible = eligible_core_ids(registry, horizon_year=horizon_year)
    index, digest = _catalog_index(master_seed, eligible)
    core_id = eligible[index]
    receipt = {
        "algorithm": SELECTION_ALGORITHM,
        "branch": "ship/technology-core",
        "branch_digest": digest,
        "planning_horizon_year": horizon_year,
        "eligible_core_ids": eligible,
        "eligible_count": len(eligible),
        "selected_index": index,
        "selected_core_id": core_id,
        "weights": "none; every eligible catalog core occupies one sorted slot",
        "manual_technology_choice": False,
    }
    return core_id, copy.deepcopy(registry["cores"][core_id]), receipt


def _evidence_sources(evidence: dict[str, Any]) -> set[str]:
    return set(evidence.get("source_ids", []))


def _validate_evidence(
    path: str,
    evidence: dict[str, Any],
    known_sources: set[str],
    known_formulas: set[str],
) -> None:
    if not isinstance(evidence, dict) or "value" not in evidence:
        raise TechnologyCoreError(f"{path}: parameter must be an evidence object")
    truth = evidence.get("truth_type")
    if truth not in {"catalog_fact", "derived"}:
        raise TechnologyCoreError(f"{path}: technology parameters must be catalog_fact or derived")
    sources = _evidence_sources(evidence)
    if truth == "catalog_fact" and not sources:
        raise TechnologyCoreError(f"{path}: catalog facts require a source")
    unknown = sources - known_sources
    if unknown:
        raise TechnologyCoreError(f"{path}: unknown source IDs {sorted(unknown)}")
    if truth == "derived":
        formula_id = evidence.get("formula_id")
        if not formula_id or formula_id not in known_formulas:
            raise TechnologyCoreError(f"{path}: derived values require a registered formula")
    value = evidence.get("value")
    if isinstance(value, bool):
        return
    if isinstance(value, (int, float)) and not evidence.get("unit"):
        raise TechnologyCoreError(f"{path}: numeric technology values require an explicit unit")


def validate_technology_registry(registry: dict[str, Any] | None = None) -> list[str]:
    registry = registry or load_technology_core_registry()
    sources = load_source_registry()
    formulas = load_formula_registry()
    known_sources = set(sources["sources"])
    known_formulas = set(formulas["formulas"])
    warnings: list[str] = []

    if not registry.get("policy", {}).get("no_invented_numeric_performance"):
        raise TechnologyCoreError("registry must enforce no_invented_numeric_performance")

    for core_id, core in registry.get("cores", {}).items():
        status = core.get("status", {})
        unknown = set(status.get("source_ids", [])) - known_sources
        if unknown:
            raise TechnologyCoreError(f"cores.{core_id}.status: unknown sources {sorted(unknown)}")
        for group in ("factual_parameters", "derived_parameters"):
            for key, evidence in core.get(group, {}).items():
                _validate_evidence(
                    f"cores.{core_id}.{group}.{key}", evidence, known_sources, known_formulas
                )
        if core.get("selection", {}).get("eligible_for_2027_reference_ship") and not core.get("capability_ids"):
            warnings.append(f"{core_id}: eligible core has no capability IDs")

    for support_id, support in registry.get("supporting_technologies", {}).items():
        unknown = set(support.get("source_ids", [])) - known_sources
        if unknown:
            raise TechnologyCoreError(f"supporting_technologies.{support_id}: unknown sources {sorted(unknown)}")
        for key, evidence in support.get("factual_parameters", {}).items():
            _validate_evidence(
                f"supporting_technologies.{support_id}.factual_parameters.{key}",
                evidence,
                known_sources,
                known_formulas,
            )
    return warnings


def _capability_translation(core: dict[str, Any], function_map: dict[str, Any]) -> list[dict[str, Any]]:
    core_caps = set(core.get("capability_ids", []))
    translations: list[dict[str, Any]] = []
    for function_id, item in function_map.get("functions", {}).items():
        matched = sorted(core_caps.intersection(item.get("real_capability_ids", [])))
        translations.append({
            "function_id": function_id,
            "reference_function": item["reference_function"],
            "real_translation": item["real_translation"],
            "supported_by_selected_core": bool(matched),
            "matched_capability_ids": matched,
            "unavailable_claims": item.get("unavailable_claims", []),
            "status": item.get("status", "partial analog only"),
            "truth_type": "research_mapping",
            "source_ids": function_map.get("source_ids", []),
        })
    return translations


def _known_parameter_summary(core: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for group in ("factual_parameters", "derived_parameters"):
        for key, evidence in core.get(group, {}).items():
            rows.append({"id": key, "group": group, **copy.deepcopy(evidence)})
    return rows


def _blocked_calculation_list(core: dict[str, Any]) -> list[dict[str, str]]:
    unknown = " ".join(core.get("unknown_parameters", [])).lower()
    blocked = list(core.get("blocked_physics", []))
    standard = [
        ("continuous_acceleration", ("thrust", "mass"), "Requires reviewed thrust and wet-mass values."),
        ("delta_v", ("specific impulse", "propellant"), "Requires reviewed specific impulse and propellant/mass values."),
        ("crew_g_load", ("acceleration",), "Requires a validated acceleration profile; inertial cancellation is unavailable."),
        ("mission_range", ("delta-v",), "Requires a valid propulsion and mass model rather than power alone."),
    ]
    result: list[dict[str, str]] = []
    for quantity, triggers, reason in standard:
        if any(trigger in unknown for trigger in triggers) or quantity in {"crew_g_load", "mission_range"}:
            result.append({"quantity": quantity, "status": "blocked_unknown", "reason": reason})
    for text in blocked:
        result.append({"quantity": "core_specific", "status": "forbidden_inference", "reason": text})
    return result


def build_ship_technology_profile(master_seed: str, *, horizon_year: int = 2027) -> dict[str, Any]:
    registry = load_technology_core_registry()
    function_map = load_exploration_function_map()
    validate_technology_registry(registry)
    core_id, core, receipt = select_technology_core(
        master_seed, registry, horizon_year=horizon_year
    )
    support_ids = core.get("supporting_demonstrator_ids", [])
    support = {
        item_id: copy.deepcopy(registry["supporting_technologies"][item_id])
        for item_id in support_ids
        if item_id in registry.get("supporting_technologies", {})
    }
    catalog = []
    for candidate_id in eligible_core_ids(registry, horizon_year=horizon_year):
        candidate = registry["cores"][candidate_id]
        catalog.append({
            "id": candidate_id,
            "name": candidate["name"],
            "core_class": candidate["core_class"],
            "domain": candidate["selection"]["domain"],
            "status": candidate["status"]["value"],
            "source_ids": candidate["status"]["source_ids"],
        })

    profile = {
        "schema": TECHNOLOGY_SCHEMA,
        "registry_version": registry["registry_version"],
        "as_of_date": registry["as_of_date"],
        "planning_horizon_year": horizon_year,
        "selected_core_id": core_id,
        "selected_core": core,
        "selection_receipt": receipt,
        "eligible_catalog": catalog,
        "supporting_technologies": support,
        "known_parameter_summary": _known_parameter_summary(core),
        "blocked_calculations": _blocked_calculation_list(core),
        "exploration_function_translation": _capability_translation(core, function_map),
        "truth_contract": {
            "selected_core_is_a_reference_lineage_not_a_claimed_copy": True,
            "numeric_values_are_only_catalog_facts_or_transparent_derivations": True,
            "unknown_values_remain_unknown": True,
            "reference_function_names_never_authorize_new_physics": True,
            "future_source_updates_require_a_new_registry_version": True,
        },
    }
    profile["profile_sha256"] = hashlib.sha256(
        repr(_stable_projection(profile)).encode("utf-8")
    ).hexdigest()
    return profile


def _stable_projection(value: Any) -> Any:
    if isinstance(value, dict):
        return tuple((k, _stable_projection(value[k])) for k in sorted(value))
    if isinstance(value, list):
        return tuple(_stable_projection(v) for v in value)
    return value


def iter_numeric_evidence(profile: dict[str, Any]) -> Iterable[tuple[str, dict[str, Any]]]:
    for index, evidence in enumerate(profile.get("known_parameter_summary", [])):
        if isinstance(evidence.get("value"), (int, float)) and not isinstance(evidence.get("value"), bool):
            yield f"known_parameter_summary[{index}]", evidence
