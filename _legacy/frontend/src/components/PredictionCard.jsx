import React, { useState } from 'react';

const espnImageBase = "https://a.espncdn.com/combiner/i?img=/i/headshots/mma/players/full/";
const getImageUrl = (espnId) => espnId ? `${espnImageBase}${espnId}.png` : "/placeholder-fighter.png";

// Split the scraped fighter name into first / last for the stacked display.
// Falls back gracefully for single-word names or pre-fix re-scrape data
// where the name may still be concatenated (e.g. "AljamainSterling").
function splitName(name) {
  if (!name) return { first: "", last: "" };
  const parts = name.trim().split(/\s+/);
  if (parts.length > 1) return { first: parts[0], last: parts.slice(1).join(" ") };

  // Fallback: split on CamelCase boundaries (e.g. "AljamainSterling" → "Aljamain", "Sterling")
  const camelParts = name.replace(/([a-z])([A-Z])/g, '$1 $2').trim().split(/\s+/);
  if (camelParts.length > 1) return { first: camelParts[0], last: camelParts.slice(1).join(" ") };

  return { first: parts[0] || "", last: "" };
}

// Apply the same CamelCase-aware spacing to any display name (e.g. the A.I. pick label)
function formatDisplayName(name) {
  if (!name) return "";
  if (/\s/.test(name)) return name; // already has spaces
  return name.replace(/([a-z])([A-Z])/g, '$1 $2');
}

