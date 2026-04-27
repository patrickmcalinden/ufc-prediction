import React, { useMemo } from 'react';

function formatName(name) {
  if (!name) return name;
  if (/\s/.test(name)) return name;
  return name.replace(/([a-z])([A-Z])/g, '$1 $2');
}
import { useQuery } from '@tanstack/react-query';
import {
  LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, ReferenceLine, CartesianGrid,
} from 'recharts';
import { api } from '../lib/api';

// ─── Stat Card ────────────────────────────────────────────────────────────────
function StatCard({ label, value, sub, valueClass = 'text-white' }) {
  return (
    <div className="glass-panel rounded-2xl p-5 flex flex-col gap-1 border border-white/5">
      <span className="text-xs font-black tracking-widest uppercase text-gray-500">{label}</span>
      <span className={`text-3xl font-black tracking-tight ${valueClass}`}>{value}</span>
      {sub && <span className="text-xs text-gray-500 font-medium">{sub}</span>}
    </div>
  );
}

// ─── Custom Tooltip ───────────────────────────────────────────────────────────
function PnLTooltip({ active, payload }) {
  if (!active || !payload?.length) return null;
  const val = payload[0].value;
  const event = payload[0].payload.fullEvent;
  const color = val >= 0 ? '#22c55e' : '#ef4444';
  return (
    <div className="bg-ufcslate-900 border border-white/10 rounded-xl px-4 py-3 text-sm shadow-xl">
      {event && <p className="text-gray-400 text-xs mb-1">{event}</p>}
      <p className="font-black" style={{ color }}>
        {val >= 0 ? `+$${val.toFixed(2)}` : `-$${Math.abs(val).toFixed(2)}`}
      </p>
    </div>
  );
}

