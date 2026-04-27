import React, { useMemo, useState, useEffect } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { api } from '../lib/api';
import { groupAndSortByEvent } from '../lib/utils';
import PredictionCard from '../components/PredictionCard';
import ModelSelector from '../components/ModelSelector';

export default function Predictions() {
  const [selectedModel, setSelectedModel] = useState(null);

  const { data: predictions, isLoading, isError, error } = useQuery({
    queryKey: ['predictions', selectedModel],
    queryFn: () => api.getPredictions(selectedModel),
    retry: 1,
  });

  const [collapsedEvents, setCollapsedEvents] = useState(new Set());

  const formatEventDate = (date) => {
    return date.toLocaleDateString('en-US', {
      weekday: 'long',
      month: 'long',
      day: 'numeric',
      year: 'numeric',
    });
  };

  const isLive = (date) => {
    const today = new Date();
    return date.getDate() === today.getDate() &&
      date.getMonth() === today.getMonth() &&
      date.getFullYear() === today.getFullYear();
  };

  const toggleEvent = (eventName) => {
    setCollapsedEvents((prev) => {
      const next = new Set(prev);
      if (next.has(eventName)) next.delete(eventName);
      else next.add(eventName);
      return next;
    });
  };

  // Filter to only ungraded (upcoming) predictions — graded ones live on Results page
  const upcomingPredictions = useMemo(() => {
    if (!predictions) return [];
    return predictions.filter((p) => p.was_correct === null || p.was_correct === undefined);
  }, [predictions]);

  const sortedEvents = useMemo(
    () => groupAndSortByEvent(upcomingPredictions),
    [upcomingPredictions]
  );

  const allCollapsed = sortedEvents.length > 0 && sortedEvents.every((e) => collapsedEvents.has(e.eventName));

  const toggleAll = () => {
    if (allCollapsed) {
      setCollapsedEvents(new Set());
    } else {
      setCollapsedEvents(new Set(sortedEvents.map((e) => e.eventName)));
    }
  };

  // Count how many graded predictions exist (for the info banner)
  const gradedCount = useMemo(() => {
    if (!predictions) return 0;
    return predictions.filter((p) => p.was_correct !== null && p.was_correct !== undefined).length;
  }, [predictions]);

  return (
    <div className="flex flex-col gap-6 w-full animate-fade-in-up pb-20 mt-4">
      <div className="flex flex-col gap-4 mb-8">
        <div className="flex justify-between items-end">
          <div>
            <h1 className="text-4xl bg-gradient-to-r from-white to-gray-400 bg-clip-text text-transparent md:text-5xl font-black tracking-tight mb-2 uppercase">Core Diagnostics</h1>
            <p className="text-gray-400 font-medium tracking-wide">Live XGBoost algorithmic probability evaluations.</p>
          </div>
          <div className="flex items-center gap-3 shrink-0 ml-4">
            <ModelSelector selected={selectedModel} onChange={setSelectedModel} />
          </div>
        </div>
      </div>

      {/* Info banner — link to Results for graded predictions */}
      {gradedCount > 0 && (
        <Link
          to="/results"
          className="flex items-center gap-3 px-5 py-3 rounded-2xl bg-green-500/5 border border-green-500/15 hover:border-green-500/30 transition-all duration-300 group"
        >
          <div className="w-8 h-8 rounded-full bg-green-500/15 flex items-center justify-center shrink-0">
            <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4 text-green-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
          </div>
          <div className="flex-1 min-w-0">
            <span className="text-sm font-bold text-green-400 group-hover:text-green-300 transition-colors">
              {gradedCount} graded prediction{gradedCount !== 1 ? 's' : ''} on the Results page →
            </span>
          </div>
        </Link>
      )}

      {isLoading ? (
        <div className="flex justify-center py-20">
          <div className="text-ufcred-500 font-bold tracking-widest animate-pulse border border-ufcred-500/20 bg-ufcred-500/5 px-8 py-4 rounded-full backdrop-blur-md">
            QUERYING MODEL PIPELINES...
          </div>
        </div>
      ) : isError ? (
        <div className="flex justify-center py-20">
          <div className="text-red-500 font-bold bg-red-500/10 border border-red-500/20 px-8 py-4 rounded-[2rem] text-center max-w-lg shadow-2xl backdrop-blur-md">
            <p className="tracking-widest uppercase mb-2">System Diagnostics Failed</p>
            <p className="text-sm text-gray-400 font-medium">Unable to connect to the prediction backend engine. Please ensure the Python API server is running locally.</p>
          </div>
        </div>
      ) : (
        <div className="flex flex-col gap-12 w-full mt-4">
          {(!upcomingPredictions || upcomingPredictions.length === 0) && (
            <div className="bg-black/20 backdrop-blur-md p-8 rounded-[2rem] border border-white/5 col-span-full py-20 flex flex-col items-center gap-4 hover:border-ufcred-500/30 transition-colors shadow-2xl">
              <div className="w-16 h-16 rounded-full bg-white/5 flex items-center justify-center mb-4">
                <svg xmlns="http://www.w3.org/2000/svg" className="h-8 w-8 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
                </svg>
              </div>
              <p className="text-white font-black tracking-widest justify-center text-center uppercase text-xl">No Upcoming Predictions</p>
              <p className="text-gray-400 font-medium text-center max-w-lg">All predictions have been graded, or no upcoming events have been processed yet. Run the prediction pipeline to generate new predictions.</p>
              {gradedCount > 0 && (
                <Link to="/results" className="mt-4 px-6 py-2 rounded-full bg-ufcred-500/80 text-white font-bold text-sm uppercase tracking-widest hover:bg-ufcred-500 transition-colors border border-ufcred-500/50">
                  View Results
                </Link>
              )}
            </div>
          )}

          {(sortedEvents.length > 0 ? [sortedEvents[0]] : []).map((event) => {
            const isCollapsed = collapsedEvents.has(event.eventName);
            return (
              <div key={event.eventName} className="flex flex-col w-full">
                {/* Event header — click anywhere to collapse/expand */}
                <button
                  onClick={() => toggleEvent(event.eventName)}
                  className="flex items-center gap-4 mb-6 px-2 w-full text-left group/header cursor-pointer focus:outline-none"
                >
                  <span className="w-2 h-10 bg-ufcred-500 rounded-full inline-block shrink-0 shadow-[0_0_10px_rgba(210,10,17,0.5)]"></span>
                  <div className="flex flex-col flex-1 min-w-0">
                    <div className="flex items-center gap-3">
                      <h2 className="text-2xl md:text-3xl font-black text-white uppercase tracking-wider leading-tight truncate">
                        {event.eventName}
                      </h2>
                      {isLive(event.date) && (
                        <span className="px-2 py-0.5 rounded-md bg-ufcred-500 text-white text-[10px] font-black tracking-widest uppercase animate-pulse shrink-0">
                          LIVE
                        </span>
                      )}
                    </div>
                    <span className="text-[11px] md:text-xs font-bold uppercase tracking-widest text-gray-500 mt-0.5">
                      {formatEventDate(event.date)} · {event.fights.length} fight{event.fights.length !== 1 ? 's' : ''}
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
                    <div className="flex flex-col gap-4">
                      {event.fights.map((p) => (
                        <PredictionCard key={p.prediction_id} fight={p} />
                      ))}
                    </div>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
