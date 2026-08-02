from __future__ import annotations

import math
from typing import Any

from .constants import (
    AU_M,
    SECONDS_PER_DAY,
    SOLAR_GM_M3_S2,
    STEFAN_BOLTZMANN_W_M2_K4,
)

C_M_S = 299_792_458.0
SOLAR_CONSTANT_W_M2 = 1361.0
PLANCK_J_S = 6.62607015e-34

PHYSICS_SCHEMA = "axm.runtime-physics-snapshot.v1"


def _value(record: Any, default: float = 0.0) -> float:
    if isinstance(record, dict) and "value" in record:
        return float(record["value"])
    try:
        return float(record)
    except (TypeError, ValueError):
        return float(default)


def planet_by_id(system: dict[str, Any], planet_id: str | None) -> dict[str, Any]:
    for planet in system["planets"]:
        if planet["id"] == planet_id:
            return planet
    return system["planets"][0]


def solve_kepler(mean_anomaly_rad: float, eccentricity: float, iterations: int = 12) -> float:
    m = mean_anomaly_rad % (2.0 * math.pi)
    e = min(0.95, max(0.0, float(eccentricity)))
    estimate = m if e < 0.8 else math.pi
    for _ in range(iterations):
        denominator = 1.0 - e * math.cos(estimate)
        if abs(denominator) < 1e-12:
            break
        estimate -= (estimate - e * math.sin(estimate) - m) / denominator
    return estimate


def orbital_state(planet: dict[str, Any], mission_time_hours: float, phase_shift_deg: float = 0.0) -> dict[str, float]:
    facts = planet["facts"]
    period_days = max(1e-9, _value(facts["orbital_period"]))
    eccentricity = _value(facts["eccentricity"])
    semi_major_axis_au = _value(facts["semi_major_axis"])
    initial_phase_deg = float(planet.get("visual", {}).get("phase_deg", 0.0))
    mean_anomaly = math.radians(initial_phase_deg + phase_shift_deg) + 2.0 * math.pi * (mission_time_hours / 24.0) / period_days
    eccentric_anomaly = solve_kepler(mean_anomaly, eccentricity)
    true_anomaly = 2.0 * math.atan2(
        math.sqrt(1.0 + eccentricity) * math.sin(eccentric_anomaly / 2.0),
        math.sqrt(max(1e-12, 1.0 - eccentricity)) * math.cos(eccentric_anomaly / 2.0),
    )
    radius_au = semi_major_axis_au * (1.0 - eccentricity * math.cos(eccentric_anomaly))
    phase_angle = abs(math.pi - abs(true_anomaly % (2.0 * math.pi) - math.pi))
    illuminated_fraction = (1.0 + math.cos(phase_angle)) / 2.0
    return {
        "mean_anomaly_deg": round(math.degrees(mean_anomaly) % 360.0, 6),
        "eccentric_anomaly_deg": round(math.degrees(eccentric_anomaly) % 360.0, 6),
        "true_anomaly_deg": round(math.degrees(true_anomaly) % 360.0, 6),
        "star_distance_au": round(radius_au, 9),
        "illuminated_fraction": round(max(0.0, min(1.0, illuminated_fraction)), 6),
    }


