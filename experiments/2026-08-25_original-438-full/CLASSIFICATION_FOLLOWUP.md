# Paired classification follow-up

This no-cost follow-up uses the cached matrix to separate two claims that the
fixed-audit safety results cannot answer by themselves:

1. Can the monitor distinguish attack candidates from honest solutions to the
   same task?
2. Can it distinguish the 32 unique successful-and-correct attacks from their
   matched honest solutions?

For each configuration and condition, ROC AUC is computed on paired tasks.
Confidence intervals use 1,000 paired bootstrap replicates clustered by task
(equivalently unique attack). The successful/correct analysis contains only the
32 unique valid attacks appearing in the paper games and their 32 matched honest
solutions. AUC describes discrimination in this constructed balanced sample; it
does not represent deployment precision or attack prevalence.

## AUC results

| Configuration | Population | Main-task AUC | Exact/focused-side AUC | Side minus main (95% task-clustered CI) |
|---|---|---:|---:|---:|
| Nemotron 180, no reasoning | All 438 | 0.679 | 0.551 | -0.128 [-0.172, -0.083] |
| Nemotron 180, no reasoning | 32 successful/correct | 0.609 | 0.533 | -0.076 [-0.273, +0.123] |
| GPT 180, no reasoning | All 438 | 0.994 | 0.975 | -0.019 [-0.027, -0.011] |
| GPT 180, no reasoning | 32 successful/correct | 0.995 | 0.929 | -0.066 [-0.130, -0.018] |
| Nemotron 512, reasoning | All 438 | 0.775 | 0.962 | +0.186 [+0.150, +0.225] |
| Nemotron 512, reasoning | 32 successful/correct | 0.840 | 0.947 | +0.107 [+0.027, +0.208] |
| GPT 512, reasoning low | All 438 | 0.993 | 0.979 | -0.014 [-0.023, -0.006] |
| GPT 512, reasoning low | 32 successful/correct | 0.988 | 0.965 | -0.023 [-0.076, +0.010] |
| Nemotron 512, focused side | All 438 | 0.775 | 0.971 | +0.195 [+0.159, +0.234] |
| Nemotron 512, focused side | 32 successful/correct | 0.840 | 0.969 | +0.129 [+0.041, +0.237] |
| GPT 512, focused side | All 438 | 0.993 | 0.998 | +0.005 [+0.001, +0.010] |
| GPT 512, focused side | 32 successful/correct | 0.988 | 0.996 | +0.008 [-0.008, +0.026] |

## Interpretation

The focused side-task prompt genuinely improves attack-versus-honest
classification. It is especially helpful for reasoning-enabled Nemotron and
makes GPT nearly perfect on the matched classification task. This validates the
earlier high detection rates: they are not merely caused by assigning high
suspicion to every candidate.

However, high attack-versus-honest AUC does not imply high selective-audit
safety. The red team's submitted pool already consists of attack candidates;
the scarce-audit problem is to rank the successful-and-correct attacks above the
other submissions. The focused prompt recognizes the written threat broadly but
does not reliably improve that within-attack ordering at fixed `k`.

This narrows the next research question. Instead of asking whether written side
tasks help at all, ask which information predicts *attack validity and success
within an already suspicious pool*. Candidate next signals include exploit
feasibility, trigger reachability, main-task correctness, and evidence that the
side effect survives tests. These should be evaluated at fixed audit counts and
on a larger unique-valid-attack pool before generated threat approximations are
pursued.

Every configuration directory contains `classification/classification_metrics.json`,
`classification_metrics.csv`, and `classification_contrasts.csv`.
