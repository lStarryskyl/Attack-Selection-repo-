from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    model: str = "gpt-4.1-nano"
    seed: int = 20260809
    bootstraps: int = 1000
    artifact_dir: Path = Path("artifacts")
    max_output_tokens: int = 180

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            model=os.getenv("ORACLE_GAP_MODEL", cls.model),
            seed=int(os.getenv("ORACLE_GAP_SEED", str(cls.seed))),
            bootstraps=int(os.getenv("ORACLE_GAP_BOOTSTRAPS", str(cls.bootstraps))),
            artifact_dir=Path(os.getenv("ORACLE_GAP_ARTIFACT_DIR", str(cls.artifact_dir))),
            max_output_tokens=int(os.getenv("ORACLE_GAP_MAX_OUTPUT_TOKENS", str(cls.max_output_tokens))),
        )