def _action_configuration(action: dict[str, Any]) -> dict[str, float]:
    category = action["category"]
    params = action.get("parameters", {})
    base = {
        "integration_seconds": 1800.0,
        "instrument_power_kw": 16.0,
        "aperture_m2": 4.0,
        "quantum_efficiency": 0.72,
        "read_noise_e": 4.5,
        "dark_current_e_s_pix": 0.012,
        "pixel_count": 64.0,
        "background_e_s_pix": 0.04,
        "reads": 4.0,
        "target_contrast": 2.2e-8,
        "absorptivity": 0.28,
        "emissivity": 0.82,
        "sunlit_area_m2": 95.0,
        "radiator_area_m2": 58.0,
        "radiator_temperature_k": 305.0,
        "incidence_factor": 0.45,
    }
    if category == "patient_observation":
        base.update(integration_seconds=7200.0, instrument_power_kw=11.0, reads=8.0)
    elif category == "instrument":
        base.update(integration_seconds=3600.0, instrument_power_kw=24.0, aperture_m2=6.0, reads=10.0)
    elif category == "probe":
        base.update(integration_seconds=900.0, instrument_power_kw=9.0, aperture_m2=0.7, target_contrast=8.0e-7)
    elif category == "engineering":
        base.update(integration_seconds=300.0, instrument_power_kw=4.0, target_contrast=1.0e-9, incidence_factor=0.30)
    elif category == "move_on":
        base.update(integration_seconds=240.0, instrument_power_kw=3.0, target_contrast=4.0e-9)

    base["integration_seconds"] *= float(params.get("integration_scale", 1.0))
    power_fraction = float(params.get("power_fraction", 1.0))
    base["instrument_power_kw"] *= power_fraction
    base["target_contrast"] *= 1.18 if params.get("band_isolation") else 1.0
    base["read_noise_e"] *= 0.72 if params.get("cross_calibration") else 1.0
    base["incidence_factor"] *= 0.35 if params.get("thermal_attitude") == "edge-on" else 1.0
    return base


def _technology_parameter(profile: dict[str, Any], parameter_id: str) -> dict[str, Any] | None:
    for item in profile.get("known_parameter_summary", []):
        if item.get("id") == parameter_id:
            return item
    return None


