# Reproducing the expanded oracle-gap experiment

## Released analysis population

The released scored population contains 1,042 unique candidate attacks from 1,042 BigCodeBench tasks, reconstructed from AttackSelection commit `1a0b4c6bf5a125a55b7512fb5ff910da437ad041` and its full 1,140-task configuration. Of these, 284 attacks both preserve main-task correctness and achieve the side task. After applying the stored attacker submission threshold, 398 unique attacks enter at least one selective-audit game, including 94 unique successful-and-correct attacks. The game export contains 2,752 attack occurrences across the original 50 train/test folds.

The monitor cache contains exactly 3,126 responses: one response for each attack under each of the three preregistered information conditions. Prompts, raw responses, parsed values, model identifiers, token usage, and retries are retained. API credentials are not retained.

## One-command reproduction from cached responses

Python 3.11 or newer is sufficient; the cached ranking analysis uses only the standard library.

```powershell
python -m pip install -e .
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\reproduce_expanded.ps1 -Python python -OutputDir work/reproduced_expanded
```

This command:

1. validates all canonical records;
2. verifies that each record has exactly the three expected conditions;
3. reconstructs every prompt and cache key;
4. reparses every raw model response and compares it with the stored score;
5. confirms the single expected model and absence of duplicate calls;
6. reruns the 50-fold estimator with 1,000 attack-clustered bootstrap samples;
7. regenerates the JSON, CSV, Markdown, and SVG outputs;
8. writes SHA-256 hashes and environment metadata to `reproduction_manifest.json`;
9. runs the complete test suite.

The equivalent platform-independent command is:

```text
oracle-gap reproduce-ranking --records work/paper_full/records.jsonl --games work/paper_full/games.json --scores work/nvidia_replication/scores.jsonl --output-dir work/reproduced_expanded --expected-model nvidia/nemotron-3-nano-30b-a3b --bootstraps 1000 --seed 20260809
```

## Reconstructing the games from the public repository

Install the versions in `requirements-paper.lock`, check out the recorded AttackSelection commit, and run:

```text
oracle-gap paper-import --repo work/public/AttackSelection --config stripped/BCB_Set/case_study_full_1140_decomposition.json --records-output work/paper_full/records.jsonl --games-output work/paper_full/games.json --budgets 0.002,0.005,0.01,0.02
```

The exact experimental choices and decision rule are frozen in `research/experiment_spec.json`.

## Resuming model scoring

This is unnecessary for reproducing the released analysis. If the cache must be regenerated, set `NVIDIA_API_KEY` and run:

```text
oracle-gap score --input work/paper_full/records.jsonl --output work/nvidia_replication/scores.jsonl --backend nvidia --model nvidia/nemotron-3-nano-30b-a3b --confirm-paid-run
```

The command is resumable and skips cache keys already present. A new model or changed prompt is a new experiment and must use a separate output file.

## Statistical scope

The primary uncertainty unit is the unique candidate attack among the 398 attacks entering the games. Task-clustered resampling is identical for this exported population because each scored attack maps to a unique task. Fold-level uncertainty is diagnostic only because the same attacks recur across overlapping folds.

The result applies to this attack population, prompt, and Nemotron monitor. It does not establish that side-task information can never help a different or stronger monitor.
