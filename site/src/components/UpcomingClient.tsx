"use client";

import { useState } from "react";
import type { Fight } from "@/lib/types";
import FightRow from "./FightRow";
import ModelTabs from "./ModelTabs";

// card_order = segment_index * 100 + match_index, so segment 0 = Main Card.
function sectionLabel(cardOrder: number | null): string {
  if (cardOrder == null) return "Other";
  const segment = Math.floor(cardOrder / 100);
  return ["Main Card", "Prelims", "Early Prelims"][segment] ?? "Other";
}

export default function UpcomingClient({
  fights,
  models,
  defaultModel,
}: {
  fights: Fight[];
  models: string[];
  defaultModel: string | null;
}) {
  const [active, setActive] = useState<string>(defaultModel ?? models[0] ?? "");

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
    <>
      <ModelTabs models={models} active={active} onChange={setActive} />

      {orderedLabels.map((label) => (
        <section key={label} className="mb-10">
          <h2 className="mb-2 text-xs font-medium uppercase tracking-wider text-neutral-500">
            {label}
          </h2>
          <ul className="divide-y divide-neutral-200 dark:divide-neutral-800">
            {sections.get(label)!.map((f) => (
              <FightRow key={f.fight_id} fight={f} modelVersion={active} />
            ))}
          </ul>
        </section>
      ))}
    </>
  );
}
