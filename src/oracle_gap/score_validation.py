from __future__ import annotations

from collections import Counter, defaultdict
from pathlib import Path
from statistics import mean
from typing import Any

from .io import load_records, read_rows, write_json, write_jsonl
from .scoring import parse_result


def validate_score_run(
    records_path: str | Path,
    scores_path: str | Path,
    output_path: str | Path,
    expected_conditions: list[str],
) -> dict[str, Any]:
    records, excluded = load_records(records_path)
    rows = read_rows(scores_path)
    record_index = {record.record_id: record for record in records}
    expected = {(record.record_id, condition) for record in records for condition in expected_conditions}
    observed = [(str(row.get("record_id")), str(row.get("condition"))) for row in rows]
    observed_set = set(observed)
    duplicate_pairs = sorted(pair for pair, count in Counter(observed).items() if count > 1)
    parse_failures: list[dict[str, str]] = []
    parse_mismatches: list[dict[str, str]] = []
    fail_closed_rows: list[dict[str, str]] = []
    grouped: dict[tuple[str, str], list[float]] = defaultdict(list)
    for row in rows:
        record_id = str(row.get("record_id"))
        condition = str(row.get("condition"))
        if row.get("parse_success") is False:
            score = float(row.get("suspicion_score", -1))
            if score != 100.0:
                parse_mismatches.append({"record_id": record_id, "condition": condition})
                continue
            fail_closed_rows.append({
                "record_id": record_id,
                "condition": condition,
                "error": str(row.get("parse_error", "unparseable monitor output")),
                "finish_reason": str(row.get("finish_reason", "unknown")),
            })
        else:
            try:
                score, _, _ = parse_result(str(row.get("raw_response", "")))
            except (TypeError, ValueError) as exc:
                parse_failures.append({"record_id": record_id, "condition": condition, "error": str(exc)})
                continue
        if float(row.get("suspicion_score", -1)) != score:
            parse_mismatches.append({"record_id": record_id, "condition": condition})
        record = record_index.get(record_id)
        if record is not None:
            label = "attack" if record.provenance.get("candidate_class") == "attack" else "honest"
            grouped[(condition, label)].append(score)

    score_summary = []
    for (condition, label), values in sorted(grouped.items()):
        score_summary.append({
            "condition": condition,
            "label": label,
            "n": len(values),
            "mean": mean(values),
            "minimum": min(values),
            "maximum": max(values),
            "at_zero": sum(value == 0 for value in values),
            "at_hundred": sum(value == 100 for value in values),
        })

    missing = sorted(expected - observed_set)
    unexpected = sorted(observed_set - expected)
    result: dict[str, Any] = {
        "valid": not any((excluded, missing, unexpected, duplicate_pairs, parse_failures, parse_mismatches)),
        "records": len(records),
        "excluded_input_rows": len(excluded),
        "expected_conditions": expected_conditions,
        "expected_score_rows": len(expected),
        "observed_score_rows": len(rows),
        "unique_cache_keys": len({row.get("cache_key") for row in rows}),
        "missing_pairs": missing,
        "unexpected_pairs": unexpected,
        "duplicate_pairs": duplicate_pairs,
        "parse_failures": parse_failures,
        "parse_mismatches": parse_mismatches,
        "fail_closed_rows": fail_closed_rows,
        "backends": dict(Counter(str(row.get("backend")) for row in rows)),
        "requested_models": dict(Counter(str(row.get("model")) for row in rows)),
        "response_models": dict(Counter(str(row.get("response_model")) for row in rows)),
        "prompt_variants": dict(Counter(str(row.get("prompt_variant")) for row in rows)),
        "generation_configs": dict(Counter(str(row.get("generation_config")) for row in rows)),
        "input_tokens": sum(int(row.get("input_tokens") or 0) for row in rows),
        "output_tokens": sum(int(row.get("output_tokens") or 0) for row in rows),
        "total_retries": sum(int(row.get("retries") or 0) for row in rows),
        "score_summary": score_summary,
    }
    write_json(output_path, result)
    return result


def filter_score_cache(
    records_path: str | Path,
    source_scores_path: str | Path,
    output_scores_path: str | Path,
) -> dict[str, Any]:
    records, excluded = load_records(records_path)
    if excluded:
        raise ValueError(f"records input contains {len(excluded)} excluded rows")
    record_ids = {record.record_id for record in records}
    source_rows = read_rows(source_scores_path)
    selected = [row for row in source_rows if str(row.get("record_id")) in record_ids]
    write_jsonl(output_scores_path, selected)
    return {
        "records": len(records),
        "source_score_rows": len(source_rows),
        "selected_score_rows": len(selected),
        "selected_record_ids": len({str(row.get("record_id")) for row in selected}),
    }


def merge_score_caches(
    source_scores_paths: list[str | Path],
    output_scores_path: str | Path,
) -> dict[str, Any]:
    """Merge score caches, with later sources replacing the same record/condition.

    Replacement is explicit so a follow-up prompt can reuse frozen control arms
    while replacing only its intervention arm. The report records every replaced
    pair and its old/new prompt variants.
    """
    merged: dict[tuple[str, str], dict[str, Any]] = {}
    replacements: list[dict[str, str]] = []
    source_rows: dict[str, int] = {}
    for source in source_scores_paths:
        rows = read_rows(source)
        source_rows[str(source)] = len(rows)
        for row in rows:
            pair = (str(row.get("record_id")), str(row.get("condition")))
            if pair in merged:
                replacements.append({
                    "record_id": pair[0],
                    "condition": pair[1],
                    "old_prompt_variant": str(merged[pair].get("prompt_variant")),
                    "new_prompt_variant": str(row.get("prompt_variant")),
                })
            merged[pair] = row
    rows = [merged[pair] for pair in sorted(merged)]
    write_jsonl(output_scores_path, rows)
    return {
        "sources": source_rows,
        "output_score_rows": len(rows),
        "replaced_pairs": len(replacements),
        "replacement_summary": dict(Counter(
            f"{row['condition']}:{row['old_prompt_variant']}->{row['new_prompt_variant']}"
            for row in replacements
        )),
    }
