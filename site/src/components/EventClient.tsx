"use client";

import { useState } from "react";
import FightRow from "./FightRow";
import ModelTabs from "./ModelTabs";
import type { Fight, Prediction } from "@/lib/types";

function pickPrediction(fight: Fight, modelVersion: string | null): Prediction | null {
  if (modelVersion) {
    return fight.predictions?.find((pp) => pp.model_version === modelVersion) ?? null;
  }
  return fight.prediction ?? fight.predictions?.[0] ?? null;
}

export default function EventClient({
  fights,
  models,
  defaultModel,
}: {
  fights: Fight[];
  models: string[];
  defaultModel: string | null;
}) {
  const [active, setActive] = useState<string>(defaultModel ?? models[0] ?? "");

  // Per-event accuracy summary for the active model
  let graded = 0;
  let correct = 0;
  for (const f of fights) {
    const p = pickPrediction(f, active);
    if (p && f.winner_id != null) {
      graded += 1;
      if (p.predicted_winner_id === f.winner_id) correct += 1;
    }
  }

  return (
    <>
      <ModelTabs models={models} active={active} onChange={setActive} />

      {graded > 0 && (
        <p className="mb-4 text-sm text-neutral-600 dark:text-neutral-400">
          <span className="font-medium">{correct}/{graded}</span> graded picks correct
          <span className="ml-1 text-neutral-500">
            ({Math.round((correct / graded) * 100)}%)
          </span>
        </p>
      )}

      <ul className="divide-y divide-neutral-200 dark:divide-neutral-800">
        {fights.map((f) => (
          <FightRow key={f.fight_id} fight={f} modelVersion={active} />
        ))}
      </ul>
    </>
  );
}
