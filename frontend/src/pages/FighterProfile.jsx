import React, { useState, useRef, useEffect } from 'react';
import { useParams, Link, useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { api } from '../lib/api';
import EloChart from '../components/EloChart';

const ESPN_IMG = (espnId) =>
  `https://a.espncdn.com/i/headshots/mma/players/full/${espnId}.png`;

function FighterImage({ espnId, name, className = '' }) {
  const [errored, setErrored] = useState(false);

  if (!espnId || errored) {
    const initials = name
      ? name.split(' ').map((w) => w[0]).slice(0, 2).join('')
      : '??';
    return (
      <div className={`flex items-end justify-center ${className}`}>
        <span className="text-7xl font-black text-white/10 select-none">{initials}</span>
      </div>
    );
  }

  return (
    <img
      src={ESPN_IMG(espnId)}
      alt={name}
      onError={() => setErrored(true)}
      className={`object-cover object-top select-none ${className}`}
    />
  );
}

function RecordBar({ wins, losses, draws }) {
  const total = (wins || 0) + (losses || 0) + (draws || 0);
  const winPct = total > 0 ? ((wins || 0) / total) * 100 : 0;
  const lossPct = total > 0 ? ((losses || 0) / total) * 100 : 0;
  const drawPct = total > 0 ? ((draws || 0) / total) * 100 : 0;

  return (
    <div className="flex flex-col gap-2 w-full">
      <div className="flex gap-1 h-2 rounded-full overflow-hidden w-full">
        <div style={{ width: `${winPct}%` }} className="bg-green-500 transition-all" />
        <div style={{ width: `${lossPct}%` }} className="bg-red-500 transition-all" />
        {drawPct > 0 && <div style={{ width: `${drawPct}%` }} className="bg-yellow-500 transition-all" />}
      </div>
      <div className="flex gap-6 text-xs font-bold uppercase tracking-widest">
        <span className="text-green-400">{wins || 0} W</span>
        <span className="text-red-400">{losses || 0} L</span>
        {(draws || 0) > 0 && <span className="text-yellow-400">{draws} D</span>}
      </div>
    </div>
  );
}

function StatCard({ label, value }) {
  return (
    <div className="bg-ufcslate-900/60 rounded-xl p-4 border border-white/5 flex flex-col gap-1">
      <span className="text-gray-400 font-bold uppercase tracking-widest text-xs">{label}</span>
      <span className="text-2xl font-black text-white">{value ?? '--'}</span>
    </div>
  );
}

const formatName = (name) => name ? name.replace(/([a-z])([A-Z])/g, '$1 $2') : name;

function FightHistoryTable({ fighterId, fights, isLoading, error }) {
  if (isLoading) return <div className="text-gray-400 text-sm animate-pulse py-4">Loading fight history...</div>;
  if (error) return <div className="text-red-500 text-sm py-4">Failed to load fight history.</div>;
  if (!fights || fights.length === 0) return <div className="text-gray-500 text-sm py-4">No fight history on record.</div>;

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="text-gray-400 font-bold uppercase tracking-widest text-xs border-b border-white/10">
            <th className="text-left pb-3 pr-4">Result</th>
            <th className="text-left pb-3 pr-4">Opponent</th>
            <th className="text-left pb-3 pr-4 hidden md:table-cell">Method</th>
            <th className="text-left pb-3 pr-4 hidden sm:table-cell">Rd</th>
            <th className="text-left pb-3 pr-4 hidden sm:table-cell">Time</th>
            <th className="text-left pb-3 hidden md:table-cell">Event</th>
            <th className="text-right pb-3">Date</th>
          </tr>
        </thead>
        <tbody>
          {fights.map((fight) => {
            const resultColor =
              fight.result === 'W'
                ? 'text-green-400'
                : fight.result === 'L'
                ? 'text-red-400'
                : 'text-yellow-400';
            return (
              <tr key={fight.fight_id} className="border-b border-white/5 hover:bg-white/5 transition-colors">
                <td className={`py-3 pr-4 font-black text-base ${resultColor}`}>
                  {fight.result || 'NC'}
                  {fight.is_title_fight && (
                    <span className="ml-1 text-yellow-400 text-xs align-top">🏆</span>
                  )}
                </td>
                <td className="py-3 pr-4 font-semibold">
                  {fight.opponent_id ? (
                    <Link
                      to={`/fighters/${fight.opponent_id}`}
                      className="hover:text-ufcred-400 transition-colors"
                    >
                      {formatName(fight.opponent_name)}
                    </Link>
                  ) : (
                    formatName(fight.opponent_name)
                  )}
                </td>
                <td className="py-3 pr-4 text-gray-300 hidden md:table-cell">{fight.method || '--'}</td>
                <td className="py-3 pr-4 text-gray-300 hidden sm:table-cell">{fight.round ?? '--'}</td>
                <td className="py-3 pr-4 text-gray-300 hidden sm:table-cell">{fight.time || '--'}</td>
                <td className="py-3 text-gray-400 text-xs hidden md:table-cell truncate max-w-[200px]">{fight.event_name || '--'}</td>
                <td className="py-3 text-gray-400 text-xs text-right whitespace-nowrap">
                  {fight.fight_date || '--'}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function FighterSearch() {
  const [query, setQuery] = useState('');
  const [open, setOpen] = useState(false);
  const navigate = useNavigate();
  const inputRef = useRef(null);
  const containerRef = useRef(null);

  const { data: fighters } = useQuery({
    queryKey: ['fighters', false],
    queryFn: () => api.getFighters(0, 300, false),
  });

  const results = query.trim().length > 1
    ? fighters?.filter((f) => f.name.toLowerCase().includes(query.toLowerCase())).slice(0, 8)
    : [];

  useEffect(() => {
    function handleClickOutside(e) {
      if (containerRef.current && !containerRef.current.contains(e.target)) {
        setOpen(false);
      }
    }
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  function handleSelect(fighter) {
    setQuery('');
    setOpen(false);
    navigate(`/fighters/${fighter.fighter_id}`);
  }

  return (
    <div ref={containerRef} className="relative w-full md:w-72">
      <span className="absolute inset-y-0 left-4 flex items-center pointer-events-none text-gray-500 z-10">
        <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M21 21l-4.35-4.35M17 11A6 6 0 1 1 5 11a6 6 0 0 1 12 0z" />
        </svg>
      </span>
      <input
        ref={inputRef}
        type="text"
        value={query}
        onChange={(e) => { setQuery(e.target.value); setOpen(true); }}
        onFocus={() => setOpen(true)}
        placeholder="SEARCH FIGHTERS..."
        className="w-full bg-ufcslate-800 border border-white/5 rounded-full pl-10 pr-4 py-2.5 text-xs font-black uppercase tracking-widest text-white placeholder-gray-600 focus:outline-none focus:border-ufcred-500 focus:ring-1 focus:ring-ufcred-500 transition-colors shadow-inner"
      />
      {open && results && results.length > 0 && (
        <ul className="absolute top-full mt-2 left-0 right-0 bg-ufcslate-800 border border-white/10 rounded-2xl overflow-hidden z-50 shadow-xl">
          {results.map((f) => (
            <li key={f.fighter_id}>
              <button
                onMouseDown={() => handleSelect(f)}
                className="w-full text-left px-5 py-3 hover:bg-ufcred-600/20 transition-colors flex justify-between items-center group"
              >
                <span className="text-xs font-black uppercase tracking-widest text-white group-hover:text-ufcred-400 transition-colors">
                  {formatName(f.name)}
                </span>
                <span className="text-xs font-bold text-gray-500 uppercase tracking-widest">
                  {f.weight_class || 'N/A'}
                </span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

export default function FighterProfile() {
  const { id } = useParams();

  const { data: fighter, isLoading, error } = useQuery({
    queryKey: ['fighter', id],
    queryFn: () => api.getFighter(id),
  });

  const { data: fights, isLoading: fightsLoading, error: fightsError } = useQuery({
    queryKey: ['fighter-fights', id],
    queryFn: () => api.getFighterFights(id),
    enabled: !!id,
  });

  if (isLoading) return <div className="text-gray-400 text-center py-20 font-bold tracking-widest animate-pulse">EXTRACTING METRICS...</div>;
  if (error || !fighter) return <div className="text-red-500 font-bold text-center">Failed to triangulate fighter endpoint.</div>;

  const elos = fighter.elo_ratings || [];
  const latestElo = elos.length > 0 ? elos[elos.length - 1] : null;

  // Derived stats from fight history
  const totalFights = fights?.length || 0;
  const winsKO = fights?.filter((f) => f.result === 'W' && f.method?.toLowerCase().includes('ko')).length || 0;
  const winsSub = fights?.filter((f) => f.result === 'W' && f.method?.toLowerCase().includes('sub')).length || 0;
  const winsDec = fights?.filter((f) => f.result === 'W' && f.method?.toLowerCase().includes('dec')).length || 0;
  const finishRate = fighter.record_wins > 0
    ? Math.round(((winsKO + winsSub) / fighter.record_wins) * 100)
    : 0;

  return (
    <div className="flex flex-col gap-8 animate-fade-in-up pb-20 mt-4">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <Link to="/fighters" className="text-gray-400 hover:text-white text-sm font-bold tracking-widest uppercase inline-flex items-center gap-2 transition-colors">
          &larr; Back to Scope
        </Link>
        <FighterSearch />
      </div>

      {/* Hero Panel */}
      <div className="glass-panel rounded-[2rem] relative overflow-hidden border-t-ufcred-600 border-t-4">
        <div className="relative flex flex-col sm:flex-row gap-0 items-stretch min-h-[220px]">

          {/* Left: Name + Record */}
          <div className="flex flex-col justify-center gap-3 flex-1 min-w-0 p-8 md:p-14 z-10">
            {fighter.nickname && (
              <span className="text-ufcred-500 font-black italic tracking-widest uppercase text-sm">
                "{fighter.nickname}"
              </span>
            )}
            <h1 className="text-4xl md:text-6xl font-black tracking-tighter uppercase leading-none break-words">
              {formatName(fighter.name)}
            </h1>
            <div className="flex flex-wrap gap-2 mt-1 font-semibold text-gray-400 uppercase tracking-widest text-xs">
              <span className="bg-ufcslate-900 px-3 py-1.5 rounded-full border border-white/10">
                {fighter.weight_class || 'Catchweight'}
              </span>
              <span className="bg-ufcslate-900 px-3 py-1.5 rounded-full border border-white/10">
                {fighter.stance || 'Switch'}
              </span>
              {fighter.is_active && (
                <span className="bg-green-900/50 text-green-400 px-3 py-1.5 rounded-full border border-green-500/20">
                  Active
                </span>
              )}
            </div>
            {/* Win/Loss Bar — stays with name */}
            <div className="mt-2 max-w-xs">
              <RecordBar
                wins={fighter.record_wins}
                losses={fighter.record_losses}
                draws={fighter.record_draws}
              />
            </div>
          </div>

          {/* Right: Fighter image behind Algorithm Rating */}
          <div className="relative flex-shrink-0 w-full sm:w-64 md:w-80 flex items-end justify-center overflow-hidden">
            {/* Fighter image — bottom-anchored, fading into bg */}
            <FighterImage
              espnId={fighter.espn_id}
              name={fighter.name}
              className="absolute bottom-0 left-1/2 -translate-x-1/2 h-full w-auto max-w-none object-bottom opacity-80"
            />
            {/* Gradient fade from left */}
            <div className="absolute inset-y-0 left-0 w-20 bg-gradient-to-r from-[#1a1a1a] to-transparent z-10 pointer-events-none" />
            {/* Gradient fade from bottom */}
            <div className="absolute bottom-0 left-0 right-0 h-16 bg-gradient-to-t from-[#1a1a1a]/60 to-transparent z-10 pointer-events-none" />
            {/* Algorithm Rating — overlaid on top of image */}
            <div className="relative z-20 w-full p-6 md:p-8 flex flex-col items-end justify-end h-full">
              <span className="text-gray-400 font-bold uppercase tracking-widest text-xs mb-1">Algorithm Rating</span>
              <span className="text-6xl md:text-7xl font-black text-white leading-none drop-shadow-lg">
                {latestElo ? latestElo.elo_modified.toFixed(1) : 'UR'}
              </span>
            </div>
          </div>

        </div>
      </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-4">
        <StatCard label="KO / TKO" value={winsKO} />
        <StatCard label="Submission" value={winsSub} />
        <StatCard label="Decision" value={winsDec} />
        <StatCard label="Finish Rate" value={`${finishRate}%`} />
        <StatCard label="Total Fights" value={totalFights} />
      </div>

      {/* Elo Chart + Physical Metrics */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 glass-panel p-8 rounded-[2rem] flex flex-col gap-6 border border-white/5">
          <h2 className="text-2xl font-black tracking-tight uppercase">Temporal Evaluation</h2>
          <EloChart data={elos} />
        </div>

        <div className="glass-panel p-8 rounded-[2rem] flex flex-col gap-6 border border-white/5">
          <h2 className="text-2xl font-black tracking-tight uppercase">Physical Metrics</h2>
          <div className="flex flex-col gap-5 mt-2">
            <div className="flex justify-between border-b border-white/5 pb-4">
              <span className="text-gray-400 font-bold uppercase text-sm w-1/2">Height</span>
              <span className="font-bold text-lg w-1/2 text-right">
                {fighter.height_cm ? `${fighter.height_cm} cm` : '--'}
              </span>
            </div>
            <div className="flex justify-between border-b border-white/5 pb-4">
              <span className="text-gray-400 font-bold uppercase text-sm w-1/2">Reach</span>
              <span className="font-bold text-lg w-1/2 text-right">
                {fighter.reach_cm ? `${fighter.reach_cm} cm` : '--'}
              </span>
            </div>
            <div className="flex justify-between border-b border-white/5 pb-4">
              <span className="text-gray-400 font-bold uppercase text-sm w-1/2">Nationality</span>
              <span className="font-bold text-lg w-1/2 text-right truncate pl-4" title={fighter.nationality}>
                {fighter.nationality || '--'}
              </span>
            </div>
            <div className="flex justify-between pb-2">
              <span className="text-gray-400 font-bold uppercase text-sm w-1/2">D.O.B</span>
              <span className="font-bold text-lg w-1/2 text-right">{fighter.date_of_birth || '--'}</span>
            </div>
          </div>
        </div>
      </div>

      {/* Fight History */}
      <div className="glass-panel p-8 rounded-[2rem] flex flex-col gap-6 border border-white/5">
        <div className="flex items-center justify-between">
          <h2 className="text-2xl font-black tracking-tight uppercase">Fight History</h2>
          {totalFights > 0 && (
            <span className="text-gray-400 font-bold text-sm uppercase tracking-widest">
              {totalFights} fights
            </span>
          )}
        </div>
        <FightHistoryTable
          fighterId={id}
          fights={fights}
          isLoading={fightsLoading}
          error={fightsError}
        />
      </div>
    </div>
  );
}
