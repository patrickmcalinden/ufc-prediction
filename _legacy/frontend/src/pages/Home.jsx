import React from 'react';
import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { api } from '../lib/api';

export default function Home() {
  const { data: health, isLoading } = useQuery({
    queryKey: ['health'],
    queryFn: api.healthCheck,
    retry: false
  });

  return (
    <div className="flex flex-col gap-12 mt-8 mb-20">
      <section className="flex flex-col items-center text-center max-w-4xl mx-auto gap-6 glass-panel rounded-3xl p-8 md:p-16 border-ufcred-900/30">

        <div className="inline-flex items-center gap-3 px-5 py-2 rounded-full bg-ufcslate-900 shadow-inner border border-ufcred-700/30 text-sm font-semibold tracking-wider">
          <span className={`w-2 h-2 rounded-full ${health ? 'bg-green-500 shadow-[0_0_10px_2px_rgba(34,197,94,0.4)] animate-pulse' : 'bg-red-500'}`}></span>
          {isLoading ? 'INITIATING FASTAPI...' : (health ? 'ALGORITHM ONLINE & SECURE' : 'ENGINE OFFLINE')}
        </div>

        <h1 className="text-5xl md:text-8xl font-black tracking-tighter leading-tight mt-2">
          Algorithmic Combats. <br />
          <span className="text-transparent bg-clip-text bg-gradient-to-r from-ufcred-500 to-orange-600">
            Absolute Precision.
          </span>
        </h1>

        <p className="text-xl md:text-2xl text-gray-400 font-medium leading-relaxed max-w-2xl mt-4 max-w-3xl">
          Harnessing XGBoost Machine Learning and temporally synchronized Elo tracking
          to forecast UFC fight outcomes before they step foot into the TWISTER.
        </p>

        <div className="flex flex-col sm:flex-row gap-4 mt-10 w-full sm:w-auto">
          <Link to="/predictions" className="px-10 py-5 bg-ufcred-600 hover:bg-ufcred-500 text-white font-bold text-center rounded-2xl transition-all shadow-xl hover:shadow-ufcred-500/25 active:scale-95 text-lg">
            View Live Predictions
          </Link>
          <Link to="/blog" className="px-10 py-5 bg-white/5 hover:bg-white/10 text-white font-bold text-center rounded-2xl transition-all shadow-xl border border-white/5 active:scale-95 text-lg backdrop-blur-sm">
            Read The Blog
          </Link>
        </div>
      </section>

      <section className="grid grid-cols-1 md:grid-cols-3 gap-6 w-full max-w-5xl mx-auto">
        <div className="glass-panel rounded-3xl p-8 flex flex-col items-center justify-center text-center gap-3 hover:-translate-y-2 transition-transform cursor-default">
          <p className="text-6xl font-black text-ufcred-500 tracking-tighter">74.5<span className="text-4xl">%</span></p>
          <p className="text-gray-400 font-semibold uppercase tracking-widest text-xs">Model Holdout Accuracy</p>
        </div>
        <div className="glass-panel rounded-3xl p-8 flex flex-col items-center justify-center text-center gap-3 hover:-translate-y-2 transition-transform cursor-default">
          <p className="text-6xl font-black text-white tracking-tighter">8.5<span className="text-4xl">k</span></p>
          <p className="text-gray-400 font-semibold uppercase tracking-widest text-xs">Historical Fights Logged</p>
        </div>
        <div className="glass-panel rounded-3xl p-8 flex flex-col items-center justify-center text-center gap-3 hover:-translate-y-2 transition-transform cursor-default">
          <p className="text-6xl font-black text-ufcred-500 tracking-tighter">XGB</p>
          <p className="text-gray-400 font-semibold uppercase tracking-widest text-xs">Surrogate Tree Classifier</p>
        </div>
      </section>
    </div>
  );
}
