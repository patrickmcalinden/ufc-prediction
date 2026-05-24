import { getUpcoming } from "@/lib/data";
import FightRow from "@/components/FightRow";
import type { Fight } from "@/lib/types";

// card_order is encoded as (segment_index * 100) + match_index by the scraper,
// so segment 0 = Main Card, 1 = Prelims, 2 = Early Prelims.
function sectionLabel(cardOrder: number | null): string {
  if (cardOrder == null) return "Other";
  const segment = Math.floor(cardOrder / 100);
  return ["Main Card", "Prelims", "Early Prelims"][segment] ?? "Other";
}

export default async function Home() {
  const { event, fights } = await getUpcoming();

  if (!event) {
    return (
      <div className="py-16 text-center text-neutral-500">
        No upcoming event with locked predictions.
      </div>
    );
  }

  const sections = new Map<string, Fight[]>();
  for (const f of fights) {
    const label = sectionLabel(f.card_order);
    if (!sections.has(label)) sections.set(label, []);
    sections.get(label)!.push(f);
  }
  const orderedLabels = ["Main Card", "Prelims", "Early Prelims", "Other"].filter((l) =>
    sections.has(l),
  );

  return (
    <div>
      <header className="mb-8">
        <p className="text-sm uppercase tracking-wider text-neutral-500">
          Next event · {event.event_date}
        </p>
        <h1 className="mt-1 text-3xl font-semibold tracking-tight">{event.name}</h1>
        {event.location && (
          <p className="mt-1 text-sm text-neutral-500">{event.location}</p>
        )}
      </header>

      {orderedLabels.map((label) => (
        <section key={label} className="mb-10">
          <h2 className="mb-2 text-xs font-medium uppercase tracking-wider text-neutral-500">
            {label}
          </h2>
          <ul className="divide-y divide-neutral-200 dark:divide-neutral-800">
            {sections.get(label)!.map((f) => (
              <FightRow key={f.fight_id} fight={f} />
            ))}
          </ul>
        </section>
      ))}
    </div>
  );
}
