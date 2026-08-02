from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from typing import Any

from .registry import data_path, load_json, load_source_registry


class CosmicPossibilityError(ValueError):
    pass


def load_cosmic_possibility_registry() -> dict[str, Any]:
    return load_json(data_path("cosmic_possibility_registry.json"))


def _ids(entries: list[dict[str, Any]], label: str) -> list[str]:
    values = [str(item.get("id", "")) for item in entries]
    if any(not value for value in values):
        raise CosmicPossibilityError(f"{label} contains an empty id")
    if len(values) != len(set(values)):
        raise CosmicPossibilityError(f"{label} contains duplicate ids")
    return values


def validate_cosmic_possibility_registry(registry: dict[str, Any] | None = None) -> list[str]:
    registry = registry or load_cosmic_possibility_registry()
    errors: list[str] = []
    try:
        if registry.get("schema") != "axm.cosmic-possibility-registry.v1":
            errors.append("unexpected registry schema")
        policy = registry.get("policy", {})
        required_policy = {
            "ai_synthesis_is_not_empirical_authority",
            "environment_controls_eligibility_not_existence",
            "life_like_behavior_is_not_automatically_life",
            "standard_physics_instrumental_and_geochemical_controls_are_tested_first",
            "all_anomalies_have_claim_ceilings",
            "theory_selection_creates_a_test_lens_not_a_world_fact",
        }
        for key in required_policy:
            if policy.get(key) is not True:
                errors.append(f"policy must be true: {key}")
        ladders = registry.get("evidence_ladder", [])
        stages = [int(item.get("stage", -1)) for item in ladders]
        if stages != list(range(len(stages))):
            errors.append("evidence ladder stages must be contiguous from zero")
        _ids(registry.get("agnostic_observables", []), "agnostic_observables")
        _ids(registry.get("universe_theory_families", []), "universe_theory_families")
        _ids(registry.get("anomaly_families", []), "anomaly_families")
        _ids(registry.get("life_architectures", []), "life_architectures")
        registered_sources = set(registry.get("source_ids", []))
        source_registry_ids = set(load_source_registry().get("sources", {}))
        for source_id in registered_sources:
            if source_id not in source_registry_ids:
                errors.append(f"cosmic registry source id is absent from source_registry.json: {source_id}")
        for family_name in ("universe_theory_families", "anomaly_families", "life_architectures"):
            for item in registry.get(family_name, []):
                if not item.get("claim_ceiling") and family_name != "universe_theory_families":
                    errors.append(f"{family_name}:{item.get('id')} lacks claim_ceiling")
                for source_id in item.get("source_ids", []):
                    if source_id not in registered_sources:
                        errors.append(f"unregistered source id {source_id} in {family_name}:{item.get('id')}")
    except (TypeError, ValueError, CosmicPossibilityError) as exc:
        errors.append(str(exc))
    return errors


def _value(evidence: Any, default: float | None = None) -> float | None:
    if isinstance(evidence, dict) and "value" in evidence:
        evidence = evidence["value"]
    try:
        return float(evidence)
    except (TypeError, ValueError):
        return default


def _target_planet(system: dict[str, Any]) -> dict[str, Any]:
    planets = system.get("planets", [])
    if not planets:
        raise CosmicPossibilityError("system has no planets")
    trigger = system.get("adventure", {}).get("selected_opportunity", {}).get("trigger", {})
    candidate_ids = [value for value in trigger.values() if isinstance(value, str) and value.startswith("planet-")]
    for candidate in candidate_ids:
        for planet in planets:
            if planet.get("id") == candidate:
                return planet
    # Prefer the world whose equilibrium temperature is closest to liquid-water Earth conditions,
    # not because it is more likely to host life, but because it tends to maximize test diversity.
    return min(
        planets,
        key=lambda planet: abs((_value(planet.get("facts", {}).get("equilibrium_temperature"), 255.0) or 255.0) - 255.0),
    )


def system_environment(system: dict[str, Any]) -> dict[str, Any]:
    planet = _target_planet(system)
    facts = planet.get("facts", {})
    star = system.get("star", {})
    return {
        "system_id": system.get("system_id"),
        "system_name": system.get("name"),
        "target_planet_id": planet.get("id"),
        "target_planet_name": planet.get("name"),
        "planet_kind": planet.get("kind"),
        "equilibrium_temperature_k": _value(facts.get("equilibrium_temperature"), 255.0),
        "insolation_earth": _value(facts.get("insolation"), 1.0),
        "surface_gravity_earth": _value(facts.get("surface_gravity"), 1.0),
        "orbital_period_days": _value(facts.get("orbital_period"), 365.25),
        "stellar_temperature_k": _value(star.get("effective_temperature"), 5772.0),
        "stellar_luminosity_solar": _value(star.get("luminosity"), 1.0),
        "truth_note": (
            "These values come from the generated system's explicit truth layers. Equilibrium temperature is not "
            "surface temperature, and no solvent, atmosphere, organism, or anomaly is implied."
        ),
    }


def _temperature_fit(value: float | None, bounds: list[float] | None) -> float:
    if value is None or not bounds or len(bounds) != 2:
        return 0.5
    low, high = float(bounds[0]), float(bounds[1])
    if low <= value <= high:
        return 1.0
    scale = max(20.0, (high - low) * 0.5)
    distance = min(abs(value - low), abs(value - high))
    return max(0.02, math.exp(-distance / scale))