def technology_physics_envelope(
    system: dict[str, Any],
    action: dict[str, Any],
    configuration: dict[str, float],
) -> tuple[dict[str, Any], dict[str, float]]:
    """Bind a reference action model to published technology facts without inventing capability.

    The action model can explore a potential operating point. It becomes a core-constrained
    scenario only when a source-pinned value exists. Even then, total generation is not treated
    as payload power and transfer requirements are never treated as demonstrated capability.
    """
    profile = system.get("ship", {}).get("technology_core") or {}
    core = profile.get("selected_core") or {}
    capabilities = set(core.get("capability_ids", []))
    known_generation = _technology_parameter(profile, "solar_power_generation")
    category = action.get("category", "instrument")
    scenario_fraction = {
        "patient_observation": 0.35,
        "instrument": 0.55,
        "probe": 0.25,
        "engineering": 0.20,
        "move_on": 0.15,
    }.get(category, 0.30)

    adjusted = dict(configuration)
    power = {
        "requested_reference_instrument_power_kw": round(configuration["instrument_power_kw"], 6),
        "published_generation_kw": None,
        "scenario_allocation_fraction": scenario_fraction,
        "scenario_power_ceiling_kw": None,
        "used_in_thermal_model_kw": round(configuration["instrument_power_kw"], 6),
        "status": "unbounded_reference_scenario",
        "truth_note": (
            "No source-pinned electrical generation value exists for this exact core snapshot; "
            "the instrument power is an AXM reference scenario and does not assert installed hardware."
        ),
    }
    if known_generation is not None:
        generation_kw = float(known_generation["value"])
        ceiling_kw = generation_kw * scenario_fraction
        adjusted["instrument_power_kw"] = min(configuration["instrument_power_kw"], ceiling_kw)
        power.update({
            "published_generation_kw": generation_kw,
            "published_generation_source_ids": known_generation.get("source_ids", []),
            "scenario_power_ceiling_kw": round(ceiling_kw, 6),
            "used_in_thermal_model_kw": round(adjusted["instrument_power_kw"], 6),
            "status": "source_bounded_potential_scenario",
            "truth_note": (
                "The ceiling is an AXM scenario fraction multiplied by published total generation. "
                "It is not a claim that this amount is available to payloads after platform loads."
            ),
        })

    crew_capacity = _technology_parameter(profile, "crew_capacity") or _technology_parameter(profile, "early_crew_capacity")
    duration = _technology_parameter(profile, "standalone_mission_duration_max") or _technology_parameter(profile, "early_crew_stay_max")
    crew = {
        "capacity": crew_capacity.get("value") if crew_capacity else None,
        "capacity_unit": crew_capacity.get("unit") if crew_capacity else None,
        "duration_max_days": duration.get("value") if duration else None,
        "duration_unit": duration.get("unit") if duration else None,
        "status": "source_pinned" if crew_capacity or duration else "unknown_for_exact_core",
        "source_ids": sorted(set((crew_capacity or {}).get("source_ids", []) + (duration or {}).get("source_ids", []))),
    }

    propulsion_caps = sorted(cap for cap in capabilities if cap in {
        "chemical_orbital_maneuvering", "solar_electric_propulsion", "cryogenic_propulsion"
    })
    propulsion = {
        "published_capability_ids": propulsion_caps,
        "quantitative_performance_status": "blocked_unknown",
        "blocked_quantities": ["continuous_acceleration", "delta_v_capability", "mission_range", "crew_g_load"],
        "truth_note": (
            "The trajectory section calculates an environmental transfer requirement only. "
            "It does not claim this selected core can supply the required delta-v or acceleration."
        ),
    }

    protection = {
        "published_capability_ids": sorted(cap for cap in capabilities if cap in {
            "radiation_and_micrometeoroid_protection", "radiation_monitoring"
        }),
        "numeric_shielding_factor_status": "not_published_in_pinned_registry",
        "truth_note": (
            "The radiation shielding factor remains an AXM operational scenario, not a measured value for the selected core."
        ),
    }

    supported_functions = [
        item["function_id"] for item in profile.get("exploration_function_translation", [])
        if item.get("supported_by_selected_core")
    ]
    envelope = {
        "schema": "axm.technology-physics-envelope.v1",
        "selected_core_id": profile.get("selected_core_id"),
        "selected_core_name": core.get("name"),
        "core_class": core.get("core_class"),
        "catalog_as_of_date": profile.get("as_of_date"),
        "planning_horizon_year": profile.get("planning_horizon_year"),
        "selection_receipt": profile.get("selection_receipt"),
        "power": power,
        "crew": crew,
        "propulsion": propulsion,
        "protection": protection,
        "supported_exploration_function_analogs": supported_functions,
        "unknown_parameters": core.get("unknown_parameters", []),
        "blocked_calculations": profile.get("blocked_calculations", []),
        "authority_rule": (
            "Catalog facts constrain only calculations they directly support. Unknown values remain blocked; "
            "scenario values are labelled and never promoted into catalog facts."
        ),
    }
    return envelope, adjusted


def sensor_expectation(
    *,
    stellar_flux_w_m2: float,
    illuminated_fraction: float,
    sensor_health_percent: float,
    configuration: dict[str, float],
) -> dict[str, float]:
    # A representative visible photon energy is used only for the simulation instrument model.
    wavelength_m = 550e-9
    photon_energy_j = PLANCK_J_S * C_M_S / wavelength_m
    collecting_power_w = max(0.0, stellar_flux_w_m2) * configuration["aperture_m2"]
    target_power_w = collecting_power_w * configuration["target_contrast"] * max(0.015, illuminated_fraction)
    target_photon_rate = target_power_w / photon_energy_j
    health = max(0.05, min(1.0, sensor_health_percent / 100.0))
    signal_e = target_photon_rate * configuration["quantum_efficiency"] * configuration["integration_seconds"] * health
    background_e = configuration["background_e_s_pix"] * configuration["integration_seconds"] * configuration["pixel_count"]
    dark_e = configuration["dark_current_e_s_pix"] * configuration["integration_seconds"] * configuration["pixel_count"]
    read_variance = configuration["read_noise_e"] ** 2 * configuration["pixel_count"] * configuration["reads"]
    systematic_variance = (signal_e * 0.0035) ** 2
    variance = max(1e-12, signal_e + background_e + dark_e + read_variance + systematic_variance)
    noise_e = math.sqrt(variance)
    snr = signal_e / noise_e
    return {
        "signal_electrons": round(signal_e, 6),
        "background_electrons": round(background_e, 6),
        "dark_electrons": round(dark_e, 6),
        "read_variance_e2": round(read_variance, 6),
        "systematic_variance_e2": round(systematic_variance, 6),
        "total_noise_electrons": round(noise_e, 6),
        "expected_snr": round(snr, 6),
        "integration_seconds": round(configuration["integration_seconds"], 3),
        "wavelength_m": wavelength_m,
    }


