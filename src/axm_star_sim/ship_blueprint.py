from __future__ import annotations

import copy
import hashlib
import json
import math
from collections import defaultdict, deque
from typing import Any

from .registry import data_path
C = 299_792_458.0


class ShipBlueprintError(ValueError):
    pass


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def domain_hash(value: Any, domain: str) -> str:
    return hashlib.sha256(f"{domain}|{canonical_json(value)}".encode("utf-8")).hexdigest()


def _load(name: str) -> dict[str, Any]:
    return json.loads(data_path(name).read_text(encoding="utf-8"))


def load_blueprint_registry() -> dict[str, Any]:
    return _load("ship_system_blueprint_registry.json")


def load_interface_graph() -> dict[str, Any]:
    return _load("ship_interface_graph.json")


def load_failure_registry() -> dict[str, Any]:
    return _load("ship_failure_mode_registry.json")


def load_qualification_registry() -> dict[str, Any]:
    return _load("crew_role_qualification_registry.json")


def load_telemetry_metric_registry() -> dict[str, Any]:
    return _load("ship_telemetry_metric_registry.json")


def load_station_display_registry() -> dict[str, Any]:
    return _load("crew_station_display_registry.json")


def load_competency_evolution_registry() -> dict[str, Any]:
    return _load("crew_competency_evolution_registry.json")


def load_blueprint(blueprint_id: str | None = None) -> dict[str, Any]:
    registry = load_blueprint_registry()
    target = blueprint_id or registry["default_blueprint_id"]
    for blueprint in registry["blueprints"]:
        if blueprint["id"] == target:
            return copy.deepcopy(blueprint)
    raise ShipBlueprintError(f"unknown ship blueprint: {target}")


