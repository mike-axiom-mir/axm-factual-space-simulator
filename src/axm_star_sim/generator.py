from __future__ import annotations

import hashlib
import json
import math
from datetime import datetime, timezone
from typing import Any

from .adventure import compose_opportunities, normalize_weights
from .models import EvidenceValue, Planet, StarSystem
from .physics import (
    equilibrium_temperature_k,
    escape_velocity_km_s,
    insolation_earth,
    mass_earth_from_radius_density,
    orbital_period_days,
    star_color_temperature_hint,
    stellar_luminosity_solar,
    surface_gravity_earth,
)
from .registry import load_formula_registry, load_priors, load_source_registry
from .seed import SeedBranch, seed_manifest
from .technology_core import build_ship_technology_profile

GENERATOR_VERSION = "0.8.0"
SCHEMA_VERSION = "axm.star-system.v2"


def _round(value: float, digits: int = 4) -> float:
    return round(float(value), digits)


def _pick_weighted(rng, entries: list[dict[str, Any]]) -> dict[str, Any]:
    total = sum(float(entry["weight"]) for entry in entries)
    roll = rng.uniform(0, total)
    cursor = 0.0
    for entry in entries:
        cursor += float(entry["weight"])
        if roll <= cursor:
            return entry
    return entries[-1]


def _system_name(master_seed: str, branch: SeedBranch) -> str:
    syllables_a = ["Astra", "Kepler", "Nadir", "Vela", "Orion", "Lyra", "Caelum", "Tethys", "Iona", "Mir"]
    syllables_b = ["Reach", "Haven", "Deep", "Arc", "Drift", "Gate", "Veil", "Crown", "Trace", "Field"]
    rng = branch.rng()
    code = int(hashlib.sha256(master_seed.encode("utf-8")).hexdigest()[:8], 16) % 9000 + 1000
    return f"{rng.choice(syllables_a)} {rng.choice(syllables_b)} {code}"


def _generate_star(master_seed: str, priors: dict[str, Any]) -> dict[str, EvidenceValue]:
    branch = SeedBranch(master_seed, "star")
    rng = branch.rng()
    profile = _pick_weighted(rng, priors["star_profiles"])
    mass = rng.uniform(*profile["mass_solar"])
    radius = rng.uniform(*profile["radius_solar"])
    temperature = rng.uniform(*profile["temperature_k"])
    luminosity = stellar_luminosity_solar(radius, temperature)
    metallicity = rng.uniform(-0.45, 0.35)
    age = rng.uniform(*profile["age_gyr"])

    prior_note = "Generated from configurable offline simulation priors; this is not a catalog observation."
    return {
        "profile": EvidenceValue(profile["id"], None, "simulation_prior", ["axm_simulation_priors_v1"], notes=prior_note),
        "mass": EvidenceValue(_round(mass), "solar_mass", "simulation_prior", ["axm_simulation_priors_v1"], notes=prior_note),
        "radius": EvidenceValue(_round(radius), "solar_radius", "simulation_prior", ["axm_simulation_priors_v1"], notes=prior_note),
        "effective_temperature": EvidenceValue(_round(temperature, 1), "K", "simulation_prior", ["axm_simulation_priors_v1"], notes=prior_note),
        "luminosity": EvidenceValue(_round(luminosity), "solar_luminosity", "derived", ["iau_2015_b3", "nasa_exoplanet_archive_pscp_calc"], formula_id="stefan_boltzmann_luminosity"),
        "metallicity": EvidenceValue(_round(metallicity), "dex", "simulation_prior", ["axm_simulation_priors_v1"], notes=prior_note),
        "age": EvidenceValue(_round(age), "Gyr", "simulation_prior", ["axm_simulation_priors_v1"], notes=prior_note),
        "visual_temperature_hint": EvidenceValue(star_color_temperature_hint(temperature), None, "derived", [], formula_id="display_temperature_bucket", notes="A display hint, not a precise rendered stellar spectrum."),
    }


