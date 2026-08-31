import React, { useState } from 'react';
import { CertamenProvider } from './context/CertamenContext';
import { Header } from './components/Header';
import { BuzzerArena } from './components/BuzzerArena';
import { StatsDashboard } from './components/StatsDashboard';
import { LeaderboardView } from './components/LeaderboardView';
import { QuestionBankManager } from './components/QuestionBankModal';
import { SettingsView } from './components/SettingsView';
import { UserLoginModal } from './components/UserLoginModal';

function MainApp() {
  const [activeTab, setActiveTab] = useState<'arena' | 'stats' | 'leaderboard' | 'bank' | 'settings'>('arena');
  const [isLoginOpen, setIsLoginOpen] = useState<boolean>(false);

  return (
    <div className="min-h-screen bg-[#f0f7ff] text-slate-900 flex flex-col font-sans relative overflow-x-hidden selection:bg-sky-500/20 selection:text-sky-900">
      {/* Ambient background celestial and sky gradients */}
      <div className="fixed inset-0 pointer-events-none z-0 overflow-hidden">
        {/* Soft Mediterranean sky ambient light */}
        <div className="absolute -top-40 left-1/2 -translate-x-1/2 w-[1200px] h-[550px] bg-gradient-to-b from-sky-400/20 via-sky-200/25 to-transparent blur-3xl rounded-full" />
        <div className="absolute top-1/3 -left-40 w-[600px] h-[600px] bg-sky-200/30 blur-3xl rounded-full" />
        <div className="absolute top-2/3 -right-40 w-[600px] h-[600px] bg-amber-100/40 blur-3xl rounded-full" />
      </div>

      {/* Top Navigation Header matching UHSJCL brand */}
      <Header
        activeTab={activeTab}
        setActiveTab={setActiveTab}
        onOpenLogin={() => setIsLoginOpen(true)}
      />

      {/* Main Stage Area */}
      <main className="flex-1 pb-16 relative z-10">
        {activeTab === 'arena' && <BuzzerArena />}
        {activeTab === 'stats' && <StatsDashboard />}
        {activeTab === 'leaderboard' && <LeaderboardView />}
        {activeTab === 'bank' && <QuestionBankManager />}
        {activeTab === 'settings' && <SettingsView />}
      </main>

      {/* User Login & Profile Modal */}
      <UserLoginModal
        isOpen={isLoginOpen}
        onClose={() => setIsLoginOpen(false)}
      />

      {/* UHSJCL Brand Footer */}
      <footer className="relative z-10 border-t border-sky-200/70 bg-white/80 backdrop-blur-md py-6 text-center text-xs text-slate-500">
        <div className="max-w-5xl mx-auto px-4 flex flex-col sm:flex-row items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <img
              src="./assets/logo.webp"
              alt="UHSJCL"
              className="w-5 h-5 rounded-full object-cover border border-sky-400/50 shadow-sm"
            />
            <span className="font-display font-semibold tracking-wider text-slate-800">
              UHSJCL CERTAMEN
            </span>
            <span className="text-slate-300">•</span>
            <span className="text-slate-600 font-editorial italic text-sm">
              aequam mementō rēbus in arduīs servāre mentem
            </span>
          </div>

          <div className="flex items-center gap-4 text-xs text-slate-600 font-medium">
            <span>University High School</span>
            <span className="text-slate-300">•</span>
            <span>Junior Classical League</span>
          </div>
        </div>
      </footer>
    </div>
  );
}

export default function App() {
  return (
    <CertamenProvider>
      <MainApp />
    </CertamenProvider>
  );
}



