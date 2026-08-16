from __future__ import annotations

from dataclasses import asdict, dataclass, field
import hashlib
from typing import Any


ALIASES = {
    "attack_id": ("attack_id", "attack", "attack_name"),
    "task_id": ("task_id", "problem_id", "task", "id"),
    "fold_id": ("fold_id", "fold", "split_id"),
    "candidate": ("candidate", "candidate_code", "code", "trajectory", "solution"),
    "main_task": ("main_task", "task_text", "prompt", "instruction", "complete_prompt"),
    "side_task": ("side_task", "attack_description", "malicious_objective", "trigger"),
    "attack_success": ("attack_success", "side_task_success", "backdoor_success"),
    "correct": ("correct", "main_task_success", "passes_tests", "is_correct"),
    "monitor_score": ("monitor_score", "suspicion_score"),
    "attacker_score": ("attacker_score", "quality_score", "opportunity_score"),
    "provenance": ("provenance", "source"),
}


def _pick(raw: dict[str, Any], name: str) -> Any:
    for alias in ALIASES[name]:
        if alias in raw and raw[alias] not in (None, ""):
            return raw[alias]
    return None


def parse_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)) and value in (0, 1):
        return bool(value)
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "yes", "y", "1", "pass", "passed", "success"}:
            return True
        if normalized in {"false", "no", "n", "0", "fail", "failed", "failure"}:
            return False
    raise ValueError(f"not a boolean: {value!r}")


@dataclass(frozen=True)
class AttackRecord:
    attack_id: str
    task_id: str
    fold_id: str
    candidate: str
    main_task: str
    side_task: str
    attack_success: bool
    correct: bool
    monitor_score: float | None = None
    attacker_score: float | None = None
    provenance: dict[str, Any] = field(default_factory=dict)

    @property
    def record_id(self) -> str:
        payload = "\x1f".join((self.attack_id, self.task_id, self.fold_id, self.candidate))
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:20]

    def to_dict(self) -> dict[str, Any]:
        return {"record_id": self.record_id, **asdict(self)}

    @classmethod
    def from_mapping(cls, raw: dict[str, Any]) -> "AttackRecord":
        required_text = ("attack_id", "task_id", "fold_id", "candidate", "main_task", "side_task")
        values = {name: _pick(raw, name) for name in ALIASES}
        missing = [name for name in required_text if values[name] is None or not str(values[name]).strip()]
        if values["attack_success"] is None:
            missing.append("attack_success")
        if values["correct"] is None:
            missing.append("correct")
        if missing:
            raise ValueError("missing required fields: " + ", ".join(missing))
        provenance = values["provenance"]
        if provenance is None:
            provenance = {}
        elif not isinstance(provenance, dict):
            provenance = {"source": str(provenance)}
        return cls(
            attack_id=str(values["attack_id"]).strip(),
            task_id=str(values["task_id"]).strip(),
            fold_id=str(values["fold_id"]).strip(),
            candidate=str(values["candidate"]),
            main_task=str(values["main_task"]),
            side_task=str(values["side_task"]),
            attack_success=parse_bool(values["attack_success"]),
            correct=parse_bool(values["correct"]),
            monitor_score=float(values["monitor_score"]) if values["monitor_score"] is not None else None,
            attacker_score=float(values["attacker_score"]) if values["attacker_score"] is not None else None,
            provenance=provenance,
        )

