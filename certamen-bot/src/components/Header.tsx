import React, { useState } from 'react';
import { useCertamen } from '../context/CertamenContext';

export type Tab = 'arena' | 'stats' | 'leaderboard' | 'bank' | 'settings';

export const TABS: { id: Tab; label: string }[] = [
  { id: 'arena', label: 'Arena' },
  { id: 'stats', label: 'Analytics' },
  { id: 'leaderboard', label: 'Leaderboard' },
  { id: 'bank', label: 'Questions' },
  { id: 'settings', label: 'Settings' },
];

interface HeaderProps {
  activeTab: Tab;
  onOpenLogin: () => void;
}

/* The same theme logic as the convention site's js/main.js: nothing stored
 * means "follow the system", and the icon shows what you would GET. */
function currentTheme(): 'dark' | 'light' {
  try {
    const stored = localStorage.getItem('theme');
    if (stored === 'dark' || stored === 'light') return stored;
  } catch {
    /* storage blocked */
  }
  return window.matchMedia?.('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
}

const SUN = ['M12 4.5v-2', 'M12 21.5v-2', 'M4.5 12h-2', 'M21.5 12h-2',
  'M6.7 6.7 5.3 5.3', 'M18.7 18.7l-1.4-1.4', 'M6.7 17.3l-1.4 1.4', 'M18.7 5.3l-1.4 1.4',
  'M12 7.5a4.5 4.5 0 1 0 0 9 4.5 4.5 0 0 0 0-9z'];
const MOON = ['M20 14.5A8.5 8.5 0 0 1 9.5 4a8.5 8.5 0 1 0 10.5 10.5z'];

const ThemeToggle: React.FC = () => {
  const [theme, setTheme] = useState(currentTheme);
  const dark = theme === 'dark';
  const label = dark ? 'Switch to light mode' : 'Switch to dark mode';

  return (
    <button
      type="button"
      className="nav__theme"
      aria-label={label}
      title={label}
      onClick={() => {
        const next = dark ? 'light' : 'dark';
        document.documentElement.setAttribute('data-theme', next);
        try {
          localStorage.setItem('theme', next);
        } catch {
          /* the page still switches; it just will not persist */
        }
        setTheme(next);
      }}
    >
      <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor"
        strokeWidth="1.7" strokeLinecap="round" aria-hidden="true">
        {(dark ? SUN : MOON).map((d) => <path key={d} d={d} />)}
      </svg>
    </button>
  );
};

export const Header: React.FC<HeaderProps> = ({ activeTab, onOpenLogin }) => {
  const { user } = useCertamen();

  return (
    <>
      <header className="masthead">
        <div className="page">
          <div className="masthead__bar">
            <div>
              <p className="masthead__mark"><a href="../">CAJCL</a></p>
              <p className="masthead__line">Certamen Arena &middot; 72nd State Convention</p>
            </div>
            <p className="label">Practice</p>
          </div>
        </div>
      </header>

      <div className="page">
        <nav className="nav" aria-label="Certamen">
          {TABS.map((t) => (
            <a key={t.id} href={`#/${t.id}`} aria-current={activeTab === t.id ? 'page' : undefined}>
              {t.label}
            </a>
          ))}

          <span className="nav__you">
            <a className="nav__back" href="../">Convention site</a>
            <button type="button" className="nav__profile" onClick={onOpenLogin}>
              <span>{user.username}</span>
              <span className="mono">{user.stats.totalPoints} pts</span>
            </button>
            <ThemeToggle />
          </span>
        </nav>
      </div>
    </>
  );
};
