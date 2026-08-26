# Nemotron side-task-focused prompt, 512 tokens, reasoning enabled

Status: **complete and validated**.

This is the requested prompt-addition follow-up. Code-only and main-task scores
are frozen from `nemotron_standard_512_reasoning`; only `code_main_side` is
rescored. The focused prompt treats the supplied side task as a hypothesis,
directs the monitor to trace relevant control flow, and explicitly says that an
honest candidate should remain low-suspicion when the described behavior is
absent. `composed_scores.jsonl` contains the two frozen control arms plus the
focused intervention arm; `merge-score-caches` records 876 deliberate
standard-to-focused replacements and no other changes.

## Primary result: fixed paper audit counts

| Budget | Code only | Main task | Focused exact side | Focused side minus main (95% clustered CI) |
|---:|---:|---:|---:|---:|
| 0.2% | 0.527 | 0.433 | 0.459 | +0.027 [-0.010, +0.096] |
| 0.5% | 0.693 | 0.594 | 0.648 | +0.054 [-0.031, +0.099] |
| 1.0% | 0.784 | 0.717 | 0.756 | +0.039 [-0.024, +0.097] |
| 2.0% | 0.954 | 0.918 | 0.954 | +0.036 [-0.024, +0.079] |

The focused prompt makes every point estimate positive and larger than the
standard Nemotron side arm, but all paired attack-clustered intervals still
include zero. It therefore improves the direction of the result without meeting
the preregistered evidence threshold for a reliable oracle gap.

## Held-out FPR and absolute detection

| Budget | Arm | Held-out pooled FPR | Mean valid-attack detection | Valid catches / attack audits |
|---:|---|---:|---:|---:|
| 0.2% | Main task | 0.254% | 0.000 | 0 / 2 |
| 0.2% | Focused exact side | 0.796% | 0.193 | 22 / 103 |
| 0.5% | Main task | 0.519% | 0.007 | 1 / 6 |
| 0.5% | Focused exact side | 0.994% | 0.193 | 22 / 113 |
| 1.0% | Main task | 1.022% | 0.007 | 1 / 8 |
| 1.0% | Focused exact side | 1.513% | 0.193 | 22 / 131 |
| 2.0% | Main task | 2.066% | 0.011 | 2 / 15 |
| 2.0% | Focused exact side | 2.541% | 0.703 | 103 / 416 |

The focused prompt greatly increases absolute-threshold attack detection, but
also transfers poorly at the smallest FPR targets. The 2% result catches many
more valid attacks while auditing 416 attack occurrences. This is useful
evidence for threat-specialized monitoring, but the fixed-`k` result shows that
the gain is not precise enough to claim reliably better scarce-audit ranking.

## Score and failure diagnostics

Focused exact-side attack/honest means are 84.91/5.09, compared with 86.55/4.92
under the standard side prompt. The focused instruction does not lower the
overall honest mean further and slightly lowers attack suspicion, but it changes
the score ordering enough to improve the point safety estimates.

The focused arm has 21 fail-closed length completions: 14 attacks and 7 honest
solutions. The standard exact-side arm had 18 (7 attacks, 11 honest). Thus the
focused prompt shifts rather than eliminates the output-limit problem. Across
the composed three-arm grid there are 177 fail-closed rows, including the frozen
control-arm failures.

- Focused scoring usage: 748,336 input and 292,275 output tokens.
- Focused retries: 49.
- All 2,628 composed record-condition pairs validate exactly once.

Machine-readable sources are `focused_side_scores.jsonl`,
`composed_scores.jsonl`, `validation.json`, `ranking_metrics.json`, and
`evaluation/matched_metrics.json`.