def _system_index(blueprint: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {row["id"]: row for row in blueprint["systems"]}


def _parameter_value(system: dict[str, Any], parameter_id: str) -> Any:
    try:
        return system["parameters"][parameter_id]["value"]
    except KeyError as exc:
        raise ShipBlueprintError(f"missing parameter {system['id']}.{parameter_id}") from exc


def validate_blueprint(blueprint_id: str | None = None) -> dict[str, Any]:
    blueprint = load_blueprint(blueprint_id)
    systems = _system_index(blueprint)
    failures: list[str] = []

    required_systems = {
        "primary_structure", "mmod_and_external_protection",
        "electrical_power_generation", "energy_storage", "power_distribution",
        "thermal_control", "main_propulsion", "reaction_control", "gnc",
        "avionics_cdh", "communications", "eclss_atmosphere", "water_and_waste",
        "fire_and_emergency_response", "radiation_monitoring_and_shelter",
        "docking_airlock_eva", "robotics_and_probe_operations", "external_sensors",
        "science_payload_and_analysis", "crew_health_medical",
        "logistics_maintenance_fabrication", "fault_management",
    }
    missing = sorted(required_systems - set(systems))
    if missing:
        failures.append(f"missing required systems: {missing}")

    valid_truth_types = {
        "catalog_fact", "derived", "simulation_design_assumption", "unknown"
    }
    for system in systems.values():
        if not system.get("functions"):
            failures.append(f"system has no functions: {system['id']}")
        if not system.get("criticality"):
            failures.append(f"system has no criticality: {system['id']}")
        for parameter_id, parameter in system.get("parameters", {}).items():
            truth_type = parameter.get("truth_type")
            if truth_type not in valid_truth_types:
                failures.append(f"invalid truth type {system['id']}.{parameter_id}: {truth_type}")
            if truth_type == "catalog_fact" and not parameter.get("source_ids"):
                failures.append(f"catalog fact lacks source: {system['id']}.{parameter_id}")
            if truth_type == "unknown" and parameter.get("value") is not None:
                failures.append(f"unknown parameter has value: {system['id']}.{parameter_id}")
            if truth_type == "simulation_design_assumption" and not parameter.get("rationale"):
                failures.append(f"assumption lacks rationale: {system['id']}.{parameter_id}")
        for dependency in system.get("dependencies", []):
            if dependency not in systems and dependency != "all_systems":
                failures.append(f"{system['id']} references unknown dependency {dependency}")

    graph = load_interface_graph()
    for edge in graph["edges"]:
        if edge["source"] not in systems and edge["source"] != "all_systems":
            failures.append(f"interface source missing: {edge['source']}")
        if edge["target"] not in systems and edge["target"] != "all_systems":
            failures.append(f"interface target missing: {edge['target']}")

    failure_registry = load_failure_registry()
    for mode in failure_registry["failure_modes"]:
        if mode["system_id"] not in systems:
            failures.append(f"failure mode references unknown system: {mode['id']}")

    source_registry = _load("source_registry.json")
    known_sources = set(source_registry["sources"])

    def check_sources(owner: str, source_ids: list[str]) -> None:
        for source_id in source_ids:
            if source_id not in known_sources:
                failures.append(f"{owner} references unknown source {source_id}")

    for system in systems.values():
        check_sources(f"system {system['id']}", system.get("source_ids", []))
        for parameter_id, parameter in system.get("parameters", {}).items():
            check_sources(f"parameter {system['id']}.{parameter_id}", parameter.get("source_ids", []))
    check_sources("interface graph", graph.get("source_ids", []))
    check_sources("failure registry", failure_registry.get("source_ids", []))

    qualifications = load_qualification_registry()
    check_sources("qualification registry", qualifications.get("source_ids", []))
    for module in qualifications.get("universal_training", []):
        check_sources(f"training {module['id']}", module.get("source_ids", []))
    role_ids = {row["id"] for row in qualifications["role_profiles"]}
    if len(role_ids) != len(qualifications["role_profiles"]):
        failures.append("duplicate qualification role id")
    for profile in qualifications["role_profiles"]:
        for system_id in profile.get("system_depth", {}):
            if system_id not in systems:
                failures.append(f"role {profile['id']} references unknown system {system_id}")

    telemetry = load_telemetry_metric_registry()
    metric_ids = [row["id"] for row in telemetry["metrics"]]
    if len(metric_ids) != len(set(metric_ids)):
        failures.append("duplicate telemetry metric id")
    for metric in telemetry["metrics"]:
        if metric["system_id"] not in systems:
            failures.append(f"metric {metric['id']} references unknown system {metric['system_id']}")
        for role_id in metric.get("role_ids", []):
            if role_id not in role_ids:
                failures.append(f"metric {metric['id']} references unknown role {role_id}")
    check_sources("telemetry registry", telemetry.get("source_ids", []))

    displays = load_station_display_registry()
    known_metrics = set(metric_ids)
    controls = {row["id"] for row in displays["control_influences"]}
    for station in displays["stations"]:
        for role_id in station["seat_role_ids"]:
            if role_id not in role_ids:
                failures.append(f"station {station['id']} references unknown role {role_id}")
        for surface in station["display_surfaces"]:
            for metric_id in surface["metric_ids"]:
                if metric_id not in known_metrics:
                    failures.append(f"surface {surface['id']} references unknown metric {metric_id}")
        for control_id in station["control_influence_ids"]:
            if control_id not in controls:
                failures.append(f"station {station['id']} references unknown control {control_id}")
    check_sources("station display registry", displays.get("source_ids", []))

    competency = load_competency_evolution_registry()
    skill_ids = [row["id"] for row in competency["skills"]]
    if len(skill_ids) != len(set(skill_ids)):
        failures.append("duplicate competency skill id")
    for skill in competency["skills"]:
        if skill["role_id"] not in role_ids:
            failures.append(f"skill {skill['id']} references unknown role {skill['role_id']}")
        for system_id in skill["system_ids"]:
            if system_id not in systems:
                failures.append(f"skill {skill['id']} references unknown system {system_id}")
        for metric_id in skill["metric_ids"]:
            if metric_id not in known_metrics:
                failures.append(f"skill {skill['id']} references unknown metric {metric_id}")
    check_sources("competency registry", competency.get("source_ids", []))

    result = {
        "schema": "axm.ship-blueprint-validation.v1",
        "blueprint_id": blueprint["id"],
        "blueprint_version": blueprint["version"],
        "system_count": len(systems),
        "module_count": len(blueprint["modules"]),
        "interface_count": len(graph["edges"]),
        "failure_mode_count": len(failure_registry["failure_modes"]),
        "role_profile_count": len(qualifications["role_profiles"]),
        "telemetry_metric_count": len(telemetry["metrics"]),
        "station_count": len(displays["stations"]),
        "competency_skill_count": len(competency["skills"]),
        "valid": not failures,
        "failures": failures,
    }
    result["validation_receipt"] = domain_hash(result, "AXM-SHIP-BLUEPRINT-VALIDATION-V1")
    return result


def blueprint_commitment(blueprint_id: str | None = None) -> str:
    blueprint = load_blueprint(blueprint_id)
    return domain_hash(
        {
            "blueprint": blueprint,
            "interfaces": load_interface_graph(),
            "failure_modes": load_failure_registry(),
            "qualifications": load_qualification_registry(),
            "telemetry_metrics": load_telemetry_metric_registry(),
            "station_displays": load_station_display_registry(),
            "competency_evolution": load_competency_evolution_registry(),
        },
        "AXM-FACTUAL-SHIP-BLUEPRINT-V1",
    )


def _default_system_health(blueprint: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        row["id"]: {
            "health": 1.0,
            "availability": 1.0,
            "mode": "nominal",
            "active_fault_ids": [],
            "last_observation": "baseline",
        }
        for row in blueprint["systems"]
    }


def _default_role_training() -> dict[str, dict[str, int]]:
    registry = load_qualification_registry()
    result: dict[str, dict[str, int]] = {}
    for profile in registry["role_profiles"]:
        levels = {
            "roots_and_command_authority": 5,
            "integrated_spacecraft_systems": 2,
            "emergency_and_fault_response": 2,
            "medical_and_physiological_exposure": 1,
            "human_factors_and_crew_resource_management": 2,
            "integrated_simulation_qualification": 2,
        }
        for system_id, level in profile.get("system_depth", {}).items():
            levels[f"system:{system_id}"] = int(level)
        result[profile["id"]] = levels
    return result


def create_ship_state(seed: str, blueprint_id: str | None = None) -> dict[str, Any]:
    blueprint = load_blueprint(blueprint_id)
    systems = _system_index(blueprint)
    generation_nameplate = float(_parameter_value(systems["electrical_power_generation"], "reference_nameplate_power_kw"))
    availability = float(_parameter_value(systems["electrical_power_generation"], "nominal_availability_fraction"))
    battery_capacity = float(_parameter_value(systems["energy_storage"], "usable_capacity_kwh"))
    thermal_capacity = float(_parameter_value(systems["thermal_control"], "nominal_rejection_capacity_kw"))
    stored_water = float(_parameter_value(systems["water_and_waste"], "stored_potable_water_kg"))
    active_humans = int(_parameter_value(systems["eclss_atmosphere"], "active_human_crew"))

    loads = {
        "eclss_atmosphere": 8.0,
        "water_and_waste": 2.5,
        "thermal_control": 7.0,
        "avionics_cdh": 4.0,
        "gnc": 2.0,
        "communications": 3.5,
        "external_sensors": 4.5,
        "crew_health_medical": 1.0,
        "habitability_and_lighting": 4.0,
        "robotics_and_probe_operations": 0.0,
        "science_payload_and_analysis": 2.5,
        "ai_systems_integrator": 1.2,
    }
    state: dict[str, Any] = {
        "schema": "axm.ship-state.v1",
        "blueprint_id": blueprint["id"],
        "blueprint_version": blueprint["version"],
        "blueprint_commitment": blueprint_commitment(blueprint["id"]),
        "seed_receipt": hashlib.sha256(seed.encode("utf-8")).hexdigest(),
        "mission_elapsed_minutes": 0.0,
        "mode": "nominal",
        "system_health": _default_system_health(blueprint),
        "power": {
            "nameplate_generation_kw": generation_nameplate,
            "solar_flux_ratio": 1.0,
            "source_availability_fraction": availability,
            "distribution_efficiency": float(_parameter_value(systems["power_distribution"], "distribution_efficiency")),
            "loads_kw": loads,
            "shed_loads": [],
            "battery_capacity_kwh": battery_capacity,
            "battery_energy_kwh": battery_capacity * 0.82,
            "battery_minimum_reserve_fraction": float(_parameter_value(systems["energy_storage"], "minimum_reserve_fraction")),
        },
        "thermal": {
            "rejection_capacity_kw": thermal_capacity,
            "extra_external_heat_kw": 0.0,
            "thermal_storage_kwh": 0.0,
            "maximum_thermal_storage_kwh": 18.0,
        },
        "atmosphere": {
            "cabin_pressure_kpa": float(_parameter_value(systems["primary_structure"], "nominal_cabin_pressure_kpa")),
            "pressure_leak_kpa_per_hour": 0.0,
            "active_humans": active_humans,
            "oxygen_generation_multiplier": 1.0,
            "co2_removal_multiplier": 1.0,
            "co2_removal_nominal_capacity_person_equivalent": active_humans * (
                1.0 + float(_parameter_value(systems["eclss_atmosphere"], "nominal_co2_removal_margin_fraction"))
            ),
            "oxygen_store_person_days": 90.0,
            "co2_load_person_equivalent": float(active_humans),
            "humidity_state": "nominal",
            "air_quality_state": "nominal",
        },
        "water": {
            "stored_potable_water_kg": stored_water,
            "recovery_fraction": float(_parameter_value(systems["water_and_waste"], "simulation_nominal_recovery_fraction")),
            "recovery_multiplier": 1.0,
            "consumption_kg_per_person_day_assumption": 3.2,
            "other_loss_kg_per_day_assumption": 1.5,
            "quality_state": "nominal",
        },
        "navigation": {
            "position_km": [0.0, 0.0, 0.0],
            "velocity_km_s": [0.0, 0.0, 0.0],
            "attitude_error_deg": 0.05,
            "navigation_uncertainty_km": 0.25,
            "pointing_performance_multiplier": 1.0,
            "propulsion_available": True,
        },
        "communications": {
            "distance_m": 384_400_000.0,
            "availability": 1.0,
            "data_queue_gb": 4.0,
            "store_capacity_gb": float(_parameter_value(systems["communications"], "store_and_forward_capacity_gb")),
            "telemetry_visibility_fraction": 1.0,
        },
        "radiation": {
            "environment_index": 1.0,
            "cumulative_relative_exposure": 0.0,
            "shelter_active": False,
        },
        "structure": {
            "health": 1.0,
            "isolated_rooms": [],
            "pressure_boundary_state": "nominal",
        },
        "crew": {
            "available_human_crew": active_humans,
            "role_training": _default_role_training(),
            "current_workload_by_role": {
                profile["id"]: 0.25
                for profile in load_qualification_registry()["role_profiles"]
            },
        },
        "maintenance": {
            "open_work_orders": [],
            "spares_index": 1.0,
            "repair_capacity_person_hours_per_day": 18.0,
        },
        "command": {
            "pending_recall": None,
            "held_irreversible_actions": [],
        },
        "fault_ledger": [],
        "encounter_ledger": [],
        "state_history": [],
        "assumption_disclosure": {
            "loads_kw": "simulation_design_assumptions",
            "water_consumption": "simulation_design_assumption",
            "oxygen_store": "simulation_design_assumption",
            "thermal_storage": "simulation_design_assumption",
            "complete_vehicle_mass": "unknown",
            "verified_delta_v": "unknown",
        },
    }
    _append_state_history(state, "initial_state")
    state["state_hash"] = state_hash(state)
    return state


def state_hash(state: dict[str, Any]) -> str:
    clean = copy.deepcopy(state)
    clean.pop("state_hash", None)
    return domain_hash(clean, "AXM-SHIP-STATE-V1")


def _compact_state_summary(state: dict[str, Any]) -> dict[str, Any]:
    return {
        "mode": state["mode"],
        "battery_energy_kwh": round(state["power"]["battery_energy_kwh"], 6),
        "cabin_pressure_kpa": round(state["atmosphere"]["cabin_pressure_kpa"], 6),
        "stored_potable_water_kg": round(state["water"]["stored_potable_water_kg"], 6),
        "navigation_uncertainty_km": round(state["navigation"]["navigation_uncertainty_km"], 6),
        "communications_availability": round(state["communications"]["availability"], 6),
        "structure_health": round(state["structure"]["health"], 6),
        "active_fault_count": sum(len(v["active_fault_ids"]) for v in state["system_health"].values()),
    }


def _append_state_history(state: dict[str, Any], reason: str) -> None:
    previous = state["state_history"][-1]["history_hash"] if state["state_history"] else None
    record = {
        "sequence": len(state["state_history"]) + 1,
        "mission_elapsed_minutes": state["mission_elapsed_minutes"],
        "reason": reason,
        "state_summary": _compact_state_summary(state),
        "previous_history_hash": previous,
    }
    record["history_hash"] = domain_hash(record, "AXM-SHIP-STATE-HISTORY-V1")
    state["state_history"].append(record)


def total_power_load_kw(state: dict[str, Any]) -> float:
    return sum(
        value for key, value in state["power"]["loads_kw"].items()
        if key not in state["power"]["shed_loads"]
    )


def evaluate_power(state: dict[str, Any]) -> dict[str, Any]:
    power = state["power"]
    generation = (
        power["nameplate_generation_kw"]
        * power["solar_flux_ratio"]
        * power["source_availability_fraction"]
        * state["system_health"]["electrical_power_generation"]["availability"]
        * power["distribution_efficiency"]
        * state["system_health"]["power_distribution"]["availability"]
    )
    load = total_power_load_kw(state)
    margin = generation - load
    reserve_energy = power["battery_capacity_kwh"] * power["battery_minimum_reserve_fraction"]
    return {
        "generated_power_kw": round(generation, 6),
        "served_load_kw": round(load, 6),
        "power_margin_kw": round(margin, 6),
        "battery_energy_kwh": round(power["battery_energy_kwh"], 6),
        "battery_reserve_energy_kwh": round(reserve_energy, 6),
        "battery_above_reserve": power["battery_energy_kwh"] >= reserve_energy,
        "shed_loads": list(power["shed_loads"]),
    }


def evaluate_thermal(state: dict[str, Any]) -> dict[str, Any]:
    power = evaluate_power(state)
    waste_heat = power["served_load_kw"] + state["thermal"]["extra_external_heat_kw"]
    capacity = state["thermal"]["rejection_capacity_kw"] * state["system_health"]["thermal_control"]["availability"]
    return {
        "waste_heat_kw": round(waste_heat, 6),
        "rejection_capacity_kw": round(capacity, 6),
        "thermal_margin_kw": round(capacity - waste_heat, 6),
        "thermal_storage_kwh": round(state["thermal"]["thermal_storage_kwh"], 6),
        "thermal_storage_limit_kwh": round(state["thermal"]["maximum_thermal_storage_kwh"], 6),
    }


def evaluate_life_support(state: dict[str, Any]) -> dict[str, Any]:
    atmosphere = state["atmosphere"]
    humans = max(0, state["crew"]["available_human_crew"])
    co2_capacity = (
        atmosphere["co2_removal_nominal_capacity_person_equivalent"]
        * atmosphere["co2_removal_multiplier"]
        * state["system_health"]["eclss_atmosphere"]["availability"]
    )
    co2_margin = co2_capacity - humans
    effective_recovery = (
        state["water"]["recovery_fraction"]
        * state["water"]["recovery_multiplier"]
        * state["system_health"]["water_and_waste"]["availability"]
    )
    net_water_loss_per_day = (
        humans * state["water"]["consumption_kg_per_person_day_assumption"] * (1.0 - effective_recovery)
        + state["water"]["other_loss_kg_per_day_assumption"]
    )
    water_days = (
        state["water"]["stored_potable_water_kg"] / net_water_loss_per_day
        if net_water_loss_per_day > 0 else math.inf
    )
    oxygen_days = atmosphere["oxygen_store_person_days"] / humans if humans > 0 else math.inf
    return {
        "active_humans": humans,
        "cabin_pressure_kpa": round(atmosphere["cabin_pressure_kpa"], 6),
        "pressure_loss_rate_kpa_per_hour": round(atmosphere["pressure_leak_kpa_per_hour"], 6),
        "co2_removal_margin_person_equivalent": round(co2_margin, 6),
        "effective_water_recovery_fraction": round(effective_recovery, 6),
        "net_water_loss_kg_per_day": round(net_water_loss_per_day, 6),
        "estimated_water_days": round(water_days, 6) if math.isfinite(water_days) else None,
        "stored_oxygen_days_at_current_crew": round(oxygen_days, 6) if math.isfinite(oxygen_days) else None,
        "air_quality_state": atmosphere["air_quality_state"],
        "water_quality_state": state["water"]["quality_state"],
    }


def evaluate_communications(state: dict[str, Any]) -> dict[str, Any]:
    distance = max(0.0, state["communications"]["distance_m"])
    return {
        "distance_m": distance,
        "one_way_light_time_s": round(distance / C, 9),
        "round_trip_light_time_s": round(2.0 * distance / C, 9),
        "availability": state["communications"]["availability"],
        "data_queue_gb": round(state["communications"]["data_queue_gb"], 6),
        "store_capacity_gb": state["communications"]["store_capacity_gb"],
        "queue_fraction": round(state["communications"]["data_queue_gb"] / state["communications"]["store_capacity_gb"], 6),
        "telemetry_visibility_fraction": state["communications"]["telemetry_visibility_fraction"],
    }


def evaluate_ship(state: dict[str, Any]) -> dict[str, Any]:
    power = evaluate_power(state)
    thermal = evaluate_thermal(state)
    life = evaluate_life_support(state)
    comm = evaluate_communications(state)
    systems = _system_index(load_blueprint(state["blueprint_id"]))
    critical_health = min(
        row["health"]
        for system_id, row in state["system_health"].items()
        if systems[system_id]["criticality"] in {"crew_survival", "mission_critical"}
    )
    safe = (
        power["battery_above_reserve"]
        and life["cabin_pressure_kpa"] >= 55.0
        and life["co2_removal_margin_person_equivalent"] >= 0.0
        and thermal["thermal_storage_kwh"] < thermal["thermal_storage_limit_kwh"]
        and critical_health > 0.2
    )
    result = {
        "schema": "axm.ship-evaluation.v1",
        "mission_elapsed_minutes": state["mission_elapsed_minutes"],
        "mode": state["mode"],
        "power": power,
        "thermal": thermal,
        "life_support": life,
        "communications": comm,
        "navigation": copy.deepcopy(state["navigation"]),
        "radiation": copy.deepcopy(state["radiation"]),
        "structure": copy.deepcopy(state["structure"]),
        "maintenance": copy.deepcopy(state["maintenance"]),
        "command": copy.deepcopy(state["command"]),
        "minimum_critical_system_health": round(critical_health, 6),
        "crew_survival_state_currently_supported": safe,
    }
    result["evaluation_receipt"] = domain_hash(result, "AXM-SHIP-EVALUATION-V1")
    return result


def _set_safe_state_if_needed(state: dict[str, Any]) -> None:
    evaluation = evaluate_ship(state)
    if not evaluation["crew_survival_state_currently_supported"]:
        state["mode"] = "safe_state"
        for load in (
            "robotics_and_probe_operations", "science_payload_and_analysis",
            "external_sensors", "habitability_and_lighting",
        ):
            if load in state["power"]["loads_kw"] and load not in state["power"]["shed_loads"]:
                state["power"]["shed_loads"].append(load)


def advance_ship_state(
    state: dict[str, Any],
    minutes: float,
    activity_loads_kw: dict[str, float] | None = None,
    solar_flux_ratio: float | None = None,
    data_generated_gb: float = 0.0,
) -> dict[str, Any]:
    if minutes < 0:
        raise ShipBlueprintError("minutes cannot be negative")
    updated = copy.deepcopy(state)
    if solar_flux_ratio is not None:
        updated["power"]["solar_flux_ratio"] = max(0.0, float(solar_flux_ratio))
    original_loads = copy.deepcopy(updated["power"]["loads_kw"])
    if activity_loads_kw:
        for key, value in activity_loads_kw.items():
            updated["power"]["loads_kw"][key] = max(0.0, float(value))

    hours = minutes / 60.0
    days = minutes / 1440.0
    power = evaluate_power(updated)
    if power["power_margin_kw"] >= 0:
        efficiency = float(_parameter_value(_system_index(load_blueprint(updated["blueprint_id"]))["energy_storage"], "round_trip_efficiency"))
        charge = power["power_margin_kw"] * hours * efficiency
        updated["power"]["battery_energy_kwh"] = min(updated["power"]["battery_capacity_kwh"], updated["power"]["battery_energy_kwh"] + charge)
    else:
        updated["power"]["battery_energy_kwh"] = max(0.0, updated["power"]["battery_energy_kwh"] + power["power_margin_kw"] * hours)

    thermal = evaluate_thermal(updated)
    if thermal["thermal_margin_kw"] < 0:
        updated["thermal"]["thermal_storage_kwh"] += -thermal["thermal_margin_kw"] * hours
    else:
        updated["thermal"]["thermal_storage_kwh"] = max(0.0, updated["thermal"]["thermal_storage_kwh"] - thermal["thermal_margin_kw"] * hours)

    humans = max(0, updated["crew"]["available_human_crew"])
    effective_recovery = updated["water"]["recovery_fraction"] * updated["water"]["recovery_multiplier"] * updated["system_health"]["water_and_waste"]["availability"]
    net_water_loss = (
        humans * updated["water"]["consumption_kg_per_person_day_assumption"] * (1.0 - effective_recovery)
        + updated["water"]["other_loss_kg_per_day_assumption"]
    ) * days
    updated["water"]["stored_potable_water_kg"] = max(0.0, updated["water"]["stored_potable_water_kg"] - net_water_loss)
    updated["atmosphere"]["oxygen_store_person_days"] = max(
        0.0,
        updated["atmosphere"]["oxygen_store_person_days"]
        - humans * days * max(0.0, 1.0 - updated["atmosphere"]["oxygen_generation_multiplier"]),
    )
    updated["atmosphere"]["cabin_pressure_kpa"] = max(
        0.0,
        updated["atmosphere"]["cabin_pressure_kpa"] - updated["atmosphere"]["pressure_leak_kpa_per_hour"] * hours,
    )
    updated["radiation"]["cumulative_relative_exposure"] += (
        updated["radiation"]["environment_index"] * hours * (0.35 if updated["radiation"]["shelter_active"] else 1.0)
    )

    if updated["communications"]["availability"] > 0:
        transmitted = min(
            updated["communications"]["data_queue_gb"],
            0.15 * minutes * updated["communications"]["availability"],
        )
        updated["communications"]["data_queue_gb"] -= transmitted
    updated["communications"]["data_queue_gb"] = min(
        updated["communications"]["store_capacity_gb"],
        updated["communications"]["data_queue_gb"] + max(0.0, data_generated_gb),
    )

    updated["navigation"]["navigation_uncertainty_km"] += 0.002 * minutes / max(0.1, updated["system_health"]["gnc"]["availability"])
    updated["mission_elapsed_minutes"] += minutes
    updated["power"]["loads_kw"] = original_loads
    _set_safe_state_if_needed(updated)
    _append_state_history(updated, "advance_ship_state")
    updated["state_hash"] = state_hash(updated)
    return updated


def _append_fault(state: dict[str, Any], record: dict[str, Any]) -> None:
    previous = state["fault_ledger"][-1]["fault_hash"] if state["fault_ledger"] else None
    record = copy.deepcopy(record)
    record["sequence"] = len(state["fault_ledger"]) + 1
    record["mission_elapsed_minutes"] = state["mission_elapsed_minutes"]
    record["previous_fault_hash"] = previous
    record["fault_hash"] = domain_hash(record, "AXM-SHIP-FAULT-V1")
    state["fault_ledger"].append(record)


def apply_failure_mode(state: dict[str, Any], failure_mode_id: str) -> dict[str, Any]:
    modes = {row["id"]: row for row in load_failure_registry()["failure_modes"]}
    if failure_mode_id not in modes:
        raise ShipBlueprintError(f"unknown failure mode: {failure_mode_id}")
    mode = modes[failure_mode_id]
    updated = copy.deepcopy(state)
    system_id = mode["system_id"]
    health = updated["system_health"][system_id]
    if failure_mode_id not in health["active_fault_ids"]:
        health["active_fault_ids"].append(failure_mode_id)
    health["mode"] = "faulted"
    effects = mode["effects"]

    if "generation_multiplier" in effects:
        updated["system_health"]["electrical_power_generation"]["availability"] *= effects["generation_multiplier"]
    if "battery_soc_delta" in effects:
        updated["power"]["battery_energy_kwh"] = max(0.0, updated["power"]["battery_energy_kwh"] + effects["battery_soc_delta"] * updated["power"]["battery_capacity_kwh"])
    if "load_service_fraction" in effects:
        updated["system_health"]["power_distribution"]["availability"] *= effects["load_service_fraction"]
    if "thermal_capacity_multiplier" in effects:
        updated["system_health"]["thermal_control"]["availability"] *= effects["thermal_capacity_multiplier"]
    if "pressure_leak_kpa_per_hour" in effects:
        updated["atmosphere"]["pressure_leak_kpa_per_hour"] += effects["pressure_leak_kpa_per_hour"]
        updated["structure"]["pressure_boundary_state"] = "leaking"
    if "structure_health_delta" in effects:
        updated["structure"]["health"] = max(0.0, updated["structure"]["health"] + effects["structure_health_delta"])
        updated["system_health"]["primary_structure"]["health"] = updated["structure"]["health"]
    if "sensor_health_delta" in effects:
        updated["system_health"]["external_sensors"]["health"] = max(0.0, updated["system_health"]["external_sensors"]["health"] + effects["sensor_health_delta"])
    if "co2_removal_multiplier" in effects:
        updated["atmosphere"]["co2_removal_multiplier"] *= effects["co2_removal_multiplier"]
    if "oxygen_generation_multiplier" in effects:
        updated["atmosphere"]["oxygen_generation_multiplier"] *= effects["oxygen_generation_multiplier"]
    if "water_recovery_multiplier" in effects:
        updated["water"]["recovery_multiplier"] *= effects["water_recovery_multiplier"]
    if "power_load_kw_delta" in effects:
        updated["power"]["loads_kw"]["habitability_and_lighting"] = max(0.0, updated["power"]["loads_kw"]["habitability_and_lighting"] + effects["power_load_kw_delta"])
    if "affected_zone_available" in effects and effects["affected_zone_available"] is False:
        zone = f"fault_zone:{failure_mode_id}"
        if zone not in updated["structure"]["isolated_rooms"]:
            updated["structure"]["isolated_rooms"].append(zone)
    if "cdh_capacity_multiplier" in effects:
        updated["system_health"]["avionics_cdh"]["availability"] *= effects["cdh_capacity_multiplier"]
    if "telemetry_visibility_fraction" in effects:
        updated["communications"]["telemetry_visibility_fraction"] *= effects["telemetry_visibility_fraction"]
    if "navigation_uncertainty_km_delta" in effects:
        updated["navigation"]["navigation_uncertainty_km"] += effects["navigation_uncertainty_km_delta"]
    if "pointing_performance_multiplier" in effects:
        updated["navigation"]["pointing_performance_multiplier"] *= effects["pointing_performance_multiplier"]
    if "communications_availability" in effects:
        updated["communications"]["availability"] = effects["communications_availability"]
    if "propulsion_available" in effects:
        updated["navigation"]["propulsion_available"] = effects["propulsion_available"]
    if "docking_transfer_allowed" in effects and effects["docking_transfer_allowed"] is False:
        updated["system_health"]["docking_airlock_eva"]["mode"] = "transfer_inhibited"
    if "radiation_index_delta" in effects:
        updated["radiation"]["environment_index"] += effects["radiation_index_delta"]
        updated["radiation"]["shelter_active"] = True
    if "robotics_health_delta" in effects:
        updated["system_health"]["robotics_and_probe_operations"]["health"] = max(0.0, updated["system_health"]["robotics_and_probe_operations"]["health"] + effects["robotics_health_delta"])
    if "available_human_crew_delta" in effects:
        updated["crew"]["available_human_crew"] = max(0, updated["crew"]["available_human_crew"] + int(effects["available_human_crew_delta"]))

    if mode["command_level"] == "command_required":
        updated["command"]["pending_recall"] = {
            "reason": failure_mode_id,
            "summary": f"{mode['system_id']} fault requires command review.",
            "held_irreversible_action": True,
        }
    _append_fault(updated, {
        "failure_mode_id": failure_mode_id,
        "system_id": system_id,
        "criticality": mode["criticality"],
        "automatic_response": mode["automatic_response"],
        "command_level": mode["command_level"],
        "effects": effects,
    })
    _set_safe_state_if_needed(updated)
    _append_state_history(updated, f"apply_failure_mode:{failure_mode_id}")
    updated["state_hash"] = state_hash(updated)
    return updated


def _append_encounter(state: dict[str, Any], record: dict[str, Any]) -> None:
    previous = state["encounter_ledger"][-1]["encounter_hash"] if state["encounter_ledger"] else None
    record = copy.deepcopy(record)
    record["sequence"] = len(state["encounter_ledger"]) + 1
    record["mission_elapsed_minutes"] = state["mission_elapsed_minutes"]
    record["previous_encounter_hash"] = previous
    record["encounter_hash"] = domain_hash(record, "AXM-SHIP-ENCOUNTER-EFFECT-V1")
    state["encounter_ledger"].append(record)


def apply_encounter_effects(state: dict[str, Any], encounter: dict[str, Any]) -> dict[str, Any]:
    updated = copy.deepcopy(state)
    effects = copy.deepcopy(encounter.get("effects", {}))
    observations = copy.deepcopy(encounter.get("observations", []))
    declared_intent = encounter.get("declared_intent")
    if declared_intent not in {None, "unknown", "cooperative", "hostile", "natural", "accidental"}:
        raise ShipBlueprintError("invalid declared intent")
    intent_assessment = declared_intent or "unknown"

    kinetic = max(0.0, float(effects.get("kinetic_impact_index", 0.0)))
    if kinetic:
        damage = min(0.45, 0.04 * math.log1p(kinetic))
        updated["structure"]["health"] = max(0.0, updated["structure"]["health"] - damage)
        updated["system_health"]["primary_structure"]["health"] = updated["structure"]["health"]
        updated["system_health"]["mmod_and_external_protection"]["health"] = max(0.0, updated["system_health"]["mmod_and_external_protection"]["health"] - damage * 0.8)
        if kinetic > 8.0:
            updated["atmosphere"]["pressure_leak_kpa_per_hour"] += min(12.0, 0.3 * kinetic)
            updated["structure"]["pressure_boundary_state"] = "possible_penetration"

    external_heat = max(0.0, float(effects.get("external_thermal_load_kw", 0.0)))
    updated["thermal"]["extra_external_heat_kw"] += external_heat

    radiation = max(0.0, float(effects.get("radiation_index_delta", 0.0)))
    updated["radiation"]["environment_index"] += radiation
    if radiation >= 2.0:
        updated["radiation"]["shelter_active"] = True

    emi = max(0.0, min(1.0, float(effects.get("electromagnetic_interference_fraction", 0.0))))
    updated["communications"]["availability"] *= 1.0 - emi
    updated["system_health"]["external_sensors"]["availability"] *= 1.0 - 0.55 * emi

    nav_uncertainty = max(0.0, float(effects.get("navigation_uncertainty_km_delta", 0.0)))
    updated["navigation"]["navigation_uncertainty_km"] += nav_uncertainty

    power_loss = max(0.0, min(1.0, float(effects.get("power_generation_loss_fraction", 0.0))))
    updated["system_health"]["electrical_power_generation"]["availability"] *= max(0.0, 1.0 - power_loss)

    data_fault = max(0.0, min(1.0, float(effects.get("data_integrity_risk_fraction", 0.0))))
    if data_fault:
        updated["communications"]["telemetry_visibility_fraction"] *= 1.0 - 0.6 * data_fault
        updated["command"]["held_irreversible_actions"].append({
            "reason": "data_integrity_risk",
            "fraction": data_fault,
            "rule": "Irreversible commands held until state and command provenance are revalidated.",
        })

    contact_load = max(0.0, float(effects.get("docking_contact_load_index", 0.0)))
    if contact_load:
        updated["system_health"]["docking_airlock_eva"]["health"] = max(0.0, updated["system_health"]["docking_airlock_eva"]["health"] - min(0.3, contact_load * 0.03))

    medical = max(0, int(effects.get("crew_injury_count", 0)))
    if medical:
        updated["crew"]["available_human_crew"] = max(0, updated["crew"]["available_human_crew"] - medical)

    requires_command = any([
        kinetic >= 3.0,
        radiation >= 2.0,
        nav_uncertainty >= 5.0,
        power_loss >= 0.25,
        data_fault >= 0.25,
        contact_load >= 5.0,
        medical > 0,
    ])
    if requires_command:
        updated["command"]["pending_recall"] = {
            "reason": encounter.get("encounter_id", "unidentified_encounter"),
            "summary": encounter.get("summary", "Encounter effects exceed routine crew authority."),
            "held_irreversible_action": True,
        }

    record = {
        "encounter_id": encounter.get("encounter_id") or domain_hash(encounter, "AXM-ENCOUNTER-ID-V1")[:20],
        "summary": encounter.get("summary", "Unspecified encounter"),
        "observations": observations,
        "effects": effects,
        "declared_intent": declared_intent,
        "intent_assessment": intent_assessment,
        "hostility_inferred_from_damage": False,
        "command_recall_required": requires_command,
    }
    _append_encounter(updated, record)
    _set_safe_state_if_needed(updated)
    _append_state_history(updated, f"apply_encounter:{record['encounter_id']}")
    updated["state_hash"] = state_hash(updated)
    return updated


def role_profiles() -> dict[str, dict[str, Any]]:
    return {row["id"]: row for row in load_qualification_registry()["role_profiles"]}


def role_perspective_snapshot(state: dict[str, Any], role_id: str) -> dict[str, Any]:
    profiles = role_profiles()
    if role_id not in profiles:
        raise ShipBlueprintError(f"unknown role profile: {role_id}")
    evaluation = evaluate_ship(state)
    profile = profiles[role_id]
    metric_map = {
        "crew_survival_margin": evaluation["crew_survival_state_currently_supported"],
        "mission_objective_state": state["mode"],
        "irreversible_decision_count": len(state["command"]["held_irreversible_actions"]),
        "available_reversible_options": None,
        "cross_system_risk": 1.0 - evaluation["minimum_critical_system_health"],
        "crew_readiness": state["crew"]["available_human_crew"],
        "communications_latency": evaluation["communications"]["one_way_light_time_s"],
        "command_authority": profile["may_authorize"],
        "interface_consistency": max(0.0, 1.0 - len(state["fault_ledger"]) * 0.01),
        "telemetry_contradictions": 1.0 - state["communications"]["telemetry_visibility_fraction"],
        "root_eligibility": "required",
        "cross_system_fault_propagation": len(state["fault_ledger"]),
        "data_provenance": "hash_chained",
        "model_uncertainty": state["navigation"]["navigation_uncertainty_km"],
        "replay_integrity": state_hash(state) == state.get("state_hash"),
        "position_velocity_state": {"position_km": state["navigation"]["position_km"], "velocity_km_s": state["navigation"]["velocity_km_s"]},
        "navigation_uncertainty": state["navigation"]["navigation_uncertainty_km"],
        "relative_motion": "scenario_dependent",
        "attitude_error": state["navigation"]["attitude_error_deg"],
        "pointing_constraints": {"performance_multiplier": state["navigation"]["pointing_performance_multiplier"]},
        "maneuver_reversibility": state["navigation"]["propulsion_available"],
        "collision_risk": "requires encounter geometry",
        "power_margin_kw": evaluation["power"]["power_margin_kw"],
        "battery_state_of_charge": state["power"]["battery_energy_kwh"] / state["power"]["battery_capacity_kwh"],
        "thermal_margin_kw": evaluation["thermal"]["thermal_margin_kw"],
        "pressure_integrity": state["structure"]["pressure_boundary_state"],
        "life_support_margin": evaluation["life_support"]["co2_removal_margin_person_equivalent"],
        "maintenance_backlog": len(state["maintenance"]["open_work_orders"]),
        "spares_and_repair_time": {"spares_index": state["maintenance"]["spares_index"], "person_hours_per_day": state["maintenance"]["repair_capacity_person_hours_per_day"]},
        "measurement_quality": state["system_health"]["external_sensors"]["health"],
        "calibration_state": state["system_health"]["external_sensors"]["mode"],
        "independent_replication": "case_dependent",
        "false_positive_controls": "case_dependent",
        "hypothesis_contradictions": "case_dependent",
        "claim_ceiling": "case_dependent",
        "unresolved_alternatives": "case_dependent",
        "one_way_light_time": evaluation["communications"]["one_way_light_time_s"],
        "link_availability": evaluation["communications"]["availability"],
        "antenna_pointing": state["navigation"]["pointing_performance_multiplier"],
        "data_queue": evaluation["communications"]["data_queue_gb"],
        "command_integrity": state["communications"]["telemetry_visibility_fraction"],
        "robot_contact_force": "operation_dependent",
        "remote_system_latency": evaluation["communications"]["one_way_light_time_s"],
        "crew_reported_condition": "privacy_controlled_record",
        "environmental_exposure": state["radiation"]["cumulative_relative_exposure"],
        "fitness_for_task": "requires medical assessment",
        "medical_resource_availability": state["maintenance"]["spares_index"],
        "evacuation_or_safe_haven_time": "mission_geometry_dependent",
    }
    snapshot = {
        "schema": "axm.crew-role-perspective.v1",
        "role_id": role_id,
        "display_name": profile["display_name"],
        "ship_state_hash": state["state_hash"],
        "starting_perspective_metrics": {key: metric_map.get(key) for key in profile["starting_perspective_metrics"]},
        "system_depth": profile["system_depth"],
        "role_training": profile["role_training"],
        "may_authorize": profile["may_authorize"],
        "may_not_override": profile["may_not_override"],
        "perspective_rule": (
            "The role begins with factual system metrics and qualification depth. "
            "It may evolve strategies and derived principles without changing the immutable roots."
        ),
    }
    snapshot["perspective_receipt"] = domain_hash(snapshot, "AXM-CREW-ROLE-PERSPECTIVE-V1")
    return snapshot


def task_readiness(
    state: dict[str, Any],
    role_id: str,
    required_system_levels: dict[str, int],
    required_training_levels: dict[str, int] | None = None,
) -> dict[str, Any]:
    profiles = role_profiles()
    if role_id not in profiles:
        raise ShipBlueprintError(f"unknown role profile: {role_id}")
    training = state["crew"]["role_training"].get(role_id, {})
    gaps = []
    for system_id, required_level in required_system_levels.items():
        actual = int(training.get(f"system:{system_id}", 0))
        if actual < required_level:
            gaps.append({"type": "system_depth", "system_id": system_id, "required": required_level, "actual": actual})
    for training_id, required_level in (required_training_levels or {}).items():
        actual = int(training.get(training_id, 0))
        if actual < required_level:
            gaps.append({"type": "training", "training_id": training_id, "required": required_level, "actual": actual})
    result = {
        "schema": "axm.crew-task-readiness.v1",
        "role_id": role_id,
        "ready": not gaps,
        "gaps": gaps,
        "required_system_levels": required_system_levels,
        "required_training_levels": required_training_levels or {},
    }
    result["readiness_receipt"] = domain_hash(result, "AXM-CREW-TASK-READINESS-V1")
    return result


def qualification_gap_plan(state: dict[str, Any], role_id: str, target_system_levels: dict[str, int]) -> dict[str, Any]:
    readiness = task_readiness(state, role_id, target_system_levels)
    modules = []
    for gap in readiness["gaps"]:
        if gap["type"] == "system_depth":
            modules.append({
                "module_id": f"qualify:{gap['system_id']}:{gap['required']}",
                "system_id": gap["system_id"],
                "current_level": gap["actual"],
                "target_level": gap["required"],
                "required_evidence": [
                    "knowledge_check", "part_task_simulation",
                    "integrated_off_nominal_simulation",
                    "instructor_or_system_verifier_signoff",
                ],
                "automatic_promotion_forbidden": True,
            })
    result = {
        "schema": "axm.crew-qualification-gap-plan.v1",
        "role_id": role_id,
        "ready_now": readiness["ready"],
        "training_modules": modules,
        "rule": "Reading or model output alone does not grant operational qualification.",
    }
    result["plan_receipt"] = domain_hash(result, "AXM-CREW-QUALIFICATION-GAP-PLAN-V1")
    return result


def fault_propagation_paths(system_id: str) -> list[list[str]]:
    systems = _system_index(load_blueprint())
    if system_id not in systems:
        raise ShipBlueprintError(f"unknown system: {system_id}")
    graph = load_interface_graph()
    adjacency: dict[str, list[str]] = defaultdict(list)
    for edge in graph["edges"]:
        if edge["source"] == "all_systems" or edge["target"] == "all_systems":
            continue
        adjacency[edge["source"]].append(edge["target"])
    paths: list[list[str]] = []
    queue: deque[list[str]] = deque([[system_id]])
    seen_depth: dict[str, int] = {system_id: 0}
    while queue:
        path = queue.popleft()
        if len(path) >= 7:
            continue
        for target in adjacency.get(path[-1], []):
            new_path = path + [target]
            paths.append(new_path)
            depth = len(new_path) - 1
            if depth < seen_depth.get(target, 999):
                seen_depth[target] = depth
                queue.append(new_path)
    return paths


def verify_ship_state(state: dict[str, Any]) -> dict[str, Any]:
    failures: list[str] = []
    try:
        validation = validate_blueprint(state.get("blueprint_id"))
        if not validation["valid"]:
            failures.extend(validation["failures"])
    except Exception as exc:
        failures.append(f"blueprint validation error: {exc}")

    if state.get("blueprint_commitment") != blueprint_commitment(state.get("blueprint_id")):
        failures.append("blueprint commitment mismatch")

    previous = None
    for index, record in enumerate(state.get("fault_ledger", []), start=1):
        core = copy.deepcopy(record)
        supplied = core.pop("fault_hash", None)
        if core.get("sequence") != index:
            failures.append(f"fault sequence mismatch at {index}")
        if core.get("previous_fault_hash") != previous:
            failures.append(f"fault previous hash mismatch at {index}")
        if supplied != domain_hash(core, "AXM-SHIP-FAULT-V1"):
            failures.append(f"fault hash mismatch at {index}")
        previous = supplied

    previous = None
    for index, record in enumerate(state.get("encounter_ledger", []), start=1):
        core = copy.deepcopy(record)
        supplied = core.pop("encounter_hash", None)
        if core.get("sequence") != index:
            failures.append(f"encounter sequence mismatch at {index}")
        if core.get("previous_encounter_hash") != previous:
            failures.append(f"encounter previous hash mismatch at {index}")
        if supplied != domain_hash(core, "AXM-SHIP-ENCOUNTER-EFFECT-V1"):
            failures.append(f"encounter hash mismatch at {index}")
        previous = supplied

    previous = None
    for index, record in enumerate(state.get("state_history", []), start=1):
        core = copy.deepcopy(record)
        supplied = core.pop("history_hash", None)
        if core.get("sequence") != index:
            failures.append(f"history sequence mismatch at {index}")
        if core.get("previous_history_hash") != previous:
            failures.append(f"history previous hash mismatch at {index}")
        if supplied != domain_hash(core, "AXM-SHIP-STATE-HISTORY-V1"):
            failures.append(f"history hash mismatch at {index}")
        previous = supplied

    if state.get("state_hash") != state_hash(state):
        failures.append("state hash mismatch")

    result = {
        "schema": "axm.ship-state-verification.v1",
        "valid": not failures,
        "failures": failures,
        "fault_count": len(state.get("fault_ledger", [])),
        "encounter_count": len(state.get("encounter_ledger", [])),
        "history_count": len(state.get("state_history", [])),
        "blueprint_commitment": state.get("blueprint_commitment"),
    }
    result["verification_receipt"] = domain_hash(result, "AXM-SHIP-STATE-VERIFY-V1")
    return result
