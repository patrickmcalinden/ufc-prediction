import Link from "next/link";
import { getPerformance } from "@/lib/data";
import AccuracyChart from "@/components/AccuracyChart";
import CalibrationChart from "@/components/CalibrationChart";

export const metadata = { title: "Performance · UFC Predictor" };

export default async function PerformancePage() {
  const { totals, per_event, calibration, timeseries } = await getPerformance();
  const accPct =
    totals.accuracy == null ? "—" : `${(Number(totals.accuracy) * 100).toFixed(1)}%`;
  const logLoss =
    totals.log_loss == null ? "—" : Number(totals.log_loss).toFixed(3);

  return (
    <div>
      <h1 className="text-3xl font-semibold tracking-tight">Performance</h1>
      <p className="mt-1 text-sm text-neutral-500">
        Tracked across deployed events using locked pre-event snapshots only.
        Backtest numbers don&apos;t count.
      </p>

      <section className="mt-6 grid grid-cols-2 gap-4 sm:grid-cols-4">
        <Stat label="Graded picks" value={totals.graded.toString()} />
        <Stat label="Correct" value={totals.correct.toString()} />
        <Stat label="Accuracy" value={accPct} />
        <Stat label="Log loss" value={logLoss} />
      </section>

      <h2 className="mt-10 text-xl font-semibold">Cumulative accuracy</h2>
      <p className="mt-1 text-xs text-neutral-500">
        Rolling accuracy after each event. Dashed line marks 50% (coin flip).
      </p>
      <div className="mt-3">
        <AccuracyChart data={timeseries} />
      </div>

      <h2 className="mt-10 text-xl font-semibold">Calibration</h2>
      <p className="mt-1 text-xs text-neutral-500">
        Predicted probability vs. actual win rate, in 5%-wide buckets. Points
        on the diagonal mean the model&apos;s confidence matches reality.
        Bubble size = pick count.
      </p>
      <div className="mt-3">
        <CalibrationChart data={calibration} />
      </div>

      <h2 className="mt-10 text-xl font-semibold">Per event</h2>
      <table className="mt-3 w-full text-sm">
        <thead className="text-left text-neutral-500">
          <tr className="border-b border-neutral-200 dark:border-neutral-800">
            <th className="py-2">Date</th>
            <th>Event</th>
            <th className="text-right">Picks</th>
            <th className="text-right">Correct</th>
            <th className="text-right">Pending</th>
          </tr>
        </thead>
        <tbody>
          {per_event.map((e) => (
            <tr
              key={e.event_id}
              className="border-b border-neutral-100 dark:border-neutral-900"
            >
              <td className="py-2 tabular-nums text-neutral-500">{e.event_date}</td>
              <td>
                <Link
                  href={`/events/${e.event_id}/`}
                  className="hover:underline"
                >
                  {e.name}
                </Link>
              </td>
              <td className="text-right tabular-nums">{e.n_picks}</td>
              <td className="text-right tabular-nums">{e.n_correct}</td>
              <td className="text-right tabular-nums text-neutral-500">
                {e.n_pending}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
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
