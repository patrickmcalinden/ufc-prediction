import React, { useMemo, useState, useEffect } from 'react';
import { useQuery } from '@tanstack/react-query';
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, LabelList, CartesianGrid,
  LineChart, Line, ScatterChart, Scatter, ReferenceLine, ComposedChart, Area,
} from 'recharts';
import { api } from '../lib/api';
import { groupAndSortByEvent } from '../lib/utils';
import ResultRow from '../components/ResultRow';
import ModelSelector from '../components/ModelSelector';

export default function Results() {
  const [selectedModel, setSelectedModel] = useState(null);

  const { data: results, isLoading, isError } = useQuery({
    queryKey: ['results', selectedModel],
    queryFn: () => api.getResults(selectedModel),
    retry: 1,
  });

  // ── Event groups ─────────────────────────────────────────────────
  // Only show the last 2 graded events (most recent first).
  const sortedEvents = useMemo(
    () => groupAndSortByEvent(results, { chronological: true }).slice(0, 2),
    [results]
  );

  // ── Filtered results: only fights from the last 2 events ─────────
  // All summary stats and charts derive from this scoped set, so historical
  // events do not pollute the dashboard.
  const scopedResults = useMemo(
    () => sortedEvents.flatMap((e) => e.fights),
    [sortedEvents]
  );

  // ── Derived analytics ─────────────────────────────────────────────
  const analytics = useMemo(() => {
    if (!scopedResults || scopedResults.length === 0) {
      return {
        total: 0, correct: 0, wrong: 0, accuracy: '0.0',
        byConfidence: [], calibration: [], distribution: [],
        avgConfidence: '0.0', avgConfidenceCorrect: '0.0', avgConfidenceWrong: '0.0',
        highConfidenceAcc: '0.0', titleFightAcc: null,
      };
    }

    const total = scopedResults.length;
    const correct = scopedResults.filter((r) => r.was_correct === true).length;
    const wrong = scopedResults.filter((r) => r.was_correct === false).length;
    const accuracy = (correct / total * 100).toFixed(1);

    // Average confidence
    const avgConfidence = (scopedResults.reduce((s, r) => s + r.win_probability, 0) / total * 100).toFixed(1);
    const correctPreds = scopedResults.filter((r) => r.was_correct === true);
    const wrongPreds = scopedResults.filter((r) => r.was_correct === false);
    const avgConfidenceCorrect = correctPreds.length > 0
      ? (correctPreds.reduce((s, r) => s + r.win_probability, 0) / correctPreds.length * 100).toFixed(1) : '0.0';
    const avgConfidenceWrong = wrongPreds.length > 0
      ? (wrongPreds.reduce((s, r) => s + r.win_probability, 0) / wrongPreds.length * 100).toFixed(1) : '0.0';

    // High confidence accuracy (>70%)
    const highConf = scopedResults.filter((r) => r.win_probability > 0.70);
    const highConfidenceAcc = highConf.length > 0
      ? (highConf.filter((r) => r.was_correct).length / highConf.length * 100).toFixed(1) : null;

    // Title fight accuracy
    const titleFights = scopedResults.filter((r) => r.is_title_fight);
    const titleFightAcc = titleFights.length > 0
      ? (titleFights.filter((r) => r.was_correct).length / titleFights.length * 100).toFixed(1) : null;

    // ── Confidence calibration (finer buckets) ────────────────────
    const bucketEdges = [50, 55, 60, 65, 70, 75, 80, 100];
    const calibration = [];
    const distribution = [];

    for (let i = 0; i < bucketEdges.length - 1; i++) {
      const low = bucketEdges[i];
      const high = bucketEdges[i + 1];
      const label = high === 100 ? `${low}%+` : `${low}-${high}%`;
      const inBucket = scopedResults.filter((r) => {
        const pct = r.win_probability * 100;
        return pct >= low && pct < high;
      });
      const bucketCorrect = inBucket.filter((r) => r.was_correct === true).length;
      const bucketAcc = inBucket.length > 0 ? Math.round((bucketCorrect / inBucket.length) * 100) : null;
      const midpoint = high === 100 ? 85 : (low + high) / 2;

      calibration.push({
        bucket: label,
        predicted: Math.round(midpoint),
        actual: bucketAcc,
        fights: inBucket.length,
      });

      distribution.push({
        bucket: label,
        count: inBucket.length,
        correct: bucketCorrect,
        wrong: inBucket.length - bucketCorrect,
      });
    }

    // ── Legacy tier buckets for the bar chart ─────────────────────
    const tierBuckets = { Low: { correct: 0, total: 0 }, Medium: { correct: 0, total: 0 }, High: { correct: 0, total: 0 } };
    scopedResults.forEach((r) => {
      const pct = r.win_probability * 100;
      const tier = pct < 55 ? 'Low' : pct <= 70 ? 'Medium' : 'High';
      tierBuckets[tier].total++;
      if (r.was_correct === true) tierBuckets[tier].correct++;
    });
    const byConfidence = ['Low', 'Medium', 'High'].map((tier) => ({
      tier: `${tier} (${tier === 'Low' ? '<55%' : tier === 'Medium' ? '55-70%' : '>70%'})`,
      accuracy: tierBuckets[tier].total > 0 ? Math.round((tierBuckets[tier].correct / tierBuckets[tier].total) * 100) : 0,
      fights: tierBuckets[tier].total,
    }));

    return {
      total, correct, wrong, accuracy, byConfidence, calibration, distribution,
      avgConfidence, avgConfidenceCorrect, avgConfidenceWrong, highConfidenceAcc, titleFightAcc,
    };
  }, [scopedResults]);

  // ── Collapse state ─────────────────────────────────────────────
  const [collapsedEvents, setCollapsedEvents] = useState(new Set());
  const [initializedCollapse, setInitializedCollapse] = useState(false);

  useEffect(() => {
    if (sortedEvents.length === 0 || initializedCollapse) return;
    setCollapsedEvents(new Set(sortedEvents.map((e) => e.eventName)));
    setInitializedCollapse(true);
  }, [sortedEvents, initializedCollapse]);

  const toggleEvent = (eventName) => {
    setCollapsedEvents((prev) => {
      const next = new Set(prev);
      if (next.has(eventName)) next.delete(eventName);
      else next.add(eventName);
      return next;
    });
  };

  const allCollapsed = sortedEvents.length > 0 && sortedEvents.every((e) => collapsedEvents.has(e.eventName));
  const toggleAll = () => {
    if (allCollapsed) setCollapsedEvents(new Set());
    else setCollapsedEvents(new Set(sortedEvents.map((e) => e.eventName)));
  };

  const formatEventDate = (date) => {
    return date.toLocaleDateString('en-US', {
      timeZone: 'UTC',
      weekday: 'long',
      month: 'long',
      day: 'numeric',
      year: 'numeric',
    });
  };

  // ── Custom tooltips ─────────────────────────────────────────────
  const TierTooltip = ({ active, payload }) => {
    if (!active || !payload || !payload.length) return null;
    const d = payload[0].payload;
    return (
      <div className="bg-[#0a0a0a] border border-white/10 rounded-xl px-4 py-3 shadow-2xl text-xs">
        <p className="font-black text-white uppercase tracking-wide">{d.tier}</p>
        <p className="text-gray-400 mt-1">{d.accuracy}% accuracy across {d.fights} fight{d.fights !== 1 ? 's' : ''}</p>
      </div>
    );
  };

  const CalibrationTooltip = ({ active, payload }) => {
    if (!active || !payload || !payload.length) return null;
    const d = payload[0].payload;
    if (d.actual === null) return null;
    return (
      <div className="bg-[#0a0a0a] border border-white/10 rounded-xl px-4 py-3 shadow-2xl text-xs">
        <p className="font-black text-white uppercase tracking-wide">{d.bucket}</p>
        <p className="text-gray-400 mt-1">
          Predicted: ~{d.predicted}%
        </p>
        <p className="text-gray-400">
          Actual: {d.actual}% ({d.fights} fight{d.fights !== 1 ? 's' : ''})
        </p>
        <p className={`mt-1 font-bold ${d.actual >= d.predicted ? 'text-green-400' : 'text-amber-400'}`}>
          {d.actual >= d.predicted ? 'Well calibrated ✓' : 'Over-confident'}
        </p>
      </div>
    );
  };

  const DistributionTooltip = ({ active, payload }) => {
    if (!active || !payload || !payload.length) return null;
    const d = payload[0].payload;
    return (
      <div className="bg-[#0a0a0a] border border-white/10 rounded-xl px-4 py-3 shadow-2xl text-xs">
        <p className="font-black text-white uppercase tracking-wide">{d.bucket}</p>
        <p className="text-green-400 mt-1">{d.correct} correct</p>
        <p className="text-red-400">{d.wrong} wrong</p>
        <p className="text-gray-400 mt-1">{d.count} total predictions</p>
      </div>
    );
  };

  // ── Render ─────────────────────────────────────────────────────
  return (
    <div className="flex flex-col gap-6 w-full animate-fade-in-up pb-20 mt-4">
      {/* Page header */}
      <div className="flex justify-between items-end mb-4">
        <div>
          <h1 className="text-4xl bg-gradient-to-r from-white to-gray-400 bg-clip-text text-transparent md:text-5xl font-black tracking-tight mb-2 uppercase">
            Prediction Results
          </h1>
          <p className="text-gray-400 font-medium tracking-wide">
            Historical model performance and calibration analytics.
          </p>
        </div>
        <div className="flex items-center gap-3 shrink-0 ml-4">
          <ModelSelector selected={selectedModel} onChange={setSelectedModel} />
          {sortedEvents.length > 0 && (
          <button
            onClick={toggleAll}
            className="flex items-center gap-2 px-4 py-2 rounded-full bg-white/5 border border-white/10 hover:bg-white/10 transition-colors text-[11px] font-bold uppercase tracking-widest text-gray-400 hover:text-white shrink-0 ml-4"
          >
            <svg
              xmlns="http://www.w3.org/2000/svg"
              className={`h-3.5 w-3.5 transition-transform duration-300 ${allCollapsed ? 'rotate-180' : ''}`}
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
            </svg>
            {allCollapsed ? 'Expand All' : 'Collapse All'}
          </button>
        )}
        </div>
      </div>

      {/* Loading / Error / Empty */}
      {isLoading ? (
        <div className="flex justify-center py-20">
          <div className="text-ufcred-500 font-bold tracking-widest animate-pulse border border-ufcred-500/20 bg-ufcred-500/5 px-8 py-4 rounded-full backdrop-blur-md">
            LOADING RESULT DATA...
          </div>
        </div>
      ) : isError ? (
        <div className="flex justify-center py-20">
          <div className="text-red-500 font-bold bg-red-500/10 border border-red-500/20 px-8 py-4 rounded-[2rem] text-center max-w-lg shadow-2xl backdrop-blur-md">
            <p className="tracking-widest uppercase mb-2">Results Retrieval Failed</p>
            <p className="text-sm text-gray-400 font-medium">
              Unable to connect to the prediction backend engine. Please ensure the Python API server is running locally.
            </p>
          </div>
        </div>
      ) : !results || results.length === 0 ? (
        <div className="bg-black/20 backdrop-blur-md p-8 rounded-[2rem] border border-white/5 py-20 flex flex-col items-center gap-4 hover:border-ufcred-500/30 transition-colors shadow-2xl">
          <div className="w-16 h-16 rounded-full bg-white/5 flex items-center justify-center mb-4">
            <svg xmlns="http://www.w3.org/2000/svg" className="h-8 w-8 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
          </div>
          <p className="text-white font-black tracking-widest text-center uppercase text-xl">No Graded Predictions Yet</p>
          <p className="text-gray-400 font-medium text-center max-w-lg">
            Completed fights have not been graded yet. Results will appear here once predictions are evaluated against actual outcomes.
          </p>
        </div>
      ) : (
        <div className="flex flex-col gap-8 w-full">

          {/* ══════════════════════════════════════════════════════════════
               SECTION 1 — Summary Stat Cards
              ═══════════════════════════════════════════════════════════ */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            {[
              { label: 'Total Graded', value: analytics.total, accent: false },
              { label: 'Correct Picks', value: analytics.correct, accent: false, color: 'text-green-400' },
              { label: 'Wrong Picks', value: analytics.wrong, accent: false, color: 'text-red-400' },
              { label: 'Accuracy', value: `${analytics.accuracy}%`, accent: true },
            ].map((card) => (
              <div
                key={card.label}
                className="bg-[#111111]/80 backdrop-blur-md rounded-2xl border border-white/5 p-4 md:p-6 flex flex-col items-center justify-center text-center shadow-lg shadow-black/40 hover:border-white/10 transition-colors"
              >
                <span className={`text-3xl md:text-4xl font-black ${card.accent ? 'text-ufcred-500' : card.color || 'text-white'}`}>
                  {card.value}
                </span>
                <span className="text-[10px] md:text-[11px] font-bold uppercase tracking-widest text-gray-500 mt-2">
                  {card.label}
                </span>
              </div>
            ))}
          </div>

          {/* ══════════════════════════════════════════════════════════════
               SECTION 2 — Insight Chips
              ═══════════════════════════════════════════════════════════ */}
          <div className="flex flex-wrap gap-3">
            <InsightChip label="Avg Confidence" value={`${analytics.avgConfidence}%`} />
            <InsightChip label="Avg (Correct)" value={`${analytics.avgConfidenceCorrect}%`} color="text-green-400" />
            <InsightChip label="Avg (Wrong)" value={`${analytics.avgConfidenceWrong}%`} color="text-red-400" />
            {analytics.highConfidenceAcc !== null && (
              <InsightChip label="High Conf (>70%) Acc" value={`${analytics.highConfidenceAcc}%`} color="text-amber-400" />
            )}
            {analytics.titleFightAcc !== null && (
              <InsightChip label="Title Fight Acc" value={`${analytics.titleFightAcc}%`} color="text-purple-400" />
            )}
          </div>

          {/* ══════════════════════════════════════════════════════════════
               SECTION 3 — Charts Grid
              ═══════════════════════════════════════════════════════════ */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">

            {/* Accuracy by Confidence Tier */}
            <div className="bg-[#111111]/80 backdrop-blur-md rounded-2xl border border-white/5 p-4 md:p-6 shadow-lg shadow-black/40">
              <h3 className="text-sm md:text-base font-black text-white uppercase tracking-wider mb-4">
                Accuracy by Confidence Tier
              </h3>
              <ResponsiveContainer width="100%" height={220}>
                <BarChart data={analytics.byConfidence} margin={{ top: 20, right: 20, bottom: 5, left: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
                  <XAxis
                    dataKey="tier"
                    tick={{ fill: '#6b7280', fontSize: 11, fontWeight: 700 }}
                    axisLine={{ stroke: 'rgba(255,255,255,0.1)' }}
                    tickLine={false}
                  />
                  <YAxis
                    domain={[0, 100]}
                    tick={{ fill: '#6b7280', fontSize: 11 }}
                    axisLine={{ stroke: 'rgba(255,255,255,0.1)' }}
                    tickLine={false}
                    tickFormatter={(v) => `${v}%`}
                  />
                  <Tooltip content={<TierTooltip />} cursor={{ fill: 'rgba(255,255,255,0.03)' }} />
                  <Bar dataKey="accuracy" fill="#d20a11" radius={[6, 6, 0, 0]} maxBarSize={80}>
                    <LabelList dataKey="accuracy" position="top" formatter={(v) => `${v}%`} style={{ fill: '#ffffff', fontSize: 12, fontWeight: 800 }} />
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>

            {/* Confidence Calibration */}
            <div className="bg-[#111111]/80 backdrop-blur-md rounded-2xl border border-white/5 p-4 md:p-6 shadow-lg shadow-black/40">
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-sm md:text-base font-black text-white uppercase tracking-wider">
                  Confidence Calibration
                </h3>
                <span className="text-[9px] md:text-[10px] font-bold uppercase tracking-widest text-gray-500 bg-white/5 px-2 py-1 rounded-full border border-white/10">
                  Predicted vs Actual
                </span>
              </div>
              <ResponsiveContainer width="100%" height={220}>
                <ComposedChart data={analytics.calibration.filter((d) => d.actual !== null)} margin={{ top: 10, right: 20, bottom: 5, left: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
                  <XAxis
                    dataKey="predicted"
                    tick={{ fill: '#6b7280', fontSize: 11, fontWeight: 700 }}
                    axisLine={{ stroke: 'rgba(255,255,255,0.1)' }}
                    tickLine={false}
                    tickFormatter={(v) => `${v}%`}
                    label={{ value: 'Model Confidence', position: 'bottom', fill: '#4b5563', fontSize: 10, fontWeight: 700, offset: -2 }}
                  />
                  <YAxis
                    domain={[0, 100]}
                    tick={{ fill: '#6b7280', fontSize: 11 }}
                    axisLine={{ stroke: 'rgba(255,255,255,0.1)' }}
                    tickLine={false}
                    tickFormatter={(v) => `${v}%`}
                    label={{ value: 'Actual Win %', angle: -90, position: 'insideLeft', fill: '#4b5563', fontSize: 10, fontWeight: 700 }}
                  />
                  <ReferenceLine
                    segment={[{ x: 50, y: 50 }, { x: 85, y: 85 }]}
                    stroke="rgba(255,255,255,0.15)"
                    strokeDasharray="6 4"
                    label={{ value: 'Perfect', position: 'end', fill: '#4b5563', fontSize: 9, fontWeight: 700 }}
                  />
                  <Tooltip content={<CalibrationTooltip />} cursor={false} />
                  <Area type="monotone" dataKey="actual" fill="rgba(210,10,17,0.1)" stroke="none" />
                  <Line
                    type="monotone"
                    dataKey="actual"
                    stroke="#d20a11"
                    strokeWidth={2.5}
                    dot={{ fill: '#d20a11', stroke: '#0a0a0a', strokeWidth: 2, r: 5 }}
                    activeDot={{ r: 7, fill: '#ff2a33', stroke: '#0a0a0a', strokeWidth: 2 }}
                  />
                </ComposedChart>
              </ResponsiveContainer>
            </div>

            {/* Confidence Distribution */}
            <div className="bg-[#111111]/80 backdrop-blur-md rounded-2xl border border-white/5 p-4 md:p-6 shadow-lg shadow-black/40 lg:col-span-2">
              <h3 className="text-sm md:text-base font-black text-white uppercase tracking-wider mb-4">
                Prediction Distribution by Confidence
              </h3>
              <ResponsiveContainer width="100%" height={200}>
                <BarChart data={analytics.distribution} margin={{ top: 15, right: 20, bottom: 5, left: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
                  <XAxis
                    dataKey="bucket"
                    tick={{ fill: '#6b7280', fontSize: 11, fontWeight: 700 }}
                    axisLine={{ stroke: 'rgba(255,255,255,0.1)' }}
                    tickLine={false}
                  />
                  <YAxis
                    tick={{ fill: '#6b7280', fontSize: 11 }}
                    axisLine={{ stroke: 'rgba(255,255,255,0.1)' }}
                    tickLine={false}
                    allowDecimals={false}
                  />
                  <Tooltip content={<DistributionTooltip />} cursor={{ fill: 'rgba(255,255,255,0.03)' }} />
                  <Bar dataKey="correct" stackId="a" fill="#22c55e" radius={[0, 0, 0, 0]} maxBarSize={60} name="Correct" />
                  <Bar dataKey="wrong" stackId="a" fill="#ef4444" radius={[6, 6, 0, 0]} maxBarSize={60} name="Wrong">
                    <LabelList
                      dataKey="count"
                      position="top"
                      style={{ fill: '#9ca3af', fontSize: 10, fontWeight: 800 }}
                    />
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
              {/* Stacked bar legend */}
              <div className="flex justify-center gap-6 mt-2">
                <span className="flex items-center gap-2 text-[10px] font-bold uppercase tracking-widest text-gray-500">
                  <span className="w-3 h-3 rounded-sm bg-green-500 inline-block"></span> Correct
                </span>
                <span className="flex items-center gap-2 text-[10px] font-bold uppercase tracking-widest text-gray-500">
                  <span className="w-3 h-3 rounded-sm bg-red-500 inline-block"></span> Wrong
                </span>
              </div>
            </div>
          </div>

          {/* ══════════════════════════════════════════════════════════════
               SECTION 4 — Per-Event Scorecards
              ═══════════════════════════════════════════════════════════ */}
          <div className="flex flex-col gap-10 mt-2">
            <h2 className="text-xl md:text-2xl font-black text-white uppercase tracking-wider">
              Event Breakdown
            </h2>

            {sortedEvents.map((event) => {
              const isCollapsed = collapsedEvents.has(event.eventName);
              const eventCorrect = event.fights.filter((f) => f.was_correct === true).length;
              const eventTotal = event.fights.length;
              const eventAcc = eventTotal > 0 ? (eventCorrect / eventTotal * 100) : 0;

              // Color-code: green >= 60%, amber 40-60%, red < 40%
              const accColor = eventAcc >= 60 ? 'text-green-400' : eventAcc >= 40 ? 'text-amber-400' : 'text-red-400';
              const accBg = eventAcc >= 60 ? 'bg-green-500/10 border-green-500/20' : eventAcc >= 40 ? 'bg-amber-500/10 border-amber-500/20' : 'bg-red-500/10 border-red-500/20';

              return (
                <div key={event.eventName} className="flex flex-col w-full">
                  {/* Event header */}
                  <button
                    onClick={() => toggleEvent(event.eventName)}
                    className="flex items-center gap-4 mb-4 px-2 w-full text-left group/header cursor-pointer focus:outline-none"
                  >
                    <span className="w-2 h-10 bg-ufcred-500 rounded-full inline-block shrink-0 shadow-[0_0_10px_rgba(210,10,17,0.5)]"></span>
                    <div className="flex flex-col flex-1 min-w-0">
                      <h2 className="text-xl md:text-2xl font-black text-white uppercase tracking-wider leading-tight truncate">
                        {event.eventName}
                      </h2>
                      <span className="text-[10px] md:text-[11px] font-bold uppercase tracking-widest text-gray-500 mt-0.5">
                        {formatEventDate(event.date)}
                      </span>
                    </div>
                    {/* Event scorecard badge */}
                    <div className={`shrink-0 flex items-center gap-2 px-3 py-1.5 rounded-full border ${accBg}`}>
                      <span className={`text-xs md:text-sm font-black ${accColor}`}>
                        {eventCorrect}/{eventTotal}
                      </span>
                      <span className={`text-[10px] md:text-[11px] font-black uppercase tracking-wide ${accColor}`}>
                        {eventAcc.toFixed(0)}%
                      </span>
                    </div>
                    {/* Collapse chevron */}
                    <div className="shrink-0 w-8 h-8 rounded-full bg-white/5 border border-white/10 flex items-center justify-center group-hover/header:bg-white/10 transition-colors">
                      <svg
                        xmlns="http://www.w3.org/2000/svg"
                        className={`h-4 w-4 text-gray-400 transition-transform duration-300 ${isCollapsed ? '-rotate-90' : ''}`}
                        fill="none"
                        viewBox="0 0 24 24"
                        stroke="currentColor"
                      >
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                      </svg>
                    </div>
                  </button>

                  {/* Fights list — animated collapse */}
                  <div className={`grid transition-all duration-300 ease-in-out ${isCollapsed ? 'grid-rows-[0fr] opacity-0' : 'grid-rows-[1fr] opacity-100'}`}>
                    <div className="overflow-hidden">
                      <div className="flex flex-col gap-3">
                        {event.fights.map((f) => (
                          <ResultRow key={f.prediction_id} fight={f} />
                        ))}
                      </div>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}

// ── Helper components ──────────────────────────────────────────────────

function InsightChip({ label, value, color = 'text-white' }) {
  return (
    <div className="flex items-center gap-2 bg-[#111111]/80 backdrop-blur-md rounded-full border border-white/5 px-4 py-2 shadow-lg shadow-black/40">
      <span className="text-[9px] md:text-[10px] font-bold uppercase tracking-widest text-gray-500">
        {label}
      </span>
      <span className={`text-sm md:text-base font-black ${color}`}>
        {value}
      </span>
    </div>
  );
}
