import React from 'react';
import { useCertamen } from '../context/CertamenContext';
import {
  Volume2,
  VolumeX,
  Settings,
  Eye,
  Headphones,
  ExternalLink,
} from 'lucide-react';

interface HeaderProps {
  activeTab: 'arena' | 'stats' | 'leaderboard' | 'bank' | 'settings';
  setActiveTab: (tab: 'arena' | 'stats' | 'leaderboard' | 'bank' | 'settings') => void;
  onOpenLogin: () => void;
}

export const Header: React.FC<HeaderProps> = ({
  activeTab,
  setActiveTab,
  onOpenLogin,
}) => {
  const { user, settings, updateSettings } = useCertamen();

  return (
    <header className="sticky top-0 z-40 px-4 sm:px-6 py-3.5 backdrop-blur-xl bg-white/90 border-b border-sky-200/60 shadow-sm">
      <div className="max-w-5xl mx-auto flex items-center justify-between gap-3 sm:gap-6">
        {/* UHSJCL Brand Mark */}
        <div
          onClick={() => setActiveTab('arena')}
          className="flex items-center gap-2.5 cursor-pointer select-none group"
        >
          <div className="relative w-8 h-8 rounded-full overflow-hidden ring-2 ring-sky-400/40 group-hover:ring-sky-500 transition-all shadow-sm">
            <img
              src="./assets/uhsjcl_crest.jpg"
              alt="UHSJCL Logo"
              className="w-full h-full object-cover"
            />
          </div>
          <div className="flex flex-col">
            <div className="flex items-center gap-1.5">
              <span className="font-display font-bold text-base tracking-wider text-slate-900 group-hover:text-sky-700 transition-colors">
                UHSJCL
              </span>
              <span className="text-[10px] font-sans font-semibold uppercase px-2 py-0.5 bg-sky-100 text-sky-800 border border-sky-200 rounded-full">
                Certamen
              </span>
            </div>
          </div>
        </div>

        {/* Tab Navigation */}
        <nav className="flex items-center gap-1 bg-sky-50/80 p-1 rounded-2xl border border-sky-200/60">
          <button
            onClick={() => setActiveTab('arena')}
            className={`px-3.5 py-1.5 rounded-xl text-xs font-semibold transition-all cursor-pointer ${
              activeTab === 'arena'
                ? 'bg-sky-600 text-white shadow-sm shadow-sky-600/30'
                : 'text-slate-600 hover:text-slate-900 hover:bg-sky-100/60'
            }`}
          >
            Arena
          </button>
          <button
            onClick={() => setActiveTab('stats')}
            className={`px-3.5 py-1.5 rounded-xl text-xs font-semibold transition-all cursor-pointer ${
              activeTab === 'stats'
                ? 'bg-sky-600 text-white shadow-sm shadow-sky-600/30'
                : 'text-slate-600 hover:text-slate-900 hover:bg-sky-100/60'
            }`}
          >
            Analytics
          </button>
          <button
            onClick={() => setActiveTab('leaderboard')}
            className={`px-3.5 py-1.5 rounded-xl text-xs font-semibold transition-all cursor-pointer ${
              activeTab === 'leaderboard'
                ? 'bg-sky-600 text-white shadow-sm shadow-sky-600/30'
                : 'text-slate-600 hover:text-slate-900 hover:bg-sky-100/60'
            }`}
          >
            Leaderboard
          </button>
          <button
            onClick={() => setActiveTab('bank')}
            className={`hidden sm:inline-block px-3.5 py-1.5 rounded-xl text-xs font-semibold transition-all cursor-pointer ${
              activeTab === 'bank'
                ? 'bg-sky-600 text-white shadow-sm shadow-sky-600/30'
                : 'text-slate-600 hover:text-slate-900 hover:bg-sky-100/60'
            }`}
          >
            Treasury
          </button>
        </nav>

        {/* Quick Actions & User Profile */}
        <div className="flex items-center gap-1.5 sm:gap-2">
          {/* Reader Mode Toggle */}
          <button
            onClick={() => updateSettings({ readerMode: settings.readerMode === 'visual' ? 'audio' : 'visual' })}
            className="p-2 rounded-xl text-slate-600 hover:text-slate-900 hover:bg-sky-50 border border-transparent hover:border-sky-200 transition-all cursor-pointer"
            title={settings.readerMode === 'visual' ? 'Visual Reading (Click to switch to Speech Moderator)' : 'Speech Reader Active (Click for Visual)'}
          >
            {settings.readerMode === 'visual' ? <Eye className="w-4 h-4" /> : <Headphones className="w-4 h-4 text-sky-600 animate-pulse" />}
          </button>

          {/* Sound Toggle */}
          <button
            onClick={() => updateSettings({ soundEnabled: !settings.soundEnabled })}
            className="p-2 rounded-xl text-slate-600 hover:text-slate-900 hover:bg-sky-50 border border-transparent hover:border-sky-200 transition-all cursor-pointer"
            title={settings.soundEnabled ? 'Mute Sound FX' : 'Enable Sound FX'}
          >
            {settings.soundEnabled ? <Volume2 className="w-4 h-4 text-sky-700" /> : <VolumeX className="w-4 h-4 text-slate-400" />}
          </button>

          {/* Settings */}
          <button
            onClick={() => setActiveTab('settings')}
            className={`p-2 rounded-xl border transition-all cursor-pointer ${
              activeTab === 'settings'
                ? 'text-sky-800 bg-sky-100 border-sky-300'
                : 'text-slate-600 hover:text-slate-900 hover:bg-sky-50 border-transparent hover:border-sky-200'
            }`}
            title="Settings"
          >
            <Settings className="w-4 h-4" />
          </button>

          {/* Convention Back Link */}
          <a
            href="/"
            className="hidden md:inline-flex items-center gap-1 px-3 py-1.5 rounded-xl text-xs font-semibold text-sky-900 bg-sky-100/70 hover:bg-sky-200/80 border border-sky-200 shadow-sm transition-all"
            title="Return to CAJCL Convention Site"
          >
            <span>← Convention</span>
          </a>

          {/* User Profile */}
          <button
            onClick={onOpenLogin}
            className="flex items-center gap-2 pl-3 pr-3.5 py-1.5 rounded-full bg-white border border-sky-200 hover:border-sky-400 shadow-sm transition-all text-xs group cursor-pointer"
          >
            <span className="text-slate-800 font-semibold">{user.username}</span>
            <span className="text-sky-700 font-bold ml-0.5 bg-sky-50 px-2 py-0.5 rounded-full border border-sky-200">
              {user.stats.totalPoints} pts
            </span>
          </button>
        </div>
      </div>
    </header>
  );
};


