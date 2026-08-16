from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import json
import logging
from pathlib import Path
import sys

from .config import Settings
from .evaluation import evaluate
from .io import load_records, read_rows, write_json, write_jsonl
from .reporting import write_ranking_summary, write_results, write_score_deltas, write_summary
from .scoring import DeterministicBackend, NvidiaBackend, OpenAIBackend, score_records
from .synthetic import make_synthetic
from .validation import validate_file
from .paper import evaluate_ranking_games, import_attackselection_repo
from .reproducibility import reproduce_ranking_run, verify_cached_scores


def configure_logging() -> None:
    logging.basicConfig(level=logging.INFO, format='{"time":"%(asctime)s","level":"%(levelname)s","message":"%(message)s"}')


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(prog="oracle-gap")
    sub = root.add_subparsers(dest="command", required=True)
    synthetic = sub.add_parser("synthetic")
    synthetic.add_argument("--output", required=True)
    synthetic.add_argument("--attacks", type=int, default=20)
    synthetic.add_argument("--seed", type=int)
    validate = sub.add_parser("validate")
    validate.add_argument("--input", required=True)
    validate.add_argument("--output", required=True)
    enrich = sub.add_parser("enrich")
    enrich.add_argument("--input", required=True)
    enrich.add_argument("--metadata", required=True)
    enrich.add_argument("--output", required=True)
    score = sub.add_parser("score")
    score.add_argument("--input", required=True)
    score.add_argument("--output", required=True)
    score.add_argument("--backend", choices=("deterministic", "openai", "nvidia"), default="deterministic")
    score.add_argument("--model")
    score.add_argument("--smoke-limit", type=int)
    score.add_argument("--confirm-paid-run", action="store_true")
    evaluate_p = sub.add_parser("evaluate")
    evaluate_p.add_argument("--input", required=True)
    evaluate_p.add_argument("--scores", required=True)
    evaluate_p.add_argument("--output-dir", required=True)
    evaluate_p.add_argument("--budgets", default="0.005,0.01,0.02,0.05,0.1")
    evaluate_p.add_argument("--bootstraps", type=int)
    evaluate_p.add_argument("--seed", type=int)
    report = sub.add_parser("report")
    report.add_argument("--results-dir", required=True)
    paper_import = sub.add_parser("paper-import")
    paper_import.add_argument("--repo", required=True)
    paper_import.add_argument("--records-output", required=True)
    paper_import.add_argument("--games-output", required=True)
    paper_import.add_argument("--budgets", default="0.002,0.005,0.01,0.02")
    paper_import.add_argument("--config", default="stripped/BCB_Set/case_study_438_decomposition.json")
    paper_import.add_argument("--case-name", default="Attack Selection:\nGEPA + optimized threshold")
    ranking = sub.add_parser("ranking-gate")
    ranking.add_argument("--games", required=True)
    ranking.add_argument("--output", required=True)
    ranking.add_argument("--scores")
    ranking.add_argument("--bootstraps", type=int)
    ranking.add_argument("--seed", type=int)
    verify = sub.add_parser("verify-cache")
    verify.add_argument("--records", required=True)
    verify.add_argument("--scores", required=True)
    verify.add_argument("--expected-model")
    verify.add_argument("--output", required=True)
    reproduce = sub.add_parser("reproduce-ranking")
    reproduce.add_argument("--records", required=True)
    reproduce.add_argument("--games", required=True)
    reproduce.add_argument("--scores", required=True)
    reproduce.add_argument("--output-dir", required=True)
    reproduce.add_argument("--expected-model")
    reproduce.add_argument("--bootstraps", type=int)
    reproduce.add_argument("--seed", type=int)
    return root


