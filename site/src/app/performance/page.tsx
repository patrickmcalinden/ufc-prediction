import { getPerformance } from "@/lib/data";
import PerformanceClient from "@/components/PerformanceClient";

export const metadata = { title: "Performance · UFC Predictor" };

export default async function PerformancePage() {
  const payload = await getPerformance();

  return (
    <div>
      <h1 className="text-3xl font-semibold tracking-tight">Performance</h1>
      <p className="mt-1 mb-6 text-sm text-neutral-500">
        Tracked across deployed events using locked pre-event snapshots only.
        Backtest numbers don&apos;t count. Switch models to compare.
      </p>
      <PerformanceClient payload={payload} />
    </div>
  );
}
