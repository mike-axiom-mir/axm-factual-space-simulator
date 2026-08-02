from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal

TruthType = Literal[
    "catalog_fact",
    "derived",
    "simulation_prior",
    "observation",
    "hypothesis",
    "speculation",
]


@dataclass
class EvidenceValue:
    value: Any
    unit: str | None
    truth_type: TruthType
    source_ids: list[str] = field(default_factory=list)
    formula_id: str | None = None
    uncertainty: Any | None = None
    notes: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Planet:
    id: str
    name: str
    seed_digest: str
    kind: str
    facts: dict[str, EvidenceValue]
    visual: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "seed_digest": self.seed_digest,
            "kind": self.kind,
            "facts": {key: value.to_dict() for key, value in self.facts.items()},
            "visual": self.visual,
        }


@dataclass
class StarSystem:
    schema_version: str
    generator_version: str
    generated_at: str
    master_seed: str
    system_id: str
    name: str
    seed_manifest: dict[str, str]
    source_registry: dict[str, Any]
    formulas: dict[str, Any]
    star: dict[str, EvidenceValue]
    planets: list[Planet]
    ship: dict[str, Any]
    party_director: dict[str, Any]
    adventure: dict[str, Any]
    causality: list[dict[str, Any]]
    integrity: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "generator_version": self.generator_version,
            "generated_at": self.generated_at,
            "master_seed": self.master_seed,
            "system_id": self.system_id,
            "name": self.name,
            "seed_manifest": self.seed_manifest,
            "source_registry": self.source_registry,
            "formulas": self.formulas,
            "star": {key: value.to_dict() for key, value in self.star.items()},
            "planets": [planet.to_dict() for planet in self.planets],
            "ship": self.ship,
            "party_director": self.party_director,
            "adventure": self.adventure,
            "causality": self.causality,
            "integrity": self.integrity,
        }