// ─── Dashboard ────────────────────────────────────────────────────────────────
function BetDashboard({ bets }) {
  const settled = useMemo(
    () => bets.filter((b) => b.result === 'WIN' || b.result === 'LOSS'),
    [bets]
  );

  const wins = settled.filter((b) => b.result === 'WIN').length;
  const winRate = settled.length > 0 ? (wins / settled.length) * 100 : null;

  const totalProfit = settled.reduce((s, b) => s + (Number(b.profit_usd) || 0), 0);
  const totalStaked = settled.reduce((s, b) => s + (Number(b.stake_usd) || 0), 0);
  const roi = totalStaked > 0 ? (totalProfit / totalStaked) * 100 : null;

  // Cumulative P&L series — oldest left, newest right, one X label per event group
  const chartData = useMemo(() => {
    const sorted = [...settled].sort((a, b) => a.bet_id - b.bet_id);
    // Group bets by event, preserving order
    const groups = [];
    sorted.forEach((bet) => {
      const eventLabel = bet.event_name || `Bet #${bet.bet_id}`;
      if (!groups.length || groups[groups.length - 1].event !== eventLabel) {
        groups.push({ event: eventLabel, bets: [bet] });
      } else {
        groups[groups.length - 1].bets.push(bet);
      }
    });
    // One data point per event — cumulative P&L at end of that event
    let running = 0;
    return groups.map((group) => {
      group.bets.forEach((bet) => { running += Number(bet.profit_usd) || 0; });
      return { name: group.event, pnl: parseFloat(running.toFixed(2)), fullEvent: group.event };
    });
  }, [settled]);

  const pnlColor = totalProfit >= 0 ? '#22c55e' : '#ef4444';
  const winRateColor = winRate === null ? 'text-gray-500' : winRate >= 55 ? 'text-green-400' : winRate >= 45 ? 'text-yellow-400' : 'text-red-400';

  return (
    <div className="flex flex-col gap-6">
      {/* Stat Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <StatCard
          label="Win Rate"
          value={winRate !== null ? `${winRate.toFixed(1)}%` : '—'}
          sub={settled.length > 0 ? `${wins}W / ${settled.length - wins}L` : 'No settled bets'}
          valueClass={winRateColor}
        />
        <StatCard
          label="Total P&L"
          value={
            settled.length > 0
              ? `${totalProfit >= 0 ? '+' : ''}$${totalProfit.toFixed(2)}`
              : '—'
          }
          sub={totalStaked > 0 ? `$${totalStaked.toFixed(2)} staked` : undefined}
          valueClass={totalProfit > 0 ? 'text-green-400' : totalProfit < 0 ? 'text-red-400' : 'text-white'}
        />
        <StatCard
          label="ROI"
          value={roi !== null ? `${roi >= 0 ? '+' : ''}${roi.toFixed(1)}%` : '—'}
          sub="return on staked"
          valueClass={roi > 0 ? 'text-green-400' : roi < 0 ? 'text-red-400' : 'text-white'}
        />
        <StatCard
          label="Total Bets"
          value={bets.length}
          sub={`${settled.length} settled · ${bets.length - settled.length} pending`}
        />
      </div>

      {/* P&L Line Chart */}
      {chartData.length > 1 && (
        <div className="glass-panel rounded-2xl border border-white/5 p-6">
          <p className="text-xs font-black tracking-widest uppercase text-gray-500 mb-6">
            Cumulative P&amp;L
          </p>
          <ResponsiveContainer width="100%" height={220}>
            <LineChart data={chartData} margin={{ top: 4, right: 8, left: 0, bottom: 4 }}>
              <CartesianGrid stroke="rgba(255,255,255,0.04)" vertical={false} />
              <XAxis
                dataKey="name"
                tick={{ fill: '#6b7280', fontSize: 10, fontWeight: 700 }}
                axisLine={false}
                tickLine={false}
                interval={0}
              />
              <YAxis
                tick={{ fill: '#6b7280', fontSize: 10, fontWeight: 700 }}
                axisLine={false}
                tickLine={false}
                tickFormatter={(v) => `$${v}`}
                width={52}
              />
              <Tooltip content={<PnLTooltip />} />
              <ReferenceLine y={0} stroke="rgba(255,255,255,0.1)" strokeDasharray="4 4" />
              <Line
                type="monotone"
                dataKey="pnl"
                stroke={pnlColor}
                strokeWidth={2.5}
                dot={false}
                activeDot={{ r: 4, fill: pnlColor, strokeWidth: 0 }}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}

      {chartData.length === 1 && (
        <div className="glass-panel rounded-2xl border border-white/5 p-6 text-center text-gray-500 text-xs font-bold tracking-widest uppercase">
          Chart available after 2+ settled bets
        </div>
      )}
    </div>
  );
}

// ─── Page ─────────────────────────────────────────────────────────────────────
export default function BetTracker() {
  const { data: bets, isLoading } = useQuery({
    queryKey: ['bets'],
    queryFn: api.getBets,
    refetchOnWindowFocus: true,
    staleTime: 0,
  });

  return (
    <div className="flex flex-col gap-6 w-full animate-fade-in-up pb-20 mt-4">
      <div className="flex justify-between items-end mb-2">
        <div>
          <h1 className="text-4xl md:text-5xl font-black tracking-tight mb-2 uppercase">ROI Analytics</h1>
          <p className="text-gray-400 font-medium tracking-wide">Financial deployment tracker and dynamic wager outcomes.</p>
        </div>
      </div>

      {isLoading ? (
        <div className="text-gray-400 font-bold tracking-widest animate-pulse mt-4">FETCHING ALGORITHMIC LEDGER...</div>
      ) : (
        <>
          {/* Dashboard sits above the table */}
          {bets && bets.length > 0 && <BetDashboard bets={bets} />}

          {/* Bets Table */}
          <div className="glass-panel rounded-3xl overflow-hidden border border-white/5 mt-2">
            <table className="w-full text-left text-sm text-gray-400">
              <thead className="text-xs uppercase bg-ufcslate-800/80 text-gray-300 font-black tracking-widest">
                <tr>
                  <th scope="col" className="px-6 py-6">Fighter</th>
                  <th scope="col" className="px-6 py-6">Event</th>
                  <th scope="col" className="px-6 py-6">Odds</th>
                  <th scope="col" className="px-6 py-6">Stake</th>
                  <th scope="col" className="px-6 py-6 border-l border-white/5">Profit</th>
                  <th scope="col" className="px-6 py-6 border-l border-white/5 text-center">Status</th>
                </tr>
              </thead>
              <tbody>
                {(!bets || bets.length === 0) && (
                  <tr className="border-t border-white/5">
                    <td colSpan="6" className="px-6 py-10 text-center font-bold tracking-widest uppercase text-gray-500">
                      No active automated trades recorded.
                    </td>
                  </tr>
                )}
                {bets?.map((bet) => (
                  <tr key={bet.bet_id} className="border-t border-white/5 hover:bg-white/5 transition-colors font-medium">
                    <td className="px-6 py-5">
                      <span className="text-white font-black tracking-wide">
                        {formatName(bet.fighter_backed_name) || `#${bet.fighter_backed_id}`}
                      </span>
                    </td>
                    <td className="px-6 py-5 text-gray-400 text-xs uppercase tracking-widest">
                      {bet.event_name || `Fight #${bet.fight_id}`}
                    </td>
                    <td className="px-6 py-5 text-gray-300">{bet.odds}</td>
                    <td className="px-6 py-5">${Number(bet.stake_usd).toFixed(2)}</td>
                    <td className={`px-6 py-5 border-l border-white/5 font-black tracking-wide ${
                      bet.profit_usd > 0 ? 'text-green-500' : bet.profit_usd < 0 ? 'text-red-500' : 'text-gray-500'
                    }`}>
                      {bet.profit_usd != null
                        ? bet.profit_usd > 0
                          ? `+$${Number(bet.profit_usd).toFixed(2)}`
                          : `-$${Math.abs(Number(bet.profit_usd)).toFixed(2)}`
                        : 'PENDING'}
                    </td>
                    <td className="px-6 py-5 border-l border-white/5 text-center">
                      <span className={`px-4 py-2 rounded-full text-xs font-bold tracking-wider ${
                        bet.result === 'WIN'
                          ? 'bg-green-500/10 text-green-500'
                          : bet.result === 'LOSS'
                          ? 'bg-red-500/10 text-red-500'
                          : 'bg-gray-500/10 text-gray-500'
                      }`}>
                        {bet.result || 'PROCESSING'}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  );
}