def main(argv: list[str] | None = None) -> int:
    configure_logging()
    args = parser().parse_args(argv)
    settings = Settings.from_env()
    if args.command == "synthetic":
        write_jsonl(args.output, make_synthetic(args.attacks, seed=args.seed or settings.seed))
        return 0
    if args.command == "validate":
        _, report = validate_file(args.input)
        write_json(args.output, report)
        print(json.dumps({key: report[key] for key in ("input_rows", "usable_rows", "excluded_rows", "repeated_attack_count")}, indent=2))
        return 0 if report["usable_rows"] else 2
    if args.command == "enrich":
        rows = read_rows(args.input)
        metadata = read_rows(args.metadata)
        index = {str(row.get("task_id", row.get("id", row.get("task")))): row for row in metadata}
        enriched = []
        for row in rows:
            task_id = str(row.get("task_id", row.get("problem_id", row.get("task", ""))))
            meta = index.get(task_id, {})
            merged = dict(row)
            if not merged.get("main_task"):
                merged["main_task"] = meta.get("complete_prompt", meta.get("instruct_prompt", meta.get("prompt", "")))
            merged["provenance"] = {"source": "team+bigcodebench", "metadata_matched": bool(meta)}
            enriched.append(merged)
        write_jsonl(args.output, enriched)
        return 0
    if args.command == "score":
        records, excluded = load_records(args.input)
        if excluded:
            logging.warning("excluded %s invalid input rows", len(excluded))
        if args.backend in {"openai", "nvidia"}:
            if args.smoke_limit is None and not args.confirm_paid_run:
                raise SystemExit("Refusing full paid run: pass --smoke-limit N or --confirm-paid-run")
            if args.backend == "openai":
                backend = OpenAIBackend(args.model or settings.model, settings.max_output_tokens)
            else:
                backend = NvidiaBackend(args.model or "nvidia/nemotron-3-nano-30b-a3b", settings.max_output_tokens)
        else:
            backend = DeterministicBackend()
        summary = score_records(records, backend, args.output, args.smoke_limit)
        score_rows = read_rows(args.output)
        write_json(Path(args.output).with_name("scoring_manifest.json"), {
            "backend": backend.name,
            "models": dict(Counter(str(row.get("model")) for row in score_rows)),
            "conditions": dict(Counter(str(row.get("condition")) for row in score_rows)),
            "rows": len(score_rows),
            "unique_cache_keys": len({row.get("cache_key") for row in score_rows}),
            "input_tokens": sum(int(row.get("input_tokens") or 0) for row in score_rows),
            "output_tokens": sum(int(row.get("output_tokens") or 0) for row in score_rows),
            "retry_counts": dict(Counter(str(row.get("retries", 0)) for row in score_rows)),
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "command": " ".join(sys.argv),
        })
        print(json.dumps(summary, indent=2))
        return 0
    if args.command == "evaluate":
        records, excluded = load_records(args.input)
        scores = read_rows(args.scores)
        budgets = [float(value) for value in args.budgets.split(",")]
        results = evaluate(records, scores, budgets, args.bootstraps or settings.bootstraps, args.seed or settings.seed)
        manifest = {
            "input": str(Path(args.input).resolve()),
            "scores": str(Path(args.scores).resolve()),
            "budgets": budgets,
            "seed": args.seed or settings.seed,
            "excluded_input_rows": len(excluded),
            "command": " ".join(sys.argv),
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }
        write_results(args.output_dir, results, manifest)
        write_score_deltas(args.output_dir, scores)
        write_summary(args.output_dir)
        print(json.dumps({"complete_records": results["complete_records"], "metrics": len(results["metrics"])}, indent=2))
        return 0
    if args.command == "report":
        print(write_summary(args.results_dir))
        return 0
    if args.command == "paper-import":
        budgets = [float(value) for value in args.budgets.split(",")]
        print(json.dumps(import_attackselection_repo(
            args.repo,
            args.records_output,
            args.games_output,
            budgets,
            config_path=args.config,
            case_name=args.case_name,
        ), indent=2))
        return 0
    if args.command == "ranking-gate":
        result = evaluate_ranking_games(args.games, args.output, args.bootstraps or settings.bootstraps, args.seed or settings.seed, args.scores)
        write_ranking_summary(args.output)
        print(json.dumps({"metrics": len(result["metrics"]), "cluster_unit": result["cluster_unit"]}, indent=2))
        return 0
    if args.command == "verify-cache":
        result = verify_cached_scores(args.records, args.scores, args.expected_model)
        write_json(args.output, result)
        print(json.dumps(result, indent=2))
        return 0
    if args.command == "reproduce-ranking":
        manifest = reproduce_ranking_run(
            args.records,
            args.games,
            args.scores,
            args.output_dir,
            args.bootstraps or settings.bootstraps,
            args.seed or settings.seed,
            args.expected_model,
        )
        print(json.dumps({
            "verified": manifest["verification"]["verified"],
            "records": manifest["verification"]["records"],
            "score_rows": manifest["verification"]["score_rows"],
            "folds": manifest["game_folds"],
            "manifest": str(Path(args.output_dir).resolve() / "reproduction_manifest.json"),
        }, indent=2))
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
