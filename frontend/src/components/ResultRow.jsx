import React from 'react';

const espnImageBase = "https://a.espncdn.com/combiner/i?img=/i/headshots/mma/players/full/";
const getImageUrl = (espnId) => espnId ? `${espnImageBase}${espnId}.png` : null;

function formatName(name) {
  if (!name) return "";
  if (/\s/.test(name)) return name;
  return name.replace(/([a-z])([A-Z])/g, '$1 $2');
}

function splitName(name) {
  if (!name) return { first: "", last: "" };
  const formatted = formatName(name);
  const parts = formatted.trim().split(/\s+/);
  if (parts.length > 1) return { first: parts[0], last: parts.slice(1).join(" ") };
  return { first: parts[0] || "", last: "" };
}

export default function ResultRow({ fight }) {
  const isCorrect = fight.was_correct === true;
  const prob = (fight.win_probability * 100).toFixed(1);

  const aName = splitName(fight.fighter_a_name);
  const bName = splitName(fight.fighter_b_name);

  const aImgUrl = getImageUrl(fight.fighter_a_espn_id);
  const bImgUrl = getImageUrl(fight.fighter_b_espn_id);

  // Who won?
  const isAWinner = fight.actual_winner_id === fight.fighter_a_id;
  const isBWinner = fight.actual_winner_id === fight.fighter_b_id;

  // Build finish line
  const finishParts = [
    fight.method,
    fight.round != null ? `Rd ${fight.round}` : null,
    fight.time,
  ].filter(Boolean);
  const finishLine = finishParts.join(' · ');

  // Glow colors
  const borderColor = isCorrect ? 'border-green-500/20 hover:border-green-500/40' : 'border-red-500/20 hover:border-red-500/40';
  const glowColor = isCorrect ? 'shadow-green-500/5' : 'shadow-red-500/5';

  return (
    <div className={`group flex flex-col bg-[#111111]/80 backdrop-blur-md rounded-2xl overflow-hidden border ${borderColor} transition-all duration-300 shadow-lg ${glowColor}`}>
      <div className="relative flex flex-col w-full">

        {/* Top bar: verdict + weight class + confidence */}
        <div className="flex items-center justify-between px-4 py-2.5 border-b border-white/5 bg-black/30">
          {/* Verdict badge */}
          <span className={`inline-flex items-center text-[10px] md:text-[11px] font-black uppercase tracking-widest px-3 py-1 rounded-full border ${
            isCorrect
              ? 'bg-green-500/15 text-green-400 border-green-500/30'
              : 'bg-red-500/15 text-red-400 border-red-500/30'
          }`}>
            <span className={`w-1.5 h-1.5 rounded-full mr-2 ${isCorrect ? 'bg-green-400' : 'bg-red-400'}`}></span>
            {isCorrect ? 'Correct' : 'Wrong'}
          </span>

          {/* Weight class */}
          <span className="text-[9px] md:text-[10px] font-bold uppercase tracking-widest text-gray-500">
            {fight.weight_class && fight.weight_class !== "Unknown" ? fight.weight_class : "Bout"}
            {fight.is_title_fight ? ' · Title Fight' : ''}
          </span>

          {/* Confidence */}
          <span className="flex items-center gap-1.5 text-[9px] md:text-xs font-black uppercase text-white bg-ufcred-500/80 px-2 md:px-3 py-0.5 md:py-1 rounded-full border border-ufcred-500/50 shadow-[0_0_10px_rgba(210,10,17,0.4)]">
            <div className="w-1.5 h-1.5 bg-white rounded-full"></div>
            {prob}%
          </span>
        </div>

        {/* Fighter matchup row */}
        <div className="relative flex flex-row items-stretch w-full min-h-[100px] md:min-h-[130px]">

          {/* Fighter A side */}
          <div className="relative flex-1 flex items-center overflow-hidden">
            {aImgUrl && (
              <img
                src={aImgUrl}
                alt={fight.fighter_a_name}
                onError={(e) => { e.target.style.display = 'none'; }}
                className={`absolute inset-y-0 left-0 h-full w-auto max-w-none object-contain object-left transition-all duration-500 ${isAWinner ? 'opacity-40' : 'opacity-15 grayscale brightness-[0.6]'}`}
              />
            )}
            <div className="absolute inset-0 bg-gradient-to-r from-black/20 via-[#111111]/60 to-[#111111]" />
            {/* Winner glow */}
            {isAWinner && (
              <div className="absolute inset-0 bg-gradient-to-r from-green-500/10 to-transparent pointer-events-none" />
            )}

            <div className="relative z-10 pl-4 md:pl-5 pr-2 flex flex-col items-start text-left">
              <span className="text-sm md:text-lg font-black text-white leading-[1.05] uppercase tracking-wide drop-shadow-[0_2px_6px_rgba(0,0,0,0.9)]">
                {aName.first}
              </span>
              <span className="text-base md:text-xl font-black text-white leading-[1.05] uppercase tracking-wide drop-shadow-[0_2px_6px_rgba(0,0,0,0.9)]">
                {aName.last}
              </span>
              {isAWinner && (
                <span className="text-[8px] md:text-[9px] font-black uppercase tracking-widest text-green-400 mt-1 bg-green-500/10 px-2 py-0.5 rounded-full border border-green-500/20">Winner</span>
              )}
            </div>
          </div>

          {/* Center: Result info */}
          <div className="relative z-20 flex flex-col shrink-0 px-3 md:px-5 items-center justify-center text-center">
            <span className="text-[8px] md:text-[9px] font-black uppercase tracking-[0.15em] text-gray-500 mb-1">Model Pick</span>
            <span className="font-black text-xs md:text-sm text-white tracking-wider uppercase truncate max-w-[120px] md:max-w-[180px]">
              {formatName(fight.predicted_winner_name)}
            </span>
            {finishLine && (
              <span className="text-[8px] md:text-[9px] text-gray-500 font-medium mt-2 bg-white/5 px-2 py-0.5 rounded-full">
                {finishLine}
              </span>
            )}
          </div>

          {/* Fighter B side */}
          <div className="relative flex-1 flex items-center overflow-hidden">
            {bImgUrl && (
              <img
                src={bImgUrl}
                alt={fight.fighter_b_name}
                onError={(e) => { e.target.style.display = 'none'; }}
                className={`absolute inset-y-0 right-0 h-full w-auto max-w-none object-contain object-right transition-all duration-500 ${isBWinner ? 'opacity-40' : 'opacity-15 grayscale brightness-[0.6]'}`}
              />
            )}
            <div className="absolute inset-0 bg-gradient-to-l from-black/20 via-[#111111]/60 to-[#111111]" />
            {isBWinner && (
              <div className="absolute inset-0 bg-gradient-to-l from-green-500/10 to-transparent pointer-events-none" />
            )}

            <div className="relative z-10 w-full pr-4 md:pr-5 pl-2 flex flex-col items-end text-right">
              <span className="text-sm md:text-lg font-black text-white leading-[1.05] uppercase tracking-wide drop-shadow-[0_2px_6px_rgba(0,0,0,0.9)]">
                {bName.first}
              </span>
              <span className="text-base md:text-xl font-black text-white leading-[1.05] uppercase tracking-wide drop-shadow-[0_2px_6px_rgba(0,0,0,0.9)]">
                {bName.last}
              </span>
              {isBWinner && (
                <span className="text-[8px] md:text-[9px] font-black uppercase tracking-widest text-green-400 mt-1 bg-green-500/10 px-2 py-0.5 rounded-full border border-green-500/20">Winner</span>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
