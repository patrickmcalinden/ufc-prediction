"use client";

import Link from "next/link";
import { useState } from "react";
import AccuracyChart from "./AccuracyChart";
import CalibrationChart from "./CalibrationChart";
import ModelTabs from "./ModelTabs";
import type { PerformancePayload } from "@/lib/types";

export default function PerformanceClient({ payload }: { payload: PerformancePayload }) {
  const [active, setActive] = useState<string>(payload.default_model ?? payload.models[0] ?? "");
  const data = payload.by_model[active];

  if (!data) {
    return <p className="py-8 text-neutral-500">No data for model &ldquo;{active}&rdquo;.</p>;
  }

  const t = data.totals;
  const accPct = t.accuracy == null ? "—" : `${(Number(t.accuracy) * 100).toFixed(1)}%`;
  const logLoss = t.log_loss == null ? "—" : Number(t.log_loss).toFixed(3);

  return (
    <>
      <ModelTabs models={payload.models} active={active} onChange={setActive} />

      {data.meta && (
        <p className="mb-4 text-sm text-neutral-600 dark:text-neutral-400">
          <span className="font-medium">{data.meta.model_version}</span> ·{" "}
          {data.meta.description}{" "}
          <span className="text-neutral-500">
            (CV acc {(data.meta.cv_accuracy * 100).toFixed(1)}% · log-loss {data.meta.cv_logloss.toFixed(3)} ·{" "}
            {data.meta.n_samples.toLocaleString()} samples · {data.meta.features.length} features)
          </span>
        </p>
      )}

      <section className="mt-2 grid grid-cols-2 gap-4 sm:grid-cols-4">
        <Stat label="Graded picks" value={t.graded.toString()} />
        <Stat label="Correct" value={t.correct.toString()} />
        <Stat label="Accuracy" value={accPct} />
        <Stat label="Log loss" value={logLoss} />
      </section>

      <h2 className="mt-10 text-xl font-semibold">Cumulative accuracy</h2>
      <p className="mt-1 text-xs text-neutral-500">
        Rolling accuracy after each event. Dashed line marks 50% (coin flip).
      </p>
      <div className="mt-3">
        <AccuracyChart data={data.timeseries} />
      </div>

      <h2 className="mt-10 text-xl font-semibold">Calibration</h2>
      <p className="mt-1 text-xs text-neutral-500">
        Predicted probability vs. actual win rate, in 5%-wide buckets. Points on the diagonal mean the model&apos;s confidence matches reality. Bubble size = pick count.
      </p>
      <div className="mt-3">
        <CalibrationChart data={data.calibration} />
      </div>

      <h2 className="mt-10 text-xl font-semibold">Per event</h2>
      <div className="-mx-4 mt-3 overflow-x-auto sm:mx-0">
        <table className="w-full min-w-[520px] text-sm">
          <thead className="text-left text-neutral-500">
            <tr className="border-b border-neutral-200 dark:border-neutral-800">
              <th className="py-2 pl-4 pr-3 sm:pl-0">Date</th>
              <th className="pr-3">Event</th>
              <th className="px-2 text-right">Picks</th>
              <th className="px-2 text-right">Correct</th>
              <th className="pl-2 pr-4 text-right sm:pr-0">Pending</th>
            </tr>
          </thead>
          <tbody>
            {data.per_event.map((e) => (
              <tr key={e.event_id} className="border-b border-neutral-100 dark:border-neutral-900">
                <td className="py-2 pl-4 pr-3 tabular-nums whitespace-nowrap text-neutral-500 sm:pl-0">
                  {e.event_date}
                </td>
                <td className="pr-3">
                  <Link href={`/events/${e.event_id}/`} className="hover:underline">
                    {e.name}
                  </Link>
                </td>
                <td className="px-2 text-right tabular-nums">{e.n_picks}</td>
                <td className="px-2 text-right tabular-nums">{e.n_correct}</td>
                <td className="pl-2 pr-4 text-right tabular-nums text-neutral-500 sm:pr-0">
                  {e.n_pending}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-neutral-200 p-4 dark:border-neutral-800">
      <div className="text-xs uppercase tracking-wider text-neutral-500">{label}</div>
      <div className="mt-1 text-2xl font-semibold tabular-nums">{value}</div>
    </div>
  );
}
