import React, { useState, useRef, useEffect } from 'react';
import { useQuery } from '@tanstack/react-query';
import { api } from '../lib/api';
import { Link, useNavigate } from 'react-router-dom';

const formatName = (name) => name ? name.replace(/([a-z])([A-Z])/g, '$1 $2') : name;

export default function Fighters() {
  const [activeOnly, setActiveOnly] = useState(true);
  const [query, setQuery] = useState('');
  const [open, setOpen] = useState(false);
  const navigate = useNavigate();
  const containerRef = useRef(null);

  const { data: fighters, isLoading } = useQuery({
    queryKey: ['fighters', activeOnly],
    queryFn: () => api.getFighters(0, 300, activeOnly),
  });

  // Search always across all fighters (not filtered by activeOnly)
  const { data: allFighters } = useQuery({
    queryKey: ['fighters', false],
    queryFn: () => api.getFighters(0, 300, false),
  });

  const results = query.trim().length > 1
    ? allFighters?.filter((f) => f.name.toLowerCase().includes(query.toLowerCase())).slice(0, 8)
    : [];

  const displayedFighters = query.trim().length > 1
    ? allFighters?.filter((f) => f.name.toLowerCase().includes(query.toLowerCase()))
    : fighters;

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
    <div className="flex flex-col gap-6 w-full animate-fade-in-up mt-4 pb-20">
      <div className="flex flex-col gap-3 w-full mb-4">
        <div className="flex items-start justify-between gap-4">
          <div>
            <h1 className="text-4xl md:text-5xl font-black tracking-tight mb-2 uppercase">Fighter Scope</h1>
            <p className="text-gray-400 font-medium">Pivoting dataset spanning the comprehensive historic roster arrays.</p>
          </div>
          {/* Active toggle — right-justified on same row as heading */}
          <div className="flex items-center gap-4 bg-ufcslate-800 p-3 rounded-full border border-white/5 shadow-inner shrink-0">
            <span className={`text-xs font-black uppercase tracking-widest transition-colors ${!activeOnly ? 'text-white' : 'text-gray-500'}`}>
              Historic Legacy
            </span>
            <button
              onClick={() => setActiveOnly(p => !p)}
              className={`relative inline-flex h-8 w-16 items-center rounded-full transition-colors shadow-inner focus:outline-none ${activeOnly ? 'bg-ufcred-600' : 'bg-ufcslate-600'}`}
            >
              <span className={`inline-block h-6 w-6 transform rounded-full bg-white shadow-lg transition-transform ${activeOnly ? 'translate-x-9' : 'translate-x-1'}`} />
            </button>
            <span className={`text-xs font-black uppercase tracking-widest transition-colors ${activeOnly ? 'text-ufcred-500' : 'text-gray-500'}`}>
              Active Roster
            </span>
          </div>
        </div>
          {/* Big search bar under heading */}
          <div className="relative w-full max-w-xl">
            <span className="absolute inset-y-0 left-5 flex items-center pointer-events-none text-gray-500">
              <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M21 21l-4.35-4.35M17 11A6 6 0 1 1 5 11a6 6 0 0 1 12 0z" />
              </svg>
            </span>
            <input
              type="text"
              value={query}
              onChange={(e) => { setQuery(e.target.value); setOpen(false); }}
              placeholder="SEARCH FIGHTERS..."
              className="w-full bg-ufcslate-800 border border-white/5 rounded-full pl-14 pr-5 py-4 text-sm font-black uppercase tracking-widest text-white placeholder-gray-600 focus:outline-none focus:border-ufcred-500 focus:ring-1 focus:ring-ufcred-500 transition-colors shadow-inner"
            />
            {query && (
              <button
                onClick={() => setQuery('')}
                className="absolute inset-y-0 right-5 flex items-center text-gray-500 hover:text-white transition-colors"
              >
                <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            )}
          </div>
          {query.trim().length > 1 && (
            <p className="text-xs font-black uppercase tracking-widest text-gray-500">
              {(allFighters?.filter((f) => f.name.toLowerCase().includes(query.toLowerCase()))?.length ?? 0)} result{allFighters?.filter((f) => f.name.toLowerCase().includes(query.toLowerCase()))?.length !== 1 ? 's' : ''} for &ldquo;{query.trim()}&rdquo;
            </p>
          )}
      </div>

      {isLoading ? (
        <div className="text-gray-400 font-bold tracking-widest animate-pulse">FETCHING DATABASE...</div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
          {displayedFighters?.length === 0 && (
            <p className="text-gray-500 font-medium">No fighters logged internally matching constraints.</p>
          )}
          {displayedFighters?.map((f) => (
            <Link key={f.fighter_id} to={`/fighters/${f.fighter_id}`}
                  className="glass-panel p-6 rounded-[1.5rem] hover:scale-[1.02] transition-transform flex justify-between items-center bg-ufcslate-800 hover:bg-black group border-l-4 border-l-transparent hover:border-l-ufcred-500">
              <div>
                <h3 className="text-2xl font-black tracking-tight group-hover:text-white text-gray-100 uppercase">
                  {f.name.replace(/([A-Z])/g, ' $1').trim()}
                </h3>
                <p className="text-xs font-bold text-gray-500 uppercase tracking-widest mt-1">
                  {f.weight_class || "Absolute"} &middot; {f.record_wins}-{f.record_losses}-{f.record_draws}
                </p>
              </div>
              <div className="text-right">
                <span className="text-3xl text-ufcred-500 font-black opacity-0 group-hover:opacity-100 transition-opacity">&rarr;</span>
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
