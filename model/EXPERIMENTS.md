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

## Search: 2026-09-25 — "is there something there?"

Written before any search experiment ran.

- **Question:** with the data available (fights table, DOB/stance/reach,
  fighter_stats for every fighter with a 2018+ fight), is there a model
  meaningfully better than v3?
- **Base:** v3 (tuned Elo + fight history + age). Search-window score
  (2021 → 2024-09-25): 59.7% acc, 0.6644 log loss.
- **Holdout:** fights on/after 2024-09-26, ~1,100. One `--final` run at
  the end.
- **Budget:** ≤ 30 experiments; stop after 5 in a row without a *better*.
- **"Something there" =** the final model beats v3 on the holdout with
  the Δlogloss 95% CI entirely below 0. Otherwise the answer is "not in
  this data" and the write-up says what data would change that.
- **Known caveat:** v3's `ELO3_CONFIG` was tuned on 2019+ log loss, which
  overlaps the holdout. That flatters v3's *absolute* holdout score a
  little; comparisons against it are unaffected or conservative.

### Search notes (2026-09-25)

- **002 corner** — ESPN's A/B order is stable pre vs post fight (0 of 98
  verifiable locked snapshots swapped) and A wins 55–58% in every era
  except 2007–09 (66%). `d_corner = +1` (negated by mirroring) —
  **better** in search: 59.7% → 60.9%, −0.0055. Kept.
- **003 opponent_quality** — quality_wins won 4/4 years but CI touched 0
  (+0.0003). Not kept. SoS and Elo momentum: nothing.
- **004 method_profile**, **005 cage_time** — nothing; v3's history
  features already carry it.
- **006 elo_retune** — honest re-tune on 2012–2020 picked K=80,
  decay 0.3, split-decision weight 0.5; no gain. Confirms v3's Elo tuning
  (which overlapped the holdout) wasn't flattering it.
- **007 striking_grappling** — after backfilling fighter_stats for every
  fighter with a 2018+ fight (566 of 1,084 had ESPN stats; 518 had none),
  only 72.7% of 2018+ fights have stats for both fighters. **ESPN's own
  stats coverage is survivorship-biased**: in 2018+ UFC fights where only
  one fighter has a stats row, that fighter wins 69.5%. Using only
  both-covered fights passes the leak check but is inconclusive
  (best −0.0024, CI ±0.0055). Stop rule hit (5 without a better).
- **008 tuning** — every setting within ±0.0005. v3's hyperparameters are
  fine.
- **009 final (holdout, once)** — v3+corner vs v3 on 1,149 held-out
  fights: log loss 0.6371 vs 0.6413 (−0.0042, CI [−0.0102, +0.0018]),
  better in both folds, but accuracy 62.6% vs 64.1%. **Inconclusive.**

**Answer: not in this data.** Against the criteria written before the
search, nothing beats v3 on the holdout with a CI below zero. v3 itself
scores 64.1% / 0.6413 on the held-out two years. Corner order is the
only candidate with consistent direction; it's a reasonable low-stakes
live test but not a proven improvement. What would move it: per-fight
stats for *both* fighters from ESPN's event pages (fixes the coverage
bias above) and betting odds.

## Results

