import React, { createContext, useContext, useState, useEffect, useCallback, useRef, useMemo } from 'react';
import {
  Category,
  DifficultyLevel,
  PlayMode,
  Question,
  UserProfile,
  UserStats,
  QuestionAttemptLog,
  AppSettings,
} from '../types/certamen';
import { INITIAL_QUESTION_BANK, flattenQuestions } from '../data/questionBank';
import { checkAnswer, MatchResult } from '../services/answerChecker';
import { soundService } from '../services/audioService';
import {
  syncUserToTurso,
  logAttemptToTurso,
  loginUserFromTurso,
  fetchQuestionsFromTurso,
} from '../services/tursoService';
import confetti from 'canvas-confetti';

const STORAGE_KEY_USER = 'certamen_master_user_v1';
const STORAGE_KEY_SETTINGS = 'certamen_master_settings_v1';
const STORAGE_KEY_CUSTOM_QUESTIONS = 'certamen_master_custom_questions_v1';

export const INITIAL_USER_STATS: UserStats = {
  totalPoints: 0,
  totalAnswered: 0,
  totalCorrect: 0,
  currentStreak: 0,
  bestStreak: 0,
  powerBuzzes: 0,
  averageBuzzPercentage: 0,
  totalBuzzes: 0,
  byCategory: {
    grammar: { answered: 0, correct: 0, points: 0 },
    mythology: { answered: 0, correct: 0, points: 0 },
    history: { answered: 0, correct: 0, points: 0 },
    culture: { answered: 0, correct: 0, points: 0 },
    literature: { answered: 0, correct: 0, points: 0 },
  },
};

// Confetti draws on a canvas, so it cannot take var(). Read the palette from
// the site's tokens.css at the moment of firing, so a re-skin reaches it too.
function brandColours(): string[] | undefined {
  const css = getComputedStyle(document.documentElement);
  const colours = ['--purple', '--gold', '--lavender', '--blue']
    .map((name) => css.getPropertyValue(name).trim())
    .filter(Boolean);
  return colours.length ? colours : undefined;
}

const DEFAULT_SETTINGS: AppSettings = {
  readerMode: 'visual',
  readingSpeed: 45, // ms per character (or ~250-300 wpm)
  timerDuration: 6, // 6 seconds to answer after buzzing
  soundEnabled: true,
  confettiEnabled: true,
  powerBuzzEnabled: true,
  speechRate: 1.0,
  tursoUrl: (typeof import.meta !== 'undefined' && (import.meta as any).env?.VITE_TURSO_DATABASE_URL) || '',
  tursoAuthToken: (typeof import.meta !== 'undefined' && (import.meta as any).env?.VITE_TURSO_AUTH_TOKEN) || '',
  theme: 'classical-gold',
};

export type GameStage =
  | 'idle'
  | 'reading_tossup'
  | 'buzzed_tossup'
  | 'result_tossup'
  | 'round_summary';

interface CertamenContextType {
  user: UserProfile;
  settings: AppSettings;
  questions: Question[];
  currentQuestion: Question | null;
  currentBoni: null;
  boniIndex: null;
  gameStage: GameStage;
  revealedText: string;
  fullQuestionText: string;
  isBuzzActive: boolean;
  timeLeft: number;
  userAnswerInput: string;
  lastEvaluation: MatchResult | null;
  lastAttemptLog: QuestionAttemptLog | null;
  selectedCategory: Category | 'all';
  selectedDifficulty: DifficultyLevel | 'all';
  playMode: PlayMode;
  isSyncing: boolean;
  syncStatus: string;
  scoreThisRound: number;

  // Actions
  startQuestion: () => void;
  buzz: () => void;
  setUserAnswerInput: (val: string) => void;
  submitAnswer: () => void;
  skipQuestion: () => void;
  overrideAnswer: () => void;
  nextStep: () => void;
  setSelectedCategory: (cat: Category | 'all') => void;
  setSelectedDifficulty: (diff: DifficultyLevel | 'all') => void;
  setPlayMode: (mode: PlayMode) => void;
  updateSettings: (newSettings: Partial<AppSettings>) => void;
  loginUser: (username: string, pin: string, school?: string) => Promise<boolean>;
  logoutUser: () => void;
  addCustomQuestion: (q: Question) => void;
  deleteCustomQuestion: (id: string) => void;
  importQuestions: (newQuestions: Question[]) => number;
  resetUserStats: () => void;
  triggerManualSync: () => Promise<void>;
  syncQuestionsFromCloud: () => Promise<number>;
}

