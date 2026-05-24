"use client";

import {
  CartesianGrid,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import type { AccuracyPoint } from "@/lib/types";

export default function AccuracyChart({ data }: { data: AccuracyPoint[] }) {
  if (data.length === 0) {
    return (
      <p className="py-6 text-sm text-neutral-500">No graded picks yet — chart will appear once events have been graded.</p>
    );
  }
  const rows = data.map((d) => ({
    date: d.event_date,
    name: d.event_name,
    accuracy: Math.round(d.accuracy_so_far * 1000) / 10,
  }));
  return (
    <div className="h-64 w-full">
      <ResponsiveContainer>
        <LineChart data={rows} margin={{ top: 5, right: 10, left: -10, bottom: 5 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="currentColor" strokeOpacity={0.1} />
          <XAxis dataKey="date" tick={{ fontSize: 11, fill: "currentColor" }} stroke="currentColor" strokeOpacity={0.3} />
          <YAxis
            domain={[40, 75]}
            tickFormatter={(v) => `${v}%`}
            tick={{ fontSize: 11, fill: "currentColor" }}
            stroke="currentColor"
            strokeOpacity={0.3}
          />
          <ReferenceLine y={50} stroke="currentColor" strokeDasharray="4 4" strokeOpacity={0.4} />
          <Tooltip
            contentStyle={{
              background: "var(--background)",
              border: "1px solid currentColor",
              borderRadius: 6,
              fontSize: 12,
            }}
            formatter={(v) => [`${Number(v).toFixed(1)}%`, "Accuracy"]}
            labelFormatter={(_label, payload) => {
              const item = payload?.[0]?.payload as { date: string; name: string } | undefined;
              return item ? `${item.date} — ${item.name}` : "";
            }}
          />
          <Line type="monotone" dataKey="accuracy" stroke="currentColor" strokeWidth={2} dot={{ r: 3 }} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