def thermal_expectation(
    *,
    stellar_flux_w_m2: float,
    configuration: dict[str, float],
    ship_heat_percent: float,
) -> dict[str, float]:
    absorbed_w = (
        stellar_flux_w_m2
        * configuration["sunlit_area_m2"]
        * configuration["absorptivity"]
        * configuration["incidence_factor"]
    )
    instrument_w = configuration["instrument_power_kw"] * 1000.0
    emitted_w = (
        configuration["emissivity"]
        * STEFAN_BOLTZMANN_W_M2_K4
        * configuration["radiator_area_m2"]
        * configuration["radiator_temperature_k"] ** 4
    )
    inherited_w = max(0.0, ship_heat_percent - 12.0) * 170.0
    net_w = absorbed_w + instrument_w + inherited_w - emitted_w
    load_ratio = (absorbed_w + instrument_w + inherited_w) / max(1.0, emitted_w)
    return {
        "absorbed_stellar_w": round(absorbed_w, 6),
        "instrument_waste_heat_w": round(instrument_w, 6),
        "radiator_capacity_w": round(emitted_w, 6),
        "inherited_heat_equivalent_w": round(inherited_w, 6),
        "net_thermal_w": round(net_w, 6),
        "thermal_load_ratio": round(load_ratio, 6),
        "thermal_margin_w": round(emitted_w - absorbed_w - instrument_w - inherited_w, 6),
    }


def radiation_expectation(
    *,
    star_age_gyr: float,
    star_distance_au: float,
    shielding_factor: float,
) -> dict[str, float | str]:
    # This is deliberately an engineering risk index, not a human dose calculation.
    age_activity = max(0.35, min(4.0, (4.6 / max(0.12, star_age_gyr)) ** 0.55))
    inverse_square = 1.0 / max(0.01, star_distance_au) ** 2
    unshielded_index = age_activity * inverse_square
    shielded_index = unshielded_index * max(0.08, 1.0 - shielding_factor)
    if shielded_index < 0.8:
        band = "low"
    elif shielded_index < 2.5:
        band = "elevated"
    elif shielded_index < 8.0:
        band = "high"
    else:
        band = "severe"
    return {
        "stellar_activity_factor": round(age_activity, 6),
        "inverse_square_factor": round(inverse_square, 6),
        "unshielded_risk_index": round(unshielded_index, 6),
        "shielded_risk_index": round(shielded_index, 6),
        "risk_band": band,
        "model_scope": "relative spacecraft electronics/operations risk index; not absorbed dose or medical exposure",
    }


def communication_expectation(distance_au: float, data_volume_mbit: float = 220.0, link_rate_kbps: float = 64.0) -> dict[str, float]:
    one_way_s = max(0.0, distance_au) * AU_M / C_M_S
    transmit_s = data_volume_mbit * 1000.0 / max(0.001, link_rate_kbps)
    return {
        "distance_au": round(distance_au, 9),
        "one_way_light_time_s": round(one_way_s, 6),
        "round_trip_light_time_s": round(one_way_s * 2.0, 6),
        "data_volume_mbit": round(data_volume_mbit, 3),
        "link_rate_kbps": round(link_rate_kbps, 3),
        "transmit_duration_s": round(transmit_s, 6),
        "earliest_full_response_s": round(one_way_s * 2.0 + transmit_s, 6),
    }


