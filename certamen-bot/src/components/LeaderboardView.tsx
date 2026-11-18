import React, { useState, useEffect } from 'react';
import { useCertamen } from '../context/CertamenContext';
import { Category, ChapterStanding, DifficultyLevel } from '../types/certamen';
import { fetchLeaderboardFromTurso, subjectPoints } from '../services/tursoService';
import { CATEGORY_NAMES } from './BuzzerArena';

const LEVELS: (DifficultyLevel | 'all')[] = ['all', 'novice', 'intermediate', 'advanced'];
const capitalise = (s: string) => s.charAt(0).toUpperCase() + s.slice(1);
const sameChapter = (a: string, b: string) => a.trim().toLowerCase() === b.trim().toLowerCase();

/* Chapters ranked by the XP their players have earned together. There is
 * deliberately no individual scoreboard. */
export const LeaderboardView: React.FC = () => {
  const { user, settings } = useCertamen();
  const [selectedSubject, setSelectedSubject] = useState<Category | 'all'>('all');
  const [selectedLevel, setSelectedLevel] = useState<DifficultyLevel | 'all'>('all');
  const [entries, setEntries] = useState<ChapterStanding[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(false);

  const loadLeaderboard = async () => {
    setIsLoading(true);
    try {
      setEntries(await fetchLeaderboardFromTurso(
        settings.tursoUrl,
        settings.tursoAuthToken,
        selectedSubject,
        selectedLevel
      ));
    } catch (err) {
      console.error('Failed to load leaderboard:', err);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    loadLeaderboard();
  }, [selectedSubject, selectedLevel, settings.tursoUrl, settings.tursoAuthToken, user.stats.totalPoints]);

  const subjects = [['all', 'All subjects'], ...Object.entries(CATEGORY_NAMES)] as [Category | 'all', string][];

  return (
    <>
      <div className="page-head">
        <div>
          <h1>Leaderboard</h1>
          <p className="small muted">Chapters ranked by the XP their members have earned in the arena.</p>
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
          <span>Loading scores from the database...</span>
        </div>
      ) : entries.length === 0 ? (
        <div className="empty">
          <h3>No scores yet</h3>
          <p style={{ margin: '0 auto' }}>No chapter has XP in this subject and division yet. Answer a few questions to put yours on the board.</p>
        </div>
      ) : (
        <div className="table-wrap">
          <table className="table">
            <thead>
              <tr>
                <th>Rank</th>
                <th>Chapter</th>
                <th className="num">Players</th>
                <th className="num">Accuracy</th>
                <th className="num">XP</th>
              </tr>
            </thead>
            <tbody>
              {entries.map((entry) => {
                const isYours = !!user.school && sameChapter(entry.school, user.school);
                return (
                  <tr key={entry.school.toLowerCase()} className={isYours ? 'is-you' : undefined}>
                    <td className="rank">{entry.rank}</td>
                    <td>
                      {entry.school}
                      {isYours && <span className="label" style={{ marginLeft: 'var(--space-2)' }}>Yours</span>}
                    </td>
                    <td className="num">{entry.players}</td>
                    <td className="num">{entry.accuracy}%</td>
                    <td className="num">{subjectPoints(entry, selectedSubject)}</td>
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
