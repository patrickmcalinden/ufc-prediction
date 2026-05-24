import React, { useEffect } from 'react';
import { useQuery } from '@tanstack/react-query';
import { api } from '../lib/api';

/**
 * Reusable model version dropdown selector.
 * Fetches available models from the API and renders a premium toggle bar.
 */
export default function ModelSelector({ selected, onChange }) {
  const { data: models, isLoading } = useQuery({
    queryKey: ['models'],
    queryFn: api.getModels,
    retry: 1,
    staleTime: 60_000,
  });

  useEffect(() => {
    // Automatically select the latest model if nothing is selected
    if (models && models.length > 0 && !selected) {
      onChange(models[models.length - 1].model_version);
    }
  }, [models, selected, onChange]);

  if (isLoading || !models || models.length <= 1) return null;

  return (
    <div className="flex items-center gap-2">
      <span className="text-[9px] md:text-[10px] font-bold uppercase tracking-widest text-gray-500">
        Model
      </span>
      <div className="flex bg-[#111111]/80 rounded-full border border-white/10 p-0.5 gap-0.5">
        {models.map((m) => (
          <button
            key={m.model_version}
            onClick={() => onChange(m.model_version)}
            className={`px-3 py-1.5 rounded-full text-[10px] md:text-[11px] font-bold uppercase tracking-widest transition-all duration-200
              ${selected === m.model_version
                ? 'bg-ufcred-500 text-white shadow-lg shadow-ufcred-500/30'
                : 'text-gray-400 hover:text-white hover:bg-white/5'
              }`}
          >
            {m.model_version}
            {m.graded > 0 && (
              <span className="ml-1.5 text-[8px] opacity-60">
                {m.accuracy}%
              </span>
            )}
          </button>
        ))}
      </div>
    </div>
  );
}
