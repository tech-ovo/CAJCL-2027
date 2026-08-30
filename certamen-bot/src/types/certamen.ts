export type Category = 'grammar' | 'mythology' | 'history' | 'culture' | 'literature';

export type DifficultyLevel = 'novice' | 'intermediate' | 'advanced';

export type PlayMode = 'tossup_only' | 'tossup_boni' | 'speed_drill' | 'study_review';

export interface BoniQuestion {
  boniNumber: 1 | 2;
  prompt: string;
  answers: string[];
  points: number;
  explanation?: string;
}

export interface Question {
  id: string;
  category: Category;
  difficulty: DifficultyLevel;
  tossup: string;
  answers: string[]; // Multiple acceptable answers
  boni?: BoniQuestion[];
  explanation?: string;
  source?: string;
  powerMarkIndex?: number; // Character index before which a buzz is a "power buzz" (15 pts instead of 10)
}

export interface CategoryStat {
  answered: number;
  correct: number;
  points: number;
}

export interface UserStats {
  totalPoints: number;
  totalAnswered: number;
  totalCorrect: number;
  currentStreak: number;
  bestStreak: number;
  powerBuzzes: number;
  averageBuzzPercentage: number; // Avg % of question revealed before buzzing
  totalBuzzes: number;
  byCategory: Record<Category, CategoryStat>;
}

export interface QuestionAttemptLog {
  id: string;
  questionId: string;
  category: Category;
  difficulty: DifficultyLevel;
  questionText: string;
  userAnswer: string;
  acceptableAnswers: string[];
  isCorrect: boolean;
  pointsEarned: number;
  buzzPercentage: number;
  timestamp: number;
  wasOverridden?: boolean;
}

export interface UserProfile {
  username: string;
  pin: string;
  school?: string;
  level: DifficultyLevel;
  stats: UserStats;
  history: QuestionAttemptLog[];
  lastSyncedAt?: number;
}

export interface LeaderboardEntry {
  rank?: number;
  username: string;
  school: string;
  level: DifficultyLevel;
  totalPoints: number;
  grammarPoints: number;
  mythologyPoints: number;
  historyPoints: number;
  culturePoints: number;
  literaturePoints: number;
  accuracy: number;
  totalAnswered: number;
  lastActive: string;
}

export type ReaderMode = 'visual' | 'audio';

export interface AppSettings {
  readerMode: ReaderMode; // 'visual' (typewriter on screen) or 'audio' (spoken aloud in-browser via Web Speech API)
  readingSpeed: number; // words per minute or delay in ms
  timerDuration: number; // seconds after buzz to answer (standard Certamen is 5s)
  soundEnabled: boolean;
  powerBuzzEnabled: boolean;
  speechRate: number; // rate for in-browser speech synthesis (e.g. 0.8 to 1.4)
  selectedVoiceURI?: string;
  appsScriptUrl: string;
  theme: 'classical-gold' | 'imperial-purple' | 'marble-dark';
}
