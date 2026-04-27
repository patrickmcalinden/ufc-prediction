import React from 'react';
import { BrowserRouter, Routes, Route, Link } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import Home from './pages/Home';
import Fighters from './pages/Fighters';
import FighterProfile from './pages/FighterProfile';
import Blog from './pages/Blog';
import BlogPost from './pages/BlogPost';
import Predictions from './pages/Predictions';
import BetTracker from './pages/BetTracker';
import Results from './pages/Results';
import ModelLeaderboard from './pages/ModelLeaderboard';

const queryClient = new QueryClient();

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter basename={import.meta.env.BASE_URL}>
        <div className="min-h-screen flex flex-col font-sans">

          <nav className="fixed w-full z-50 glass-panel border-b-white/5 rounded-none bg-ufcslate-900/90 py-4 px-6 flex justify-between items-center shadow-2xl">
            <Link to="/" className="text-2xl font-black tracking-tighter text-white">
              TWISTER<span className="text-ufcred-500"></span>
            </Link>

            <div className="hidden md:flex gap-8 font-medium tracking-wide">
              <Link to="/fighters" className="hover:text-ufcred-500 transition-colors">Fighters</Link>
              <Link to="/predictions" className="hover:text-ufcred-500 transition-colors">Predictions</Link>
              <Link to="/results" className="hover:text-ufcred-500 transition-colors">Results</Link>
              <Link to="/models" className="hover:text-ufcred-500 transition-colors">Models</Link>
              <Link to="/bets" className="hover:text-ufcred-500 transition-colors">Bet Tracker</Link>
              <Link to="/blog" className="hover:text-ufcred-500 transition-colors">Blog</Link>
            </div>

            <button className="md:hidden text-white p-2">
              <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" /></svg>
            </button>
          </nav>

          <main className="flex-1 pt-28 px-4 md:px-8 max-w-7xl w-full mx-auto">
            <Routes>
              <Route path="/" element={<Home />} />
              <Route path="/fighters" element={<Fighters />} />
              <Route path="/fighters/:id" element={<FighterProfile />} />
              <Route path="/predictions" element={<Predictions />} />
              <Route path="/results" element={<Results />} />
              <Route path="/models" element={<ModelLeaderboard />} />
              <Route path="/bets" element={<BetTracker />} />
              <Route path="/blog" element={<Blog />} />
              <Route path="/blog/:slug" element={<BlogPost />} />
            </Routes>
          </main>

        </div>
      </BrowserRouter>
    </QueryClientProvider>
  );
}

export default App;