def hohmann_transfer(star_mass_solar: float, origin_au: float, target_au: float) -> dict[str, float]:
    r1 = max(0.001, origin_au) * AU_M
    r2 = max(0.001, target_au) * AU_M
    mu = SOLAR_GM_M3_S2 * max(0.08, star_mass_solar)
    transfer_a = (r1 + r2) / 2.0
    transfer_time_s = math.pi * math.sqrt(transfer_a ** 3 / mu)
    v1 = math.sqrt(mu / r1)
    v2 = math.sqrt(mu / r2)
    vt1 = math.sqrt(mu * (2.0 / r1 - 1.0 / transfer_a))
    vt2 = math.sqrt(mu * (2.0 / r2 - 1.0 / transfer_a))
    dv1 = abs(vt1 - v1)
    dv2 = abs(v2 - vt2)
    return {
        "origin_au": round(origin_au, 9),
        "target_au": round(target_au, 9),
        "transfer_time_days": round(transfer_time_s / SECONDS_PER_DAY, 6),
        "departure_delta_v_km_s": round(dv1 / 1000.0, 6),
        "arrival_delta_v_km_s": round(dv2 / 1000.0, 6),
        "total_delta_v_km_s": round((dv1 + dv2) / 1000.0, 6),
    }


def build_physics_snapshot(
    system: dict[str, Any],
    state: dict[str, Any],
    action: dict[str, Any],
) -> dict[str, Any]:
    planet = planet_by_id(system, action.get("target_planet_id"))
    params = action.get("parameters", {})
    orbit = orbital_state(
        planet,
        float(state["mission_time_hours"]),
        phase_shift_deg=float(params.get("phase_shift_deg", 0.0)),
    )
    luminosity = _value(system["star"]["luminosity"], 1.0)
    stellar_flux = SOLAR_CONSTANT_W_M2 * luminosity / max(1e-8, orbit["star_distance_au"] ** 2)
    reference_config = _action_configuration(action)
    technology_envelope, config = technology_physics_envelope(system, action, reference_config)
    sensor = sensor_expectation(
        stellar_flux_w_m2=stellar_flux,
        illuminated_fraction=orbit["illuminated_fraction"],
        sensor_health_percent=float(state["resources"]["sensor_health_percent"]),
        configuration=config,
    )
    thermal = thermal_expectation(
        stellar_flux_w_m2=stellar_flux,
        configuration=config,
        ship_heat_percent=float(state["resources"]["heat_percent"]),
    )
    radiation = radiation_expectation(
        star_age_gyr=_value(system["star"]["age"], 4.6),
        star_distance_au=orbit["star_distance_au"],
        shielding_factor=0.58 if params.get("shield_mode") else 0.36,
    )

    origin_au = float(state.get("navigation", {}).get("ship_orbit_au", max(0.05, orbit["star_distance_au"] * 1.25)))
    trajectory = hohmann_transfer(_value(system["star"]["mass"], 1.0), origin_au, orbit["star_distance_au"])
    separation_au = abs(origin_au - orbit["star_distance_au"])
    communications = communication_expectation(separation_au)

    expected_duration_hours = max(0.1, config["integration_seconds"] / 3600.0)
    if action["category"] == "probe":
        if params.get("wait_for_probe"):
            active = [
                item for item in state.get("active_probes", [])
                if item.get("status") == "in-flight" and item.get("target_planet_id") == planet["id"]
            ]
            if active:
                remaining = min(
                    max(0.0, float(item["arrival_mission_time_hours"]) - float(state["mission_time_hours"]))
                    for item in active
                )
                expected_duration_hours += min(240.0, remaining)
            else:
                expected_duration_hours += min(24.0, trajectory["transfer_time_days"] * 24.0)
        elif params.get("trajectory_correction") or params.get("relay_mode"):
            expected_duration_hours += communications["round_trip_light_time_s"] / 3600.0 + 0.75
        else:
            # Launch and checkout happen now; coast time remains represented by an active
            # probe trajectory and does not silently fast-forward the whole encounter.
            expected_duration_hours += 2.0
    if params.get("cooldown_hours"):
        expected_duration_hours += float(params["cooldown_hours"])
    if params.get("wait_for_comm"):
        expected_duration_hours += communications["earliest_full_response_s"] / 3600.0

    return {
        "schema": PHYSICS_SCHEMA,
        "target_planet_id": planet["id"],
        "target_planet_name": planet["name"],
        "action_id": action["action_id"],
        "action_category": action["category"],
        "orbital_state": orbit,
        "stellar_flux": {
            "value_w_m2": round(stellar_flux, 6),
            "earth_flux_ratio": round(stellar_flux / SOLAR_CONSTANT_W_M2, 6),
            "truth_type": "derived-simulation-state",
            "formula_id": "runtime_inverse_square_flux",
        },
        "sensor": sensor,
        "thermal": thermal,
        "radiation": radiation,
        "communications": communications,
        "trajectory": trajectory,
        "configuration": {key: round(value, 9) for key, value in config.items()},
        "reference_configuration": {key: round(value, 9) for key, value in reference_config.items()},
        "technology_envelope": technology_envelope,
        "expected_duration_hours": round(expected_duration_hours, 6),
        "limitations": [
            "Sensor values are a transparent instrument scenario, not proof that the selected technology core carries that instrument.",
            "Published total electrical generation bounds a scenario only when available; it is not treated as payload-available power.",
            "Radiation is a relative operational risk index and the shielding factor is not a measured value for the selected core.",
            "The trajectory is a two-body Hohmann transfer requirement, not proof that the selected core can execute it.",
            "Thermal balance is a lumped radiative scenario and does not replace a spacecraft finite-element thermal analysis.",
            "Unpublished mass, thrust, specific impulse, propellant, and acceleration values remain blocked.",
        ],
    }


