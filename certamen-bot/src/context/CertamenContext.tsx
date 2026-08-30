import React, { createContext, useContext, useState, useEffect, useCallback, useRef } from 'react';
import {
  Category,
  DifficultyLevel,
  PlayMode,
  Question,
  BoniQuestion,
  UserProfile,
  UserStats,
  QuestionAttemptLog,
  AppSettings,
} from '../types/certamen';
import { INITIAL_QUESTION_BANK } from '../data/questionBank';
import { checkAnswer, MatchResult } from '../services/answerChecker';
import { soundService } from '../services/audioService';
import { syncUserToCloud, logAttemptToCloud, loginUserFromCloud, fetchQuestionsFromCloud } from '../services/googleSheetsService';
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

const DEFAULT_SETTINGS: AppSettings = {
  readerMode: 'visual',
  readingSpeed: 45, // ms per character (or ~250-300 wpm)
  timerDuration: 6, // 6 seconds to answer after buzzing
  soundEnabled: true,
  powerBuzzEnabled: true,
  speechRate: 1.0,
  appsScriptUrl: 'https://script.google.com/macros/s/AKfycbwk0qpdmiyMAIJEAsJvzS6tpHywNf9__OJJH_8nqOfHXq2lQH5SxJT1yT4tn-QDLRaznA/exec',
  theme: 'classical-gold',
};

export type GameStage =
  | 'idle'
  | 'reading_tossup'
  | 'buzzed_tossup'
  | 'result_tossup'
  | 'reading_boni1'
  | 'buzzed_boni1'
  | 'result_boni1'
  | 'reading_boni2'
  | 'buzzed_boni2'
  | 'result_boni2'
  | 'round_summary';

interface CertamenContextType {
  user: UserProfile;
  settings: AppSettings;
  questions: Question[];
  currentQuestion: Question | null;
  currentBoni: BoniQuestion | null;
  boniIndex: 1 | 2 | null;
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
  const [selectedCategory, setSelectedCategory] = useState<Category | 'all'>('all');
  const [selectedDifficulty, setSelectedDifficulty] = useState<DifficultyLevel | 'all'>('all');
  const [playMode, setPlayMode] = useState<PlayMode>('tossup_only');

  const [currentQuestion, setCurrentQuestion] = useState<Question | null>(null);
  const [currentBoni, setCurrentBoni] = useState<BoniQuestion | null>(null);
  const [boniIndex, setBoniIndex] = useState<1 | 2 | null>(null);
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

  const allQuestions = customQuestions.length > 0 ? customQuestions : INITIAL_QUESTION_BANK;

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

  const fullQuestionText =
    gameStage.startsWith('reading_boni') || gameStage.startsWith('buzzed_boni') || gameStage.startsWith('result_boni')
      ? currentBoni?.prompt || ''
      : currentQuestion?.tossup || '';

  // Filter available questions
  const getEligibleQuestions = useCallback(() => {
    return allQuestions.filter((q) => {
      if (selectedCategory !== 'all' && q.category !== selectedCategory) return false;
      if (selectedDifficulty !== 'all' && q.difficulty !== selectedDifficulty) return false;
      return true;
    });
  }, [allQuestions, selectedCategory, selectedDifficulty]);

