import React, { useState, useEffect } from 'react';
import { useCertamen } from '../context/CertamenContext';
import { Category, DifficultyLevel, LeaderboardEntry } from '../types/certamen';
import { fetchLeaderboardFromCloud } from '../services/googleSheetsService';
import { CATEGORY_NAMES } from './BuzzerArena';

const LEVELS: (DifficultyLevel | 'all')[] = ['all', 'novice', 'intermediate', 'advanced'];
const capitalise = (s: string) => s.charAt(0).toUpperCase() + s.slice(1);

export const LeaderboardView: React.FC = () => {
  const { user, settings } = useCertamen();
  const [selectedSubject, setSelectedSubject] = useState<Category | 'all'>('all');
  const [selectedLevel, setSelectedLevel] = useState<DifficultyLevel | 'all'>('all');
  const [entries, setEntries] = useState<LeaderboardEntry[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(false);

  const loadLeaderboard = async () => {
    setIsLoading(true);
    try {
      const data = await fetchLeaderboardFromCloud(
        settings.appsScriptUrl,
        selectedSubject,
        selectedLevel
      );

      const hasCurrentUser = data.some((e) => e.username.toLowerCase() === user.username.toLowerCase());
      if (!hasCurrentUser && user.stats.totalPoints > 0) {
        const myEntry: LeaderboardEntry = {
          username: user.username,
          school: user.school || 'University High School',
          level: user.level,
          totalPoints: user.stats.totalPoints,
          grammarPoints: user.stats.byCategory.grammar?.points || 0,
          mythologyPoints: user.stats.byCategory.mythology?.points || 0,
          historyPoints: user.stats.byCategory.history?.points || 0,
          culturePoints: user.stats.byCategory.culture?.points || 0,
          literaturePoints: user.stats.byCategory.literature?.points || 0,
          accuracy: user.stats.totalAnswered > 0
            ? Math.round((user.stats.totalCorrect / user.stats.totalAnswered) * 100)
            : 0,
          totalAnswered: user.stats.totalAnswered,
          lastActive: new Date().toISOString(),
        };

        const combined = [...data, myEntry];
        combined.sort((a, b) => {
          if (selectedSubject === 'grammar') return b.grammarPoints - a.grammarPoints;
          if (selectedSubject === 'mythology') return b.mythologyPoints - a.mythologyPoints;
          if (selectedSubject === 'history') return b.historyPoints - a.historyPoints;
          if (selectedSubject === 'culture') return b.culturePoints - a.culturePoints;
          if (selectedSubject === 'literature') return b.literaturePoints - a.literaturePoints;
          return b.totalPoints - a.totalPoints;
        });

        setEntries(combined.map((item, idx) => ({ ...item, rank: idx + 1 })));
      } else {
        setEntries(data);
      }
    } catch (err) {
      console.error('Failed to load leaderboard:', err);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    loadLeaderboard();
  }, [selectedSubject, selectedLevel, settings.appsScriptUrl, user.stats.totalPoints]);

  const getSubjectPoints = (entry: LeaderboardEntry) => {
    switch (selectedSubject) {
      case 'grammar':
        return entry.grammarPoints;
      case 'mythology':
        return entry.mythologyPoints;
      case 'history':
        return entry.historyPoints;
      case 'culture':
        return entry.culturePoints;
      case 'literature':
        return entry.literaturePoints;
      default:
        return entry.totalPoints;
    }
  };

  const subjects = [['all', 'All subjects'], ...Object.entries(CATEGORY_NAMES)] as [Category | 'all', string][];

  return (
    <>
      <div className="page-head">
        <div>
          <h1>Leaderboard</h1>
          <p className="small muted">Practice scores from everyone using the arena.</p>
        </div>
        <button type="button" className="btn btn--small" onClick={loadLeaderboard} disabled={isLoading}>
          {isLoading && <span className="btn__spinner" aria-hidden="true" />}
          {isLoading ? 'Refreshing' : 'Refresh'}
        </button>
      </div>

      <div className="tabs" role="group" aria-label="Subject">
        {subjects.map(([id, label]) => (
          <button
            key={id}
            type="button"
            className={`tabs__tab${selectedSubject === id ? ' is-current' : ''}`}
            aria-pressed={selectedSubject === id}
            onClick={() => setSelectedSubject(id)}
          >
            {label}
          </button>
        ))}
      </div>

      <div className="dials" style={{ marginBottom: 'var(--space-4)', paddingTop: 0 }}>
        <div className="dial">
          <span className="label">Division</span>
          <span className="seg">
            {LEVELS.map((lvl) => (
              <button
                key={lvl}
                type="button"
                className="btn btn--small"
                aria-pressed={selectedLevel === lvl}
                onClick={() => setSelectedLevel(lvl)}
              >
                {lvl === 'all' ? 'All' : capitalise(lvl)}
              </button>
            ))}
          </span>
        </div>
      </div>

      {isLoading && entries.length === 0 ? (
        <div className="waking" role="status">
          <span className="waking__dot" aria-hidden="true" />
          <span>Loading scores from the sheet. This can take a few seconds.</span>
        </div>
      ) : entries.length === 0 ? (
        <div className="empty">
          <h3>No scores yet</h3>
          <p style={{ margin: '0 auto' }}>Nobody has a score in this subject and division. Answer a few questions and you will be first.</p>
        </div>
      ) : (
        <div className="table-wrap">
          <table className="table">
            <thead>
              <tr>
                <th>Rank</th>
                <th>Name</th>
                <th>Chapter</th>
                <th>Division</th>
                <th className="num">Accuracy</th>
                <th className="num">Points</th>
              </tr>
            </thead>
            <tbody>
              {entries.map((entry) => {
                const isCurrent = entry.username.toLowerCase() === user.username.toLowerCase();
                return (
                  <tr key={entry.username} className={isCurrent ? 'is-you' : undefined}>
                    <td className="rank">{entry.rank}</td>
                    <td>
                      {entry.username}
                      {isCurrent && <span className="label" style={{ marginLeft: 'var(--space-2)' }}>You</span>}
                    </td>
                    <td>{entry.school || 'University High School'}</td>
                    <td>{capitalise(entry.level || 'novice')}</td>
                    <td className="num">{entry.accuracy}%</td>
                    <td className="num">{getSubjectPoints(entry)}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </>
  );
};
