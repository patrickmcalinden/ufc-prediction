"use client";

import {
  CartesianGrid,
  ComposedChart,
  ReferenceLine,
  ResponsiveContainer,
  Scatter,
  Tooltip,
  XAxis,
  YAxis,
  ZAxis,
} from "recharts";

import type { CalibrationBin } from "@/lib/types";

export default function CalibrationChart({ data }: { data: CalibrationBin[] }) {
  if (data.length === 0) {
    return <p className="py-6 text-sm text-neutral-500">No graded picks yet.</p>;
  }
  const rows = data.map((d) => ({
    predicted: Math.round(d.bucket_center * 100),
    actual: Math.round(d.actual_win_rate * 100),
    n: d.n,
  }));
  return (
    <div className="h-64 w-full">
      <ResponsiveContainer>
        <ComposedChart data={rows} margin={{ top: 5, right: 10, left: -10, bottom: 15 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="currentColor" strokeOpacity={0.1} />
          <XAxis
            dataKey="predicted"
            type="number"
            domain={[50, 100]}
            tickFormatter={(v) => `${v}%`}
            tick={{ fontSize: 11, fill: "currentColor" }}
            stroke="currentColor"
            strokeOpacity={0.3}
            label={{ value: "Predicted", position: "insideBottom", offset: -10, fontSize: 11 }}
          />
          <YAxis
            dataKey="actual"
            type="number"
            domain={[0, 100]}
            tickFormatter={(v) => `${v}%`}
            tick={{ fontSize: 11, fill: "currentColor" }}
            stroke="currentColor"
            strokeOpacity={0.3}
          />
          <ZAxis dataKey="n" range={[40, 240]} />
          <ReferenceLine
            segment={[
              { x: 50, y: 50 },
              { x: 100, y: 100 },
            ]}
            stroke="currentColor"
            strokeDasharray="4 4"
            strokeOpacity={0.5}
          />
          <Tooltip
            contentStyle={{
              background: "var(--background)",
              border: "1px solid currentColor",
              borderRadius: 6,
              fontSize: 12,
            }}
            formatter={(v, key) => {
              if (key === "actual") return [`${v}%`, "Actual"];
              if (key === "predicted") return [`${v}%`, "Predicted"];
              return [String(v), key === "n" ? "Picks" : String(key)];
            }}
          />
          <Scatter data={rows} fill="currentColor" />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}