  // Helper to fetch questions for a specific category and difficulty from Google Sheets
  const fetchCategoryQuestions = useCallback(
    async (
      category: Category | 'all' = selectedCategory,
      level: DifficultyLevel | 'all' = selectedDifficulty,
      forceRefresh = false
    ): Promise<Question[]> => {
      if (!settings.appsScriptUrl) return [];
      if (isFetchingQuestionsRef.current && !forceRefresh) return [];

      try {
        isFetchingQuestionsRef.current = true;
        setIsSyncing(true);
        setSyncStatus('Fetching fresh questions from Google Sheets...');

        const excludeIds = Array.from(seenQuestionIdsRef.current).slice(-80);
        const newQs = await fetchQuestionsFromCloud(
          settings.appsScriptUrl,
          category,
          level,
          50,
          true,
          excludeIds
        );

        if (newQs && newQs.length > 0) {
          // Merge into customQuestions bank so questions accumulate permanently
          setCustomQuestions((prev) => {
            const map = new Map(prev.map((q) => [q.id, q]));
            newQs.forEach((q) => map.set(q.id, q));
            return Array.from(map.values());
          });

          // Unseen question IDs matching current filter
          const eligibleUnseen = newQs.filter((q) => {
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

          setSyncStatus(`Loaded ${newQs.length} fresh questions from Google Sheets!`);
          return newQs;
        }
        return [];
      } catch (e) {
        console.warn('Failed to fetch questions from Google Sheets:', e);
        setSyncStatus('Failed to load questions from Google Sheets');
        return [];
      } finally {
        isFetchingQuestionsRef.current = false;
        setIsSyncing(false);
      }
    },
    [selectedCategory, selectedDifficulty, settings.appsScriptUrl]
  );

  // Background replenish helper
  const checkAndReplenishQuestions = useCallback(
    (category: Category | 'all' = selectedCategory, level: DifficultyLevel | 'all' = selectedDifficulty) => {
      if (!settings.appsScriptUrl || isFetchingQuestionsRef.current) return;
      if (unplayedQueueRef.current.length < 12) {
        fetchCategoryQuestions(category, level, false);
      }
    },
    [fetchCategoryQuestions, selectedCategory, selectedDifficulty, settings.appsScriptUrl]
  );

  // Auto-fetch fresh questions from Google Sheets when filter changes or on initial boot
  useEffect(() => {
    unplayedQueueRef.current = [];
    if (settings.appsScriptUrl) {
      fetchCategoryQuestions(selectedCategory, selectedDifficulty, true);
    }
  }, [fetchCategoryQuestions, selectedCategory, selectedDifficulty, settings.appsScriptUrl]);

  // Periodic background heartbeat to constantly fetch new questions and keep queue populated
  useEffect(() => {
    if (!settings.appsScriptUrl) return;
    const interval = setInterval(() => {
      if (unplayedQueueRef.current.length < 12 && !isFetchingQuestionsRef.current) {
        fetchCategoryQuestions(selectedCategory, selectedDifficulty, false);
      }
    }, 12000);
    return () => clearInterval(interval);
  }, [fetchCategoryQuestions, selectedCategory, selectedDifficulty, settings.appsScriptUrl]);

  // Typewriter effect
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

  // Start next question
  const startQuestion = useCallback(async () => {
    stopTypewriter();
    stopCountdown();
    if ('speechSynthesis' in window) {
      window.speechSynthesis.cancel();
    }

    let pool = getEligibleQuestions();

    // 1. If queue is empty, attempt to fill from unseen local pool or fetch
    if (unplayedQueueRef.current.length === 0) {
      const unseenLocal = pool.filter((q) => !seenQuestionIdsRef.current.has(q.id));
      if (unseenLocal.length > 0) {
        unplayedQueueRef.current = unseenLocal.map((q) => q.id).sort(() => Math.random() - 0.5);
      } else if (settings.appsScriptUrl) {
        // Immediate fetch from cloud
        const fetched = await fetchCategoryQuestions(selectedCategory, selectedDifficulty, false);
        if (fetched && fetched.length > 0) {
          pool = getEligibleQuestions();
        }
      }

      // If still empty (all questions in bank and cloud have been seen), recycle pool with recent buffer
      if (unplayedQueueRef.current.length === 0 && pool.length > 0) {
        // Retain only the most recent 15 seen IDs to avoid immediate repeats
        const recentHistory = Array.from(seenQuestionIdsRef.current).slice(-15);
        seenQuestionIdsRef.current = new Set(recentHistory);
        const recycled = pool.filter((q) => !seenQuestionIdsRef.current.has(q.id));
        const toUse = recycled.length > 0 ? recycled : pool;
        unplayedQueueRef.current = toUse.map((q) => q.id).sort(() => Math.random() - 0.5);
      }
    }

    if (unplayedQueueRef.current.length === 0 && pool.length === 0) {
      setSyncStatus('No questions available for this category/difficulty.');
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

    // Proactively replenish background queue
    checkAndReplenishQuestions(selectedCategory, selectedDifficulty);

    setCurrentQuestion(selected);
    setCurrentBoni(null);
    setBoniIndex(null);
    setRevealedText('');
    setUserAnswerInput('');
    setLastEvaluation(null);
    setLastAttemptLog(null);
    setScoreThisRound(0);
    setGameStage('reading_tossup');

    const targetText = selected.tossup;
    let charIdx = 0;

    // Audio Mode: In-browser Web Speech API (zero AI / zero API calls)
    if (settings.readerMode === 'audio' && 'speechSynthesis' in window) {
      const utterance = new SpeechSynthesisUtterance(targetText);
      utterance.rate = settings.speechRate || 1.0;
      utterance.lang = 'en-US';

      // Pick preferred voice if available
      if (settings.selectedVoiceURI) {
        const voices = window.speechSynthesis.getVoices();
        const matched = voices.find((v) => v.voiceURI === settings.selectedVoiceURI);
        if (matched) utterance.voice = matched;
      }

      utterance.onboundary = (e) => {
        if (e.charIndex !== undefined) {
          // Estimate spoken length at word boundary
          const spoken = targetText.substring(0, Math.min(targetText.length, e.charIndex + (e.charLength || 6)));
          setRevealedText(spoken);
        }
      };

      utterance.onend = () => {
        setRevealedText(targetText);
      };

      window.speechSynthesis.speak(utterance);
    } else {
      // Visual Mode: Progressive typewriter reveal on screen
      typewriterTimerRef.current = setInterval(() => {
        charIdx += 2; // smooth 2 chars per tick for natural flow
        if (charIdx >= targetText.length) {
          setRevealedText(targetText);
          stopTypewriter();
        } else {
          setRevealedText(targetText.substring(0, charIdx));
        }
      }, settings.readingSpeed);
    }
  }, [
    allQuestions,
    checkAndReplenishQuestions,
    currentQuestion,
    fetchCategoryQuestions,
    getEligibleQuestions,
    selectedCategory,
    selectedDifficulty,
    settings.appsScriptUrl,
    settings.readerMode,
    settings.readingSpeed,
    settings.selectedVoiceURI,
    settings.speechRate,
    stopCountdown,
    stopTypewriter,
  ]);

  // Buzz action
  const buzz = useCallback(() => {
    if (
      gameStage !== 'reading_tossup' &&
      gameStage !== 'reading_boni1' &&
      gameStage !== 'reading_boni2'
    ) {
      return;
    }

    // Stop typewriter & speech immediately!
    stopTypewriter();
    if ('speechSynthesis' in window) {
      window.speechSynthesis.cancel();
    }

    soundService.playBuzzer();

    const isTossup = gameStage === 'reading_tossup';
    const isBoni1 = gameStage === 'reading_boni1';

    if (isTossup) setGameStage('buzzed_tossup');
    else if (isBoni1) setGameStage('buzzed_boni1');
    else setGameStage('buzzed_boni2');

    // Start 5-second countdown timer
    const duration = settings.timerDuration || 5;
    setTimeLeft(duration);

    stopCountdown();
    countdownTimerRef.current = setInterval(() => {
      setTimeLeft((prev) => {
        if (prev <= 1) {
          stopCountdown();
          // Timeout = incorrect auto-submit
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

  // Helper to handle timeout
  const handleTimeoutAnswer = useCallback(() => {
    if (!currentQuestion) return;
    const isTossup = gameStage === 'buzzed_tossup';
    const acceptable = isTossup ? currentQuestion.answers : currentBoni?.answers || [];

    const evalResult: MatchResult = {
      isCorrect: false,
      cleanedUserAnswer: '',
      feedback: 'Time expired (No answer submitted in time). Acceptable: ' + acceptable.join(', '),
    };

    recordResult(evalResult, 0, false);
  }, [currentBoni?.answers, currentQuestion, gameStage]);



  // Record stats and sync
  const recordResult = useCallback(
    (evalResult: MatchResult, pointsEarned: number, isPowerBuzz: boolean) => {
      stopCountdown();
      if (!currentQuestion) return;

      const isTossup = gameStage === 'buzzed_tossup' || gameStage === 'reading_tossup';
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
        acceptableAnswers: isTossup ? currentQuestion.answers : currentBoni?.answers || [],
        isCorrect: evalResult.isCorrect,
        pointsEarned,
        buzzPercentage: buzzPercent,
        timestamp: Date.now(),
      };

      setLastEvaluation(evalResult);
      setLastAttemptLog(attemptLog);

      if (evalResult.isCorrect) {
        if (isPowerBuzz) {
          soundService.playPowerBuzz();
        } else {
          soundService.playCorrect();
        }

        confetti({
          particleCount: isPowerBuzz ? 80 : 40,
          spread: 60,
          origin: { y: 0.7 },
          colors: ['#D97706', '#F59E0B', '#B45309', '#10B981', '#6366F1'],
        });
      } else {
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

        // Background cloud sync
        if (settings.appsScriptUrl) {
          syncUserToCloud(settings.appsScriptUrl, updatedProfile);
          logAttemptToCloud(settings.appsScriptUrl, { ...attemptLog, username: prev.username });
        }

        return updatedProfile;
      });

      // Advance stage
      if (isTossup) {
        setScoreThisRound((s) => s + pointsEarned);
        setGameStage('result_tossup');
      } else if (gameStage === 'buzzed_boni1') {
        setScoreThisRound((s) => s + pointsEarned);
        setGameStage('result_boni1');
      } else {
        setScoreThisRound((s) => s + pointsEarned);
        setGameStage('result_boni2');
      }
    },
    [
      currentBoni?.answers,
      currentQuestion,
      fullQuestionText,
      gameStage,
      revealedText.length,
      settings.appsScriptUrl,
      stopCountdown,
      userAnswerInput,
    ]
  );

  // Submit Answer
  const submitAnswer = useCallback(() => {
    if (!currentQuestion) return;

    const isTossup = gameStage === 'buzzed_tossup';
    const acceptable = isTossup ? currentQuestion.answers : currentBoni?.answers || [];
    const evalResult = checkAnswer(userAnswerInput, acceptable);

    let points = 0;
    let isPowerBuzz = false;

    if (evalResult.isCorrect) {
      if (isTossup) {
        // Power Buzz check: if buzzed before half of the question
        const isEarly = revealedText.length < fullQuestionText.length * 0.6;
        if (settings.powerBuzzEnabled && isEarly) {
          points = 15; // 15 pt power buzz
          isPowerBuzz = true;
        } else {
          points = 10; // Standard 10 pt tossup
        }
      } else {
        points = 5; // Standard 5 pt boni
      }
    }

    recordResult(evalResult, points, isPowerBuzz);
  }, [
    currentBoni?.answers,
    currentQuestion,
    fullQuestionText.length,
    gameStage,
    recordResult,
    revealedText.length,
    settings.powerBuzzEnabled,
    userAnswerInput,
  ]);

  // Skip question
  const skipQuestion = useCallback(() => {
    stopTypewriter();
    stopCountdown();
    if (!currentQuestion) return;

    setRevealedText(fullQuestionText);
    const evalResult: MatchResult = {
      isCorrect: false,
      cleanedUserAnswer: '',
      feedback: `Skipped. Correct answer was: ${currentQuestion.answers.join(', ')}`,
    };

    recordResult(evalResult, 0, false);
  }, [currentQuestion, fullQuestionText, recordResult, stopCountdown, stopTypewriter]);

  // Override answer ("I was right!" button)
  const overrideAnswer = useCallback(() => {
    if (!lastAttemptLog || !currentQuestion || lastAttemptLog.isCorrect) return;

    const cat = currentQuestion.category;
    const pointsToAward = lastAttemptLog.pointsEarned === 0 ? 10 : 0;

    soundService.playCorrect();
    confetti({
      particleCount: 50,
      spread: 50,
      origin: { y: 0.7 },
    });

    setLastEvaluation((prev) =>
      prev
        ? { ...prev, isCorrect: true, feedback: `Marked correct via manual judge override (+${pointsToAward} pts).` }
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

      if (settings.appsScriptUrl) {
        syncUserToCloud(settings.appsScriptUrl, updatedProfile);
      }

      return updatedProfile;
    });
  }, [currentQuestion, lastAttemptLog, settings.appsScriptUrl]);

  // Next step in round (e.g. Move from Tossup -> Boni 1 -> Boni 2 -> Next Tossup)
  const nextStep = useCallback(() => {
    if (!currentQuestion) {
      startQuestion();
      return;
    }

    // If we're playing Tossup + Boni mode AND the tossup was answered correctly AND boni exists
    if (playMode === 'tossup_boni' && currentQuestion.boni && currentQuestion.boni.length > 0) {
      if (gameStage === 'result_tossup' && lastEvaluation?.isCorrect) {
        // Start Boni 1
        const b1 = currentQuestion.boni.find((b) => b.boniNumber === 1) || currentQuestion.boni[0];
        setCurrentBoni(b1);
        setBoniIndex(1);
        setRevealedText('');
        setUserAnswerInput('');
        setLastEvaluation(null);
        setGameStage('reading_boni1');

        if (settings.readerMode === 'audio' && 'speechSynthesis' in window) {
          window.speechSynthesis.cancel();
          const utterance = new SpeechSynthesisUtterance(b1.prompt);
          utterance.rate = settings.speechRate || 1.0;
          utterance.lang = 'en-US';
          if (settings.selectedVoiceURI) {
            const matched = window.speechSynthesis.getVoices().find((v) => v.voiceURI === settings.selectedVoiceURI);
            if (matched) utterance.voice = matched;
          }
          utterance.onboundary = (e) => {
            if (e.charIndex !== undefined) {
              const spoken = b1.prompt.substring(0, Math.min(b1.prompt.length, e.charIndex + (e.charLength || 6)));
              setRevealedText(spoken);
            }
          };
          utterance.onend = () => setRevealedText(b1.prompt);
          window.speechSynthesis.speak(utterance);
        } else {
          let charIdx = 0;
          typewriterTimerRef.current = setInterval(() => {
            charIdx += 2;
            if (charIdx >= b1.prompt.length) {
              setRevealedText(b1.prompt);
              stopTypewriter();
            } else {
              setRevealedText(b1.prompt.substring(0, charIdx));
            }
          }, settings.readingSpeed);
        }
        return;
      }

      if (gameStage === 'result_boni1') {
        // Start Boni 2
        const b2 = currentQuestion.boni.find((b) => b.boniNumber === 2);
        if (b2) {
          setCurrentBoni(b2);
          setBoniIndex(2);
          setRevealedText('');
          setUserAnswerInput('');
          setLastEvaluation(null);
          setGameStage('reading_boni2');

          if (settings.readerMode === 'audio' && 'speechSynthesis' in window) {
            window.speechSynthesis.cancel();
            const utterance = new SpeechSynthesisUtterance(b2.prompt);
            utterance.rate = settings.speechRate || 1.0;
            utterance.lang = 'en-US';
            if (settings.selectedVoiceURI) {
              const matched = window.speechSynthesis.getVoices().find((v) => v.voiceURI === settings.selectedVoiceURI);
              if (matched) utterance.voice = matched;
            }
            utterance.onboundary = (e) => {
              if (e.charIndex !== undefined) {
                const spoken = b2.prompt.substring(0, Math.min(b2.prompt.length, e.charIndex + (e.charLength || 6)));
                setRevealedText(spoken);
              }
            };
            utterance.onend = () => setRevealedText(b2.prompt);
            window.speechSynthesis.speak(utterance);
          } else {
            let charIdx = 0;
            typewriterTimerRef.current = setInterval(() => {
              charIdx += 2;
              if (charIdx >= b2.prompt.length) {
                setRevealedText(b2.prompt);
                stopTypewriter();
              } else {
                setRevealedText(b2.prompt.substring(0, charIdx));
              }
            }, settings.readingSpeed);
          }
          return;
        }
      }
    }

    // Default: Start a fresh new question
    startQuestion();
  }, [
    currentQuestion,
    gameStage,
    lastEvaluation?.isCorrect,
    playMode,
    settings.readingSpeed,
    startQuestion,
    stopTypewriter,
  ]);

  // Keyboard Shortcuts: Spacebar to Buzz / Start, 'N' for Next Question
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      // If user is currently typing in an input or textarea, don't trigger global shortcuts
      const target = e.target as HTMLElement;
      if (target.tagName === 'INPUT' || target.tagName === 'TEXTAREA') {
        return;
      }

      // 'N' shortcut for next question / next step / start
      if (e.key === 'n' || e.key === 'N') {
        e.preventDefault();
        if (gameStage === 'idle') {
          startQuestion();
        } else if (
          gameStage === 'result_tossup' ||
          gameStage === 'result_boni1' ||
          gameStage === 'result_boni2' ||
          gameStage === 'round_summary'
        ) {
          nextStep();
        } else if (
          gameStage === 'reading_tossup' ||
          gameStage === 'reading_boni1' ||
          gameStage === 'reading_boni2'
        ) {
          skipQuestion();
        }
        return;
      }

      // Spacebar to Buzz / Start
      if (e.code === 'Space') {
        e.preventDefault();
        if (
          gameStage === 'reading_tossup' ||
          gameStage === 'reading_boni1' ||
          gameStage === 'reading_boni2'
        ) {
          buzz();
        } else if (gameStage === 'idle') {
          startQuestion();
        } else if (
          gameStage === 'result_tossup' ||
          gameStage === 'result_boni1' ||
          gameStage === 'result_boni2' ||
          gameStage === 'round_summary'
        ) {
          nextStep();
        }
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [buzz, gameStage, nextStep, skipQuestion, startQuestion]);

  // Login / Switch user across devices
  const loginUser = async (username: string, pin: string, school?: string): Promise<boolean> => {
    setIsSyncing(true);
    setSyncStatus('Logging in...');

    // Try cloud login if URL configured
    if (settings.appsScriptUrl) {
      try {
        const cloudUser = await loginUserFromCloud(settings.appsScriptUrl, username, pin);
        if (cloudUser) {
          setUser(cloudUser);
          setIsSyncing(false);
          setSyncStatus('Cloud profile restored!');
          return true;
        }
      } catch (e) {
        console.warn('Cloud login failed:', e);
      }
    }

    // Local profile creation / switch
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

    if (settings.appsScriptUrl) {
      syncUserToCloud(settings.appsScriptUrl, newProfile);
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
    setCustomQuestions((prev) => [q, ...prev]);
  };

  const deleteCustomQuestion = (id: string) => {
    setCustomQuestions((prev) => prev.filter((q) => q.id !== id));
  };

  const importQuestions = (newQuestions: Question[]): number => {
    if (!Array.isArray(newQuestions)) return 0;
    const valid = newQuestions.filter((q) => q.tossup && Array.isArray(q.answers) && q.answers.length > 0);
    setCustomQuestions((prev) => [...valid, ...prev]);
    return valid.length;
  };

  const resetUserStats = () => {
    setUser((prev) => ({
      ...prev,
      stats: INITIAL_USER_STATS,
      history: [],
    }));
  };

  const triggerManualSync = async () => {
    if (!settings.appsScriptUrl) {
      setSyncStatus('Please set a Google Apps Script URL in Settings');
      return;
    }
    setIsSyncing(true);
    setSyncStatus('Syncing with Google Sheets...');
    const res = await syncUserToCloud(settings.appsScriptUrl, user);
    setIsSyncing(false);
    setSyncStatus(res.message || (res.success ? 'Sync complete!' : 'Sync failed'));
  };

  const syncQuestionsFromCloud = async (): Promise<number> => {
    if (!settings.appsScriptUrl) return 0;
    try {
      setIsSyncing(true);
      setSyncStatus('Fetching questions from Google Sheets...');
      const cloudQuestions = await fetchQuestionsFromCloud(settings.appsScriptUrl, 'all', 'all', 0, true);
      if (cloudQuestions.length > 0) {
        setCustomQuestions((prev) => {
          const map = new Map(prev.map((q) => [q.id, q]));
          cloudQuestions.forEach((q) => map.set(q.id, q));
          return Array.from(map.values());
        });
        setSyncStatus(`Loaded ${cloudQuestions.length} questions from cloud!`);
        setIsSyncing(false);
        return cloudQuestions.length;
      } else {
        setSyncStatus('No questions found in Google Sheets.');
      }
    } catch (e) {
      console.warn('Error fetching questions from cloud:', e);
      setSyncStatus('Failed to load questions from cloud.');
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
        currentBoni,
        boniIndex,
        gameStage,
        revealedText,
        fullQuestionText,
        isBuzzActive: gameStage.startsWith('buzzed_'),
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
