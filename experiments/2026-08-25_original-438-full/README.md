# Original-438 monitor-information experiment: complete matrix

Status: **all six preregistered configurations complete, validated, and
individually documented**.

The matrix contains 12,264 record-condition scores on the original 438
paper-aligned attack tasks, each paired with one honest solution to the same
task. It uses identical tasks, prompts within each registered arm, seeds, 50
paper games, and audit budgets. Total recorded usage is approximately 7.82
million input tokens and 1.87 million output tokens. The Nemotron 180-token
attack half was safely reused from the prior expanded run after exact prompt
verification; all other rows were newly scored.

## Primary answer

The preregistered contrast is exact-side-task minus main-task safety while
holding the paper's audit count fixed within every fold and budget.

| Configuration | 0.5% delta (95% CI) | 1% delta (95% CI) | Result |
|---|---:|---:|---|
| Nemotron, 180, no reasoning | +0.093 [-0.014, +0.123] | +0.069 [-0.016, +0.099] | Uncertain |
| GPT-5.4 Mini, 180, no reasoning | +0.104 [+0.006, +0.143] | +0.107 [+0.004, +0.138] | Positive |
| Nemotron, 512, reasoning | +0.002 [-0.062, +0.059] | +0.008 [-0.047, +0.071] | Negligible |
| GPT-5.4 Mini, 512, reasoning low | +0.020 [-0.011, +0.058] | +0.013 [-0.027, +0.049] | Uncertain/negligible |
| Nemotron, 512, focused side prompt | +0.054 [-0.031, +0.099] | +0.039 [-0.024, +0.097] | Uncertain |
| GPT-5.4 Mini, 512, focused side prompt | +0.026 [-0.031, +0.070] | +0.052 [-0.029, +0.074] | Uncertain |

Only GPT at 180 tokens with reasoning disabled produces a positive clustered
interval at the primary 0.5% and 1% budgets. That effect disappears when the
same deployed model receives more output budget and low reasoning, and it is not
restored by the focused side-task prompt. Nemotron never produces a clustered
interval excluding zero. Therefore, the matrix does **not** support the broad
hypothesis that the ranking gap is mainly caused by withholding the attacker's
written side-task objective. It shows a configuration-specific effect, not a
robust information-boundary result.

## What the focused prompts do show

The focused prompt materially improves absolute attack-versus-honest
classification. For GPT, focused-side attack/honest mean suspicion is
95.40/4.48 and mean valid-attack detection is about 0.85 around a held-out FPR
near 1%. Nemotron focused-side detection also rises, reaching 0.70 at the 2%
setting. Yet neither model gains statistically reliable fixed-`k` safety.

This is not contradictory. Absolute classification asks whether attacks score
above a threshold calibrated on honest code. Selective safety asks whether the
successful attacks rank inside a very small, fixed number of audit slots among
all attacks the red team submits. The added prompt helps the former much more
than the latter. The next defensible direction is threat-specialized monitoring
or information filtering with explicit audit-capacity evaluation—not generated
threat approximations premised on a proven oracle gap.

## Reliability and limitations

- Confidence intervals use 1,000 paired bootstrap replicates clustered by
  unique attack. The 638 fold occurrences correspond to only 143 unique
  submitted attacks and 32 unique successful-and-correct attacks.
- Each condition's absolute threshold uses training honest candidates only.
  Tied boundaries use a seeded lottery; test records never select thresholds.
- Small training sets (about 85 honest tasks per fold) make sub-1% FPR
  calibration noisy, so realized held-out FPR is reported rather than assumed.
- Nemotron 512-token reasoning has 174/2,628 fail-closed length responses in the
  standard composed grid; the focused composed grid has 177. GPT has none.
- GPT-5.4 Mini is a robustness model, not an exact model-controlled replacement
  for GPT-4.1 Nano. The planned GPT-4.1 Nano replication remains necessary.

`comparison_summary.csv` contains every fixed-`k` point estimate and clustered
contrast. Each configuration directory contains raw prompts/responses, token and
retry metadata, validation, fold-level FPR/detection, plots, and a standalone
methodology/result README.

The cached paired ROC analysis is reported in `CLASSIFICATION_FOLLOWUP.md`. It
confirms that focused side-task prompts strongly improve attack-versus-honest
discrimination, while explaining why that does not imply better ordering within
the red team's already suspicious submitted pool.
