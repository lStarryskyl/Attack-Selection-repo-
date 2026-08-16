from __future__ import annotations

from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from .io import load_records


def validate_file(path: str | Path) -> tuple[list, dict[str, Any]]:
    records, excluded = load_records(path)
    attack_folds: dict[str, set[str]] = defaultdict(set)
    task_folds: dict[str, set[str]] = defaultdict(set)
    for record in records:
        attack_folds[record.attack_id].add(record.fold_id)
        task_folds[record.task_id].add(record.fold_id)
    repeated = {key: sorted(value) for key, value in attack_folds.items() if len(value) > 1}
    report = {
        "source": str(Path(path).resolve()),
        "input_rows": len(records) + len(excluded),
        "usable_rows": len(records),
        "excluded_rows": len(excluded),
        "exclusions": excluded,
        "unique_attacks": len(attack_folds),
        "unique_tasks": len(task_folds),
        "unique_folds": len({r.fold_id for r in records}),
        "attacks_repeated_across_folds": repeated,
        "repeated_attack_count": len(repeated),
        "label_counts": dict(Counter(f"success={r.attack_success},correct={r.correct}" for r in records)),
        "optional_score_coverage": {
            "monitor_score": sum(r.monitor_score is not None for r in records),
            "attacker_score": sum(r.attacker_score is not None for r in records),
        },
    }
    return records, report

