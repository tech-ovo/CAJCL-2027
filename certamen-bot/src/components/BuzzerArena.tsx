import React, { useRef, useEffect } from 'react';
import { useCertamen } from '../context/CertamenContext';
import { FormattedText } from './FormattedText';
import { Category, DifficultyLevel } from '../types/certamen';

export const CATEGORY_NAMES: Record<Category, string> = {
  grammar: 'Grammar',
  mythology: 'Mythology',
  history: 'History',
  culture: 'Culture',
  literature: 'Literature',
};

const LEVELS: (DifficultyLevel | 'all')[] = ['all', 'novice', 'intermediate', 'advanced'];

const capitalise = (s: string) => s.charAt(0).toUpperCase() + s.slice(1);

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

  const nextLabel =
    playMode === 'tossup_boni' && lastEvaluation?.isCorrect && !boniIndex && currentQuestion?.boni?.length
      ? 'On to bonus 1'
      : playMode === 'tossup_boni' && boniIndex === 1 && (currentQuestion?.boni?.length ?? 0) > 1
      ? 'On to bonus 2'
      : 'Next question';

  const accepted = boniIndex ? currentBoni?.answers || [] : currentQuestion?.answers || [];
  const explanation = boniIndex ? currentBoni?.explanation : currentQuestion?.explanation;

  return (
    <section className="with-rail">
      {/* The filters live in the rail, where the site keeps its metadata. */}
      <div className="rail">
        <div className="rail__item">
          <p className="label">Subject</p>
          <ul className="filter">
            {(['all', ...Object.keys(CATEGORY_NAMES)] as (Category | 'all')[]).map((cat) => (
              <li key={cat}>
                <button type="button" aria-pressed={selectedCategory === cat}
                  onClick={() => setSelectedCategory(cat)}>
                  {cat === 'all' ? 'All subjects' : CATEGORY_NAMES[cat]}
                </button>
              </li>
            ))}
          </ul>
        </div>
        <div className="rail__item">
          <p className="label">Level</p>
          <ul className="filter">
            {LEVELS.map((lvl) => (
              <li key={lvl}>
                <button type="button" aria-pressed={selectedDifficulty === lvl}
                  onClick={() => setSelectedDifficulty(lvl)}>
                  {lvl === 'all' ? 'All levels' : capitalise(lvl)}
                </button>
              </li>
            ))}
          </ul>
        </div>
        <div className="rail__item">
          <p className="label">Format</p>
          <ul className="filter">
            <li>
              <button type="button" aria-pressed={playMode === 'tossup_only'}
                onClick={() => setPlayMode('tossup_only')}>Tossups only</button>
            </li>
            <li>
              <button type="button" aria-pressed={playMode === 'tossup_boni'}
                onClick={() => setPlayMode('tossup_boni')}>Tossups and boni</button>
            </li>
          </ul>
        </div>
      </div>

      <div>
        <div className="page-head">
          <div>
            <h1>Certamen Arena</h1>
            <p className="small muted">
              Press <span className="key">Space</span> to start and to buzz,{' '}
              <span className="key">N</span> for the next question.
            </p>
          </div>
          <p className="label">
            {user.stats.currentStreak > 1 && <>Streak <span className="mono">{user.stats.currentStreak}</span> &middot; </>}
            This round <span className="mono">+{scoreThisRound}</span>
          </p>
        </div>

        <div className="tabula stage" aria-live="polite">
          <div className="tabula__row stage__meta">
            {currentQuestion ? (
              <p className="label label--ink">
                {CATEGORY_NAMES[currentQuestion.category] ?? currentQuestion.category} &middot;{' '}
                {capitalise(currentQuestion.difficulty)} &middot;{' '}
                {boniIndex ? `Bonus ${boniIndex}, 5 points` : 'Tossup, 10 points'}
              </p>
            ) : (
              <p className="label">Ready</p>
            )}
            <p className="label">{questions.length} questions</p>
          </div>

          {gameStage === 'idle' ? (
            <div className="stage__idle">
              <button type="button" className="btn btn--primary buzz" onClick={startQuestion}
                disabled={isSyncing && questions.length === 0}>
                {isSyncing && questions.length === 0 ? (
                  <><span className="btn__spinner" aria-hidden="true" />Loading questions</>
                ) : (
                  <>Start <span className="key">Space</span></>
                )}
              </button>
              {syncStatus && <p className="small muted">{syncStatus}</p>}
            </div>
          ) : (
            <>
              {settings.readerMode === 'audio' && isReading ? (
                <p className="pulse-line">
                  <span className="waking__dot" aria-hidden="true" />
                  The moderator is reading aloud. Press Space to buzz.
                </p>
              ) : (
                <p className="stage__text">
                  <FormattedText text={isResult ? fullQuestionText : revealedText} />
                  {isReading && <span className="caret" aria-hidden="true" />}
                </p>
              )}

              <div className="progress" aria-hidden="true">
                <div className="progress__fill" style={{ width: `${progressPercent}%` }} />
              </div>
            </>
          )}

          {isReading && (
            <div className="btn-row">
              <button type="button" className="btn btn--primary buzz" onClick={buzz}>
                Buzz <span className="key">Space</span>
              </button>
              <button type="button" className="btn btn--quiet" onClick={skipQuestion}>
                Skip
              </button>
            </div>
          )}

          {isBuzzed && (
            <div className="field field--wide">
              <label htmlFor="answer">
                Your answer{' '}
                <span className={`timer${timeLeft <= 2 ? ' timer--low' : ''}`}>{timeLeft} s left</span>
              </label>
              <div className="answer-row">
                <input
                  id="answer"
                  ref={inputRef}
                  type="text"
                  autoComplete="off"
                  value={userAnswerInput}
                  onChange={(e) => setUserAnswerInput(e.target.value)}
                  onKeyDown={handleKeyDownInput}
                  placeholder="In Latin or English"
                />
                <button type="button" className="btn btn--primary" onClick={submitAnswer}>
                  Submit
                </button>
              </div>
              <div className="btn-row" style={{ marginTop: 'var(--space-3)' }}>
                <button type="button" className="btn btn--quiet btn--small" onClick={skipQuestion}>
                  Pass
                </button>
              </div>
            </div>
          )}

          {isResult && lastEvaluation && currentQuestion && (
            <div>
              <p className={`verdict ${lastEvaluation.isCorrect ? 'verdict--right' : 'verdict--wrong'}`}>
                <span aria-hidden="true">{lastEvaluation.isCorrect ? '✓' : '✗'}</span>
                <span>{lastEvaluation.isCorrect ? 'Correct' : 'Incorrect'}</span>
                <span className="verdict__latin">{lastEvaluation.isCorrect ? 'Optimē!' : 'Ēheu!'}</span>
              </p>

              <dl className="detail answers">
                <dt>Accepted</dt>
                <dd>
                  {accepted.map((ans, i) => (
                    <React.Fragment key={i}>
                      {i > 0 && ' · '}
                      <span className={lastEvaluation.matchedAnswer === ans ? 'answers__matched' : undefined}>
                        {ans}
                      </span>
                    </React.Fragment>
                  ))}
                </dd>
              </dl>

              {explanation && (
                <p className="note"><FormattedText text={explanation} /></p>
              )}

              <div className="btn-row" style={{ marginTop: 'var(--space-5)' }}>
                <button type="button" className="btn btn--primary" onClick={nextStep}>
                  {nextLabel} <span className="key">N</span>
                </button>
                {!lastEvaluation.isCorrect && (
                  <button type="button" className="btn" onClick={overrideAnswer}
                    title="Count this answer as correct">
                    I was right
                  </button>
                )}
              </div>
            </div>
          )}
        </div>

        <div className="dials">
          <div className="dial">
            <span className="label">Reader</span>
            <span className="seg">
              <button type="button" className="btn btn--small" aria-pressed={settings.readerMode === 'visual'}
                onClick={() => updateSettings({ readerMode: 'visual' })}>Text</button>
              <button type="button" className="btn btn--small" aria-pressed={settings.readerMode === 'audio'}
                onClick={() => updateSettings({ readerMode: 'audio' })}>Voice</button>
            </span>
          </div>

          <label className="dial">
            <span className="label">Pace</span>
            {settings.readerMode === 'visual' ? (
              <input
                type="range"
                min="20"
                max="90"
                step="5"
                // Lower is faster, so the slider runs the other way.
                value={110 - settings.readingSpeed}
                onChange={(e) => updateSettings({ readingSpeed: 110 - Number(e.target.value) })}
              />
            ) : (
              <input
                type="range"
                min="0.75"
                max="1.5"
                step="0.05"
                value={settings.speechRate || 1.0}
                onChange={(e) => updateSettings({ speechRate: Number(e.target.value) })}
              />
            )}
          </label>

          <label className="check">
            <input
              type="checkbox"
              checked={settings.soundEnabled}
              onChange={(e) => updateSettings({ soundEnabled: e.target.checked })}
            />
            Sounds
          </label>

          <label className="check">
            <input
              type="checkbox"
              checked={settings.powerBuzzEnabled}
              onChange={(e) => updateSettings({ powerBuzzEnabled: e.target.checked })}
            />
            Power buzz (15 points for an early buzz)
          </label>
        </div>
      </div>
    </section>
  );
};
