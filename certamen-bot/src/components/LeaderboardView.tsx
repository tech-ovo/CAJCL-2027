import React, { useState, useEffect } from 'react';
import { useCertamen } from '../context/CertamenContext';
import { Category, DifficultyLevel, LeaderboardEntry } from '../types/certamen';
import { fetchLeaderboardFromCloud } from '../services/googleSheetsService';
import { RefreshCw, Crown } from 'lucide-react';

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

  return (
    <div className="max-w-5xl mx-auto px-4 sm:px-6 py-6 space-y-6">
      {/* Controls Bar */}
      <div className="flex flex-wrap items-center justify-between gap-3 pb-3 border-b border-sky-200/80">
        {/* Subject Pills */}
        <div className="flex items-center gap-1.5 flex-wrap">
          <button
            onClick={() => setSelectedSubject('all')}
            className={`px-3 py-1.5 rounded-xl text-xs font-semibold transition-all cursor-pointer ${
              selectedSubject === 'all'
                ? 'bg-sky-600 text-white shadow-sm'
                : 'bg-sky-50 text-slate-700 hover:bg-sky-100 border border-sky-200/60'
            }`}
          >
            All Standings
          </button>
          {(['grammar', 'mythology', 'history', 'culture', 'literature'] as Category[]).map((cat) => (
            <button
              key={cat}
              onClick={() => setSelectedSubject(cat)}
              className={`px-3 py-1.5 rounded-xl text-xs font-semibold capitalize transition-all cursor-pointer ${
                selectedSubject === cat
                  ? 'bg-sky-600 text-white shadow-sm'
                  : 'bg-sky-50 text-slate-700 hover:bg-sky-100 border border-sky-200/60'
              }`}
            >
              {cat}
            </button>
          ))}
        </div>

        {/* Division & Refresh */}
        <div className="flex items-center gap-2">
          <div className="flex items-center gap-1 bg-sky-50 p-1 rounded-xl border border-sky-200/60">
            {(['all', 'novice', 'intermediate', 'advanced'] as (DifficultyLevel | 'all')[]).map((lvl) => (
              <button
                key={lvl}
                onClick={() => setSelectedLevel(lvl)}
                className={`px-2.5 py-1 rounded-lg text-xs font-medium capitalize transition-all cursor-pointer ${
                  selectedLevel === lvl
                    ? 'bg-white text-sky-900 font-bold shadow-sm'
                    : 'text-slate-500 hover:text-slate-800'
                }`}
              >
                {lvl}
              </button>
            ))}
          </div>

          <button
            onClick={loadLeaderboard}
            disabled={isLoading}
            className="p-2 rounded-xl bg-white hover:bg-sky-50 text-slate-600 hover:text-sky-900 border border-sky-200 transition-all cursor-pointer shadow-xs"
            title="Refresh Leaderboard"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isLoading ? 'animate-spin text-sky-600' : ''}`} />
          </button>
        </div>
      </div>

      {/* Standings Table Card */}
      <div className="classical-card-elevated rounded-3xl overflow-hidden shadow-md">
        {isLoading && entries.length === 0 ? (
          <div className="py-16 text-center text-xs text-slate-500 font-editorial italic text-base">
            Loading scholar records from Google Sheets...
          </div>
        ) : entries.length === 0 ? (
          <div className="py-16 text-center text-xs text-slate-500 font-editorial italic text-base">
            No tournament records found for this category.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs border-collapse">
              <thead>
                <tr className="border-b border-sky-100 bg-sky-50/80 text-sky-950 font-display uppercase tracking-wider text-[11px]">
                  <th className="py-3.5 px-4 w-14 text-center">Rank</th>
                  <th className="py-3.5 px-4">Scholar</th>
                  <th className="py-3.5 px-4">School / Chapter</th>
                  <th className="py-3.5 px-4 text-center">Division</th>
                  <th className="py-3.5 px-4 text-right">Accuracy</th>
                  <th className="py-3.5 px-4 text-right">Points</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-sky-100 text-slate-900">
                {entries.map((entry) => {
                  const isCurrent = entry.username.toLowerCase() === user.username.toLowerCase();
                  const isTop1 = entry.rank === 1;
                  const isTop2 = entry.rank === 2;
                  const isTop3 = entry.rank === 3;

                  return (
                    <tr
                      key={entry.username}
                      className={`transition-colors ${
                        isCurrent
                          ? 'bg-sky-100/60 font-semibold'
                          : 'hover:bg-sky-50/50'
                      }`}
                    >
                      {/* Rank */}
                      <td className="py-3.5 px-4 text-center">
                        {isTop1 ? (
                          <div className="flex items-center justify-center">
                            <span className="w-6 h-6 rounded-full bg-amber-100 text-amber-900 border border-amber-300 flex items-center justify-center text-xs font-bold shadow-xs">
                              1
                            </span>
                          </div>
                        ) : isTop2 ? (
                          <div className="flex items-center justify-center">
                            <span className="w-6 h-6 rounded-full bg-slate-200 text-slate-800 border border-slate-300 flex items-center justify-center text-xs font-bold shadow-xs">
                              2
                            </span>
                          </div>
                        ) : isTop3 ? (
                          <div className="flex items-center justify-center">
                            <span className="w-6 h-6 rounded-full bg-amber-50 text-amber-800 border border-amber-200 flex items-center justify-center text-xs font-bold shadow-xs">
                              3
                            </span>
                          </div>
                        ) : (
                          <span className="text-slate-500 font-medium">{entry.rank}</span>
                        )}
                      </td>

                      {/* Username */}
                      <td className="py-3.5 px-4">
                        <div className="flex items-center gap-2">
                          {isTop1 && <Crown className="w-4 h-4 text-amber-500 fill-amber-400" />}
                          <span className={isCurrent ? 'text-sky-900 font-bold' : 'text-slate-900 font-medium'}>
                            {entry.username}
                          </span>
                          {isCurrent && (
                            <span className="text-[10px] px-2 py-0.5 rounded-full bg-sky-600 text-white font-bold">
                              YOU
                            </span>
                          )}
                        </div>
                      </td>

                      {/* School */}
                      <td className="py-3.5 px-4 text-slate-600 font-editorial text-sm">
                        {entry.school || 'University High School'}
                      </td>

                      {/* Division */}
                      <td className="py-3.5 px-4 text-center capitalize text-slate-600">
                        <span className="px-2.5 py-0.5 rounded-full bg-sky-50 border border-sky-200 text-[11px] font-medium">
                          {entry.level || 'Novice'}
                        </span>
                      </td>

                      {/* Accuracy */}
                      <td className="py-3.5 px-4 text-right text-slate-700 font-medium">
                        {entry.accuracy}%
                      </td>

                      {/* Points */}
                      <td className="py-3.5 px-4 text-right font-display font-bold text-sky-900 text-sm">
                        {getSubjectPoints(entry)}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
};
