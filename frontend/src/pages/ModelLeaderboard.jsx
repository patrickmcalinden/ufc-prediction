import React, { useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, LabelList, CartesianGrid,
  RadarChart, Radar, PolarGrid, PolarAngleAxis, PolarRadiusAxis,
} from 'recharts';
import { api } from '../lib/api';
import { groupAndSortByEvent } from '../lib/utils';

export default function ModelLeaderboard() {
  const { data: results, isLoading, isError } = useQuery({
    queryKey: ['results', null],
    queryFn: () => api.getResults(),
    retry: 1,
  });

  // Scope to the last 2 graded events (matches Results page).
  const scopedResults = useMemo(() => {
    const events = groupAndSortByEvent(results, { chronological: true }).slice(0, 2);
    return events.flatMap((e) => e.fights);
  }, [results]);

  // Aggregate per-model stats from the scoped fights.
  const models = useMemo(() => {
    if (!scopedResults || scopedResults.length === 0) return [];
    const byModel = new Map();
    for (const r of scopedResults) {
      const v = r.model_version;
      if (!byModel.has(v)) {
        byModel.set(v, { model_version: v, graded: 0, correct: 0, confSum: 0, hcTotal: 0, hcCorrect: 0 });
      }
      const m = byModel.get(v);
      m.graded += 1;
      if (r.was_correct === true) m.correct += 1;
      m.confSum += r.win_probability;
      if (r.win_probability > 0.70) {
        m.hcTotal += 1;
        if (r.was_correct === true) m.hcCorrect += 1;
      }
    }
    return Array.from(byModel.values()).map((m) => ({
      model_version: m.model_version,
      total_predictions: m.graded,
      graded: m.graded,
      correct: m.correct,
      accuracy: m.graded > 0 ? Math.round((m.correct / m.graded) * 1000) / 10 : 0,
      avg_confidence: m.graded > 0 ? Math.round((m.confSum / m.graded) * 1000) / 10 : 0,
      high_conf_accuracy: m.hcTotal > 0 ? Math.round((m.hcCorrect / m.hcTotal) * 1000) / 10 : null,
    }));
  }, [scopedResults]);

  const sortedModels = useMemo(() => {
    if (!models) return [];
    return [...models].sort((a, b) => b.accuracy - a.accuracy);
  }, [models]);

  // Chart data for accuracy comparison
  const chartData = useMemo(() => {
    if (!models) return [];
    return models.map((m) => ({
      model: m.model_version.toUpperCase(),
      accuracy: m.accuracy,
      confidence: m.avg_confidence,
      highConf: m.high_conf_accuracy || 0,
      graded: m.graded,
    }));
  }, [models]);

  // Radar data for multi-dimensional comparison
  const radarData = useMemo(() => {
    if (!models || models.length === 0) return [];
    const maxGraded = Math.max(...models.map(m => m.graded), 1);
    return [
      { metric: 'Accuracy', ...Object.fromEntries(models.map(m => [m.model_version, m.accuracy])) },
      { metric: 'Confidence', ...Object.fromEntries(models.map(m => [m.model_version, m.avg_confidence])) },
      { metric: 'High Conf Acc', ...Object.fromEntries(models.map(m => [m.model_version, m.high_conf_accuracy || 0])) },
      { metric: 'Sample Size', ...Object.fromEntries(models.map(m => [m.model_version, (m.graded / maxGraded) * 100])) },
    ];
  }, [models]);

  const MODEL_COLORS = ['#d20a11', '#3b82f6', '#22c55e', '#f59e0b', '#a855f7', '#ec4899'];

  const CustomTooltip = ({ active, payload }) => {
    if (!active || !payload || !payload.length) return null;
    const d = payload[0].payload;
    return (
      <div className="bg-[#0a0a0a] border border-white/10 rounded-xl px-4 py-3 shadow-2xl text-xs">
        <p className="font-black text-white uppercase tracking-wide">{d.model}</p>
        <p className="text-gray-400 mt-1">Accuracy: {d.accuracy}%</p>
        <p className="text-gray-400">Avg Confidence: {d.confidence}%</p>
        <p className="text-gray-400">High Conf Acc: {d.highConf}%</p>
        <p className="text-gray-400">Graded Fights: {d.graded}</p>
      </div>
    );
  };

  return (
    <div className="flex flex-col gap-6 w-full animate-fade-in-up pb-20 mt-4">
      {/* Header */}
      <div className="mb-4">
        <h1 className="text-4xl bg-gradient-to-r from-white to-gray-400 bg-clip-text text-transparent md:text-5xl font-black tracking-tight mb-2 uppercase">
          Model Leaderboard
        </h1>
        <p className="text-gray-400 font-medium tracking-wide">
          Compare prediction model performance across the last 2 graded events.
        </p>
      </div>

      {isLoading ? (
        <div className="flex justify-center py-20">
          <div className="text-ufcred-500 font-bold tracking-widest animate-pulse border border-ufcred-500/20 bg-ufcred-500/5 px-8 py-4 rounded-full backdrop-blur-md">
            LOADING MODEL DATA...
          </div>
        </div>
      ) : isError ? (
        <div className="flex justify-center py-20">
          <div className="text-red-500 font-bold bg-red-500/10 border border-red-500/20 px-8 py-4 rounded-[2rem] text-center max-w-lg shadow-2xl backdrop-blur-md">
            <p className="tracking-widest uppercase mb-2">Model Data Unavailable</p>
            <p className="text-sm text-gray-400 font-medium">
              Unable to connect to the prediction backend engine.
            </p>
          </div>
        </div>
      ) : !models || models.length === 0 ? (
        <div className="bg-black/20 backdrop-blur-md p-8 rounded-[2rem] border border-white/5 py-20 flex flex-col items-center gap-4 shadow-2xl">
          <div className="w-16 h-16 rounded-full bg-white/5 flex items-center justify-center mb-4">
            <svg xmlns="http://www.w3.org/2000/svg" className="h-8 w-8 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
            </svg>
          </div>
          <p className="text-white font-black tracking-widest text-center uppercase text-xl">No Models Found</p>
          <p className="text-gray-400 font-medium text-center max-w-lg">
            Run the prediction pipeline to generate model predictions first.
          </p>
        </div>
      ) : (
        <div className="flex flex-col gap-8">

          {/* ═══ LEADERBOARD TABLE ═══ */}
          <div className="bg-[#111111]/80 backdrop-blur-md rounded-2xl border border-white/5 overflow-hidden shadow-lg shadow-black/40">
            <div className="px-6 py-4 border-b border-white/5">
              <h3 className="text-sm md:text-base font-black text-white uppercase tracking-wider">
                Rankings
              </h3>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr className="border-b border-white/5">
                    <th className="px-6 py-3 text-left text-[10px] font-bold uppercase tracking-widest text-gray-500">Rank</th>
                    <th className="px-6 py-3 text-left text-[10px] font-bold uppercase tracking-widest text-gray-500">Model</th>
                    <th className="px-6 py-3 text-right text-[10px] font-bold uppercase tracking-widest text-gray-500">Accuracy</th>
                    <th className="px-6 py-3 text-right text-[10px] font-bold uppercase tracking-widest text-gray-500">Correct</th>
                    <th className="px-6 py-3 text-right text-[10px] font-bold uppercase tracking-widest text-gray-500">Graded</th>
                    <th className="px-6 py-3 text-right text-[10px] font-bold uppercase tracking-widest text-gray-500">Total</th>
                    <th className="px-6 py-3 text-right text-[10px] font-bold uppercase tracking-widest text-gray-500">Avg Conf</th>
                    <th className="px-6 py-3 text-right text-[10px] font-bold uppercase tracking-widest text-gray-500">High Conf Acc</th>
                  </tr>
                </thead>
                <tbody>
                  {sortedModels.map((m, idx) => {
                    const isTop = idx === 0 && sortedModels.length > 1;
                    const accColor = m.accuracy >= 60 ? 'text-green-400' : m.accuracy >= 50 ? 'text-amber-400' : 'text-red-400';
                    return (
                      <tr
                        key={m.model_version}
                        className={`border-b border-white/5 hover:bg-white/[0.02] transition-colors ${isTop ? 'bg-ufcred-500/5' : ''}`}
                      >
                        <td className="px-6 py-4">
                          <div className="flex items-center gap-2">
                            {isTop && (
                              <span className="text-amber-400 text-sm">👑</span>
                            )}
                            <span className="text-white font-black text-lg">{idx + 1}</span>
                          </div>
                        </td>
                        <td className="px-6 py-4">
                          <span className={`text-sm font-black uppercase tracking-widest px-3 py-1 rounded-full border ${isTop ? 'text-ufcred-500 border-ufcred-500/30 bg-ufcred-500/10' : 'text-white border-white/10 bg-white/5'}`}>
                            {m.model_version}
                          </span>
                        </td>
                        <td className={`px-6 py-4 text-right font-black text-lg ${accColor}`}>
                          {m.accuracy}%
                        </td>
                        <td className="px-6 py-4 text-right text-green-400 font-bold">
                          {m.correct}
                        </td>
                        <td className="px-6 py-4 text-right text-gray-400 font-medium">
                          {m.graded}
                        </td>
                        <td className="px-6 py-4 text-right text-gray-500 font-medium">
                          {m.total_predictions}
                        </td>
                        <td className="px-6 py-4 text-right text-gray-400 font-medium">
                          {m.avg_confidence}%
                        </td>
                        <td className="px-6 py-4 text-right font-medium">
                          {m.high_conf_accuracy !== null ? (
                            <span className={m.high_conf_accuracy >= 70 ? 'text-green-400' : 'text-amber-400'}>
                              {m.high_conf_accuracy}%
                            </span>
                          ) : (
                            <span className="text-gray-600">—</span>
                          )}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>

          {/* ═══ CHARTS GRID ═══ */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">

            {/* Accuracy Comparison Bar Chart */}
            <div className="bg-[#111111]/80 backdrop-blur-md rounded-2xl border border-white/5 p-4 md:p-6 shadow-lg shadow-black/40">
              <h3 className="text-sm md:text-base font-black text-white uppercase tracking-wider mb-4">
                Accuracy Comparison
              </h3>
              <ResponsiveContainer width="100%" height={260}>
                <BarChart data={chartData} margin={{ top: 20, right: 20, bottom: 5, left: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
                  <XAxis
                    dataKey="model"
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
                  <Tooltip content={<CustomTooltip />} cursor={{ fill: 'rgba(255,255,255,0.03)' }} />
                  <Bar dataKey="accuracy" fill="#d20a11" radius={[8, 8, 0, 0]} maxBarSize={80}>
                    <LabelList dataKey="accuracy" position="top" formatter={(v) => `${v}%`} style={{ fill: '#ffffff', fontSize: 13, fontWeight: 800 }} />
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>

            {/* Confidence vs Accuracy */}
            <div className="bg-[#111111]/80 backdrop-blur-md rounded-2xl border border-white/5 p-4 md:p-6 shadow-lg shadow-black/40">
              <h3 className="text-sm md:text-base font-black text-white uppercase tracking-wider mb-4">
                Confidence vs Accuracy
              </h3>
              <ResponsiveContainer width="100%" height={260}>
                <BarChart data={chartData} margin={{ top: 20, right: 20, bottom: 5, left: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
                  <XAxis
                    dataKey="model"
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
                  <Tooltip cursor={{ fill: 'rgba(255,255,255,0.03)' }} contentStyle={{ background: '#0a0a0a', border: '1px solid rgba(255,255,255,0.1)', borderRadius: '12px' }} />
                  <Bar dataKey="accuracy" fill="#d20a11" radius={[6, 6, 0, 0]} maxBarSize={35} name="Accuracy" />
                  <Bar dataKey="confidence" fill="#3b82f6" radius={[6, 6, 0, 0]} maxBarSize={35} name="Avg Confidence" />
                  <Bar dataKey="highConf" fill="#22c55e" radius={[6, 6, 0, 0]} maxBarSize={35} name="High Conf Acc" />
                </BarChart>
              </ResponsiveContainer>
              <div className="flex justify-center gap-6 mt-2">
                <span className="flex items-center gap-2 text-[10px] font-bold uppercase tracking-widest text-gray-500">
                  <span className="w-3 h-3 rounded-sm bg-ufcred-500 inline-block"></span> Accuracy
                </span>
                <span className="flex items-center gap-2 text-[10px] font-bold uppercase tracking-widest text-gray-500">
                  <span className="w-3 h-3 rounded-sm bg-blue-500 inline-block"></span> Avg Conf
                </span>
                <span className="flex items-center gap-2 text-[10px] font-bold uppercase tracking-widest text-gray-500">
                  <span className="w-3 h-3 rounded-sm bg-green-500 inline-block"></span> High Conf
                </span>
              </div>
            </div>
          </div>

          {/* ═══ PER-MODEL DETAILED CARDS ═══ */}
          <h2 className="text-xl md:text-2xl font-black text-white uppercase tracking-wider mt-4">
            Detailed Breakdown
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {sortedModels.map((m, idx) => {
              const accColor = m.accuracy >= 60 ? 'text-green-400' : m.accuracy >= 50 ? 'text-amber-400' : 'text-red-400';
              const borderColor = idx === 0 && sortedModels.length > 1 ? 'border-ufcred-500/30 hover:border-ufcred-500/50' : 'border-white/5 hover:border-white/10';
              const wrongCount = m.graded - m.correct;
              const correctPct = m.graded > 0 ? Math.round((m.correct / m.graded) * 100) : 0;

              return (
                <div key={m.model_version} className={`bg-[#111111]/80 backdrop-blur-md rounded-2xl border ${borderColor} p-6 shadow-lg shadow-black/40 transition-colors flex flex-col gap-4`}>
                  {/* Model badge */}
                  <div className="flex items-center justify-between">
                    <span className="text-lg font-black uppercase tracking-widest text-white">
                      {m.model_version}
                    </span>
                    {idx === 0 && sortedModels.length > 1 && (
                      <span className="px-2 py-0.5 rounded-md bg-ufcred-500/20 text-ufcred-500 text-[9px] font-black tracking-widest uppercase">
                        Best
                      </span>
                    )}
                  </div>

                  {/* Big accuracy number */}
                  <div className="text-center py-4">
                    <span className={`text-5xl font-black ${accColor}`}>{m.accuracy}%</span>
                    <p className="text-[10px] font-bold uppercase tracking-widest text-gray-500 mt-2">Accuracy</p>
                  </div>

                  {/* Win/Loss bar */}
                  <div className="w-full h-2 bg-white/5 rounded-full overflow-hidden">
                    <div
                      className="h-full bg-gradient-to-r from-green-500 to-green-400 rounded-full transition-all duration-500"
                      style={{ width: `${correctPct}%` }}
                    />
                  </div>

                  {/* Stats grid */}
                  <div className="grid grid-cols-2 gap-3">
                    <StatMini label="Correct" value={m.correct} color="text-green-400" />
                    <StatMini label="Wrong" value={wrongCount} color="text-red-400" />
                    <StatMini label="Avg Confidence" value={`${m.avg_confidence}%`} />
                    <StatMini label="High Conf Acc" value={m.high_conf_accuracy !== null ? `${m.high_conf_accuracy}%` : '—'} />
                    <StatMini label="Total Predictions" value={m.total_predictions} />
                    <StatMini label="Graded" value={m.graded} />
                  </div>

                  {/* Link to results filtered by this model */}
                  <Link
                    to={`/results`}
                    className="mt-2 flex items-center justify-center gap-2 px-4 py-2.5 rounded-xl bg-white/5 border border-white/10 hover:bg-white/10 transition-colors text-[10px] font-bold uppercase tracking-widest text-gray-400 hover:text-white"
                  >
                    View Detailed Results →
                  </Link>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}

function StatMini({ label, value, color = 'text-white' }) {
  return (
    <div className="bg-white/[0.02] rounded-xl px-3 py-2.5 border border-white/5">
      <span className={`text-base font-black ${color}`}>{value}</span>
      <p className="text-[8px] font-bold uppercase tracking-widest text-gray-500 mt-0.5">{label}</p>
    </div>
  );
}
