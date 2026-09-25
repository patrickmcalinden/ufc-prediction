# Experiment log

Every model idea tried, kept or not. Rows are appended by
`python -m pipeline.experiment experiments/<file>.py --log`; add a line
under **Notes** when a result needs context.

Metrics are from the walk-forward backtest (train on years before Y, test
on Y, 2021 onward) on the same fights as the base model. Δlogloss < 0 is
better; the CI is a paired bootstrap over fights. **better** requires the
CI entirely below 0 *and* a win in at least 2/3 of test years.

## Notes

- **Background (pre-log)** — v2's fighter_stats features fail the leak
  check (75.6%); v3 (tuned Elo + fight history + age) backtests 61.3% /
  0.655 vs v1 56.4% / 0.680. See PR #36.
- **001 reach_height** — Raw reach/height trips the leak check (height: the
  fighter with a known height wins 73.5% of one-sided fights; profiles are
  scraped for active fighters). Masked, neither helps: age + history
  already carry it. Dropped. Revisit only if profile coverage becomes
  complete.

## Results

| Date | Experiment / candidate | Base | # feat | Acc | Log loss | Δlogloss [95% CI] | Years won | Verdict | Hypothesis |
|---|---|---|---|---|---|---|---|---|---|
| 2026-09-25 | reach_height / raw | v3 | 31 | 0.616 | 0.6525 | -0.0030 [-0.0071, +0.0009] | 2/6 | LEAK | Reach and height advantage add signal on top of v3. |
| 2026-09-25 | reach_height / masked | v3 | 31 | 0.611 | 0.6547 | -0.0007 [-0.0028, +0.0013] | 4/6 | inconclusive | Reach and height advantage add signal on top of v3. |
| 2026-09-25 | reach_height / masked_diff | v3 | 27 | 0.612 | 0.6557 | +0.0003 [-0.0015, +0.0020] | 3/6 | inconclusive | Reach and height advantage add signal on top of v3. |