def probability_modifiers(snapshot: dict[str, Any]) -> dict[str, float]:
    snr = float(snapshot["sensor"]["expected_snr"])
    thermal_ratio = float(snapshot["thermal"]["thermal_load_ratio"])
    radiation = float(snapshot["radiation"]["shielded_risk_index"])
    comm_hours = float(snapshot["communications"]["earliest_full_response_s"]) / 3600.0
    delta_v = float(snapshot["trajectory"]["total_delta_v_km_s"])
    illumination = float(snapshot["orbital_state"]["illuminated_fraction"])
    return {
        "clear_evidence": min(0.24, max(-0.16, math.log10(max(0.01, snr)) * 0.07 + illumination * 0.04)),
        "ambiguous_evidence": min(0.18, max(-0.08, (5.0 - min(5.0, snr)) * 0.025)),
        "operational_complication": min(0.32, max(-0.08, (thermal_ratio - 0.75) * 0.15 + min(10.0, radiation) * 0.012 + min(20.0, delta_v) * 0.004)),
        "quiet_constraint": min(0.24, max(-0.10, (3.0 - min(3.0, snr)) * 0.06)),
        "delay_pressure": min(0.12, comm_hours * 0.012),
    }


def realized_measurement(snapshot: dict[str, Any], noise_roll: float, detail_roll: float) -> dict[str, Any]:
    expected_snr = float(snapshot["sensor"]["expected_snr"])
    # Box-Muller-like bounded approximation from two deterministic entropy rolls.
    centered = (noise_roll - 0.5) * 2.0
    realized_snr = max(0.0, expected_snr * (1.0 + centered * 0.18))
    channels = [
        "spectral slope",
        "timing drift",
        "polarization channel",
        "thermal response",
        "orbital-phase correlation",
        "instrument cross-calibration",
        "radiation coincidence channel",
        "probe range-rate",
    ]
    detail = channels[min(int(detail_roll * len(channels)), len(channels) - 1)]
    if realized_snr >= 8.0:
        confidence = "strong"
    elif realized_snr >= 5.0:
        confidence = "moderate"
    elif realized_snr >= 3.0:
        confidence = "candidate"
    else:
        confidence = "below-detection-threshold"
    return {
        "expected_snr": round(expected_snr, 6),
        "realized_snr": round(realized_snr, 6),
        "confidence_band": confidence,
        "detail_channel": detail,
        "noise_roll": round(noise_roll, 12),
        "model": "Poisson signal/background + dark current + read variance + systematic floor",
    }


