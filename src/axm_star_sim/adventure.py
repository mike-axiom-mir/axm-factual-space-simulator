from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .models import Planet
from .seed import SeedBranch

DEFAULT_WEIGHTS = {
    "wonder": 30,
    "mystery": 25,
    "engineering": 20,
    "danger": 10,
    "contact": 10,
    "humour": 5,
}


@dataclass
class Opportunity:
    id: str
    title: str
    tone: str
    trigger: dict[str, Any]
    observations: list[str]
    hypotheses: list[str]
    actions: list[str]
    consequence_axes: list[str]
    novelty_basis: list[str]

    def to_dict(self) -> dict[str, Any]:
        return self.__dict__.copy()


def normalize_weights(weights: dict[str, int] | None) -> dict[str, int]:
    result = DEFAULT_WEIGHTS.copy()
    if weights:
        for key, value in weights.items():
            if key not in result:
                raise ValueError(f"unknown party direction: {key}")
            if value < 0:
                raise ValueError("weights cannot be negative")
            result[key] = int(value)
    if sum(result.values()) <= 0:
        raise ValueError("at least one party weight must be positive")
    return result


def weighted_tone(branch: SeedBranch, weights: dict[str, int]) -> str:
    rng = branch.rng()
    population = list(weights)
    cumulative = []
    total = 0
    for name in population:
        total += weights[name]
        cumulative.append(total)
    roll = rng.uniform(0, total)
    for name, upper in zip(population, cumulative):
        if roll <= upper:
            return name
    return population[-1]


def compose_opportunities(
    branch: SeedBranch,
    planets: list[Planet],
    weights: dict[str, int],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    rng = branch.rng()
    dominant = weighted_tone(branch.child("tone"), weights)
    rocky = [p for p in planets if p.kind in {"terrestrial", "super-earth"}]
    giants = [p for p in planets if p.kind in {"neptune-like", "gas-giant"}]
    temperate = [
        p for p in rocky
        if 0.35 <= float(p.facts["insolation"].value) <= 1.25
    ]
    eccentric = [
        p for p in planets
        if float(p.facts["eccentricity"].value) >= 0.08
    ]
    close_rocky = [
        p for p in rocky
        if float(p.facts["insolation"].value) > 2.5
    ]

    opportunities: list[Opportunity] = []

    if temperate and eccentric:
        target = rng.choice(temperate)
        opportunities.append(Opportunity(
            id="seasonal-atmosphere-window",
            title=f"The changing atmosphere of {target.name}",
            tone="mystery",
            trigger={
                "planet_id": target.id,
                "temperate_screen": True,
                "eccentricity": target.facts["eccentricity"].value,
            },
            observations=[
                "Orbital geometry predicts strongly varying stellar input.",
                "Spectral readings can be scheduled at multiple orbital phases.",
            ],
            hypotheses=[
                "Volatiles may migrate between atmosphere and surface seasonally.",
                "A transient signal may be geological rather than biological or artificial.",
            ],
            actions=[
                "Delay arrival to observe a complete phase transition.",
                "Deploy a fast probe during the current observation window.",
                "Spend ship power on long-baseline spectroscopy.",
            ],
            consequence_axes=["time", "power", "knowledge", "probe-risk"],
            novelty_basis=["orbital phase", "sensor timing", "resource pressure", "party interpretation"],
        ))

    if giants and rocky:
        giant = rng.choice(giants)
        target = rng.choice(rocky)
        opportunities.append(Opportunity(
            id="system-history-reconstruction",
            title="A system that may have moved its worlds",
            tone="wonder",
            trigger={"giant_id": giant.id, "rocky_id": target.id},
            observations=[
                "The system contains both a large outer world and compact rocky bodies.",
                "Current orbits alone do not reveal the system's formation history.",
            ],
            hypotheses=[
                "Past migration or scattering may explain the architecture.",
                "A debris region could preserve evidence of earlier encounters.",
            ],
            actions=[
                "Map dust and small bodies before approaching the planets.",
                "Perform precision orbit fitting over a longer observation period.",
                "Take the direct route and accept incomplete historical context.",
            ],
            consequence_axes=["arrival-time", "navigation-risk", "scientific-confidence"],
            novelty_basis=["planet ordering", "debris search", "mission clock", "crew priorities"],
        ))

    if close_rocky:
        target = rng.choice(close_rocky)
        opportunities.append(Opportunity(
            id="stripped-world",
            title=f"The exposed world {target.name}",
            tone="engineering",
            trigger={
                "planet_id": target.id,
                "high_insolation": target.facts["insolation"].value,
                "density": target.facts["density"].value,
            },
            observations=[
                "The planet receives intense stellar flux.",
                "Its bulk properties are compatible with a dense rocky body.",
            ],
            hypotheses=[
                "The present surface may be the remnant of a once larger world.",
                "A tenuous atmosphere or escaping material could still be detectable.",
            ],
            actions=[
                "Use a heat-shielded probe for a close pass.",
                "Observe from distance using occultation geometry.",
                "Ignore the world and conserve mission resources.",
            ],
            consequence_axes=["thermal-load", "probe-integrity", "fuel", "discovery"],
            novelty_basis=["ship capability", "stellar state", "probe route", "evidence quality"],
        ))

    if not opportunities:
        target = rng.choice(planets)
        opportunities.append(Opportunity(
            id="weak-signal-investigation",
            title=f"A signal that exists only at the edge of certainty near {target.name}",
            tone="mystery",
            trigger={"planet_id": target.id, "generator_fallback": True},
            observations=[
                "A repeatable but low-significance spectral feature is present.",
                "The signal is not yet strong enough to classify as a discovery.",
            ],
            hypotheses=[
                "Instrument interaction, natural chemistry, or an external emitter remain possible.",
            ],
            actions=[
                "Reconfigure sensors and accept reduced navigation accuracy.",
                "Change viewing geometry.",
                "Log the candidate and continue the primary mission.",
            ],
            consequence_axes=["sensor-availability", "navigation", "confidence", "time"],
            novelty_basis=["noise realization", "ship state", "viewing geometry", "decision sequence"],
        ))

    # Party direction changes emphasis, not physical reality.
    def score(item: Opportunity) -> tuple[int, float]:
        direct = 1 if item.tone == dominant else 0
        return (direct, rng.random())

    opportunities.sort(key=score, reverse=True)
    selected = opportunities[0]

    party = {
        "weights": weights,
        "dominant_direction": dominant,
        "rule": "Weights select which valid opportunity receives attention; they do not change the generated physical values.",
    }
    adventure = {
        "selected_opportunity": selected.to_dict(),
        "alternate_opportunities": [item.to_dict() for item in opportunities[1:]],
        "truth_boundary": {
            "observations": "Generated sensor-accessible conditions or direct calculations.",
            "hypotheses": "Plausible interpretations requiring further evidence.",
            "speculation": "Never promoted to fact without an in-simulation observation path.",
        },
    }
    return party, [adventure]
