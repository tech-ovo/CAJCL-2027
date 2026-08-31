import React, { useRef, useEffect } from 'react';
import { useCertamen } from '../context/CertamenContext';
import {
  Play,
  CheckCircle2,
  XCircle,
  ExternalLink,
  Flame,
  Radio,
  Loader2,
  Zap,
  Check,
  ArrowRight,
} from 'lucide-react';
import { FormattedText } from './FormattedText';
import { Category, DifficultyLevel } from '../types/certamen';

const CATEGORY_NAMES: Record<Category, string> = {
  grammar: 'Grammar',
  mythology: 'Mythology',
  history: 'History',
  culture: 'Culture',
  literature: 'Literature',
};

export const BuzzerArena: React.FC = () => {
  const {
    currentQuestion,
    currentBoni,
    boniIndex,
    gameStage,
    revealedText,
    fullQuestionText,
    timeLeft,
    userAnswerInput,
    setUserAnswerInput,
    lastEvaluation,
    selectedCategory,
    setSelectedCategory,
    selectedDifficulty,
    setSelectedDifficulty,
    playMode,
    setPlayMode,
    startQuestion,
    buzz,
    submitAnswer,
    skipQuestion,
    overrideAnswer,
    nextStep,
    user,
    settings,
    updateSettings,
    isSyncing,
    syncStatus,
    scoreThisRound,
    questions,
  } = useCertamen();

  const isReading =
    gameStage === 'reading_tossup' ||
    gameStage === 'reading_boni1' ||
    gameStage === 'reading_boni2';
  const isBuzzed =
    gameStage === 'buzzed_tossup' ||
    gameStage === 'buzzed_boni1' ||
    gameStage === 'buzzed_boni2';
  const isResult =
    gameStage === 'result_tossup' ||
    gameStage === 'result_boni1' ||
    gameStage === 'result_boni2' ||
    gameStage === 'round_summary';

  const progressPercent =
    fullQuestionText.length > 0
      ? Math.min(100, Math.round((revealedText.length / fullQuestionText.length) * 100))
      : 0;


  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (isBuzzed) {
      setTimeout(() => {
        inputRef.current?.focus();
      }, 50);
    }
  }, [isBuzzed]);

  const handleKeyDownInput = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      submitAnswer();
    }
  };

  return (
    <div className="max-w-5xl mx-auto px-4 sm:px-6 py-6 space-y-6">
      {/* UHSJCL Hero Banner */}
      <div className="relative rounded-3xl overflow-hidden shadow-md border border-sky-200/80 bg-white">
        <div className="relative h-40 sm:h-48 w-full overflow-hidden">
          <img
            src="./assets/hero_colosseum_starry.jpg"
            alt="UHSJCL Colosseum & Sky"
            className="w-full h-full object-cover object-center"
          />
          <div className="absolute inset-0 bg-gradient-to-r from-sky-950/75 via-sky-900/40 to-transparent" />
          <div className="absolute inset-0 bg-gradient-to-t from-black/50 via-transparent to-transparent" />

          {/* Banner Content */}
          <div className="absolute inset-0 p-6 sm:p-8 flex flex-col justify-between">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <span className="font-display font-black text-2xl sm:text-3xl tracking-widest text-white drop-shadow-md">
                  UHSJCL
                </span>
                <span className="text-sky-200 text-sm sm:text-base font-serif">|</span>
                <span className="text-sky-100 font-editorial text-sm sm:text-base italic">
                  Classical League
                </span>
              </div>

              {/* Community links from brand image */}
              <div className="flex items-center gap-2">
                <a
                  href="https://discord.gg/cgkYcWYGYj"
                  target="_blank"
                  rel="noreferrer"
                  className="hidden sm:inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-full bg-white/90 hover:bg-white text-sky-950 text-xs font-semibold backdrop-blur-md shadow-sm transition-all hover:scale-105"
                >
                  <span>Join our Discord!</span>
                  <ExternalLink className="w-3 h-3 text-sky-700" />
                </a>
                <a
                  href="https://instagram.com/uhsjcl"
                  target="_blank"
                  rel="noreferrer"
                  className="hidden sm:inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-full bg-white/90 hover:bg-white text-sky-950 text-xs font-semibold backdrop-blur-md shadow-sm transition-all hover:scale-105"
                >
                  <span>Follow @uhsjcl</span>
                  <ExternalLink className="w-3 h-3 text-sky-700" />
                </a>
              </div>
            </div>

            <div>
              <h1 className="font-display font-bold text-2xl sm:text-3xl text-white drop-shadow-md tracking-wide">
                Certamen Arena
              </h1>
              <p className="text-sky-100 font-editorial text-sm sm:text-base italic max-w-xl drop-shadow">
                Practice all subjects for this fast-paced buzzer game.
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* Filter & Configuration Bar */}
      <div className="flex flex-wrap items-center justify-between gap-3 bg-white/90 backdrop-blur-md p-3.5 rounded-2xl border border-sky-200/70 shadow-sm">
        {/* Subject Pills */}
        <div className="flex items-center gap-1.5 flex-wrap">
          <button
            onClick={() => setSelectedCategory('all')}
            className={`px-3 py-1.5 rounded-xl text-xs font-semibold transition-all cursor-pointer ${
              selectedCategory === 'all'
                ? 'bg-sky-600 text-white shadow-sm shadow-sky-600/30'
                : 'bg-sky-50 text-slate-700 hover:bg-sky-100 border border-sky-200/60'
            }`}
          >
            All Subjects
          </button>
          {(['grammar', 'mythology', 'history', 'culture', 'literature'] as Category[]).map((cat) => (
            <button
              key={cat}
              onClick={() => setSelectedCategory(cat)}
              className={`px-3 py-1.5 rounded-xl text-xs font-semibold capitalize transition-all cursor-pointer ${
                selectedCategory === cat
                  ? 'bg-sky-600 text-white shadow-sm shadow-sky-600/30'
                  : 'bg-sky-50 text-slate-700 hover:bg-sky-100 border border-sky-200/60'
              }`}
            >
              {CATEGORY_NAMES[cat]}
            </button>
          ))}
        </div>

        {/* Level & Mode Selectors */}
        <div className="flex items-center gap-2">
          <div className="flex items-center gap-1 bg-sky-50 p-1 rounded-xl border border-sky-200/60">
            {(['all', 'novice', 'intermediate', 'advanced'] as (DifficultyLevel | 'all')[]).map((lvl) => (
              <button
                key={lvl}
                onClick={() => setSelectedDifficulty(lvl)}
                className={`px-2.5 py-1 rounded-lg text-xs font-medium capitalize transition-all cursor-pointer ${
                  selectedDifficulty === lvl
                    ? 'bg-white text-sky-900 font-bold shadow-sm'
                    : 'text-slate-500 hover:text-slate-800'
                }`}
              >
                {lvl}
              </button>
            ))}
          </div>

          <div className="flex items-center gap-1 bg-sky-50 p-1 rounded-xl border border-sky-200/60">
            <button
              onClick={() => setPlayMode('tossup_only')}
              className={`px-2.5 py-1 rounded-lg text-xs font-medium transition-all cursor-pointer ${
                playMode === 'tossup_only'
                  ? 'bg-white text-sky-900 font-bold shadow-sm'
                  : 'text-slate-500 hover:text-slate-800'
              }`}
            >
              Tossups
            </button>
            <button
              onClick={() => setPlayMode('tossup_boni')}
              className={`px-2.5 py-1 rounded-lg text-xs font-medium transition-all cursor-pointer ${
                playMode === 'tossup_boni'
                  ? 'bg-white text-sky-900 font-bold shadow-sm'
                  : 'text-slate-500 hover:text-slate-800'
              }`}
            >
              + Boni
            </button>
          </div>
        </div>
      </div>

      {/* Classical Arena Stage Card */}
      <div className="classical-card-elevated rounded-3xl p-6 sm:p-8 space-y-6 relative overflow-hidden">
        {/* Stage Header */}
        <div className="flex items-center justify-between border-b border-sky-100 pb-4">
          <div className="flex items-center gap-2.5">
            {currentQuestion ? (
              <>
                <span className="px-3 py-1 rounded-full bg-sky-100 text-sky-900 text-xs font-bold uppercase tracking-wider border border-sky-200">
                  {currentQuestion.category}
                </span>
                <span className="text-slate-300">•</span>
                <span className="capitalize text-slate-600 font-medium text-xs">
                  {currentQuestion.difficulty} Level
                </span>
                <span className="text-slate-300">•</span>
                <span className="text-slate-600 font-medium text-xs">
                  {boniIndex ? `Boni #${boniIndex} (5 pts)` : 'Tossup (10 pts)'}
                </span>
              </>
            ) : (
              <span className="text-slate-500 text-xs font-medium flex items-center gap-1.5">
                <span className="w-2 h-2 rounded-full bg-sky-500 animate-ping" />
                <span>Certamen Arena Ready</span>
              </span>
            )}
          </div>

          <div className="flex items-center gap-3">
            {user.stats.currentStreak > 1 && (
              <span className="flex items-center gap-1 px-3 py-1 rounded-full bg-amber-50 border border-amber-300 text-amber-900 text-xs font-bold shadow-sm">
                <Flame className="w-3.5 h-3.5 fill-amber-500 text-amber-600" />
                <span>{user.stats.currentStreak} Streak</span>
              </span>
            )}
            <span className="text-slate-800 font-bold text-xs">
              +{scoreThisRound} pts
            </span>
          </div>
        </div>

        {/* Question Text Display Area */}
        <div className="min-h-[160px] flex flex-col justify-center py-2">
          {gameStage === 'idle' ? (
            <div className="text-center py-8 space-y-4">
              <button
                onClick={startQuestion}
                disabled={isSyncing && questions.length === 0}
                className="px-8 py-3.5 rounded-2xl bg-gradient-to-r from-sky-600 to-sky-700 hover:from-sky-500 hover:to-sky-600 disabled:opacity-60 text-white font-bold text-xs tracking-wider uppercase transition-all shadow-md shadow-sky-600/30 flex items-center gap-2.5 mx-auto cursor-pointer hover:scale-105 active:scale-95"
              >
                {isSyncing ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin text-white" />
                    <span>Syncing Questions...</span>
                  </>
                ) : (
                  <>
                    <Play className="w-4 h-4 fill-white" />
                    <span>Start Question (Space)</span>
                  </>
                )}
              </button>
              {syncStatus && (
                <p className="text-xs text-slate-500 font-editorial italic">{syncStatus}</p>
              )}
            </div>
          ) : (
            <div className="space-y-4">
              {/* Audio speech active pulse wave */}
              {settings.readerMode === 'audio' && isReading && (
                <div className="flex items-center justify-center gap-2 py-2 text-xs text-sky-900 font-medium bg-sky-50 rounded-xl border border-sky-200">
                  <Radio className="w-4 h-4 animate-pulse text-sky-600" />
                  <span>Moderator Reading Aloud... Press Space to Buzz</span>
                </div>
              )}

              {/* Text Typewriter Reveal */}
              {(settings.readerMode === 'visual' || !isReading) && (
                <div className="text-xl sm:text-2xl font-editorial text-slate-900 leading-relaxed font-normal">
                  <FormattedText text={isResult ? fullQuestionText : revealedText} />
                  {isReading && settings.readerMode === 'visual' && (
                    <span className="inline-block w-2 h-5 ml-1 bg-sky-600 animate-pulse align-middle rounded-sm" />
                  )}
                </div>
              )}

              {/* Progress Bar */}
              <div className="w-full bg-sky-100 h-1.5 rounded-full overflow-hidden">
                <div
                  className="bg-sky-600 h-full transition-all duration-100"
                  style={{ width: `${progressPercent}%` }}
                />
              </div>
            </div>
          )}
        </div>

        {/* Action States */}
        {gameStage !== 'idle' && (
          <div className="pt-2">
            {/* Reading State: Buzz In Button */}
            {isReading && (
              <div className="flex items-center justify-center gap-6">
                <button
                  onClick={buzz}
                  className="px-10 py-4 rounded-2xl bg-gradient-to-r from-red-600 to-rose-600 hover:from-red-500 hover:to-rose-500 text-white font-extrabold text-sm tracking-widest uppercase shadow-xl shadow-red-600/30 ring-4 ring-red-100 active:scale-95 transition-all flex items-center gap-2.5 cursor-pointer hover:scale-105"
                >
                  <Zap className="w-5 h-5 fill-white" />
                  <span>BUZZ (SPACE)</span>
                </button>
                <button
                  onClick={skipQuestion}
                  className="text-xs text-slate-500 hover:text-slate-800 px-3 py-1.5 rounded-lg hover:bg-sky-50 transition-all cursor-pointer"
                >
                  Skip Question
                </button>
              </div>
            )}

            {/* Buzzed State: Input Box & Countdown */}
            {isBuzzed && (
              <div className="space-y-3 p-5 rounded-2xl bg-sky-50/90 border border-sky-200">
                <div className="flex items-center justify-between text-xs">
                  <span className="text-sky-950 font-bold">Enter your answer:</span>
                  <span className="text-red-700 font-bold px-2.5 py-0.5 rounded-full bg-red-100 border border-red-200">
                    {timeLeft}s remaining
                  </span>
                </div>

                <div className="flex gap-2">
                  <input
                    ref={inputRef}
                    type="text"
                    value={userAnswerInput}
                    onChange={(e) => setUserAnswerInput(e.target.value)}
                    onKeyDown={handleKeyDownInput}
                    placeholder="Type Latin or English answer..."
                    className="flex-1 bg-white border-2 border-sky-400 focus:border-sky-600 rounded-xl px-4 py-3 text-slate-900 text-sm outline-none font-medium transition-all shadow-sm"
                  />
                  <button
                    onClick={submitAnswer}
                    className="px-6 py-3 bg-sky-600 hover:bg-sky-700 text-white font-bold text-xs rounded-xl transition-all shadow-sm cursor-pointer"
                  >
                    Submit
                  </button>
                </div>

                <div className="flex justify-end">
                  <button
                    onClick={skipQuestion}
                    className="text-xs text-slate-500 hover:text-slate-800 transition-colors cursor-pointer"
                  >
                    Pass on this question
                  </button>
                </div>
              </div>
            )}

            {/* Result State */}
            {isResult && lastEvaluation && currentQuestion && (
              <div className="space-y-4 pt-2 p-5 rounded-2xl bg-sky-50/80 border border-sky-200/80">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2.5">
                    {lastEvaluation.isCorrect ? (
                      <CheckCircle2 className="w-5 h-5 text-emerald-600 fill-emerald-100" />
                    ) : (
                      <XCircle className="w-5 h-5 text-rose-600 fill-rose-100" />
                    )}
                    <span
                      className={`text-sm font-bold ${
                        lastEvaluation.isCorrect ? 'text-emerald-800' : 'text-rose-800'
                      }`}
                    >
                      {lastEvaluation.isCorrect ? 'Optime! Correct' : 'Eheu! Incorrect'}
                    </span>
                  </div>

                  {!lastEvaluation.isCorrect && (
                    <button
                      onClick={overrideAnswer}
                      className="px-3 py-1.5 text-xs text-slate-700 hover:text-sky-900 border border-sky-300 bg-white rounded-lg transition-all flex items-center gap-1.5 shadow-xs cursor-pointer"
                    >
                      <Check className="w-3.5 h-3.5 text-emerald-600" />
                      <span>Judge Override</span>
                    </button>
                  )}
                </div>

                {/* Accepted Answers Chips */}
                <div className="text-xs space-y-1.5">
                  <span className="text-slate-600 font-medium">Accepted Answers: </span>
                  <div className="flex flex-wrap gap-1.5 pt-0.5">
                    {(boniIndex ? currentBoni?.answers || [] : currentQuestion.answers).map((ans, i) => (
                      <span
                        key={i}
                        className={`px-3 py-1 rounded-lg text-xs ${
                          lastEvaluation.matchedAnswer === ans
                            ? 'bg-emerald-100 text-emerald-900 border border-emerald-300 font-bold'
                            : 'bg-white text-slate-800 border border-sky-200'
                        }`}
                      >
                        {ans}
                      </span>
                    ))}
                  </div>
                </div>

                {/* Explanation / Translation Note */}
                {(currentQuestion.explanation || currentBoni?.explanation) && (
                  <div className="text-xs text-slate-700 bg-white p-3.5 rounded-xl border border-sky-200 font-editorial text-sm italic">
                    <FormattedText
                      text={
                        boniIndex
                          ? currentBoni?.explanation || ''
                          : currentQuestion.explanation || ''
                      }
                    />
                  </div>
                )}

                {/* Next Step Button */}
                <div className="flex justify-end pt-1">
                  <button
                    onClick={nextStep}
                    className="px-6 py-2.5 rounded-xl bg-gradient-to-r from-sky-600 to-sky-700 hover:from-sky-500 hover:to-sky-600 text-white font-bold text-xs transition-all flex items-center gap-2 shadow-md cursor-pointer hover:scale-105"
                  >
                    <span>
                      {playMode === 'tossup_boni' && lastEvaluation.isCorrect && !boniIndex && currentQuestion.boni?.length
                        ? 'Advance to Boni 1'
                        : playMode === 'tossup_boni' && boniIndex === 1 && currentQuestion.boni?.length && currentQuestion.boni.length > 1
                        ? 'Advance to Boni 2'
                        : 'Next Question (N)'}
                    </span>
                    <ArrowRight className="w-3.5 h-3.5" />
                  </button>
                </div>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Speed & Power Buzz Controls */}
      <div className="flex items-center justify-between text-xs text-slate-600 px-2 bg-white/80 p-3 rounded-2xl border border-sky-200/60 shadow-xs">
        <div className="flex items-center gap-3">
          <span className="font-medium">Reading Pace:</span>
          {settings.readerMode === 'visual' ? (
            <input
              type="range"
              min="20"
              max="90"
              step="5"
              value={settings.readingSpeed}
              onChange={(e) => updateSettings({ readingSpeed: Number(e.target.value) })}
              className="w-28 accent-sky-600 cursor-pointer"
            />
          ) : (
            <input
              type="range"
              min="0.75"
              max="1.5"
              step="0.05"
              value={settings.speechRate || 1.0}
              onChange={(e) => updateSettings({ speechRate: Number(e.target.value) })}
              className="w-28 accent-sky-600 cursor-pointer"
            />
          )}
        </div>

        <label className="flex items-center gap-2 cursor-pointer text-slate-700 hover:text-sky-800 transition-colors font-medium">
          <input
            type="checkbox"
            checked={settings.powerBuzzEnabled}
            onChange={(e) => updateSettings({ powerBuzzEnabled: e.target.checked })}
            className="rounded accent-sky-600"
          />
          <span>Power Buzz (+15 pts before pause)</span>
        </label>
      </div>
    </div>
  );
};
