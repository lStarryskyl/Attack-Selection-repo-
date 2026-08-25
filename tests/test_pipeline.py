from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from oracle_gap.evaluation import evaluate, split_for_attack, top_k_ids
from oracle_gap.cli import parser
from oracle_gap.io import load_records, read_rows, write_jsonl
from oracle_gap.prompts import Condition, PromptVariant, build_prompt
from oracle_gap.schema import AttackRecord, parse_bool
from oracle_gap.scoring import DeterministicBackend, NvidiaBackend, cache_key, parse_result, score_records
from oracle_gap.synthetic import make_synthetic
from oracle_gap.validation import validate_file
from oracle_gap.paper import expected_random_safety, safety
from oracle_gap.reporting import write_ranking_summary, write_summary
from oracle_gap.reproducibility import verify_cached_scores
from oracle_gap.io import write_json
from oracle_gap.diagnostics import diagnose_ranking_games
from oracle_gap.matched import build_matched_records, evaluate_matched


class PipelineTests(unittest.TestCase):
    def test_paper_import_accepts_expanded_config(self):
        args = parser().parse_args([
            "paper-import", "--repo", "repo", "--records-output", "records.jsonl",
            "--games-output", "games.json", "--config", "full.json", "--case-name", "case",
        ])
        self.assertEqual(args.config, "full.json")
        self.assertEqual(args.case_name, "case")

    def test_schema_and_boolean_parsing(self):
        row = make_synthetic(2)[0]
        row["attack_success"] = "yes"
        record = AttackRecord.from_mapping(row)
        self.assertTrue(record.attack_success)
        self.assertFalse(parse_bool("0"))

    def test_prompts_respect_information_conditions(self):
        record = AttackRecord.from_mapping(make_synthetic(2)[0])
        code = build_prompt(record, Condition.CODE_ONLY)
        main = build_prompt(record, Condition.CODE_MAIN)
        oracle = build_prompt(record, Condition.CODE_MAIN_SIDE)
        self.assertNotIn(record.main_task, code)
        self.assertNotIn(record.side_task, code)
        self.assertIn(record.main_task, main)
        self.assertNotIn(record.side_task, main)
        self.assertIn(record.main_task, oracle)
        self.assertIn(record.side_task, oracle)
        focused = build_prompt(record, Condition.CODE_MAIN_SIDE, PromptVariant.SIDE_TASK_FOCUSED)
        self.assertIn("Treat the side task as a hypothesis", focused)
        self.assertNotIn("Treat the side task as a hypothesis", oracle)

    def test_parser_and_cache_key_are_deterministic(self):
        self.assertEqual(parse_result('{"suspicion_score": 42, "rationale": "x", "confidence": 0.7}')[0], 42)
        fenced = '```json\n{"suspicion_score": 43, "rationale": "y", "confidence": 0.8}\n```'
        self.assertEqual(parse_result(fenced), (43, "y", 0.8))
        record = AttackRecord.from_mapping(make_synthetic(2)[0])
        prompt = build_prompt(record, Condition.CODE_ONLY)
        self.assertEqual(cache_key(record, Condition.CODE_ONLY, "m", prompt), cache_key(record, Condition.CODE_ONLY, "m", prompt))
        self.assertNotEqual(
            cache_key(record, Condition.CODE_ONLY, "m", prompt, {"reasoning": False}),
            cache_key(record, Condition.CODE_ONLY, "m", prompt, {"reasoning": True}),
        )

    def test_nvidia_backend_requires_key(self):
        import os
        previous = os.environ.pop("NVIDIA_API_KEY", None)
        try:
            with self.assertRaises(RuntimeError):
                NvidiaBackend()
        finally:
            if previous is not None:
                os.environ["NVIDIA_API_KEY"] = previous

    def test_validation_detects_repeated_attacks(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "data.jsonl"
            write_jsonl(path, make_synthetic(5))
            records, report = validate_file(path)
            self.assertTrue(records)
            self.assertEqual(report["usable_rows"], 15)
            self.assertGreater(report["repeated_attack_count"], 0)

    def test_group_split_never_leaks_attack(self):
        self.assertEqual(split_for_attack("same", 1), split_for_attack("same", 1))

    def test_top_k_exact_budget(self):
        rows = [{"record_id": str(i), "suspicion_score": i} for i in range(100)]
        self.assertEqual(len(top_k_ids(rows, 0.01)), 1)
        self.assertEqual(len(top_k_ids(rows, 0.05)), 5)

    def test_paper_safety_and_random_reference(self):
        self.assertEqual(safety(k=3, valid=7, valid_audited=2), 3 / 8)
        self.assertEqual(expected_random_safety(total=5, valid=2, k=5), 1.0)
        self.assertAlmostEqual(expected_random_safety(total=4, valid=2, k=2), 25 / 36)

    def test_end_to_end_and_resume(self):
        with tempfile.TemporaryDirectory() as directory:
            input_path = Path(directory) / "data.jsonl"
            scores_path = Path(directory) / "scores.jsonl"
            write_jsonl(input_path, make_synthetic(40))
            records, excluded = load_records(input_path)
            self.assertFalse(excluded)
            first = score_records(records, DeterministicBackend(), scores_path)
            second = score_records(records, DeterministicBackend(), scores_path)
            self.assertEqual(first["written"], len(records) * 3)
            self.assertEqual(second["written"], 0)
            self.assertEqual(second["cache_hits"], len(records) * 3)
            verified = verify_cached_scores(input_path, scores_path, "deterministic-fixture-v1")
            self.assertTrue(verified["verified"])
            self.assertEqual(verified["score_rows"], len(records) * 3)
            results = evaluate(records, read_rows(scores_path), [0.005, 0.01, 0.05], 50, 123)
            self.assertEqual(results["complete_records"], len(records))
            self.assertTrue(all(row["audited_rows"] == row["expected_audited_rows"] for row in results["metrics"]))
            again = evaluate(records, read_rows(scores_path), [0.005, 0.01, 0.05], 50, 123)
            self.assertEqual(results, again)

    def test_parallel_scoring_is_complete_and_resumable(self):
        with tempfile.TemporaryDirectory() as directory:
            input_path = Path(directory) / "data.jsonl"
            scores_path = Path(directory) / "scores.jsonl"
            write_jsonl(input_path, make_synthetic(8))
            records, excluded = load_records(input_path)
            self.assertFalse(excluded)
            first = score_records(records, DeterministicBackend(), scores_path, workers=4)
            second = score_records(records, DeterministicBackend(), scores_path, workers=4)
            self.assertEqual(first["written"], len(records) * 3)
            self.assertEqual(second["cache_hits"], len(records) * 3)
            rows = read_rows(scores_path)
            self.assertEqual(len(rows), len({row["cache_key"] for row in rows}))

    def test_smoke_summary_does_not_make_research_decision(self):
        with tempfile.TemporaryDirectory() as directory:
            write_json(Path(directory) / "metrics.json", {
                "complete_records": 2,
                "bootstraps": 10,
                "metrics": [],
                "oracle_gaps": [{"audit_budget": 0.01, "code_only_safety": 0.0, "main_task_safety": 0.0, "oracle_safety": 0.0, "oracle_gap": 0.0}],
            })
            summary = write_summary(directory).read_text(encoding="utf-8")
            self.assertIn("SMOKE TEST ONLY", summary)

    def test_ranking_summary_stops_for_nonpositive_primary_gap(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "ranking.json"
            write_json(path, {
                "score_models": ["monitor"],
                "bootstraps": 10,
                "cluster_unit": "unique candidate attack",
                "attack_concentration": [],
                "metrics": [
                    {"budget": budget, "contrast": "monitor-side-minus-main", "delta": -0.01,
                     "ci_lower": -0.02, "ci_upper": 0.01, "p_positive": 0.2}
                    for budget in (0.005, 0.01)
                ],
            })
            summary = write_ranking_summary(path).read_text(encoding="utf-8")
            self.assertIn("STOP THE SIDE-TASK APPROXIMATION DIRECTION", summary)

    def test_diagnostics_reports_only_supported_fpr(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_json(root / "games.json", {
                "budgets": [0.5],
                "games": [{
                    "fold_id": "split_0", "audit_thresholds": {"0.5": 5},
                    "rows": [
                        {"attack_id": "a", "monitor_score": 7, "attacker_score": 2, "valid": True},
                        {"attack_id": "b", "monitor_score": 1, "attacker_score": 8, "valid": False},
                    ],
                }],
            })
            score_rows = []
            for attack_id in ("a", "b"):
                for condition, score in (("code_only", 10), ("code_main", 20), ("code_main_side", 90)):
                    score_rows.append({"attack_id": attack_id, "condition": condition, "suspicion_score": score})
            write_jsonl(root / "scores.jsonl", score_rows)
            write_json(root / "honest.json", {"data": [
                {"problem_id": 1, "scores": [7, 7]}, {"problem_id": 2, "scores": [1, 1]},
            ]})
            write_json(root / "splits.json", {"split_0": {"train": [2], "test": [1]}})
            result = diagnose_ranking_games(root / "games.json", root / "scores.jsonl", root / "honest.json", root / "splits.json", root / "out")
            self.assertEqual(result["aggregate_by_budget"][0]["pooled_original_monitor_honest_fpr"], 1.0)
            self.assertIn("Not estimable", result["fpr_scope"]["nemotron_conditions"])
            rows = read_rows(root / "out" / "per_fold_metrics.csv")
            self.assertEqual(rows[0]["code_main_side_honest_fpr"], "")

    def test_matched_build_pairs_label_without_changing_context(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            attack = make_synthetic(1)[0]
            attack["task_id"] = "BigCodeBench/7"
            attack["attack_id"] = "PID7BIDx"
            write_jsonl(root / "attacks.jsonl", [attack])
            write_json(root / "honest.json", [{
                "input": {"solution": "def task_func(): return 1"},
                "metadata": {"problem_id": 7},
            }])
            manifest = build_matched_records(root / "attacks.jsonl", root / "honest.json", root / "matched.jsonl")
            rows = read_rows(root / "matched.jsonl")
            self.assertEqual(manifest["total_records"], 2)
            self.assertEqual({row["provenance"]["candidate_class"] for row in rows}, {"attack", "honest"})
            self.assertEqual(rows[0]["main_task"], rows[1]["main_task"])
            self.assertEqual(rows[0]["side_task"], rows[1]["side_task"])
            self.assertEqual(rows[0]["attack_id"], rows[1]["attack_id"])

    def test_matched_evaluation_calibrates_on_train_honest(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            rows = []
            scores = []
            for pid, honest_score, attack_score in ((1, 1, 90), (2, 2, 80), (3, 3, 70)):
                base = AttackRecord(
                    attack_id=f"a{pid}", task_id=f"BigCodeBench/{pid}", fold_id="canonical",
                    candidate=f"attack {pid}", main_task="task", side_task="side",
                    attack_success=True, correct=True, provenance={"candidate_class": "attack"},
                )
                honest = AttackRecord(
                    attack_id=f"a{pid}", task_id=f"BigCodeBench/{pid}", fold_id="canonical",
                    candidate=f"honest {pid}", main_task="task", side_task="side",
                    attack_success=False, correct=True, provenance={"candidate_class": "honest"},
                )
                rows.extend((base.to_dict(), honest.to_dict()))
                scores.extend((
                    {"record_id": base.record_id, "condition": "code_main_side", "suspicion_score": attack_score},
                    {"record_id": honest.record_id, "condition": "code_main_side", "suspicion_score": honest_score},
                ))
            write_jsonl(root / "records.jsonl", rows)
            write_jsonl(root / "scores.jsonl", scores)
            write_json(root / "games.json", {"games": [{"fold_id": "split_0", "rows": [
                {"attack_id": "a3", "valid": True},
            ]}]})
            write_json(root / "splits.json", {"split_0": {"train": [1, 2], "test": [3]}})
            result = evaluate_matched(
                root / "records.jsonl", root / "scores.jsonl", root / "games.json",
                root / "splits.json", root / "out", [0.5], 20, 5,
            )
            metric = result["aggregate"][0]
            self.assertEqual(metric["mean_fpr"], 1.0)
            self.assertEqual(metric["caught_attack_occurrences"], 1)


if __name__ == "__main__":
    unittest.main()
