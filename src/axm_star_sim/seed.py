from __future__ import annotations

import hashlib
import random
from dataclasses import dataclass, field


def _digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class SeedBranch:
    master_seed: str
    path: str
    digest: str = field(init=False)

    def __post_init__(self) -> None:
        normalized = self.master_seed.strip()
        if not normalized:
            raise ValueError("master seed cannot be empty")
        object.__setattr__(self, "digest", _digest(f"AXM-SEED-V1|{normalized}|{self.path}"))

    @property
    def short(self) -> str:
        return self.digest[:12]

    def rng(self) -> random.Random:
        return random.Random(int(self.digest, 16))

    def child(self, name: str) -> "SeedBranch":
        child_path = f"{self.path}/{name}" if self.path else name
        return SeedBranch(self.master_seed, child_path)


def seed_manifest(master_seed: str, planet_slots: int = 12) -> dict[str, str]:
    root = SeedBranch(master_seed, "root")
    paths = [
        "cosmos",
        "star",
        "planets/count",
        "ship",
        "ship/technology-core",
        "party-director",
        "unknown",
        "adventure",
        "presentation",
    ]
    result = {"root": root.digest}
    for path in paths:
        result[path] = SeedBranch(master_seed, path).digest
    for index in range(planet_slots):
        result[f"planets/{index}"] = SeedBranch(master_seed, f"planets/{index}").digest
    return result
