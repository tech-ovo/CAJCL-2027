import React, { useState } from 'react';
import { useCertamen } from '../context/CertamenContext';
import { Category } from '../types/certamen';
import { FormattedText } from './FormattedText';
import { CATEGORY_NAMES } from './BuzzerArena';

const CATEGORIES = Object.entries(CATEGORY_NAMES) as [Category, string][];
const PAGE = 50;

export const StatsDashboard: React.FC = () => {
  const { user, resetUserStats } = useCertamen();
  const [historyFilter, setHistoryFilter] = useState<'all' | 'missed' | Category>('all');
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [shown, setShown] = useState<number>(PAGE);

  const stats = user.stats;
  const overallAccuracy =
    stats.totalAnswered > 0 ? Math.round((stats.totalCorrect / stats.totalAnswered) * 100) : 0;

  const filteredHistory = user.history.filter((attempt) => {
    if (historyFilter === 'missed' && attempt.isCorrect) return false;
    if (historyFilter !== 'all' && historyFilter !== 'missed' && attempt.category !== historyFilter)
      return false;
    if (searchQuery) {
      const q = searchQuery.toLowerCase();
      return (
        attempt.questionText.toLowerCase().includes(q) ||
        attempt.userAnswer.toLowerCase().includes(q) ||
        attempt.acceptableAnswers.some((a) => a.toLowerCase().includes(q))
      );
    }
    return true;
  });

  const filters: ['all' | 'missed' | Category, string][] = [
    ['all', `All (${user.history.length})`],
    ['missed', `Missed (${user.history.filter((h) => !h.isCorrect).length})`],
    ...CATEGORIES,
  ];

  return (
    <>
      <div className="page-head">
        <div>
          <h1>Analytics</h1>
          <p className="small muted">{user.username} &middot; {user.school || 'University High School'}</p>
        </div>
        <button
          type="button"
          className="btn btn--danger btn--small"
          onClick={() => {
            if (confirm('Reset all stats and attempt history?')) resetUserStats();
          }}
        >
          Reset stats
        </button>
      </div>

      <div className="stats">
        <div className="stat">
          <span className="stat__value">{stats.totalPoints}</span>
          <span className="label">Points</span>
        </div>
        <div className="stat">
          <span className="stat__value">{overallAccuracy}%</span>
          <span className="label">Accuracy</span>
          <span className="small muted">{stats.totalCorrect} of {stats.totalAnswered} correct</span>
        </div>
        <div className="stat">
          <span className="stat__value">{stats.bestStreak}</span>
          <span className="label">Best streak</span>
          <span className="small muted">Current: {stats.currentStreak}</span>
        </div>
        <div className="stat">
          <span className="stat__value">{stats.totalAnswered}</span>
          <span className="label">Questions answered</span>
        </div>
      </div>

      <section>
        <h2>By subject</h2>
        <div className="table-wrap">
          <table className="table">
            <thead>
              <tr>
                <th>Subject</th>
                <th className="num">Correct</th>
                <th className="num">Points</th>
                <th>Accuracy</th>
              </tr>
            </thead>
            <tbody>
              {CATEGORIES.map(([id, label]) => {
                const cat = stats.byCategory[id] || { answered: 0, correct: 0, points: 0 };
                const acc = cat.answered > 0 ? Math.round((cat.correct / cat.answered) * 100) : 0;
                return (
                  <tr key={id}>
                    <td>
                      <button
                        type="button"
                        style={{
                          background: 'none',
                          border: 0,
                          padding: 0,
                          font: 'inherit',
                          color: 'var(--link)',
                          cursor: 'pointer',
                          textAlign: 'left',
                        }}
                        onClick={() => {
                          setHistoryFilter(id);
                          setShown(PAGE);
                          const el = document.getElementById('history-search');
                          if (el) el.scrollIntoView({ behavior: 'smooth' });
                        }}
                        title={`Filter history by ${label}`}
                      >
                        {label}
                      </button>
                    </td>
                    <td className="num">{cat.correct} / {cat.answered}</td>
                    <td className="num">{cat.points}</td>
                    <td>
                      <span className="meter">
                        <span className="meter__track"><span className="meter__fill" style={{ width: `${acc}%`, display: 'block' }} /></span>
                        <span className="mono">{acc}%</span>
                      </span>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </section>

      <section>
        <h2>History</h2>
        <div className="search">
          <label className="visually-hidden" htmlFor="history-search">Search history</label>
          <input
            id="history-search"
            type="search"
            value={searchQuery}
            onChange={(e) => { setSearchQuery(e.target.value); setShown(PAGE); }}
            placeholder="Search questions or answers"
          />
        </div>

        <div className="tabs" role="group" aria-label="Filter history">
          {filters.map(([id, label]) => (
            <button
              key={id}
              type="button"
              className={`tabs__tab${historyFilter === id ? ' is-current' : ''}`}
              aria-pressed={historyFilter === id}
              onClick={() => { setHistoryFilter(id); setShown(PAGE); }}
            >
              {label}
            </button>
          ))}
        </div>

        {filteredHistory.length === 0 ? (
          <div className="empty">
            <h3>Nothing here yet</h3>
            <p style={{ margin: '0 auto' }}>
              {user.history.length === 0
                ? 'Answer a question in the Arena and it will appear here.'
                : 'No attempts match this filter.'}
            </p>
            {user.history.length === 0 && (
              <p style={{ margin: 'var(--space-4) auto 0' }}>
                <a className="btn btn--primary" href="#/arena">Go to the Arena</a>
              </p>
            )}
          </div>
        ) : (
          <>
            <ul className="history">
              {filteredHistory.slice(0, shown).map((attempt, idx) => (
                <li key={idx}>
                  <div className="entry__head">
                    <p className="label label--ink">
                      <span aria-hidden="true">{attempt.isCorrect ? '✓ ' : '✗ '}</span>
                      {attempt.isCorrect ? 'Correct' : 'Missed'} &middot;{' '}
                      {CATEGORY_NAMES[attempt.category] ?? attempt.category}
                    </p>
                    <p className="entry__answers">
                      You said: <strong>{attempt.userAnswer || 'passed'}</strong>
                    </p>
                  </div>
                  <p className="entry__text"><FormattedText text={attempt.questionText} /></p>
                </li>
              ))}
            </ul>
            {filteredHistory.length > shown && (
              <button type="button" className="btn more" onClick={() => setShown(shown + PAGE)}>
                Show {Math.min(PAGE, filteredHistory.length - shown)} more
              </button>
            )}
          </>
        )}
      </section>
    </>
  );
};
