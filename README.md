# AI-Control Oracle-Gap Experiment

This package measures how trusted-monitor safety changes across three fixed information conditions:

1. candidate code only;
2. candidate code plus the main task;
3. candidate code plus the main task and exact side task.

It validates team artifacts, caches every score, calibrates on attack-group-disjoint training data, evaluates fixed audit budgets, bootstraps by unique attack and task, and produces machine-readable and human-readable reports.

## Quick start

Use Python 3.11 or newer.

```powershell
python -m pip install -e ".[all]"
oracle-gap synthetic --output data/synthetic.jsonl
oracle-gap validate --input data/synthetic.jsonl --output artifacts/validation.json
oracle-gap score --input data/synthetic.jsonl --output artifacts/scores.jsonl --backend deterministic --smoke-limit 24
oracle-gap evaluate --input data/synthetic.jsonl --scores artifacts/scores.jsonl --output-dir artifacts/results --bootstraps 200
oracle-gap report --results-dir artifacts/results
pytest
```

The deterministic backend is a pipeline test, not scientific evidence. For a small API smoke run, set `OPENAI_API_KEY`, install the `api` extra, and use `--backend openai --smoke-limit 6`. The CLI refuses a full paid run unless `--confirm-paid-run` is supplied.

For NVIDIA hosted NIM, set `NVIDIA_API_KEY` and run:

```powershell
oracle-gap score --input work/paper/records.jsonl --output artifacts/nvidia_scores.jsonl --backend nvidia --model nvidia/nemotron-3-nano-30b-a3b --smoke-limit 6
```

The NVIDIA adapter uses the OpenAI-compatible `/v1/chat/completions` endpoint but has no SDK dependency. A full run still requires `--confirm-paid-run`.

## Team data schema

Accepted inputs are `.json`, `.jsonl`, `.csv`, and `.parquet`. Field aliases are documented by `oracle-gap validate`; the canonical fields are:

| Field | Required | Meaning |
|---|---:|---|
| `attack_id` | yes | Stable attack identity across folds |
| `task_id` | yes | Stable benchmark task identity |
| `fold_id` | yes | Original evaluation fold |
| `candidate` | yes | Candidate code or trajectory |
| `main_task` | yes | Legitimate task text |
| `side_task` | yes | Exact malicious objective or attack description |
| `attack_success` | yes | Whether the side task succeeded |
| `correct` | yes | Whether the main task remained correct |
| `monitor_score` | no | Existing monitor score |
| `attacker_score` | no | Existing red-team opportunity score |
| `provenance` | no | Source/model/run metadata |

Boolean values may be booleans, `0/1`, or common true/false strings. Invalid records are excluded with reasons; duplicate canonical IDs are rejected.

## Public BigCodeBench metadata

Public task metadata can be joined by task ID:

```powershell
oracle-gap enrich --input team_attacks.jsonl --metadata BigCodeBench.jsonl --output data/enriched.jsonl
```

Public BigCodeBench does not provide the team’s generated attacks, fold assignments, or exact side-task labels, so those remain required from the research artifacts.

## Reproducibility and paid-call safety

- Train/test assignment hashes `attack_id`, preventing repeated attacks from crossing the split.
- Prompts, model identifiers, raw responses, parsed scores, token counts, retries, and timestamps are stored in JSONL.
- The cache key covers the record, condition, model, and exact prompt.
- Reruns resume from cache.
- Full OpenAI scoring requires `--confirm-paid-run`; smoke runs do not.
- Secrets are read from environment variables and never written to manifests.

All reported safety estimates are empirical detection rates among successful, correct attacks in the test split. They are benchmark estimates, not deployment guarantees.

For the completed expanded Nemotron experiment, see `REPRODUCIBILITY.md` for the one-command cached reproduction, `research/experiment_spec.json` for the frozen design, and `FINDINGS.md` for the research interpretation and comparison with the prior ranking analysis.

## Reproduce the paper ranking gate

The supplied analysis uses a different game-level safety definition and must not be mixed with the generic independent-record evaluator. After cloning the public `AttackSelection` repository and installing the `paper` extra:

```powershell
oracle-gap paper-import --repo work/public/AttackSelection --records-output data/paper_records.jsonl --games-output artifacts/paper_games.json
oracle-gap ranking-gate --games artifacts/paper_games.json --output artifacts/ranking_gate.json --bootstraps 2000
```

`paper-import` runs the repository's original 50-fold estimator once, reproduces the 0.5872 baseline, and exports the submitted games. `ranking-gate` preserves each fold's realized audit capacity `k`, compares Flat (`s_M`), Oracle-C (`q_RT`), and exact hypergeometric Random, and resamples unique candidate attacks as clusters. Passing `--scores` adds the three oracle-gap monitor conditions to the same games.
