from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import platform
import sys
from typing import Any

from .io import load_records, read_rows, write_json
from .paper import evaluate_ranking_games
from .prompts import Condition, PromptVariant, build_prompt
from .reporting import write_ranking_summary
from .scoring import cache_key, parse_result


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def verify_cached_scores(
    records_path: str | Path,
    scores_path: str | Path,
    expected_model: str | None = None,
) -> dict[str, Any]:
    records, excluded = load_records(records_path)
    if excluded:
        raise ValueError(f"records file contains {len(excluded)} invalid rows")
    by_record = {record.record_id: record for record in records}
    scores = read_rows(scores_path)
    expected_conditions = {condition.value for condition in Condition}
    observed: dict[str, set[str]] = {record_id: set() for record_id in by_record}
    cache_keys: set[str] = set()
    models: Counter[str] = Counter()
    condition_counts: Counter[str] = Counter()
    retry_counts: Counter[str] = Counter()
    errors: list[str] = []

    for index, row in enumerate(scores):
        record_id = str(row.get("record_id", ""))
        condition_name = str(row.get("condition", ""))
        model = str(row.get("model", ""))
        if record_id not in by_record:
            errors.append(f"score row {index}: unknown record_id {record_id!r}")
            continue
        try:
            condition = Condition(condition_name)
        except ValueError:
            errors.append(f"score row {index}: unknown condition {condition_name!r}")
            continue
        if condition_name in observed[record_id]:
            errors.append(f"score row {index}: duplicate condition {condition_name!r} for {record_id}")
        observed[record_id].add(condition_name)
        try:
            prompt_variant = PromptVariant(str(row.get("prompt_variant", PromptVariant.STANDARD.value)))
        except ValueError:
            errors.append(f"score row {index}: unknown prompt variant {row.get('prompt_variant')!r}")
            continue
        prompt = build_prompt(by_record[record_id], condition, prompt_variant)
        if row.get("prompt") != prompt:
            errors.append(f"score row {index}: stored prompt does not match prompt builder")
        expected_key = cache_key(by_record[record_id], condition, model, prompt, row.get("generation_config"))
        if row.get("cache_key") != expected_key:
            errors.append(f"score row {index}: cache key mismatch")
        if expected_key in cache_keys:
            errors.append(f"score row {index}: duplicate cache key")
        cache_keys.add(expected_key)
        try:
            parsed_score, parsed_rationale, parsed_confidence = parse_result(str(row["raw_response"]))
            if abs(float(row["suspicion_score"]) - parsed_score) > 1e-12:
                errors.append(f"score row {index}: parsed suspicion score mismatch")
            if str(row["rationale"]) != parsed_rationale:
                errors.append(f"score row {index}: parsed rationale mismatch")
            if abs(float(row["confidence"]) - parsed_confidence) > 1e-12:
                errors.append(f"score row {index}: parsed confidence mismatch")
        except (KeyError, TypeError, ValueError) as exc:
            errors.append(f"score row {index}: raw-response verification failed: {exc}")
        models[model] += 1
        condition_counts[condition_name] += 1
        retry_counts[str(row.get("retries", 0))] += 1

    incomplete = {
        record_id: sorted(expected_conditions - conditions)
        for record_id, conditions in observed.items()
        if conditions != expected_conditions
    }
    if incomplete:
        errors.append(f"{len(incomplete)} records do not have exactly the three preregistered conditions")
    if expected_model and set(models) != {expected_model}:
        errors.append(f"expected only model {expected_model!r}, observed {sorted(models)}")
    if len(scores) != len(records) * len(Condition):
        errors.append(f"expected {len(records) * len(Condition)} score rows, observed {len(scores)}")
    if errors:
        preview = "; ".join(errors[:10])
        raise ValueError(f"cached-score verification failed with {len(errors)} error(s): {preview}")

    return {
        "verified": True,
        "records": len(records),
        "unique_attacks": len({record.attack_id for record in records}),
        "unique_tasks": len({record.task_id for record in records}),
        "score_rows": len(scores),
        "models": dict(sorted(models.items())),
        "conditions": dict(sorted(condition_counts.items())),
        "retry_counts": dict(sorted(retry_counts.items())),
        "successful_correct_attacks": sum(record.attack_success and record.correct for record in records),
        "task_cluster_equals_attack_cluster": (
            len(records) == len({record.attack_id for record in records}) == len({record.task_id for record in records})
        ),
    }


def reproduce_ranking_run(
    records_path: str | Path,
    games_path: str | Path,
    scores_path: str | Path,
    output_dir: str | Path,
    bootstraps: int,
    seed: int,
    expected_model: str | None = None,
) -> dict[str, Any]:
    verification = verify_cached_scores(records_path, scores_path, expected_model)
    games = json.loads(Path(games_path).read_text(encoding="utf-8"))
    record_ids = {row["attack_id"] for row in read_rows(records_path)}
    game_ids = {row["attack_id"] for game in games["games"] for row in game["rows"]}
    if not game_ids <= record_ids:
        raise ValueError(f"games reference {len(game_ids - record_ids)} attacks absent from the records file")
    if len({game["fold_id"] for game in games["games"]}) != len(games["games"]):
        raise ValueError("fold identifiers are not unique")

    target = Path(output_dir)
    target.mkdir(parents=True, exist_ok=True)
    ranking_path = target / "ranking_gate.json"
    result = evaluate_ranking_games(games_path, ranking_path, bootstraps, seed, scores_path)
    summary_path = write_ranking_summary(ranking_path)
    input_paths = {
        "records": Path(records_path).resolve(),
        "games": Path(games_path).resolve(),
        "scores": Path(scores_path).resolve(),
    }
    output_paths = {
        "ranking_json": ranking_path.resolve(),
        "summary": summary_path.resolve(),
        "metrics_csv": ranking_path.with_name("ranking_gate_metrics.csv").resolve(),
        "safety_plot": ranking_path.with_name("ranking_gate_safety.svg").resolve(),
        "oracle_gap_plot": ranking_path.with_name("ranking_gate_oracle_gap.svg").resolve(),
    }
    repository_root = Path(__file__).resolve().parents[2]
    code_paths = sorted((repository_root / "src" / "oracle_gap").glob("*.py"))
    code_paths.extend([
        repository_root / "pyproject.toml",
        repository_root / "research" / "experiment_spec.json",
        repository_root / "requirements-paper.lock",
        repository_root / "scripts" / "reproduce_expanded.ps1",
    ])
    manifest = {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "python": sys.version,
        "platform": platform.platform(),
        "seed": seed,
        "bootstraps": bootstraps,
        "cluster_unit": result["cluster_unit"],
        "expected_model": expected_model,
        "verification": verification,
        "game_folds": len(games["games"]),
        "game_attack_ids": len(game_ids),
        "inputs": {
            name: {"path": str(path), "sha256": sha256_file(path), "bytes": path.stat().st_size}
            for name, path in input_paths.items()
        },
        "outputs": {
            name: {"path": str(path), "sha256": sha256_file(path), "bytes": path.stat().st_size}
            for name, path in output_paths.items()
        },
        "code_and_specification": {
            str(path.relative_to(repository_root)).replace("\\", "/"): {
                "sha256": sha256_file(path),
                "bytes": path.stat().st_size,
            }
            for path in code_paths
        },
    }
    write_json(target / "reproduction_manifest.json", manifest)
    return manifest
