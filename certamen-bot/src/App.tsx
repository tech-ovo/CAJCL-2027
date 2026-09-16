import React, { useEffect, useState } from 'react';
import { CertamenProvider } from './context/CertamenContext';
import { Header, Tab, TABS } from './components/Header';
import { BuzzerArena } from './components/BuzzerArena';
import { StatsDashboard } from './components/StatsDashboard';
import { LeaderboardView } from './components/LeaderboardView';
import { QuestionBankManager } from './components/QuestionBankModal';
import { SettingsView } from './components/SettingsView';
import { UserLoginModal } from './components/UserLoginModal';

/* Sections are hash routes, like the convention site's, so the back button
 * and a shared link both land where they should. */
function tabFromHash(): Tab {
  const name = window.location.hash.replace(/^#\/?/, '');
  return (TABS.find((t) => t.id === name)?.id ?? 'arena') as Tab;
}

function MainApp() {
  const [activeTab, setActiveTab] = useState<Tab>(tabFromHash);
  const [isLoginOpen, setIsLoginOpen] = useState<boolean>(false);

  useEffect(() => {
    const onHash = () => {
      setActiveTab(tabFromHash());
      window.scrollTo(0, 0);
    };
    window.addEventListener('hashchange', onHash);
    return () => window.removeEventListener('hashchange', onHash);
  }, []);

  return (
    <>
      <a className="skip-link" href="#main" onClick={(e) => {
        e.preventDefault();
        document.getElementById('main')?.focus();
      }}>Skip to content</a>

      <Header activeTab={activeTab} onOpenLogin={() => setIsLoginOpen(true)} />

      <main id="main" className="page" tabIndex={-1}>
        {activeTab === 'arena' && <BuzzerArena />}
        {activeTab === 'stats' && <StatsDashboard />}
        {activeTab === 'leaderboard' && <LeaderboardView />}
        {activeTab === 'bank' && <QuestionBankManager />}
        {activeTab === 'settings' && <SettingsView />}
      </main>

      <UserLoginModal isOpen={isLoginOpen} onClose={() => setIsLoginOpen(false)} />

      <footer className="page">
        <hr className="hair" />
        <p className="label">
          California Junior Classical League &middot; University High School JCL &middot;{' '}
          <a href="https://discord.gg/cgkYcWYGYj" target="_blank" rel="noreferrer">Discord</a> &middot;{' '}
          <a href="https://instagram.com/uhsjcl" target="_blank" rel="noreferrer">Instagram</a>
        </p>
      </footer>
    </>
  );
}

export default function App() {
  return (
    <CertamenProvider>
      <MainApp />
    </CertamenProvider>
  );
}
