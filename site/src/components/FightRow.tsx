import type { Fight } from "@/lib/types";

function record(f: NonNullable<Fight["fighter_a"]>) {
  return `${f.record_wins}-${f.record_losses}${f.record_draws ? `-${f.record_draws}` : ""}`;
}

export default function FightRow({ fight }: { fight: Fight }) {
  const a = fight.fighter_a;
  const b = fight.fighter_b;
  const p = fight.prediction;
  if (!a || !b) return null;

  const winnerId = p?.predicted_winner_id ?? null;
  const probA = p
    ? winnerId === a.fighter_id
      ? Number(p.win_probability)
      : 1 - Number(p.win_probability)
    : 0.5;
  const probB = 1 - probA;

  const aWon = fight.winner_id === a.fighter_id;
  const bWon = fight.winner_id === b.fighter_id;
  const decided = aWon || bWon;
  const correct = p && decided && winnerId === fight.winner_id;
  const wrong = p && decided && winnerId !== fight.winner_id;

  return (
    <li className="py-5">
      <div className="mb-2 flex items-baseline justify-between gap-4">
        <div className="flex flex-wrap items-baseline gap-x-3 text-sm text-neutral-500">
          <span>{fight.weight_class ?? "—"}</span>
          {fight.is_title_fight && (
            <span className="rounded bg-amber-100 px-1.5 py-0.5 text-xs font-medium text-amber-800 dark:bg-amber-900/40 dark:text-amber-300">
              title
            </span>
          )}
        </div>
        {p && (
          <div className="text-xs text-neutral-500">
            {correct && <span className="text-emerald-600 dark:text-emerald-400">✓ correct</span>}
            {wrong && <span className="text-rose-600 dark:text-rose-400">✗ wrong</span>}
            {!decided && <span>locked {p.snapshot_at?.slice(0, 10)}</span>}
          </div>
        )}
      </div>

      <FighterLine
        fighter={a}
        prob={probA}
        picked={winnerId === a.fighter_id}
        winner={aWon}
        decided={decided}
      />
      <FighterLine
        fighter={b}
        prob={probB}
        picked={winnerId === b.fighter_id}
        winner={bWon}
        decided={decided}
      />
    </li>
  );
}

function FighterLine({
  fighter,
  prob,
  picked,
  winner,
  decided,
}: {
  fighter: NonNullable<Fight["fighter_a"]>;
  prob: number;
  picked: boolean;
  winner: boolean;
  decided: boolean;
}) {
  const pct = Math.round(prob * 100);
  return (
    <div className="grid grid-cols-[1fr_60px] items-center gap-4 py-1">
      <div>
        <div className="flex items-baseline gap-2">
          <span className={picked ? "font-medium" : "text-neutral-600 dark:text-neutral-400"}>
            {fighter.name}
          </span>
          {decided && winner && (
            <span className="text-xs uppercase tracking-wider text-emerald-600 dark:text-emerald-400">
              winner
            </span>
          )}
          <span className="text-xs text-neutral-500">{record(fighter)}</span>
          {fighter.current_elo_modified != null && (
            <span className="text-xs tabular-nums text-neutral-500">
              elo {Math.round(Number(fighter.current_elo_modified))}
            </span>
          )}
        </div>
        <div className="mt-1 h-1.5 overflow-hidden rounded-full bg-neutral-100 dark:bg-neutral-800">
          <div
            className={`h-full ${
              picked ? "bg-neutral-900 dark:bg-neutral-100" : "bg-neutral-300 dark:bg-neutral-700"
            }`}
            style={{ width: `${pct}%` }}
          />
        </div>
      </div>
      <div className="text-right text-sm tabular-nums text-neutral-500">{pct}%</div>
    </div>
  );
}
