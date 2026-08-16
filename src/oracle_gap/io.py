from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any, Iterable

from .schema import AttackRecord


def read_rows(path: str | Path) -> list[dict[str, Any]]:
    source = Path(path)
    suffix = source.suffix.lower()
    if suffix == ".jsonl":
        return [json.loads(line) for line in source.read_text(encoding="utf-8").splitlines() if line.strip()]
    if suffix == ".json":
        value = json.loads(source.read_text(encoding="utf-8"))
        if isinstance(value, dict):
            value = value.get("records", value.get("data", value))
        if not isinstance(value, list):
            raise ValueError("JSON input must be a list or contain a records/data list")
        return value
    if suffix == ".csv":
        with source.open("r", encoding="utf-8-sig", newline="") as handle:
            return list(csv.DictReader(handle))
    if suffix == ".parquet":
        try:
            import pandas as pd
        except ImportError as exc:
            raise RuntimeError("Parquet support requires: pip install -e .[data]") from exc
        return pd.read_parquet(source).to_dict(orient="records")
    raise ValueError(f"unsupported input type: {suffix}")


def load_records(path: str | Path) -> tuple[list[AttackRecord], list[dict[str, Any]]]:
    valid: list[AttackRecord] = []
    excluded: list[dict[str, Any]] = []
    seen: set[str] = set()
    for index, raw in enumerate(read_rows(path)):
        try:
            record = AttackRecord.from_mapping(raw)
            if record.record_id in seen:
                raise ValueError("duplicate canonical record")
            seen.add(record.record_id)
            valid.append(record)
        except (TypeError, ValueError) as exc:
            excluded.append({"row": index, "reason": str(exc)})
    return valid, excluded


def write_json(path: str | Path, value: Any) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: str | Path, rows: Iterable[dict[str, Any]]) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def append_jsonl(path: str | Path, row: dict[str, Any]) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(row, sort_keys=True) + "\n")
        handle.flush()