def _epistemic_restraint(epistemic_class: str) -> float:
    text = epistemic_class.lower()
    if "only confirmed" in text or "confirmed earth" in text:
        return 1.0
    if "active nasa" in text or "known" in text:
        return 0.9
    if "origin-of-life" in text or "research" in text:
        return 0.82
    if "quantitatively" in text or "theoretical" in text:
        return 0.72
    if "hypothesis" in text:
        return 0.62
    if "speculative" in text or "low-confidence" in text:
        return 0.35
    return 0.65


def _stable_fraction(*parts: str) -> float:
    digest = hashlib.sha256("|".join(parts).encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big") / float(2**64 - 1)


def reasoned_candidate_matrix(
    system: dict[str, Any],
    forge_seed: str,
    registry: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Create a structured scorecard, not hidden chain-of-thought.

    The scorecard explains which explicit constraints influenced eligibility. It is safe to
    preserve for audit, but belongs in the private forge vault until the expedition is revealed.
    """
    registry = registry or load_cosmic_possibility_registry()
    errors = validate_cosmic_possibility_registry(registry)
    if errors:
        raise CosmicPossibilityError("; ".join(errors))
    environment = system_environment(system)
    temp = environment["equilibrium_temperature_k"]
    candidates: list[dict[str, Any]] = []
    for anomaly in registry["anomaly_families"]:
        for architecture in registry["life_architectures"]:
            bounds = architecture.get("environment", {}).get("temperature_k")
            environment_fit = _temperature_fit(temp, bounds)
            observable_overlap = len(
                set(x.lower().replace(" ", "_") for x in anomaly.get("observables", []))
                & set(x.lower().replace(" ", "_") for x in architecture.get("observables", []))
            )
            observability = min(1.0, (len(anomaly.get("observables", [])) + len(architecture.get("observables", []))) / 10.0)
            false_positive_depth = min(1.0, len(anomaly.get("controls", [])) / 4.0)
            causal_depth = min(1.0, len(architecture.get("required_questions", [])) / 4.0)
            restraint = _epistemic_restraint(architecture.get("epistemic_class", ""))
            novelty = _stable_fraction(forge_seed, system.get("system_id", ""), anomaly["id"], architecture["id"])
            cross_domain_bonus = min(0.12, observable_overlap * 0.04)
            score = (
                0.25 * environment_fit
                + 0.18 * observability
                + 0.20 * false_positive_depth
                + 0.17 * causal_depth
                + 0.15 * restraint
                + 0.05 * novelty
                + cross_domain_bonus
            )
            candidates.append({
                "candidate_id": f"{anomaly['id']}::{architecture['id']}",
                "anomaly_family_id": anomaly["id"],
                "life_architecture_id": architecture["id"],
                "score": round(score, 8),
                "scorecard": {
                    "environment_fit": round(environment_fit, 6),
                    "observability": round(observability, 6),
                    "false_positive_depth": round(false_positive_depth, 6),
                    "causal_depth": round(causal_depth, 6),
                    "epistemic_restraint": round(restraint, 6),
                    "novelty_tiebreak": round(novelty, 6),
                    "cross_domain_bonus": round(cross_domain_bonus, 6),
                },
                "claim_ceiling": architecture["claim_ceiling"],
                "source_ids": sorted(set(anomaly.get("source_ids", []) + architecture.get("source_ids", []))),
            })
    candidates.sort(key=lambda item: (-item["score"], item["candidate_id"]))
    shortlist = candidates[:12]
    # The forge seed chooses among the scientifically strongest shortlist instead of always
    # selecting the single maximum. This allows surprising but bounded scenarios.
    selector = _stable_fraction(forge_seed, system.get("system_id", ""), "shortlist-selector")
    weights = [max(0.001, item["score"] ** 4) for item in shortlist]
    total = sum(weights)
    cursor = 0.0
    selected = shortlist[-1]
    for item, weight in zip(shortlist, weights):
        cursor += weight / total
        if selector <= cursor:
            selected = item
            break
    return {
        "schema": "axm.reasoned-candidate-matrix.v1",
        "forge_method": "constraint scorecard plus seeded selection inside a high-quality shortlist",
        "environment": environment,
        "candidate_count": len(candidates),
        "shortlist": shortlist,
        "selected_candidate_id": selected["candidate_id"],
        "selection_receipt": hashlib.sha256(
            json.dumps({"forge_seed": forge_seed, "system_id": system.get("system_id"), "selected": selected["candidate_id"]}, sort_keys=True).encode("utf-8")
        ).hexdigest(),
        "reasoning_summary": [
            "Environment fit controls eligibility but never proves existence.",
            "Candidates with multiple observable channels and strong false-positive controls rank higher.",
            "Speculative architectures remain eligible at reduced authority rather than being silently removed.",
            "The selected theory pair is a private simulation lens, not a claim about the real universe.",
        ],
    }


def registry_index(registry: dict[str, Any] | None = None) -> dict[str, dict[str, Any]]:
    registry = registry or load_cosmic_possibility_registry()
    return {
        "anomalies": {item["id"]: item for item in registry["anomaly_families"]},
        "architectures": {item["id"]: item for item in registry["life_architectures"]},
        "observables": {item["id"]: item for item in registry["agnostic_observables"]},
        "theories": {item["id"]: item for item in registry["universe_theory_families"]},
    }