const CertamenContext = createContext<CertamenContextType | undefined>(undefined);

export const CertamenProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  // 1. Settings State
  const [settings, setSettings] = useState<AppSettings>(() => {
    try {
      const saved = localStorage.getItem(STORAGE_KEY_SETTINGS);
      return saved ? { ...DEFAULT_SETTINGS, ...JSON.parse(saved) } : DEFAULT_SETTINGS;
    } catch {
      return DEFAULT_SETTINGS;
    }
  });

  // 2. Questions Bank State
  const [customQuestions, setCustomQuestions] = useState<Question[]>(() => {
    try {
      const saved = localStorage.getItem(STORAGE_KEY_CUSTOM_QUESTIONS);
      return saved ? JSON.parse(saved) : [];
    } catch {
      return [];
    }
  });

  // 3. User Profile State
  const [user, setUser] = useState<UserProfile>(() => {
    try {
      const saved = localStorage.getItem(STORAGE_KEY_USER);
      if (saved) {
        const parsed = JSON.parse(saved);
        return {
          username: parsed.username || 'Discipulus',
          pin: parsed.pin || '1234',
          school: parsed.school || 'Roma Antiqua Academy',
          level: parsed.level || 'novice',
          stats: parsed.stats || INITIAL_USER_STATS,
          history: parsed.history || [],
        };
      }
    } catch {
      // ignore
    }
    return {
      username: 'Discipulus',
      pin: '1234',
      school: 'Roma Antiqua Academy',
      level: 'novice',
      stats: INITIAL_USER_STATS,
      history: [],
    };
  });

  // 4. Session / Game Controls
  const [selectedCategory, setSelectedCategoryState] = useState<Category | 'all'>('all');
  const [selectedDifficulty, setSelectedDifficultyState] = useState<DifficultyLevel | 'all'>('all');
  const [playMode, setPlayMode] = useState<PlayMode>('tossup_only');

  const [currentQuestion, setCurrentQuestion] = useState<Question | null>(null);
  const [gameStage, setGameStage] = useState<GameStage>('idle');
  const [revealedText, setRevealedText] = useState<string>('');
  const [userAnswerInput, setUserAnswerInput] = useState<string>('');
  const [timeLeft, setTimeLeft] = useState<number>(0);
  const [lastEvaluation, setLastEvaluation] = useState<MatchResult | null>(null);
  const [lastAttemptLog, setLastAttemptLog] = useState<QuestionAttemptLog | null>(null);
  const [isSyncing, setIsSyncing] = useState<boolean>(false);
  const [syncStatus, setSyncStatus] = useState<string>('');
  const [scoreThisRound, setScoreThisRound] = useState<number>(0);

  // Timers and refs
  const typewriterTimerRef = useRef<NodeJS.Timeout | null>(null);
  const countdownTimerRef = useRef<NodeJS.Timeout | null>(null);
  const unplayedQueueRef = useRef<string[]>([]);
  const isFetchingQuestionsRef = useRef<boolean>(false);
  const seenQuestionIdsRef = useRef<Set<string>>(
    new Set(user.history ? user.history.map((h) => h.questionId).filter(Boolean) : [])
  );

  // Base flattened questions - all boni treated as standalone tossup questions!
  const baseQuestions = useMemo(() => flattenQuestions(INITIAL_QUESTION_BANK), []);

  // Merge built-in questions and custom questions so no subjects are ever missing
  const allQuestions = useMemo(() => {
    const map = new Map<string, Question>();
    baseQuestions.forEach((q) => map.set(q.id, q));
    customQuestions.forEach((q) => map.set(q.id, q));
    return Array.from(map.values());
  }, [baseQuestions, customQuestions]);

  // Update sound service on settings change
  useEffect(() => {
    soundService.setMuted(!settings.soundEnabled);
  }, [settings.soundEnabled]);

  // Persist user to localStorage
  useEffect(() => {
    try {
      localStorage.setItem(STORAGE_KEY_USER, JSON.stringify(user));
    } catch {
      // ignore
    }
  }, [user]);

  // Persist settings
  useEffect(() => {
    try {
      localStorage.setItem(STORAGE_KEY_SETTINGS, JSON.stringify(settings));
    } catch {
      // ignore
    }
  }, [settings]);

  // Persist custom questions
  useEffect(() => {
    try {
      localStorage.setItem(STORAGE_KEY_CUSTOM_QUESTIONS, JSON.stringify(customQuestions));
    } catch {
      // ignore
    }
  }, [customQuestions]);

  const fullQuestionText = currentQuestion?.tossup || '';

  // Filter available questions
  const getEligibleQuestions = useCallback(
    (category: Category | 'all' = selectedCategory, difficulty: DifficultyLevel | 'all' = selectedDifficulty) => {
      return allQuestions.filter((q) => {
        if (category !== 'all' && q.category !== category) return false;
        if (difficulty !== 'all' && q.difficulty !== difficulty) return false;
        return true;
      });
    },
    [allQuestions, selectedCategory, selectedDifficulty]
  );

  // Typewriter effect cleanup
  const stopTypewriter = useCallback(() => {
    if (typewriterTimerRef.current) {
      clearInterval(typewriterTimerRef.current);
      typewriterTimerRef.current = null;
    }
  }, []);

  const stopCountdown = useCallback(() => {
    if (countdownTimerRef.current) {
      clearInterval(countdownTimerRef.current);
      countdownTimerRef.current = null;
    }
  }, []);

  // Clean up on unmount
  useEffect(() => {
    return () => {
      stopTypewriter();
      stopCountdown();
    };
  }, [stopTypewriter, stopCountdown]);

  // Helper to fetch questions for a specific category and difficulty from Turso
  const fetchCategoryQuestions = useCallback(
    async (
      category: Category | 'all' = selectedCategory,
      level: DifficultyLevel | 'all' = selectedDifficulty,
      forceRefresh = false
    ): Promise<Question[]> => {
      if (!settings.tursoUrl) return [];
      if (isFetchingQuestionsRef.current && !forceRefresh) return [];

      try {
        isFetchingQuestionsRef.current = true;
        setIsSyncing(true);
        setSyncStatus('Fetching questions from Turso...');

        const excludeIds = Array.from(seenQuestionIdsRef.current).slice(-80);
        const newQs = await fetchQuestionsFromTurso(
          settings.tursoUrl,
          settings.tursoAuthToken,
          category,
          level,
          50,
          true,
          excludeIds
        );

        if (newQs && newQs.length > 0) {
          const flattened = flattenQuestions(newQs);
          setCustomQuestions((prev) => {
            const map = new Map(prev.map((q) => [q.id, q]));
            flattened.forEach((q) => map.set(q.id, q));
            return Array.from(map.values());
          });

          const eligibleUnseen = flattened.filter((q) => {
            if (category !== 'all' && q.category !== category) return false;
            if (level !== 'all' && q.difficulty !== level) return false;
            return !seenQuestionIdsRef.current.has(q.id);
          });

          const currentQueueSet = new Set(unplayedQueueRef.current);
          const freshIds = eligibleUnseen.map((q) => q.id).filter((id) => !currentQueueSet.has(id));

          // Fisher-Yates shuffle fresh IDs
          for (let i = freshIds.length - 1; i > 0; i--) {
            const j = Math.floor(Math.random() * (i + 1));
            const temp = freshIds[i];
            freshIds[i] = freshIds[j];
            freshIds[j] = temp;
          }

          if (forceRefresh) {
            unplayedQueueRef.current = freshIds;
          } else {
            unplayedQueueRef.current = [...unplayedQueueRef.current, ...freshIds];
          }

          setSyncStatus(`Loaded ${flattened.length} questions from Turso!`);
          return flattened;
        }
        return [];
      } catch (e) {
        console.warn('Failed to fetch questions from Turso:', e);
        setSyncStatus('Failed to load questions from Turso');
        return [];
      } finally {
        isFetchingQuestionsRef.current = false;
        setIsSyncing(false);
      }
    },
    [selectedCategory, selectedDifficulty, settings.tursoAuthToken, settings.tursoUrl]
  );

  // Auto-fetch fresh questions from Turso when filter changes or on initial boot
  useEffect(() => {
    unplayedQueueRef.current = [];
    if (settings.tursoUrl) {
      fetchCategoryQuestions(selectedCategory, selectedDifficulty, true);
    }
  }, [fetchCategoryQuestions, selectedCategory, selectedDifficulty, settings.tursoUrl]);

  // Start next question
  const startQuestion = useCallback(
    async (overrideCat?: Category | 'all', overrideDiff?: DifficultyLevel | 'all') => {
      stopTypewriter();
      stopCountdown();
      if ('speechSynthesis' in window) {
        window.speechSynthesis.cancel();
      }

      const activeCat = overrideCat !== undefined ? overrideCat : selectedCategory;
      const activeDiff = overrideDiff !== undefined ? overrideDiff : selectedDifficulty;

      let pool = getEligibleQuestions(activeCat, activeDiff);

      // If queue is empty, fill from unseen local pool or fetch
      if (unplayedQueueRef.current.length === 0) {
        const unseenLocal = pool.filter((q) => !seenQuestionIdsRef.current.has(q.id));
        if (unseenLocal.length > 0) {
          unplayedQueueRef.current = unseenLocal.map((q) => q.id).sort(() => Math.random() - 0.5);
        } else if (settings.tursoUrl) {
          const fetched = await fetchCategoryQuestions(activeCat, activeDiff, false);
          if (fetched && fetched.length > 0) {
            pool = getEligibleQuestions(activeCat, activeDiff);
          }
        }

        // If still empty (all seen), recycle pool with recent buffer
        if (unplayedQueueRef.current.length === 0 && pool.length > 0) {
          const recentHistory = Array.from(seenQuestionIdsRef.current).slice(-15);
          seenQuestionIdsRef.current = new Set(recentHistory);
          const recycled = pool.filter((q) => !seenQuestionIdsRef.current.has(q.id));
          const toUse = recycled.length > 0 ? recycled : pool;
          unplayedQueueRef.current = toUse.map((q) => q.id).sort(() => Math.random() - 0.5);
        }
      }

      if (unplayedQueueRef.current.length === 0 && pool.length === 0) {
        setSyncStatus('No questions available for this subject/level.');
        return;
      }

      let nextId = unplayedQueueRef.current.shift() || pool[0]?.id;
      if (currentQuestion && nextId === currentQuestion.id && (unplayedQueueRef.current.length > 0 || pool.length > 1)) {
        const altId = unplayedQueueRef.current.shift() || pool.find((q) => q.id !== currentQuestion.id)?.id || nextId;
        if (altId !== nextId) {
          unplayedQueueRef.current.push(nextId);
          nextId = altId;
        }
      }

      const selected = pool.find((q) => q.id === nextId) || allQuestions.find((q) => q.id === nextId) || pool[0];
      if (!selected) return;

      seenQuestionIdsRef.current.add(selected.id);

      setCurrentQuestion(selected);
      setRevealedText('');
      setUserAnswerInput('');
      setLastEvaluation(null);
      setLastAttemptLog(null);
      setScoreThisRound(0);
      setGameStage('reading_tossup');

      const targetText = selected.tossup;
      let charIdx = 0;

      // Audio Mode: In-browser Web Speech API
      if (settings.readerMode === 'audio' && 'speechSynthesis' in window) {
        const utterance = new SpeechSynthesisUtterance(targetText);
        utterance.rate = settings.speechRate || 1.0;
        utterance.lang = 'en-US';

        if (settings.selectedVoiceURI) {
          const voices = window.speechSynthesis.getVoices();
          const matched = voices.find((v) => v.voiceURI === settings.selectedVoiceURI);
          if (matched) utterance.voice = matched;
        }

        utterance.onboundary = (e) => {
          if (e.charIndex !== undefined) {
            const spoken = targetText.substring(0, Math.min(targetText.length, e.charIndex + (e.charLength || 6)));
            setRevealedText(spoken);
          }
        };

        utterance.onend = () => {
          setRevealedText(targetText);
        };

        window.speechSynthesis.speak(utterance);
      } else {
        // Visual Mode: Progressive typewriter reveal
        typewriterTimerRef.current = setInterval(() => {
          charIdx += 2;
          if (charIdx >= targetText.length) {
            setRevealedText(targetText);
            stopTypewriter();
          } else {
            setRevealedText(targetText.substring(0, charIdx));
          }
        }, settings.readingSpeed);
      }
    },
    [
      allQuestions,
      currentQuestion,
      fetchCategoryQuestions,
      getEligibleQuestions,
      selectedCategory,
      selectedDifficulty,
      settings.readerMode,
      settings.readingSpeed,
      settings.selectedVoiceURI,
      settings.speechRate,
      settings.tursoUrl,
      stopCountdown,
      stopTypewriter,
    ]
  );

  // Switch category immediately and restart question if playing
  const setSelectedCategory = useCallback(
    (cat: Category | 'all') => {
      setSelectedCategoryState(cat);
      unplayedQueueRef.current = [];
      if (gameStage === 'reading_tossup' || gameStage === 'buzzed_tossup' || gameStage === 'result_tossup') {
        startQuestion(cat, selectedDifficulty);
      }
    },
    [gameStage, selectedDifficulty, startQuestion]
  );

  const setSelectedDifficulty = useCallback(
    (diff: DifficultyLevel | 'all') => {
      setSelectedDifficultyState(diff);
      unplayedQueueRef.current = [];
      if (gameStage === 'reading_tossup' || gameStage === 'buzzed_tossup' || gameStage === 'result_tossup') {
        startQuestion(selectedCategory, diff);
      }
    },
    [gameStage, selectedCategory, startQuestion]
  );

  // Buzz action
  const buzz = useCallback(() => {
    if (gameStage !== 'reading_tossup') return;

    stopTypewriter();
    if ('speechSynthesis' in window) {
      window.speechSynthesis.cancel();
    }

    soundService.playBuzzer();
    setGameStage('buzzed_tossup');

    const duration = settings.timerDuration || 5;
    setTimeLeft(duration);

    stopCountdown();
    countdownTimerRef.current = setInterval(() => {
      setTimeLeft((prev) => {
        if (prev <= 1) {
          stopCountdown();
          soundService.playIncorrect();
          handleTimeoutAnswer();
          return 0;
        }
        if (prev <= 3) {
          soundService.playTick();
        }
        return prev - 1;
      });
    }, 1000);
  }, [gameStage, settings.timerDuration, stopCountdown, stopTypewriter]);

  // Handle timeout
  const handleTimeoutAnswer = useCallback(() => {
    if (!currentQuestion) return;
    const acceptable = currentQuestion.answers;

    const evalResult: MatchResult = {
      isCorrect: false,
      cleanedUserAnswer: '',
      feedback: 'Time expired (No answer submitted in time). Acceptable: ' + acceptable.join(', '),
    };

    recordResult(evalResult, 0, false);
  }, [currentQuestion]);

  // Record stats and sync to Turso
  const recordResult = useCallback(
    (evalResult: MatchResult, pointsEarned: number, isPowerBuzz: boolean) => {
      stopCountdown();
      if (!currentQuestion) return;

      const cat = currentQuestion.category;
      const totalLen = fullQuestionText.length || 1;
      const buzzLen = revealedText.length;
      const buzzPercent = Math.min(100, Math.round((buzzLen / totalLen) * 100));

      const attemptLog: QuestionAttemptLog = {
        id: `att_${Date.now()}_${Math.random().toString(36).substr(2, 6)}`,
        questionId: currentQuestion.id,
        category: cat,
        difficulty: currentQuestion.difficulty,
        questionText: fullQuestionText,
        userAnswer: userAnswerInput,
        acceptableAnswers: currentQuestion.answers || [],
        isCorrect: evalResult.isCorrect,
        pointsEarned,
        buzzPercentage: buzzPercent,
        timestamp: Date.now(),
        wasSkipped: evalResult.wasSkipped,
      };

      setLastEvaluation(evalResult);
      setLastAttemptLog(attemptLog);

      if (evalResult.isCorrect) {
        if (isPowerBuzz) {
          soundService.playPowerBuzz();
        } else {
          soundService.playCorrect();
        }

        // Only fire confetti if enabled in settings
        if (settings.confettiEnabled !== false) {
          confetti({
            particleCount: isPowerBuzz ? 80 : 40,
            spread: 60,
            origin: { y: 0.7 },
            colors: brandColours(),
          });
        }
      } else if (!evalResult.wasSkipped) {
        soundService.playIncorrect();
      }

      // Update User Stats
      setUser((prev) => {
        const prevCat = prev.stats.byCategory[cat] || { answered: 0, correct: 0, points: 0 };
        const newCatStat = {
          answered: prevCat.answered + 1,
          correct: prevCat.correct + (evalResult.isCorrect ? 1 : 0),
          points: prevCat.points + pointsEarned,
        };

        const newStreak = evalResult.isCorrect ? prev.stats.currentStreak + 1 : 0;
        const bestStreak = Math.max(prev.stats.bestStreak, newStreak);
        const totalBuzzes = prev.stats.totalBuzzes + 1;
        const newAvgBuzz = Math.round(
          (prev.stats.averageBuzzPercentage * prev.stats.totalBuzzes + buzzPercent) / totalBuzzes
        );

        const updatedStats: UserStats = {
          ...prev.stats,
          totalPoints: prev.stats.totalPoints + pointsEarned,
          totalAnswered: prev.stats.totalAnswered + 1,
          totalCorrect: prev.stats.totalCorrect + (evalResult.isCorrect ? 1 : 0),
          currentStreak: newStreak,
          bestStreak,
          powerBuzzes: prev.stats.powerBuzzes + (isPowerBuzz ? 1 : 0),
          averageBuzzPercentage: newAvgBuzz,
          totalBuzzes,
          byCategory: {
            ...prev.stats.byCategory,
            [cat]: newCatStat,
          },
        };

        const updatedProfile: UserProfile = {
          ...prev,
          stats: updatedStats,
          history: [attemptLog, ...prev.history].slice(0, 200),
          lastSyncedAt: Date.now(),
        };

        // Cloud sync to Turso
        if (settings.tursoUrl) {
          syncUserToTurso(settings.tursoUrl, settings.tursoAuthToken, updatedProfile);
          logAttemptToTurso(settings.tursoUrl, settings.tursoAuthToken, {
            ...attemptLog,
            username: prev.username,
          });
        }

        return updatedProfile;
      });

      setScoreThisRound((s) => s + pointsEarned);
      setGameStage('result_tossup');
    },
    [
      currentQuestion,
      fullQuestionText,
      revealedText.length,
      settings.confettiEnabled,
      settings.tursoAuthToken,
      settings.tursoUrl,
      stopCountdown,
      userAnswerInput,
    ]
  );

  // Submit Answer
  const submitAnswer = useCallback(() => {
    if (!currentQuestion) return;

    const acceptable = currentQuestion.answers || [];
    const evalResult = checkAnswer(userAnswerInput, acceptable);

    let points = 0;
    let isPowerBuzz = false;

    if (evalResult.isCorrect) {
      const isEarly = revealedText.length < fullQuestionText.length * 0.6;
      if (settings.powerBuzzEnabled && isEarly) {
        points = 15;
        isPowerBuzz = true;
      } else {
        points = 10;
      }
    }

    recordResult(evalResult, points, isPowerBuzz);
  }, [
    currentQuestion,
    fullQuestionText.length,
    recordResult,
    revealedText.length,
    settings.powerBuzzEnabled,
    userAnswerInput,
  ]);

  // Skip question - marks wasSkipped: true
  const skipQuestion = useCallback(() => {
    stopTypewriter();
    stopCountdown();
    if (!currentQuestion) return;

    setRevealedText(fullQuestionText);
    const evalResult: MatchResult = {
      isCorrect: false,
      cleanedUserAnswer: '',
      feedback: `Skipped. Correct answer was: ${currentQuestion.answers.join(', ')}`,
      wasSkipped: true,
    };

    recordResult(evalResult, 0, false);
  }, [currentQuestion, fullQuestionText, recordResult, stopCountdown, stopTypewriter]);

  // Override answer ("I was right!" button) - only available when not skipped
  const overrideAnswer = useCallback(() => {
    if (!lastAttemptLog || !currentQuestion || lastAttemptLog.isCorrect || lastAttemptLog.wasSkipped) return;

    const cat = currentQuestion.category;
    const pointsToAward = lastAttemptLog.pointsEarned === 0 ? 10 : 0;

    soundService.playCorrect();
    if (settings.confettiEnabled !== false) {
      confetti({
        particleCount: 50,
        spread: 50,
        origin: { y: 0.7 },
        colors: brandColours(),
      });
    }

    setLastEvaluation((prev) =>
      prev
        ? { ...prev, isCorrect: true, feedback: `Marked correct via manual override (+${pointsToAward} pts).` }
        : null
    );

    setUser((prev) => {
      const prevCat = prev.stats.byCategory[cat] || { answered: 0, correct: 0, points: 0 };
      const updatedCat = {
        ...prevCat,
        correct: prevCat.correct + 1,
        points: prevCat.points + pointsToAward,
      };

      const updatedStats: UserStats = {
        ...prev.stats,
        totalPoints: prev.stats.totalPoints + pointsToAward,
        totalCorrect: prev.stats.totalCorrect + 1,
        byCategory: {
          ...prev.stats.byCategory,
          [cat]: updatedCat,
        },
      };

      const updatedHistory = prev.history.map((item) =>
        item.id === lastAttemptLog.id
          ? { ...item, isCorrect: true, pointsEarned: pointsToAward, wasOverridden: true }
          : item
      );

      const updatedProfile: UserProfile = {
        ...prev,
        stats: updatedStats,
        history: updatedHistory,
      };

      if (settings.tursoUrl) {
        syncUserToTurso(settings.tursoUrl, settings.tursoAuthToken, updatedProfile);
      }

      return updatedProfile;
    });
  }, [currentQuestion, lastAttemptLog, settings.confettiEnabled, settings.tursoAuthToken, settings.tursoUrl]);

  // Next step - always starts next tossup question
  const nextStep = useCallback(() => {
    startQuestion();
  }, [startQuestion]);

  // Keyboard Shortcuts: Spacebar to Buzz / Start, 'N' for Next Question
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      const target = e.target as HTMLElement;
      if (target.tagName === 'INPUT' || target.tagName === 'TEXTAREA' || target.tagName === 'SELECT') {
        return;
      }

      if (e.key === 'n' || e.key === 'N') {
        e.preventDefault();
        if (gameStage === 'idle') {
          startQuestion();
        } else if (gameStage === 'result_tossup' || gameStage === 'round_summary') {
          nextStep();
        } else if (gameStage === 'reading_tossup') {
          skipQuestion();
        }
        return;
      }

      if (e.code === 'Space') {
        e.preventDefault();
        if (gameStage === 'reading_tossup') {
          buzz();
        } else if (gameStage === 'idle') {
          startQuestion();
        } else if (gameStage === 'result_tossup' || gameStage === 'round_summary') {
          nextStep();
        }
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [buzz, gameStage, nextStep, skipQuestion, startQuestion]);

  // Login / Switch user across devices using Turso
  const loginUser = async (username: string, pin: string, school?: string): Promise<boolean> => {
    setIsSyncing(true);
    setSyncStatus('Logging in...');

    if (settings.tursoUrl) {
      try {
        const cloudUser = await loginUserFromTurso(
          settings.tursoUrl,
          settings.tursoAuthToken,
          username,
          pin
        );
        if (cloudUser) {
          setUser(cloudUser);
          setIsSyncing(false);
          setSyncStatus('Turso profile restored!');
          return true;
        }
      } catch (e) {
        console.warn('Turso login failed:', e);
      }
    }

    const newProfile: UserProfile = {
      username: username.trim(),
      pin: pin.trim(),
      school: school?.trim() || 'Roma Antiqua Academy',
      level: 'novice',
      stats: INITIAL_USER_STATS,
      history: [],
      lastSyncedAt: Date.now(),
    };

    setUser(newProfile);
    setIsSyncing(false);
    setSyncStatus('Logged in locally');

    if (settings.tursoUrl) {
      syncUserToTurso(settings.tursoUrl, settings.tursoAuthToken, newProfile);
    }
    return true;
  };

  const logoutUser = () => {
    const guestUser: UserProfile = {
      username: 'Discipulus',
      pin: '1234',
      school: 'Roma Antiqua Academy',
      level: 'novice',
      stats: INITIAL_USER_STATS,
      history: [],
    };
    setUser(guestUser);
  };

  const updateSettings = (newSettings: Partial<AppSettings>) => {
    setSettings((prev) => ({ ...prev, ...newSettings }));
  };

  const addCustomQuestion = (q: Question) => {
    const flattened = flattenQuestions([q]);
    setCustomQuestions((prev) => [...flattened, ...prev]);
  };

  const deleteCustomQuestion = (id: string) => {
    setCustomQuestions((prev) => prev.filter((q) => q.id !== id));
  };

  const importQuestions = (newQuestions: Question[]): number => {
    if (!Array.isArray(newQuestions)) return 0;
    const valid = newQuestions.filter((q) => q.tossup && Array.isArray(q.answers) && q.answers.length > 0);
    const flattened = flattenQuestions(valid);
    setCustomQuestions((prev) => [...flattened, ...prev]);
    return flattened.length;
  };

  const resetUserStats = () => {
    setUser((prev) => ({
      ...prev,
      stats: INITIAL_USER_STATS,
      history: [],
    }));
  };

  const triggerManualSync = async () => {
    if (!settings.tursoUrl) {
      setSyncStatus('Please set a Turso Database URL in Settings');
      return;
    }
    setIsSyncing(true);
    setSyncStatus('Syncing with Turso...');
    const res = await syncUserToTurso(settings.tursoUrl, settings.tursoAuthToken, user);
    setIsSyncing(false);
    setSyncStatus(res.message || (res.success ? 'Sync complete!' : 'Sync failed'));
  };

  const syncQuestionsFromCloud = async (): Promise<number> => {
    if (!settings.tursoUrl) return 0;
    try {
      setIsSyncing(true);
      setSyncStatus('Fetching questions from Turso...');
      const cloudQuestions = await fetchQuestionsFromTurso(
        settings.tursoUrl,
        settings.tursoAuthToken,
        'all',
        'all',
        0,
        false
      );
      if (cloudQuestions.length > 0) {
        const flattened = flattenQuestions(cloudQuestions);
        setCustomQuestions((prev) => {
          const map = new Map(prev.map((q) => [q.id, q]));
          flattened.forEach((q) => map.set(q.id, q));
          return Array.from(map.values());
        });
        setSyncStatus(`Loaded ${flattened.length} questions from Turso!`);
        setIsSyncing(false);
        return flattened.length;
      } else {
        setSyncStatus('No questions found in Turso.');
      }
    } catch (e) {
      console.warn('Error fetching questions from Turso:', e);
      setSyncStatus('Failed to load questions from Turso.');
    } finally {
      setIsSyncing(false);
    }
    return 0;
  };

  return (
    <CertamenContext.Provider
      value={{
        user,
        settings,
        questions: allQuestions,
        currentQuestion,
        currentBoni: null,
        boniIndex: null,
        gameStage,
        revealedText,
        fullQuestionText,
        isBuzzActive: gameStage === 'buzzed_tossup',
        timeLeft,
        userAnswerInput,
        lastEvaluation,
        lastAttemptLog,
        selectedCategory,
        selectedDifficulty,
        playMode,
        isSyncing,
        syncStatus,
        scoreThisRound,

        startQuestion,
        buzz,
        setUserAnswerInput,
        submitAnswer,
        skipQuestion,
        overrideAnswer,
        nextStep,
        setSelectedCategory,
        setSelectedDifficulty,
        setPlayMode,
        updateSettings,
        loginUser,
        logoutUser,
        addCustomQuestion,
        deleteCustomQuestion,
        importQuestions,
        resetUserStats,
        triggerManualSync,
        syncQuestionsFromCloud,
      }}
    >
      {children}
    </CertamenContext.Provider>
  );
};

export function useCertamen() {
  const context = useContext(CertamenContext);
  if (!context) {
    throw new Error('useCertamen must be used within a CertamenProvider');
  }
  return context;
}
