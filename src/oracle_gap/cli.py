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
from .scoring import AzureOpenAIBackend, DeterministicBackend, NvidiaBackend, OpenAIBackend, score_records
from .synthetic import make_synthetic
from .validation import validate_file
from .paper import evaluate_ranking_games, import_attackselection_repo
from .reproducibility import reproduce_ranking_run, verify_cached_scores
from .diagnostics import diagnose_ranking_games
from .matched import build_matched_records, evaluate_matched
from .prompts import Condition, PromptVariant
from .score_validation import filter_score_cache, merge_score_caches, validate_score_run
from .classification import evaluate_classification


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
    score.add_argument("--backend", choices=("deterministic", "openai", "azure", "nvidia"), default="deterministic")
    score.add_argument("--model")
    score.add_argument("--max-output-tokens", type=int)
    score.add_argument("--reasoning", action="store_true")
    score.add_argument("--reasoning-effort", choices=("none", "minimal", "low", "medium", "high", "xhigh"), default="medium")
    score.add_argument("--max-thinking-tokens", type=int)
    score.add_argument("--prompt-variant", choices=tuple(value.value for value in PromptVariant), default=PromptVariant.STANDARD.value)
    score.add_argument("--conditions", default=",".join(value.value for value in Condition))
    score.add_argument("--smoke-limit", type=int)
    score.add_argument("--confirm-paid-run", action="store_true")
    score.add_argument("--workers", type=int, default=1)
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
    validate_scores = sub.add_parser("validate-score-run")
    validate_scores.add_argument("--records", required=True)
    validate_scores.add_argument("--scores", required=True)
    validate_scores.add_argument("--conditions", default=",".join(value.value for value in Condition))
    validate_scores.add_argument("--output", required=True)
    filter_scores = sub.add_parser("filter-score-cache")
    filter_scores.add_argument("--records", required=True)
    filter_scores.add_argument("--source-scores", required=True)
    filter_scores.add_argument("--output", required=True)
    merge_scores = sub.add_parser("merge-score-caches")
    merge_scores.add_argument("--sources", required=True, nargs="+")
    merge_scores.add_argument("--output", required=True)
    reproduce = sub.add_parser("reproduce-ranking")
    reproduce.add_argument("--records", required=True)
    reproduce.add_argument("--games", required=True)
    reproduce.add_argument("--scores", required=True)
    reproduce.add_argument("--output-dir", required=True)
    reproduce.add_argument("--expected-model")
    reproduce.add_argument("--bootstraps", type=int)
    reproduce.add_argument("--seed", type=int)
    diagnose = sub.add_parser("diagnose-ranking")
    diagnose.add_argument("--games", required=True)
    diagnose.add_argument("--scores", required=True)
    diagnose.add_argument("--honest-scores", required=True)
    diagnose.add_argument("--splits", required=True)
    diagnose.add_argument("--output-dir", required=True)
    matched_build = sub.add_parser("matched-build")
    matched_build.add_argument("--attacks", required=True)
    matched_build.add_argument("--honest-samples", required=True)
    matched_build.add_argument("--output", required=True)
    matched_build.add_argument("--subset-tasks", type=int)
    matched_build.add_argument("--seed", type=int)
    matched_evaluate = sub.add_parser("matched-evaluate")
    matched_evaluate.add_argument("--records", required=True)
    matched_evaluate.add_argument("--scores", required=True, nargs="+")
    matched_evaluate.add_argument("--games", required=True)
    matched_evaluate.add_argument("--splits", required=True)
    matched_evaluate.add_argument("--output-dir", required=True)
    matched_evaluate.add_argument("--budgets", default="0.002,0.005,0.01,0.02")
    matched_evaluate.add_argument("--bootstraps", type=int)
    matched_evaluate.add_argument("--seed", type=int)
    classification = sub.add_parser("classification-gate")
    classification.add_argument("--records", required=True)
    classification.add_argument("--scores", required=True, nargs="+")
    classification.add_argument("--games", required=True)
    classification.add_argument("--output-dir", required=True)
    classification.add_argument("--bootstraps", type=int)
    classification.add_argument("--seed", type=int)
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
        max_output_tokens = args.max_output_tokens or settings.max_output_tokens
        if args.backend in {"openai", "azure", "nvidia"}:
            if args.smoke_limit is None and not args.confirm_paid_run:
                raise SystemExit("Refusing full paid run: pass --smoke-limit N or --confirm-paid-run")
            if args.backend == "openai":
                selected_model = args.model or settings.model
                if args.reasoning and selected_model.startswith(("gpt-4.1", "gpt-4o", "gpt-4-")):
                    raise SystemExit(f"{selected_model} is a non-reasoning GPT model; choose a reasoning-capable model or omit --reasoning")
                backend = OpenAIBackend(selected_model, max_output_tokens, args.reasoning_effort if args.reasoning else None)
            elif args.backend == "azure":
                if args.model:
                    raise SystemExit("Azure uses AZURE_OPENAI_DEPLOYMENT; omit --model")
                backend = AzureOpenAIBackend(max_output_tokens, args.reasoning_effort if args.reasoning else "none")
            else:
                backend = NvidiaBackend(
                    args.model or "nvidia/nemotron-3-nano-30b-a3b",
                    max_output_tokens,
                    args.reasoning,
                    args.max_thinking_tokens,
                )
        else:
            backend = DeterministicBackend()
        try:
            conditions = tuple(Condition(value.strip()) for value in args.conditions.split(",") if value.strip())
        except ValueError as exc:
            raise SystemExit(f"invalid condition: {exc}") from exc
        prompt_variant = PromptVariant(args.prompt_variant)
        summary = score_records(records, backend, args.output, args.smoke_limit, prompt_variant, conditions, args.workers)
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
            "generation_config": getattr(backend, "generation_config", {}),
            "prompt_variant": prompt_variant.value,
            "workers": args.workers,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "command": " ".join(sys.argv),
        })
        print(json.dumps(summary, indent=2))
        return 0
    if args.command == "matched-build":
        result = build_matched_records(
            args.attacks, args.honest_samples, args.output,
            args.subset_tasks, args.seed or settings.seed,
        )
        print(json.dumps(result, indent=2))
        return 0
    if args.command == "matched-evaluate":
        result = evaluate_matched(
            args.records, args.scores, args.games, args.splits, args.output_dir,
            [float(value) for value in args.budgets.split(",")],
            args.bootstraps or settings.bootstraps,
            args.seed or settings.seed,
        )
        print(json.dumps({
            "records": result["records"], "score_rows": result["score_rows"],
            "conditions": result["conditions"], "metrics": len(result["aggregate"]),
        }, indent=2))
        return 0
    if args.command == "classification-gate":
        result = evaluate_classification(
            args.records, args.scores, args.games, args.output_dir,
            args.bootstraps or settings.bootstraps,
            args.seed or settings.seed,
        )
        print(json.dumps({
            "paired_tasks": result["paired_tasks"],
            "successful_correct_unique_attacks": result["successful_correct_unique_attacks"],
            "metrics": len(result["metrics"]),
            "contrasts": len(result["contrasts"]),
        }, indent=2))
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
    if args.command == "validate-score-run":
        result = validate_score_run(
            args.records,
            args.scores,
            args.output,
            [value.strip() for value in args.conditions.split(",") if value.strip()],
        )
        print(json.dumps({
            "valid": result["valid"],
            "records": result["records"],
            "score_rows": result["observed_score_rows"],
            "parse_failures": len(result["parse_failures"]),
        }, indent=2))
        return 0 if result["valid"] else 2
    if args.command == "filter-score-cache":
        result = filter_score_cache(args.records, args.source_scores, args.output)
        print(json.dumps(result, indent=2))
        return 0
    if args.command == "merge-score-caches":
        result = merge_score_caches(args.sources, args.output)
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
    if args.command == "diagnose-ranking":
        result = diagnose_ranking_games(args.games, args.scores, args.honest_scores, args.splits, args.output_dir)
        print(json.dumps({
            "folds": result["split_diagnostics"]["folds"],
            "budgets": len(result["aggregate_by_budget"]),
            "report": str(Path(args.output_dir).resolve() / "methodology_audit.md"),
        }, indent=2))
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
