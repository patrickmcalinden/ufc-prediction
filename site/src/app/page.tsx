import { getUpcoming } from "@/lib/data";

export default async function Home() {
  const { event, fights } = await getUpcoming();

  if (!event) {
    return (
      <div className="py-16 text-center text-neutral-500">
        No upcoming event with locked predictions.
      </div>
    );
  }

  return (
    <div>
      <header className="mb-6">
        <p className="text-sm uppercase tracking-wider text-neutral-500">
          Next event · {event.event_date}
        </p>
        <h1 className="mt-1 text-3xl font-semibold tracking-tight">{event.name}</h1>
        {event.location && (
          <p className="mt-1 text-sm text-neutral-500">{event.location}</p>
        )}
      </header>

      <ul className="divide-y divide-neutral-200 dark:divide-neutral-800">
        {fights.map((f) => {
          const p = f.prediction;
          const a = f.fighter_a;
          const b = f.fighter_b;
          if (!a || !b || !p) return null;
          const winner = p.predicted_winner_id === a.fighter_id ? a : b;
          const conf = Math.round(Number(p.win_probability) * 100);
          return (
            <li key={f.fight_id} className="py-4">
              <div className="flex items-baseline justify-between">
                <div className="text-sm">
                  <span className={p.predicted_winner_id === a.fighter_id ? "font-medium" : "text-neutral-500"}>
                    {a.name}
                  </span>
                  <span className="mx-2 text-neutral-400">vs</span>
                  <span className={p.predicted_winner_id === b.fighter_id ? "font-medium" : "text-neutral-500"}>
                    {b.name}
                  </span>
                </div>
                <div className="text-sm text-neutral-500">
                  {f.weight_class}
                  {f.is_title_fight && <span className="ml-2 text-amber-600">· title</span>}
                </div>
              </div>
              <div className="mt-1 text-xs text-neutral-500">
                pick: <span className="text-foreground">{winner.name}</span>{" "}
                <span className="ml-1">({conf}%)</span>
              </div>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