export default function PredictionCard({ fight }) {
  const [expanded, setExpanded] = useState(false);

  const prob = (fight.win_probability * 100).toFixed(1);
  const isAWin = fight.predicted_winner_id === fight.fighter_a_id;
  const isBWin = fight.predicted_winner_id === fight.fighter_b_id;

  const aName = splitName(fight.fighter_a_name);
  const bName = splitName(fight.fighter_b_name);

  return (
    <div className="group flex flex-col bg-[#111111]/80 backdrop-blur-md rounded-2xl overflow-hidden border border-white/5 hover:border-white/20 transition-all duration-300 shadow-lg shadow-black/50">
      <div
        className="relative cursor-pointer flex flex-col w-full hover:bg-white/[0.02] transition-colors"
        onClick={() => setExpanded(!expanded)}
      >
        {/* Top label: weight class / title fight */}
        <div className="absolute top-0 left-0 w-full flex justify-center mt-2 pointer-events-none z-30">
          <span className="text-[9px] md:text-[10px] font-bold uppercase tracking-widest text-gray-400 bg-black/80 px-4 py-1 rounded-full border border-white/5 shadow-sm">
            {fight.weight_class && fight.weight_class !== "Unknown" ? fight.weight_class : "Bout"}{fight.is_title_fight ? " • Title Fight" : ""}
          </span>
        </div>

        {/* Main row: fighter A | A.I. pick | fighter B */}
        <div className="relative flex flex-row items-stretch w-full min-h-[140px] md:min-h-[180px]">

          {/* Fighter A side — headshot sits directly behind the name as a faded backdrop */}
          <div className="relative flex-1 flex items-center overflow-hidden">
            <img
              src={getImageUrl(fight.fighter_a_espn_id)}
              alt={fight.fighter_a_name}
              onError={(e) => { e.target.src = "/placeholder-fighter.png"; }}
              className={`absolute inset-y-0 left-0 h-full w-auto max-w-none object-contain object-left transition-all duration-500 ${isAWin ? 'opacity-50' : 'opacity-25 grayscale brightness-[0.7]'}`}
            />
            {/* Fade photo into the card — from transparent at the left (photo visible)
                to opaque on the right (so it reads as a background for the center pick) */}
            <div className="absolute inset-0 bg-gradient-to-r from-black/30 via-[#111111]/70 to-[#111111]" />
            {/* Subtle red glow when this fighter is the A.I. pick */}
            <div className={`absolute inset-0 bg-gradient-to-r from-ufcred-500/20 to-transparent pointer-events-none transition-opacity duration-500 ${isAWin ? 'opacity-100' : 'opacity-0'}`} />

            <div className="relative z-10 pl-4 md:pl-6 pr-2 flex flex-col items-start text-left">
              <span className="text-base md:text-2xl font-black text-white leading-[1.05] uppercase tracking-wide drop-shadow-[0_2px_6px_rgba(0,0,0,0.9)]">
                {aName.first}
              </span>
              <span className="text-lg md:text-3xl font-black text-white leading-[1.05] uppercase tracking-wide drop-shadow-[0_2px_6px_rgba(0,0,0,0.9)]">
                {aName.last}
              </span>
              <span className="text-[10px] text-gray-300 font-bold uppercase tracking-widest mt-1">
                {fight.fighter_a_record}
              </span>
            </div>
          </div>

          {/* Center: A.I. pick + confidence */}
          <div className="relative z-20 flex flex-col shrink-0 px-3 md:px-6 items-center justify-center text-center">
            <span className="text-[8px] md:text-[10px] font-black uppercase tracking-[0.2em] text-ufcred-500 drop-shadow-[0_0_5px_rgba(210,10,17,0.8)] animate-pulse">A.I. Pick</span>
            <span className="font-black text-sm md:text-xl text-white tracking-widest uppercase my-1 truncate max-w-[140px] md:max-w-[220px]">{formatDisplayName(fight.predicted_winner_name)}</span>
            <span className="flex items-center gap-1.5 text-[9px] md:text-xs font-black uppercase text-white bg-ufcred-500/80 px-2 md:px-3 py-0.5 md:py-1 rounded-full border border-ufcred-500/50 shadow-[0_0_10px_rgba(210,10,17,0.4)]">
              <div className="w-1.5 h-1.5 bg-white rounded-full"></div>
              {prob}% Conf
            </span>
          </div>

          {/* Fighter B side — mirror of A */}
          <div className="relative flex-1 flex items-center overflow-hidden">
            <img
              src={getImageUrl(fight.fighter_b_espn_id)}
              alt={fight.fighter_b_name}
              onError={(e) => { e.target.src = "/placeholder-fighter.png"; }}
              className={`absolute inset-y-0 right-0 h-full w-auto max-w-none object-contain object-right transition-all duration-500 ${isBWin ? 'opacity-50' : 'opacity-25 grayscale brightness-[0.7]'}`}
            />
            <div className="absolute inset-0 bg-gradient-to-l from-black/30 via-[#111111]/70 to-[#111111]" />
            <div className={`absolute inset-0 bg-gradient-to-l from-ufcred-500/20 to-transparent pointer-events-none transition-opacity duration-500 ${isBWin ? 'opacity-100' : 'opacity-0'}`} />

            <div className="relative z-10 w-full pr-4 md:pr-6 pl-2 flex flex-col items-end text-right">
              <span className="text-base md:text-2xl font-black text-white leading-[1.05] uppercase tracking-wide drop-shadow-[0_2px_6px_rgba(0,0,0,0.9)]">
                {bName.first}
              </span>
              <span className="text-lg md:text-3xl font-black text-white leading-[1.05] uppercase tracking-wide drop-shadow-[0_2px_6px_rgba(0,0,0,0.9)]">
                {bName.last}
              </span>
              <span className="text-[10px] text-gray-300 font-bold uppercase tracking-widest mt-1">
                {fight.fighter_b_record}
              </span>
            </div>
          </div>
        </div>

        {/* Bottom bar: nationalities + expand chevron */}
        <div className="flex justify-between items-center py-2 px-4 md:px-6 z-10 opacity-70 border-t border-white/5 bg-black/30">
          <span className="text-[9px] md:text-[10px] uppercase font-bold tracking-widest text-gray-500 w-1/3 text-left">
            {fight.fighter_a_nationality || "N/A"}
          </span>
          <div className="flex justify-center w-1/3">
            <div className="w-5 h-5 md:w-6 md:h-6 rounded-full bg-white/10 flex items-center justify-center border border-white/10 hover:bg-white/30 transition-colors">
              <svg xmlns="http://www.w3.org/2000/svg" className={`h-3 w-3 md:h-4 md:w-4 text-white transition-transform duration-300 ${expanded ? 'rotate-180' : ''}`} fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
              </svg>
            </div>
          </div>
          <span className="text-[9px] md:text-[10px] uppercase font-bold tracking-widest text-gray-500 w-1/3 text-right">
            {fight.fighter_b_nationality || "N/A"}
          </span>
        </div>
      </div>

      {/* Expanded stats panel */}
      <div className={`grid transition-all duration-300 ease-in-out ${expanded ? 'grid-rows-[1fr] opacity-100' : 'grid-rows-[0fr] opacity-0'}`}>
        <div className="overflow-hidden bg-black/60 backdrop-blur-2xl border-t border-white/5">
          <div className="flex justify-between items-center p-4 md:p-6 text-center">
            <div className="flex flex-col flex-1 items-start pl-4 md:pl-6">
              <span className="text-2xl md:text-3xl font-black text-white">{fight.fighter_a_elo ? Math.round(fight.fighter_a_elo) : "N/A"}</span>
              <span className="text-[9px] md:text-[10px] font-bold text-gray-500 uppercase tracking-widest mt-1">ELO Rating</span>
            </div>
            <div className="flex flex-col flex-1 items-center justify-center gap-2 border-l border-r border-white/5">
              <span className="text-[9px] md:text-[10px] font-bold text-gray-300 uppercase tracking-widest bg-white/5 py-1 px-3 rounded-full border border-white/10 mx-auto">
                v{fight.model_version || '1.0'} Engine
              </span>
              <div className="flex flex-col items-center gap-1 mt-1">
                <span className="text-[9px] md:text-[10px] font-mono text-gray-500 uppercase tracking-widest">
                  Fight <span className="text-gray-300">#{fight.fight_id}</span>
                </span>
                <span className="text-[9px] md:text-[10px] font-mono text-gray-500 uppercase tracking-widest">
                  <span className="text-gray-300">#{fight.fighter_a_id}</span> vs <span className="text-gray-300">#{fight.fighter_b_id}</span>
                </span>
              </div>
            </div>
            <div className="flex flex-col flex-1 items-end pr-4 md:pr-6">
              <span className="text-2xl md:text-3xl font-black text-white">{fight.fighter_b_elo ? Math.round(fight.fighter_b_elo) : "N/A"}</span>
              <span className="text-[9px] md:text-[10px] font-bold text-gray-500 uppercase tracking-widest mt-1">ELO Rating</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
