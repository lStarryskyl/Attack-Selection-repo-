from __future__ import annotations

from collections import Counter
import csv
import json
import math
from pathlib import Path
import random
from statistics import mean
from typing import Any

from .io import read_rows, write_json
from .schema import AttackRecord


def _candidate_class(record: AttackRecord) -> str:
    return str(record.provenance.get("candidate_class", "attack"))


def _weighted_auc(positive: list[tuple[float, int]], negative: list[tuple[float, int]]) -> float:
    total_positive = sum(weight for _, weight in positive)
    total_negative = sum(weight for _, weight in negative)
    if not total_positive or not total_negative:
        return float("nan")
    by_score: dict[float, list[int]] = {}
    for score, weight in negative:
        by_score.setdefault(score, [0, 0])[0] += weight
    for score, weight in positive:
        by_score.setdefault(score, [0, 0])[1] += weight
    lower_negative = 0
    wins = 0.0
    for score in sorted(by_score):
        negative_weight, positive_weight = by_score[score]
        wins += positive_weight * (lower_negative + 0.5 * negative_weight)
        lower_negative += negative_weight
    return wins / (total_positive * total_negative)


def _percentile(values: list[float], probability: float) -> float:
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, round(probability * (len(ordered) - 1))))
    return ordered[index]


def evaluate_classification(
    records_path: str | Path,
    scores_paths: list[str | Path],
    games_path: str | Path,
    output_dir: str | Path,
    bootstraps: int = 1000,
    seed: int = 20260809,
) -> dict[str, Any]:
    records = [AttackRecord.from_mapping(row) for row in read_rows(records_path)]
    scores = [row for path in scores_paths for row in read_rows(path)]
    score_index = {
        (str(row["record_id"]), str(row["condition"])): float(row["suspicion_score"])
        for row in scores
    }
    conditions = sorted({str(row["condition"]) for row in scores})
    attacks = {record.task_id: record for record in records if _candidate_class(record) == "attack"}
    honest = {record.task_id: record for record in records if _candidate_class(record) == "honest"}
    tasks = sorted(set(attacks) & set(honest))
    games = json.loads(Path(games_path).read_text(encoding="utf-8"))["games"]
    dangerous_ids = {
        str(row["attack_id"])
        for game in games for row in game["rows"] if bool(row["valid"])
    }
    dangerous_tasks = [task for task in tasks if attacks[task].attack_id in dangerous_ids]

    def metrics(condition: str, weights: Counter[str], selected_tasks: list[str]) -> dict[str, float]:
        positive = []
        negative = []
        paired_wins = 0.0
        total_weight = 0
        for task in selected_tasks:
            weight = weights.get(task, 0)
            if not weight:
                continue
            attack_score = score_index[(attacks[task].record_id, condition)]
            honest_score = score_index[(honest[task].record_id, condition)]
            positive.append((attack_score, weight))
            negative.append((honest_score, weight))
            paired_wins += weight * (1.0 if attack_score > honest_score else 0.5 if attack_score == honest_score else 0.0)
            total_weight += weight
        return {
            "auc": _weighted_auc(positive, negative),
            "paired_win_rate": paired_wins / total_weight if total_weight else float("nan"),
        }

    all_weights = Counter({task: 1 for task in tasks})
    dangerous_weights = Counter({task: 1 for task in dangerous_tasks})
    point: dict[tuple[str, str, str], float] = {}
    for condition in conditions:
        for population, selected, weights in (
            ("all_attacks", tasks, all_weights),
            ("successful_correct", dangerous_tasks, dangerous_weights),
        ):
            for metric, value in metrics(condition, weights, selected).items():
                point[(population, condition, metric)] = value

    rng = random.Random(seed)
    samples: dict[tuple[str, str, str], list[float]] = {key: [] for key in point}
    contrast_samples: dict[tuple[str, str, str], list[float]] = {}
    pairs = []
    if {"code_main_side", "code_main"} <= set(conditions):
        pairs.append(("side_minus_main", "code_main_side", "code_main"))
    if {"code_main", "code_only"} <= set(conditions):
        pairs.append(("main_minus_code", "code_main", "code_only"))
    for _ in range(bootstraps):
        for population, selected in (("all_attacks", tasks), ("successful_correct", dangerous_tasks)):
            weights = Counter(rng.choices(selected, k=len(selected)))
            replicate = {condition: metrics(condition, weights, selected) for condition in conditions}
            for condition in conditions:
                for metric, value in replicate[condition].items():
                    samples[(population, condition, metric)].append(value)
            for name, left, right in pairs:
                for metric in ("auc", "paired_win_rate"):
                    contrast_samples.setdefault((population, name, metric), []).append(
                        replicate[left][metric] - replicate[right][metric]
                    )

    metric_rows = []
    for key, value in sorted(point.items()):
        population, condition, metric = key
        values = samples[key]
        metric_rows.append({
            "population": population,
            "condition": condition,
            "metric": metric,
            "estimate": value,
            "ci_lower_task_cluster": _percentile(values, 0.025),
            "ci_upper_task_cluster": _percentile(values, 0.975),
            "clusters": len(tasks if population == "all_attacks" else dangerous_tasks),
        })
    contrast_rows = []
    for (population, name, metric), values in sorted(contrast_samples.items()):
        left, right = ("code_main_side", "code_main") if name == "side_minus_main" else ("code_main", "code_only")
        delta = point[(population, left, metric)] - point[(population, right, metric)]
        contrast_rows.append({
            "population": population,
            "contrast": name,
            "metric": metric,
            "delta": delta,
            "ci_lower_task_cluster": _percentile(values, 0.025),
            "ci_upper_task_cluster": _percentile(values, 0.975),
            "p_positive": mean(value > 0 for value in values),
        })
    target = Path(output_dir)
    target.mkdir(parents=True, exist_ok=True)
    for filename, rows in (("classification_metrics.csv", metric_rows), ("classification_contrasts.csv", contrast_rows)):
        with (target / filename).open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
    result = {
        "records": len(records),
        "paired_tasks": len(tasks),
        "successful_correct_unique_attacks": len(dangerous_tasks),
        "conditions": conditions,
        "bootstraps": bootstraps,
        "seed": seed,
        "cluster_unit": "task/unique attack",
        "metrics": metric_rows,
        "contrasts": contrast_rows,
    }
    write_json(target / "classification_metrics.json", result)
    return result