| Date | Experiment / candidate | Base | # feat | Acc | Log loss | Δlogloss [95% CI] | Years won | Verdict | Hypothesis |
|---|---|---|---|---|---|---|---|---|---|
| 2026-09-25 | reach_height / raw | v3 | 31 | 0.616 | 0.6525 | -0.0030 [-0.0071, +0.0009] | 2/6 | LEAK | Reach and height advantage add signal on top of v3. |
| 2026-09-25 | reach_height / masked | v3 | 31 | 0.611 | 0.6547 | -0.0007 [-0.0028, +0.0013] | 4/6 | inconclusive | Reach and height advantage add signal on top of v3. |
| 2026-09-25 | reach_height / masked_diff | v3 | 27 | 0.612 | 0.6557 | +0.0003 [-0.0015, +0.0020] | 3/6 | inconclusive | Reach and height advantage add signal on top of v3. |
| 2026-09-25 | corner / corner | v3 | 26 | 0.609 | 0.6589 | -0.0055 [-0.0105, -0.0008] | 3/4 | better | ESPN's A/B listing order (A wins ~57%) adds signal v3 mirrors away. |
| 2026-09-25 | opponent_quality / sos | leader | 29 | 0.603 | 0.6599 | +0.0010 [-0.0016, +0.0039] | 1/4 | inconclusive | Opponent-adjusted records (SoS, quality of wins, Elo momentum) add signal beyond win rate. |
| 2026-09-25 | opponent_quality / quality_wins | leader | 32 | 0.603 | 0.6566 | -0.0023 [-0.0048, +0.0003] | 4/4 | inconclusive | Opponent-adjusted records (SoS, quality of wins, Elo momentum) add signal beyond win rate. |
| 2026-09-25 | opponent_quality / momentum | leader | 29 | 0.608 | 0.6605 | +0.0016 [-0.0002, +0.0036] | 1/4 | inconclusive | Opponent-adjusted records (SoS, quality of wins, Elo momentum) add signal beyond win rate. |
| 2026-09-25 | opponent_quality / all | leader | 38 | 0.607 | 0.6588 | -0.0001 [-0.0029, +0.0029] | 2/4 | inconclusive | Opponent-adjusted records (SoS, quality of wins, Elo momentum) add signal beyond win rate. |
| 2026-09-25 | method_profile / win_methods | leader | 35 | 0.606 | 0.6610 | +0.0022 [-0.0003, +0.0044] | 2/4 | inconclusive | Per-method win/loss rates (power, submissions, durability) add signal beyond finish rate. |
| 2026-09-25 | method_profile / loss_methods | leader | 35 | 0.600 | 0.6595 | +0.0006 [-0.0014, +0.0026] | 2/4 | inconclusive | Per-method win/loss rates (power, submissions, durability) add signal beyond finish rate. |
| 2026-09-25 | method_profile / all | leader | 44 | 0.603 | 0.6593 | +0.0004 [-0.0020, +0.0029] | 2/4 | inconclusive | Per-method win/loss rates (power, submissions, durability) add signal beyond finish rate. |
| 2026-09-25 | cage_time / cage | leader | 35 | 0.609 | 0.6605 | +0.0016 [-0.0009, +0.0042] | 2/4 | inconclusive | Cage time, five-round/title experience and the DWCS route add signal beyond fight count. |
| 2026-09-25 | cage_time / big_fights | leader | 32 | 0.611 | 0.6592 | +0.0003 [-0.0017, +0.0023] | 1/4 | inconclusive | Cage time, five-round/title experience and the DWCS route add signal beyond fight count. |
| 2026-09-25 | cage_time / dwcs | leader | 29 | 0.605 | 0.6596 | +0.0008 [-0.0010, +0.0026] | 1/4 | inconclusive | Cage time, five-round/title experience and the DWCS route add signal beyond fight count. |
| 2026-09-25 | cage_time / all | leader | 44 | 0.611 | 0.6602 | +0.0013 [-0.0015, +0.0043] | 1/4 | inconclusive | Cage time, five-round/title experience and the DWCS route add signal beyond fight count. |
| 2026-09-25 | elo_retune / replace | leader | 26 | 0.609 | 0.6580 | -0.0009 [-0.0032, +0.0015] | 3/4 | inconclusive | An Elo tuned only on pre-2021 fights, with per-method K weights, beats ELO3_CONFIG. |
| 2026-09-25 | elo_retune / add | leader | 27 | 0.608 | 0.6582 | -0.0007 [-0.0029, +0.0017] | 2/4 | inconclusive | An Elo tuned only on pre-2021 fights, with per-method K weights, beats ELO3_CONFIG. |
| 2026-09-25 | tuning / depth2 | leader | 26 | 0.610 | 0.6584 | -0.0004 [-0.0021, +0.0013] | 2/4 | inconclusive | Different depth / learning rate / regularisation improves the leader. |
| 2026-09-25 | tuning / depth4 | leader | 26 | 0.607 | 0.6594 | +0.0005 [-0.0013, +0.0023] | 2/4 | inconclusive | Different depth / learning rate / regularisation improves the leader. |
| 2026-09-25 | tuning / slow | leader | 26 | 0.611 | 0.6593 | +0.0004 [-0.0008, +0.0019] | 1/4 | inconclusive | Different depth / learning rate / regularisation improves the leader. |
| 2026-09-25 | tuning / reg | leader | 26 | 0.611 | 0.6590 | +0.0002 [-0.0021, +0.0025] | 2/4 | inconclusive | Different depth / learning rate / regularisation improves the leader. |
| 2026-09-25 | tuning / depth2_reg | leader | 26 | 0.611 | 0.6587 | -0.0002 [-0.0024, +0.0020] | 2/4 | inconclusive | Different depth / learning rate / regularisation improves the leader. |
| 2026-09-25 | striking_grappling / striking | leader | 41 | 0.611 | 0.6580 | -0.0009 [-0.0062, +0.0044] | 2/4 | inconclusive | Per-minute striking/grappling rates (2018+ stats, full coverage) add signal beyond record-based history. |
| 2026-09-25 | striking_grappling / grappling | leader | 44 | 0.611 | 0.6591 | +0.0002 [-0.0042, +0.0046] | 2/4 | inconclusive | Per-minute striking/grappling rates (2018+ stats, full coverage) add signal beyond record-based history. |
| 2026-09-25 | striking_grappling / all | leader | 59 | 0.615 | 0.6566 | -0.0023 [-0.0079, +0.0032] | 3/4 | inconclusive | Per-minute striking/grappling rates (2018+ stats, full coverage) add signal beyond record-based history. |
| 2026-09-25 | striking_grappling / diffs_only | leader | 37 | 0.613 | 0.6565 | -0.0024 [-0.0077, +0.0033] | 3/4 | inconclusive | Per-minute striking/grappling rates (2018+ stats, full coverage) add signal beyond record-based history. |