def physics_resource_deltas(snapshot: dict[str, Any], action: dict[str, Any]) -> dict[str, float]:
    params = action.get("parameters", {})
    duration = float(snapshot["expected_duration_hours"])
    thermal_ratio = float(snapshot["thermal"]["thermal_load_ratio"])
    delta_v = float(snapshot["trajectory"]["total_delta_v_km_s"])
    deltas: dict[str, float] = {
        "mission_time_hours": round(duration, 3),
        "reactor_reserve_percent": round(-min(12.0, snapshot["configuration"]["instrument_power_kw"] * duration / 45.0), 3),
        "heat_percent": round(max(-18.0, min(22.0, (thermal_ratio - 0.72) * 12.0)), 3),
    }
    if action["category"] == "probe" and not params.get("wait_for_probe") and not params.get("trajectory_correction") and not params.get("relay_mode"):
        deltas["probe_count"] = -1
        deltas["fuel_percent"] = round(-min(8.0, 0.7 + delta_v * 0.22), 3)
    elif params.get("trajectory_correction"):
        deltas["fuel_percent"] = round(-min(4.0, 0.4 + delta_v * 0.09), 3)
    elif action["category"] == "move_on":
        deltas["fuel_percent"] = -1.2
    if params.get("repair_focus") == "sensor":
        deltas["sensor_health_percent"] = 14.0
        deltas["reactor_reserve_percent"] = deltas.get("reactor_reserve_percent", 0.0) - 2.0
    if params.get("cooldown_hours") or params.get("thermal_attitude") == "edge-on":
        deltas["heat_percent"] = min(deltas.get("heat_percent", 0.0), -12.0)
    if params.get("power_conservation"):
        deltas["reactor_reserve_percent"] = 5.0
        deltas["heat_percent"] = -5.0
    return deltas


def physics_open_threads(snapshot: dict[str, Any], action: dict[str, Any]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    if action["category"] == "probe" and not action.get("parameters", {}).get("wait_for_probe"):
        result.append({
            "thread_id": "probe-in-flight",
            "title": "Probe trajectory and delayed telemetry",
            "kind": "probe-in-flight",
            "target_planet_id": snapshot["target_planet_id"],
            "reason": f"The reference transfer requires about {snapshot['trajectory']['transfer_time_days']:.2f} days; local data cannot appear instantly.",
        })
    if float(snapshot["communications"]["earliest_full_response_s"]) > 1800.0:
        result.append({
            "thread_id": "communication-latency",
            "title": "Command and telemetry light-time",
            "kind": "communication-latency",
            "target_planet_id": snapshot["target_planet_id"],
            "reason": "The communication loop is long enough to change command timing and autonomy requirements.",
        })
    if float(snapshot["thermal"]["thermal_load_ratio"]) > 1.05:
        result.append({
            "thread_id": "thermal-recovery",
            "title": "Thermal load exceeds current radiator balance",
            "kind": "thermal-recovery",
            "target_planet_id": snapshot["target_planet_id"],
            "reason": "Absorbed and internally generated heat exceed the simplified radiator capacity.",
        })
    if float(snapshot["radiation"]["shielded_risk_index"]) > 2.5:
        result.append({
            "thread_id": "radiation-watch",
            "title": "Elevated radiation environment",
            "kind": "radiation-watch",
            "target_planet_id": snapshot["target_planet_id"],
            "reason": "The relative radiation risk index is high enough to affect electronics and operations.",
        })
    return result