def _planet_kind_parameters(rng, priors: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    selected = _pick_weighted(rng, priors["planet_profiles"])
    return selected["id"], selected


def _generate_planets(master_seed: str, star: dict[str, EvidenceValue], priors: dict[str, Any]) -> list[Planet]:
    count_rng = SeedBranch(master_seed, "planets/count").rng()
    planet_count = count_rng.randint(priors["planet_count"][0], priors["planet_count"][1])
    stellar_mass = float(star["mass"].value)
    stellar_radius = float(star["radius"].value)
    stellar_temperature = float(star["effective_temperature"].value)
    stellar_luminosity = float(star["luminosity"].value)

    planets: list[Planet] = []
    previous_axis = max(0.035, 0.045 * math.sqrt(max(stellar_luminosity, 0.02)))
    letters = "bcdefghijklmnopqrstuvwxyz"

    for index in range(planet_count):
        branch = SeedBranch(master_seed, f"planets/{index}")
        rng = branch.rng()
        kind, profile = _planet_kind_parameters(rng, priors)
        spacing = rng.uniform(1.45, 2.35)
        semi_major_axis = previous_axis * spacing
        previous_axis = semi_major_axis
        radius = rng.uniform(*profile["radius_earth"])
        density = rng.uniform(*profile["density_g_cm3"])
        mass = mass_earth_from_radius_density(radius, density)
        eccentricity = min(rng.betavariate(1.2, 7.5) * 0.55, 0.65)
        inclination = rng.uniform(0.0, 6.0)
        period = orbital_period_days(semi_major_axis, stellar_mass)
        eq_temp = equilibrium_temperature_k(stellar_temperature, stellar_radius, semi_major_axis)
        insolation = insolation_earth(stellar_luminosity, semi_major_axis)
        gravity = surface_gravity_earth(mass, radius)
        escape = escape_velocity_km_s(gravity, radius)
        phase = rng.uniform(0, 360)

        name = f"{letters[index].upper()}"
        prior_note = "Generated from configurable planet population priors; not a catalog observation."
        facts = {
            "semi_major_axis": EvidenceValue(_round(semi_major_axis), "AU", "simulation_prior", ["axm_simulation_priors_v1"], notes=prior_note),
            "eccentricity": EvidenceValue(_round(eccentricity), None, "simulation_prior", ["axm_simulation_priors_v1"], notes=prior_note),
            "inclination": EvidenceValue(_round(inclination), "deg", "simulation_prior", ["axm_simulation_priors_v1"], notes=prior_note),
            "radius": EvidenceValue(_round(radius), "earth_radius", "simulation_prior", ["axm_simulation_priors_v1"], notes=prior_note),
            "density": EvidenceValue(_round(density), "g/cm3", "simulation_prior", ["axm_simulation_priors_v1"], notes=prior_note),
            "mass": EvidenceValue(_round(mass), "earth_mass", "derived", ["iau_2015_b3"], formula_id="mass_from_radius_density"),
            "surface_gravity": EvidenceValue(_round(gravity), "earth_g", "derived", ["iau_2015_b3"], formula_id="surface_gravity_ratio"),
            "escape_velocity": EvidenceValue(_round(escape), "km/s", "derived", ["iau_2015_b3"], formula_id="escape_velocity"),
            "orbital_period": EvidenceValue(_round(period, 3), "days", "derived", ["kepler_third_law"], formula_id="kepler_period"),
            "equilibrium_temperature": EvidenceValue(_round(eq_temp, 1), "K", "derived", ["iau_2015_b3", "nasa_exoplanet_archive_pscp_calc"], formula_id="planet_equilibrium_temperature"),
            "insolation": EvidenceValue(_round(insolation), "earth_flux", "derived", ["nasa_exoplanet_archive_pscp_calc"], formula_id="planet_insolation"),
            "temperate_screen": EvidenceValue(
                0.35 <= insolation <= 1.25,
                None,
                "hypothesis",
                ["kopparapu_2013_hz"],
                formula_id="starter_temperate_flux_screen",
                notes="A broad prioritization screen only. It is not a habitability claim or climate model.",
            ),
        }
        visual = {
            "phase_deg": _round(phase),
            "size_hint": _round(max(4.0, min(15.0, 4.0 + radius * 1.2)), 2),
            "surface_hint": profile["surface_hint"],
        }
        planets.append(Planet(
            id=f"planet-{index}",
            name=name,
            seed_digest=branch.digest,
            kind=kind,
            facts=facts,
            visual=visual,
        ))

    return planets


def _generate_ship(master_seed: str) -> dict[str, Any]:
    rng = SeedBranch(master_seed, "ship").rng()
    roles = ["survey", "pathfinder", "rescue", "science-carrier", "long-range-observer"]
    role = rng.choice(roles)
    power = rng.randint(62, 96)
    sensor = rng.randint(55, 98)
    integrity = rng.randint(72, 100)
    technology = build_ship_technology_profile(master_seed, horizon_year=2027)
    crew_evidence = None
    for item in technology["known_parameter_summary"]:
        if item["id"] in {"crew_capacity", "early_crew_capacity"}:
            crew_evidence = item
            break
    return {
        "name": rng.choice(["AXM Wayfinder", "Axiom-Mir Explorer", "Quiet Horizon", "First Light", "Open Hand"]),
        "role": role,
        "seed_digest": SeedBranch(master_seed, "ship").digest,
        "systems": {
            "reactor_reserve_percent": power,
            "sensor_health_percent": sensor,
            "hull_integrity_percent": integrity,
            "probe_count": rng.randint(2, 7),
            "crew_seats": crew_evidence["value"] if crew_evidence else "undisclosed_by_pinned_sources",
        },
        "technology_core": technology,
        "truth_type": "mixed_catalog_and_simulation_state",
        "truth_note": (
            "Operational condition percentages and ship name/role are simulation state. "
            "The technology core and numeric hardware parameters are source-pinned catalog facts or transparent derivations."
        ),
    }


def generate_system(master_seed: str, weights: dict[str, int] | None = None) -> StarSystem:
    priors = load_priors()
    sources = load_source_registry()
    formulas = load_formula_registry()
    star = _generate_star(master_seed, priors)
    planets = _generate_planets(master_seed, star, priors)
    ship = _generate_ship(master_seed)
    normalized_weights = normalize_weights(weights)
    party, adventure_list = compose_opportunities(
        SeedBranch(master_seed, "adventure"), planets, normalized_weights
    )
    adventure = adventure_list[0]
    adventure["future_contract"] = {
        "seed_scope": "The master seed fixes the initial universe and generated opportunity space, not every later event outcome.",
        "deferred_resolution": True,
        "default_entropy_mode": "mixed_live",
        "supported_entropy_modes": ["deterministic", "local_live", "mixed_live", "external_beacon", "party_commit"],
        "resolved_events_become_replayable": True,
        "unresolved_events_are_not_claimed_to_exist_yet": True,
    }
    system_name = _system_name(master_seed, SeedBranch(master_seed, "cosmos"))
    system_id = hashlib.sha256(f"AXM-SYSTEM-V1|{master_seed}".encode("utf-8")).hexdigest()[:16]

    causality = [
        {
            "step": 1,
            "event": "master_seed_accepted",
            "cause": {"master_seed": master_seed},
            "effect": {"system_id": system_id},
        },
        {
            "step": 2,
            "event": "stable_seed_tree_derived",
            "cause": {"algorithm": "SHA-256 named branch derivation"},
            "effect": {"branches": len(seed_manifest(master_seed))},
        },
        {
            "step": 3,
            "event": "physical_state_generated",
            "cause": {"priors": "axm_simulation_priors_v1", "formulas": list(formulas["formulas"])},
            "effect": {"star": system_name, "planet_count": len(planets), "technology_core": ship["technology_core"]["selected_core_id"]},
        },
        {
            "step": 4,
            "event": "adventure_opportunity_selected",
            "cause": {
                "party_direction": party["dominant_direction"],
                "valid_opportunities": 1 + len(adventure["alternate_opportunities"]),
            },
            "effect": {"selected": adventure["selected_opportunity"]["id"]},
        },
    ]

    return StarSystem(
        schema_version=SCHEMA_VERSION,
        generator_version=GENERATOR_VERSION,
        generated_at=datetime.now(timezone.utc).isoformat(),
        master_seed=master_seed,
        system_id=system_id,
        name=system_name,
        seed_manifest=seed_manifest(master_seed),
        source_registry=sources,
        formulas=formulas,
        star=star,
        planets=planets,
        ship=ship,
        party_director=party,
        adventure=adventure,
        causality=causality,
    )


def canonical_json(data: dict[str, Any]) -> str:
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
