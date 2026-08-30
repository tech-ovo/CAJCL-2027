import React, { useState } from 'react';
import { useCertamen } from '../context/CertamenContext';
import { Category } from '../types/certamen';
import {
  RotateCcw,
  CheckCircle2,
  XCircle,
  Search,
  Trophy,
  Flame,
  Target,
  BarChart3,
} from 'lucide-react';
import { FormattedText } from './FormattedText';

const CATEGORIES: { id: Category; label: string }[] = [
  { id: 'grammar', label: 'Grammar' },
  { id: 'mythology', label: 'Mythology' },
  { id: 'history', label: 'History' },
  { id: 'culture', label: 'Culture' },
  { id: 'literature', label: 'Literature' },
];

export const StatsDashboard: React.FC = () => {
  const { user, resetUserStats } = useCertamen();
  const [historyFilter, setHistoryFilter] = useState<'all' | 'missed' | Category>('all');
  const [searchQuery, setSearchQuery] = useState<string>('');

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

  return (
    <div className="max-w-5xl mx-auto px-4 sm:px-6 py-6 space-y-6">
      {/* Top Header & Reset */}
      <div className="flex items-center justify-between pb-3 border-b border-sky-200/80">
        <div>
          <h2 className="text-xl font-display font-bold text-slate-900 flex items-center gap-2">
            <span>Scholar Analytics</span>
            <span className="text-sky-700 font-editorial italic font-normal text-base">
              • Performance Record
            </span>
          </h2>
          <div className="text-xs text-slate-500 font-editorial italic">
            {user.username} • {user.school || 'University High School'}
          </div>
        </div>

        <button
          onClick={() => {
            if (confirm('Reset all stats and attempt history?')) {
              resetUserStats();
            }
          }}
          className="px-3.5 py-1.5 rounded-xl text-slate-600 hover:text-rose-600 hover:bg-rose-50 border border-sky-200 hover:border-rose-300 text-xs font-semibold flex items-center gap-1.5 transition-all cursor-pointer shadow-xs"
        >
          <RotateCcw className="w-3.5 h-3.5" />
          <span>Reset Stats</span>
        </button>
      </div>

      {/* 4 Metric Cards */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3.5">
        {/* Points */}
        <div className="classical-card rounded-2xl p-4 space-y-1 border border-sky-200/70 shadow-sm">
          <div className="flex items-center justify-between text-slate-500 text-xs">
            <span className="font-semibold uppercase tracking-wider text-[11px]">Points</span>
            <Trophy className="w-4 h-4 text-amber-500" />
          </div>
          <div className="text-3xl font-display font-bold text-slate-900">
            {stats.totalPoints}
          </div>
          <div className="text-xs text-slate-500 font-editorial italic">Total score earned</div>
        </div>

        {/* Accuracy */}
        <div className="classical-card rounded-2xl p-4 space-y-1 border border-sky-200/70 shadow-sm">
          <div className="flex items-center justify-between text-slate-500 text-xs">
            <span className="font-semibold uppercase tracking-wider text-[11px]">Accuracy</span>
            <Target className="w-4 h-4 text-sky-600" />
          </div>
          <div className="text-3xl font-display font-bold text-slate-900">
            {overallAccuracy}%
          </div>
          <div className="text-xs text-slate-500 font-editorial italic">
            {stats.totalCorrect} of {stats.totalAnswered} correct
          </div>
        </div>

        {/* Best Streak */}
        <div className="classical-card rounded-2xl p-4 space-y-1 border border-sky-200/70 shadow-sm">
          <div className="flex items-center justify-between text-slate-500 text-xs">
            <span className="font-semibold uppercase tracking-wider text-[11px]">Best Streak</span>
            <Flame className="w-4 h-4 text-amber-500 fill-amber-500" />
          </div>
          <div className="text-3xl font-display font-bold text-amber-700">
            {stats.bestStreak}
          </div>
          <div className="text-xs text-slate-500 font-editorial italic">
            Current streak: {stats.currentStreak}
          </div>
        </div>

        {/* Attempts */}
        <div className="classical-card rounded-2xl p-4 space-y-1 border border-sky-200/70 shadow-sm">
          <div className="flex items-center justify-between text-slate-500 text-xs">
            <span className="font-semibold uppercase tracking-wider text-[11px]">Attempts</span>
            <BarChart3 className="w-4 h-4 text-sky-600" />
          </div>
          <div className="text-3xl font-display font-bold text-slate-900">
            {stats.totalAnswered}
          </div>
          <div className="text-xs text-slate-500 font-editorial italic">Questions faced</div>
        </div>
      </div>

      {/* Subject Accuracies */}
      <div className="classical-card-elevated rounded-3xl p-6 sm:p-7 space-y-4">
        <div className="text-sm font-bold text-slate-900 font-display uppercase tracking-wider">
          Subject Mastery Breakdown
        </div>
        <div className="space-y-4">
          {CATEGORIES.map(({ id, label }) => {
            const catStats = stats.byCategory[id] || { answered: 0, correct: 0, points: 0 };
            const acc =
              catStats.answered > 0 ? Math.round((catStats.correct / catStats.answered) * 100) : 0;

            return (
              <div key={id} className="space-y-1.5">
                <div className="flex justify-between text-xs">
                  <span className="text-slate-800 font-semibold">{label}</span>
                  <div className="flex items-center gap-3">
                    <span className="text-slate-500 font-editorial text-sm">
                      {catStats.correct}/{catStats.answered} ({catStats.points} pts)
                    </span>
                    <span className="text-sky-800 font-bold w-12 text-right">
                      {acc}%
                    </span>
                  </div>
                </div>
                <div className="w-full bg-sky-100 h-2.5 rounded-full overflow-hidden">
                  <div
                    className="bg-gradient-to-r from-sky-500 to-sky-700 h-full transition-all duration-300 rounded-full"
                    style={{ width: `${acc}%` }}
                  />
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Attempt History Log */}
      <div className="classical-card-elevated rounded-3xl p-6 sm:p-7 space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="text-sm font-bold text-slate-900 font-display uppercase tracking-wider">
            Attempt History Log
          </div>
          <div className="relative w-64">
            <Search className="w-3.5 h-3.5 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search past questions or answers..."
              className="w-full pl-9 pr-3 py-2 bg-white border border-sky-200 focus:border-sky-500 rounded-xl text-xs text-slate-900 placeholder-slate-400 outline-none transition-all shadow-xs"
            />
          </div>
        </div>

        {/* Filter Pills */}
        <div className="flex items-center gap-1.5 flex-wrap pb-2 border-b border-sky-100">
          <button
            onClick={() => setHistoryFilter('all')}
            className={`px-3 py-1 rounded-xl text-xs font-semibold transition-all cursor-pointer ${
              historyFilter === 'all'
                ? 'bg-sky-600 text-white shadow-sm'
                : 'text-slate-600 hover:bg-sky-50'
            }`}
          >
            All ({user.history.length})
          </button>
          <button
            onClick={() => setHistoryFilter('missed')}
            className={`px-3 py-1 rounded-xl text-xs font-semibold transition-all cursor-pointer ${
              historyFilter === 'missed'
                ? 'bg-rose-600 text-white shadow-sm'
                : 'text-slate-600 hover:bg-sky-50'
            }`}
          >
            Missed ({user.history.filter((h) => !h.isCorrect).length})
          </button>
          {CATEGORIES.map(({ id, label }) => (
            <button
              key={id}
              onClick={() => setHistoryFilter(id)}
              className={`px-3 py-1 rounded-xl text-xs font-semibold transition-all cursor-pointer ${
                historyFilter === id
                  ? 'bg-sky-600 text-white shadow-sm'
                  : 'text-slate-600 hover:bg-sky-50'
              }`}
            >
              {label}
            </button>
          ))}
        </div>

        {/* History List */}
        {filteredHistory.length === 0 ? (
          <div className="py-12 text-center text-xs text-slate-500 font-editorial italic text-base">
            No historical attempts recorded yet.
          </div>
        ) : (
          <div className="space-y-2.5 max-h-[420px] overflow-y-auto pr-1">
            {filteredHistory.slice(0, 50).map((attempt, idx) => (
              <div
                key={idx}
                className="p-3.5 rounded-2xl bg-white border border-sky-100 text-xs space-y-2 shadow-xs"
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    {attempt.isCorrect ? (
                      <CheckCircle2 className="w-4 h-4 text-emerald-600 fill-emerald-100" />
                    ) : (
                      <XCircle className="w-4 h-4 text-rose-600 fill-rose-100" />
                    )}
                    <span className="uppercase text-[10px] font-bold text-sky-900 px-2 py-0.5 rounded-full bg-sky-50 border border-sky-200">
                      {attempt.category}
                    </span>
                  </div>
                  <div className="text-xs">
                    <span className="text-slate-500">Answer: </span>
                    <span className={attempt.isCorrect ? 'text-emerald-700 font-bold' : 'text-rose-700 font-bold'}>
                      {attempt.userAnswer || '[Passed]'}
                    </span>
                  </div>
                </div>

                <div className="text-slate-900 font-editorial text-sm leading-relaxed">
                  <FormattedText text={attempt.questionText} />
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};
