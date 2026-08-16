# How to explain the oracle-gap findings

## Short version

Earlier work showed that changing the ranking signal can improve which submitted attacks are audited: the red team's private opportunity score sometimes ranked dangerous attacks better than the existing trusted-monitor score. Our experiment intervenes one step earlier. We reran a trusted monitor while varying what it was allowed to see, then inserted the new scores into the same ranking game. On the initial scored pool of 438 attacks (143 entering the games), exact side-task access appeared helpful, but the effect was uncertain and concentrated. On the expanded scored pool of 1,042 attacks (398 entering the games), the effect disappeared: exact side-task access was slightly worse than main-task access at every audit budget, and every clustered confidence interval included zero. Therefore, the evidence does not support the hypothesis that the ranking gap is mainly caused by the blue monitor lacking the attacker's written objective.

## Primary result

The preregistered contrast is exact side task minus main task:

| Audit budget | Safety difference | 95% attack-clustered interval |
|---:|---:|---:|
| 0.2% | -0.008 | [-0.072, +0.063] |
| 0.5% | -0.004 | [-0.066, +0.063] |
| 1.0% | -0.004 | [-0.054, +0.039] |
| 2.0% | -0.015 | [-0.043, +0.020] |

At the primary 0.5% and 1% budgets, the point estimates are negligible and negative. Under the frozen decision rule, this stops the side-task approximation direction.

## Difference from the prior ranking result

| Question | Prior ranking analysis | This experiment |
|---|---|---|
| Intervention | Replace the ranking score | Change the information supplied to a newly run monitor |
| Existing scores | `s_M`, red-team `q_RT`, and Random | Three new Nemotron scores |
| Conditions | Scores remain fixed | Code only; code + main task; code + main task + exact side task |
| Main question | Which available score chooses audits best? | Does revealing attacker information create a better monitor score? |
| Finding | `q_RT` looked useful in the 438-task ranking game, although concentrated and uncertain after clustered resampling | Exact side-task disclosure does not improve safety in the expanded game |
| Implication | Red may possess a useful selection signal | That advantage is not recovered merely by stating the exact side task to this monitor |

The results are complementary rather than contradictory. The earlier result concerns the usefulness of a private numerical ranking signal. The new result tests one proposed explanation for why that signal is useful and finds that the explanation is insufficient.

## What can and cannot be claimed

Supported claim: **For Nemotron under this fixed prompt and the expanded selective-audit games (398 unique submitted attacks, including 94 successful-and-correct attacks), revealing the exact side task does not improve safety over providing the main task.**

Supported interpretation: **The earlier ranking advantage is unlikely to be explained solely by an information boundary consisting of the missing written side-task description.**

Unsupported claims:

- side-task information never helps any monitor;
- the monitor fully understands every supplied side task;
- all attacker information is useless;
- the result directly proves that capability, ranking instability, or audit coverage is the cause.

Those are alternative hypotheses for future experiments, not findings of this experiment.

## Recommended next experiment

Test monitor capability rather than side-task approximation: preregister a small comparison between the current monitor and a stronger monitor, or use threat-specialized monitors for distinct backdoor families. A diversity or coverage-floor audit is also motivated because Flat, Random, and private-score rankings become close in the expanded population. Keep these as separate experiments with new caches and decision rules.
