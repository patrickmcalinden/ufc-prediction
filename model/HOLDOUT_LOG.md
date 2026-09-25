# Holdout log

Every scoring run on the held-out fights (on/after 2024-09-26).
Written automatically by `pipeline.experiment --final`. Each extra look at
the holdout makes it a little less honest, so keep this list short.

| Date | Experiment / candidate | Base | # feat | Acc | Log loss | Δlogloss [95% CI] | Folds won | Verdict | Hypothesis |
|---|---|---|---|---|---|---|---|---|---|
| 2026-09-25 | final_search_2026_09 / v3_corner | v3 | 26 | 0.626 | 0.6371 | -0.0042 [-0.0102, +0.0018] | 2/2 | inconclusive | v3 + corner (the search leader) beats v3 on the held-out two years. |
