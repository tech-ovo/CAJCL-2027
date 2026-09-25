import { createClient, Client } from '@libsql/client/web';
import {
  ChapterStanding,
  UserProfile,
  QuestionAttemptLog,
  Category,
  DifficultyLevel,
  Question,
} from '../types/certamen';
import { INITIAL_QUESTION_BANK, flattenQuestions } from '../data/questionBank';

// Sample players, pooled into chapter standings, for when no database answers.
type SamplePlayer = Omit<ChapterStanding, 'rank' | 'players' | 'accuracy'> & {
  level: DifficultyLevel;
  totalCorrect: number;
};

const SAMPLE_PLAYERS: SamplePlayer[] = [
  { school: 'Boston Latin School', level: 'advanced', totalPoints: 1420, grammarPoints: 380, mythologyPoints: 290, historyPoints: 340, culturePoints: 210, literaturePoints: 200, totalAnswered: 156, totalCorrect: 142 },
  { school: 'Boston Latin School', level: 'novice', totalPoints: 310, grammarPoints: 90, mythologyPoints: 80, historyPoints: 60, culturePoints: 50, literaturePoints: 30, totalAnswered: 48, totalCorrect: 34 },
  { school: 'St. Albans Classics', level: 'intermediate', totalPoints: 1190, grammarPoints: 260, mythologyPoints: 350, historyPoints: 280, culturePoints: 190, literaturePoints: 110, totalAnswered: 135, totalCorrect: 119 },
  { school: 'Roxbury Latin', level: 'advanced', totalPoints: 980, grammarPoints: 210, mythologyPoints: 220, historyPoints: 310, culturePoints: 130, literaturePoints: 110, totalAnswered: 116, totalCorrect: 97 },
  { school: 'Roxbury Latin', level: 'intermediate', totalPoints: 620, grammarPoints: 170, mythologyPoints: 150, historyPoints: 140, culturePoints: 90, literaturePoints: 70, totalAnswered: 84, totalCorrect: 66 },
  { school: 'Phillips Academy', level: 'intermediate', totalPoints: 780, grammarPoints: 190, mythologyPoints: 210, historyPoints: 160, culturePoints: 120, literaturePoints: 100, totalAnswered: 98, totalCorrect: 77 },
  { school: 'Westminster Classical', level: 'novice', totalPoints: 540, grammarPoints: 150, mythologyPoints: 140, historyPoints: 120, culturePoints: 80, literaturePoints: 50, totalAnswered: 72, totalCorrect: 54 },
];

// Names nobody chose: the guest profile's and the blank-field fallback. They
// are not chapters, so their XP counts toward no one. Mirrors
// PLACEHOLDER_CHAPTERS in backend/lib/certamen_db.py.
const PLACEHOLDER_CHAPTERS = ['independent', 'roma antiqua academy'];

const SORT_COLUMNS: Record<Category | 'all', string> = {
  all: 'total_points',
  grammar: 'grammar_pts',
  mythology: 'mythology_pts',
  history: 'history_pts',
  culture: 'culture_pts',
  literature: 'literature_pts',
};

export function subjectPoints(entry: ChapterStanding, category: Category | 'all'): number {
  switch (category) {
    case 'grammar': return entry.grammarPoints;
    case 'mythology': return entry.mythologyPoints;
    case 'history': return entry.historyPoints;
    case 'culture': return entry.culturePoints;
    case 'literature': return entry.literaturePoints;
    default: return entry.totalPoints;
  }
}

let cachedClient: Client | null = null;
let cachedKey = '';
let schemaInitialized = false;

export function getApiBase(): string {
  if (typeof window !== 'undefined' && (window as any).CAJCL_CONFIG?.apiBase) {
    return (window as any).CAJCL_CONFIG.apiBase;
  }
  if (
    typeof window !== 'undefined' &&
    (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1')
  ) {
    return 'http://127.0.0.1:8000';
  }
  return 'https://techuhsjcl--cajcl-2027-web.modal.run';
}

function cleanUrl(url: string): string {
  let cleaned = (url || '').trim();
  if (cleaned.startsWith('libsql://')) {
    cleaned = cleaned.replace(/^libsql:\/\//, 'https://');
  }
  return cleaned;
}

export function getTursoClient(url?: string, authToken?: string): Client | null {
  const targetUrl = cleanUrl(url || '');
  const targetToken = (authToken || '').trim();

  if (!targetUrl) return null;

  const key = `${targetUrl}:${targetToken}`;
  if (cachedClient && cachedKey === key) {
    return cachedClient;
  }

  try {
    cachedClient = createClient({
      url: targetUrl,
      authToken: targetToken || undefined,
    });
    cachedKey = key;
    schemaInitialized = false;
    return cachedClient;
  } catch (err) {
    console.warn('Failed to initialize Turso client:', err);
    return null;
  }
}

export async function initTursoSchema(client: Client): Promise<void> {
  if (schemaInitialized) return;

  try {
    await client.batch([
      {
        sql: `CREATE TABLE IF NOT EXISTS certamen_questions (
          id TEXT PRIMARY KEY,
          category TEXT NOT NULL,
          difficulty TEXT NOT NULL,
          tossup TEXT NOT NULL,
          answers TEXT NOT NULL,
          explanation TEXT,
          source TEXT,
          power_mark_index INTEGER
        );`,
        args: [],
      },
      {
        sql: `CREATE TABLE IF NOT EXISTS certamen_users (
          username TEXT PRIMARY KEY,
          pin TEXT NOT NULL,
          school TEXT,
          level TEXT NOT NULL,
          total_points INTEGER DEFAULT 0,
          grammar_pts INTEGER DEFAULT 0,
          mythology_pts INTEGER DEFAULT 0,
          history_pts INTEGER DEFAULT 0,
          culture_pts INTEGER DEFAULT 0,
          literature_pts INTEGER DEFAULT 0,
          total_answered INTEGER DEFAULT 0,
          total_correct INTEGER DEFAULT 0,
          accuracy INTEGER DEFAULT 0,
          best_streak INTEGER DEFAULT 0,
          power_buzzes INTEGER DEFAULT 0,
          avg_buzz_pct INTEGER DEFAULT 0,
          last_active TEXT,
          raw_stats_json TEXT
        );`,
        args: [],
      },
      {
        sql: `CREATE TABLE IF NOT EXISTS certamen_attempts (
          id TEXT PRIMARY KEY,
          timestamp INTEGER NOT NULL,
          username TEXT NOT NULL,
          category TEXT NOT NULL,
          difficulty TEXT NOT NULL,
          question_text TEXT NOT NULL,
          user_answer TEXT,
          acceptable_answers TEXT,
          is_correct INTEGER NOT NULL,
          points_earned INTEGER NOT NULL,
          buzz_percentage INTEGER NOT NULL
        );`,
        args: [],
      },
    ]);

    // Check if questions table is empty; if so, auto-seed with initial question bank
    const countRes = await client.execute('SELECT COUNT(*) as count FROM certamen_questions;');
    const count = Number(countRes.rows[0]?.count ?? 0);
    if (count === 0) {
      const initial = flattenQuestions(INITIAL_QUESTION_BANK);
      const stmts = initial.map((q) => ({
        sql: `INSERT OR IGNORE INTO certamen_questions (
          id, category, difficulty, tossup, answers, explanation, source, power_mark_index
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?);`,
        args: [
          q.id,
          q.category,
          q.difficulty,
          q.tossup,
          JSON.stringify(q.answers),
          q.explanation || null,
          q.source || null,
          q.powerMarkIndex || null,
        ],
      }));
      if (stmts.length > 0) {
        await client.batch(stmts);
      }
    }

    schemaInitialized = true;
  } catch (err) {
    console.warn('Error initializing Turso schema:', err);
  }
}

export async function pingTurso(
  url?: string,
  authToken?: string
): Promise<{ success: boolean; message?: string; error?: string }> {
  // If direct Turso credentials are provided explicitly, test direct connection
  const hasDirectUrl = url && url.trim() && !url.includes('modal.run') && !url.includes('127.0.0.1') && !url.includes('localhost');
  if (hasDirectUrl) {
    const client = getTursoClient(url, authToken);
    if (!client) {
      return { success: false, error: 'Could not configure direct Turso client.' };
    }

    try {
      await initTursoSchema(client);
      const countRes = await client.execute('SELECT COUNT(*) as count FROM certamen_questions;');
      const count = countRes.rows[0]?.count ?? 0;
      return {
        success: true,
        message: `Connected directly to Turso! (${count} questions ready)`,
      };
    } catch (err) {
      return {
        success: false,
        error: err instanceof Error ? err.message : 'Failed to connect directly to Turso.',
      };
    }
  }

  // Otherwise, route through the Modal backend API (which uses TURSO_CERTAMEN_DATABASE_URL from Modal secrets)
  try {
    const apiBase = getApiBase();
    const res = await fetch(`${apiBase}/certamen/ping`);
    if (!res.ok) {
      throw new Error(`HTTP ${res.status}: ${res.statusText}`);
    }
    const data = await res.json();
    if (data.success) {
      return {
        success: true,
        message: data.message || `Connected to Turso via Modal backend! (${data.count} questions ready)`,
      };
    }
    return {
      success: false,
      error: data.error || 'Modal backend failed to connect to database.',
    };
  } catch (err) {
    return {
      success: false,
      error: err instanceof Error ? err.message : 'Could not reach backend /certamen/ping.',
    };
  }
}

export async function fetchQuestionsFromTurso(
  url?: string,
  authToken?: string,
  category: Category | 'all' = 'all',
  level: DifficultyLevel | 'all' = 'all',
  limit = 50,
  random = true,
  excludeIds?: string[]
): Promise<Question[]> {
  const hasDirectUrl = url && url.trim() && !url.includes('modal.run') && !url.includes('127.0.0.1') && !url.includes('localhost');

  if (hasDirectUrl) {
    const client = getTursoClient(url, authToken);
    if (client) {
      try {
        await initTursoSchema(client);
        const conditions: string[] = [];
        const args: any[] = [];

        if (category !== 'all') {
          conditions.push('category = ?');
          args.push(category);
        }
        if (level !== 'all') {
          conditions.push('difficulty = ?');
          args.push(level);
        }

        const whereClause = conditions.length > 0 ? `WHERE ${conditions.join(' AND ')}` : '';
        const orderClause = random ? 'ORDER BY RANDOM()' : 'ORDER BY id ASC';
        const limitClause = limit > 0 ? `LIMIT ${limit}` : '';

        const sql = `SELECT id, category, difficulty, tossup, answers, explanation, source, power_mark_index 
                     FROM certamen_questions ${whereClause} ${orderClause} ${limitClause};`;

        const res = await client.execute({ sql, args });

        const questions: Question[] = [];
        for (const row of res.rows) {
          let parsedAnswers: string[] = [];
          try {
            parsedAnswers = JSON.parse(String(row.answers));
          } catch {
            parsedAnswers = String(row.answers || '')
              .split(',')
              .map((a) => a.trim())
              .filter(Boolean);
          }

          questions.push({
            id: String(row.id),
            category: row.category as Category,
            difficulty: row.difficulty as DifficultyLevel,
            tossup: String(row.tossup),
            answers: parsedAnswers,
            explanation: row.explanation ? String(row.explanation) : undefined,
            source: row.source ? String(row.source) : undefined,
            powerMarkIndex: row.power_mark_index ? Number(row.power_mark_index) : undefined,
          });
        }

        if (excludeIds && excludeIds.length > 0) {
          const excludeSet = new Set(excludeIds);
          return questions.filter((q) => !excludeSet.has(q.id));
        }

        return questions;
      } catch (err) {
        console.warn('Direct Turso query failed, trying Modal proxy:', err);
      }
    }
  }

  // Route through Modal backend
  try {
    const apiBase = getApiBase();
    const params = new URLSearchParams();
    if (category !== 'all') params.set('category', category);
    if (level !== 'all') params.set('level', level);
    if (limit > 0) params.set('limit', String(limit));
    if (random) params.set('random', 'true');
    if (excludeIds && excludeIds.length > 0) {
      params.set('exclude', excludeIds.join(','));
    }

    const res = await fetch(`${apiBase}/certamen/questions?${params.toString()}`);
    if (res.ok) {
      const data = await res.json();
      const list = data.questions || data;
      if (Array.isArray(list) && list.length > 0) {
        return list;
      }
    }
  } catch (err) {
    console.warn('Failed to fetch questions via Modal proxy, using fallback:', err);
  }

  // Fallback to local questions
  const fallback = flattenQuestions(INITIAL_QUESTION_BANK);
  return fallback.filter((q) => {
    if (category !== 'all' && q.category !== category) return false;
    if (level !== 'all' && q.difficulty !== level) return false;
    if (excludeIds && excludeIds.includes(q.id)) return false;
    return true;
  });
}

export async function fetchLeaderboardFromTurso(
  url?: string,
  authToken?: string,
  category: Category | 'all' = 'all',
  level: DifficultyLevel | 'all' = 'all'
): Promise<ChapterStanding[]> {
  const hasDirectUrl = url && url.trim() && !url.includes('modal.run') && !url.includes('127.0.0.1') && !url.includes('localhost');

  if (hasDirectUrl) {
    const client = getTursoClient(url, authToken);
    if (client) {
      try {
        await initTursoSchema(client);
        const conditions = [
          "TRIM(COALESCE(school, '')) <> ''",
          `LOWER(TRIM(school)) NOT IN (${PLACEHOLDER_CHAPTERS.map(() => '?').join(', ')})`,
        ];
        const args: any[] = [...PLACEHOLDER_CHAPTERS];

        if (level !== 'all') {
          conditions.push('level = ?');
          args.push(level);
        }

        const sortCol = SORT_COLUMNS[category] || 'total_points';
        const sql = `SELECT MAX(TRIM(school)) AS school, COUNT(*) AS players,
                            SUM(total_points) AS total_points, SUM(grammar_pts) AS grammar_pts,
                            SUM(mythology_pts) AS mythology_pts, SUM(history_pts) AS history_pts,
                            SUM(culture_pts) AS culture_pts, SUM(literature_pts) AS literature_pts,
                            SUM(total_answered) AS total_answered, SUM(total_correct) AS total_correct
                     FROM certamen_users
                     WHERE ${conditions.join(' AND ')}
                     GROUP BY LOWER(TRIM(school))
                     ORDER BY SUM(${sortCol}) DESC, school
                     LIMIT 100;`;

        const res = await client.execute({ sql, args });
        if (res.rows.length > 0) {
          return res.rows.map((row, idx) => {
            const answered = Number(row.total_answered || 0);
            return {
              rank: idx + 1,
              school: String(row.school),
              players: Number(row.players || 0),
              totalPoints: Number(row.total_points || 0),
              grammarPoints: Number(row.grammar_pts || 0),
              mythologyPoints: Number(row.mythology_pts || 0),
              historyPoints: Number(row.history_pts || 0),
              culturePoints: Number(row.culture_pts || 0),
              literaturePoints: Number(row.literature_pts || 0),
              accuracy: answered > 0 ? Math.round((Number(row.total_correct || 0) * 100) / answered) : 0,
              totalAnswered: answered,
            };
          });
        }
      } catch (err) {
        console.warn('Direct leaderboard query failed, trying Modal proxy:', err);
      }
    }
  }

  // Route through Modal backend
  try {
    const apiBase = getApiBase();
    const params = new URLSearchParams();
    if (category !== 'all') params.set('category', category);
    if (level !== 'all') params.set('level', level);

    const res = await fetch(`${apiBase}/certamen/leaderboard?${params.toString()}`);
    if (res.ok) {
      const data = await res.json();
      const list = data.leaderboard || data;
      if (Array.isArray(list) && list.length > 0) {
        return list;
      }
    }
  } catch (err) {
    console.warn('Failed to fetch remote leaderboard via Modal proxy:', err);
  }

  return getFilteredMockLeaderboard(category, level);
}

export async function syncUserToTurso(
  url: string | undefined,
  authToken: string | undefined,
  user: UserProfile
): Promise<{ success: boolean; message?: string }> {
  const hasDirectUrl = url && url.trim() && !url.includes('modal.run') && !url.includes('127.0.0.1') && !url.includes('localhost');

  if (hasDirectUrl) {
    const client = getTursoClient(url, authToken);
    if (client) {
      try {
        await initTursoSchema(client);
        const s = user.stats;
        const cat = s.byCategory;
        const overallAcc = s.totalAnswered > 0 ? Math.round((s.totalCorrect / s.totalAnswered) * 100) : 0;

        const sql = `INSERT INTO certamen_users (
          username, pin, school, level,
          total_points, grammar_pts, mythology_pts, history_pts, culture_pts, literature_pts,
          total_answered, total_correct, accuracy, best_streak, power_buzzes, avg_buzz_pct,
          last_active, raw_stats_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(username) DO UPDATE SET
          pin = excluded.pin,
          school = excluded.school,
          level = excluded.level,
          total_points = excluded.total_points,
          grammar_pts = excluded.grammar_pts,
          mythology_pts = excluded.mythology_pts,
          history_pts = excluded.history_pts,
          culture_pts = excluded.culture_pts,
          literature_pts = excluded.literature_pts,
          total_answered = excluded.total_answered,
          total_correct = excluded.total_correct,
          accuracy = excluded.accuracy,
          best_streak = excluded.best_streak,
          power_buzzes = excluded.power_buzzes,
          avg_buzz_pct = excluded.avg_buzz_pct,
          last_active = excluded.last_active,
          raw_stats_json = excluded.raw_stats_json;`;

        await client.execute({
          sql,
          args: [
            user.username,
            user.pin,
            user.school || 'Independent',
            user.level,
            s.totalPoints,
            cat.grammar?.points || 0,
            cat.mythology?.points || 0,
            cat.history?.points || 0,
            cat.culture?.points || 0,
            cat.literature?.points || 0,
            s.totalAnswered,
            s.totalCorrect,
            overallAcc,
            s.bestStreak,
            s.powerBuzzes,
            s.averageBuzzPercentage,
            new Date().toISOString(),
            JSON.stringify(user.stats),
          ],
        });

        return { success: true, message: 'Synced to Turso!' };
      } catch (err) {
        console.warn('Direct sync failed:', err);
      }
    }
  }

  // Route through Modal backend
  try {
    const apiBase = getApiBase();
    const res = await fetch(`${apiBase}/certamen/sync-user`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ user }),
    });
    if (res.ok) {
      const data = await res.json();
      return { success: true, message: data.message || 'Synced to Turso!' };
    }
  } catch (err) {
    console.warn('Failed to sync user via Modal proxy:', err);
  }

  return { success: true, message: 'Saved locally' };
}

export async function logAttemptToTurso(
  url: string | undefined,
  authToken: string | undefined,
  attempt: QuestionAttemptLog & { username: string }
): Promise<void> {
  const hasDirectUrl = url && url.trim() && !url.includes('modal.run') && !url.includes('127.0.0.1') && !url.includes('localhost');

  if (hasDirectUrl) {
    const client = getTursoClient(url, authToken);
    if (client) {
      try {
        await initTursoSchema(client);
        await client.execute({
          sql: `INSERT INTO certamen_attempts (
            id, timestamp, username, category, difficulty,
            question_text, user_answer, acceptable_answers,
            is_correct, points_earned, buzz_percentage
          ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);`,
          args: [
            attempt.id,
            attempt.timestamp,
            attempt.username,
            attempt.category,
            attempt.difficulty,
            attempt.questionText,
            attempt.userAnswer,
            JSON.stringify(attempt.acceptableAnswers),
            attempt.isCorrect ? 1 : 0,
            attempt.pointsEarned,
            attempt.buzzPercentage,
          ],
        });
        return;
      } catch {
        // Fall through to Modal proxy
      }
    }
  }

  // Route through Modal backend
  try {
    const apiBase = getApiBase();
    await fetch(`${apiBase}/certamen/log-attempt`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ attempt }),
    });
  } catch {
    // Background log fails silently
  }
}

export async function loginUserFromTurso(
  url: string | undefined,
  authToken: string | undefined,
  username: string,
  pin: string
): Promise<UserProfile | null> {
  const hasDirectUrl = url && url.trim() && !url.includes('modal.run') && !url.includes('127.0.0.1') && !url.includes('localhost');

  if (hasDirectUrl) {
    const client = getTursoClient(url, authToken);
    if (client) {
      try {
        await initTursoSchema(client);
        const res = await client.execute({
          sql: `SELECT username, pin, school, level, raw_stats_json 
                FROM certamen_users 
                WHERE LOWER(username) = LOWER(?) AND pin = ?;`,
          args: [username.trim(), pin.trim()],
        });

        if (res.rows.length > 0) {
          const row = res.rows[0];
          let stats = null;
          try {
            if (row.raw_stats_json) {
              stats = JSON.parse(String(row.raw_stats_json));
            }
          } catch {
            // ignore
          }

          return {
            username: String(row.username),
            pin: String(row.pin),
            school: row.school ? String(row.school) : undefined,
            level: (row.level as DifficultyLevel) || 'novice',
            stats: stats || undefined,
            history: [],
            lastSyncedAt: Date.now(),
          };
        }
      } catch (err) {
        console.warn('Direct login failed:', err);
      }
    }
  }

  // Route through Modal backend
  try {
    const apiBase = getApiBase();
    const res = await fetch(`${apiBase}/certamen/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, pin }),
    });
    if (res.ok) {
      const data = await res.json();
      if (data.user) {
        return {
          username: String(data.user.username),
          pin: String(data.user.pin),
          school: data.user.school || undefined,
          level: (data.user.level as DifficultyLevel) || 'novice',
          stats: data.user.stats || undefined,
          history: [],
          lastSyncedAt: Date.now(),
        };
      }
    }
  } catch (err) {
    console.warn('Failed to login via Modal proxy:', err);
  }

  return null;
}

export async function uploadQuestionsBatchToTurso(
  url: string | undefined,
  authToken: string | undefined,
  questions: Question[],
  replace = false
): Promise<{ success: boolean; imported?: number; error?: string }> {
  // Try Modal proxy
  try {
    const apiBase = getApiBase();
    const res = await fetch(`${apiBase}/certamen/questions/batch`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ questions, replace }),
    });
    if (res.ok) {
      const data = await res.json();
      return { success: true, imported: data.imported ?? questions.length };
    }
  } catch (err) {
    console.warn('Failed to batch upload questions via Modal proxy:', err);
  }

  // Fallback to direct client
  const hasDirectUrl = url && url.trim() && !url.includes('modal.run') && !url.includes('127.0.0.1') && !url.includes('localhost');
  if (hasDirectUrl) {
    const client = getTursoClient(url, authToken);
    if (!client) {
      return { success: false, error: 'Turso database is not configured' };
    }

    try {
      await initTursoSchema(client);
      const stmts: { sql: string; args: any[] }[] = [];

      if (replace) {
        stmts.push({ sql: 'DELETE FROM certamen_questions;', args: [] });
      }

      for (const q of questions) {
        stmts.push({
          sql: `INSERT OR REPLACE INTO certamen_questions (
            id, category, difficulty, tossup, answers, explanation, source, power_mark_index
          ) VALUES (?, ?, ?, ?, ?, ?, ?, ?);`,
          args: [
            q.id,
            q.category,
            q.difficulty,
            q.tossup,
            JSON.stringify(q.answers),
            q.explanation || null,
            q.source || null,
            q.powerMarkIndex || null,
          ],
        });
      }

      const BATCH_SIZE = 100;
      for (let i = 0; i < stmts.length; i += BATCH_SIZE) {
        const chunk = stmts.slice(i, i + BATCH_SIZE);
        await client.batch(chunk);
      }

      return { success: true, imported: questions.length };
    } catch (err) {
      return {
        success: false,
        error: err instanceof Error ? err.message : 'Batch upload failed.',
      };
    }
  }

  return { success: false, error: 'Could not upload questions.' };
}

function getFilteredMockLeaderboard(
  category: Category | 'all',
  level: DifficultyLevel | 'all'
): ChapterStanding[] {
  const byChapter = new Map<string, ChapterStanding & { totalCorrect: number }>();
  for (const p of SAMPLE_PLAYERS) {
    if (level !== 'all' && p.level !== level) continue;
    const c = byChapter.get(p.school) || {
      rank: 0, school: p.school, players: 0, totalPoints: 0, grammarPoints: 0, mythologyPoints: 0,
      historyPoints: 0, culturePoints: 0, literaturePoints: 0, accuracy: 0, totalAnswered: 0, totalCorrect: 0,
    };
    c.players += 1;
    c.totalPoints += p.totalPoints;
    c.grammarPoints += p.grammarPoints;
    c.mythologyPoints += p.mythologyPoints;
    c.historyPoints += p.historyPoints;
    c.culturePoints += p.culturePoints;
    c.literaturePoints += p.literaturePoints;
    c.totalAnswered += p.totalAnswered;
    c.totalCorrect += p.totalCorrect;
    byChapter.set(p.school, c);
  }

  return Array.from(byChapter.values())
    .sort((a, b) => subjectPoints(b, category) - subjectPoints(a, category))
    .map(({ totalCorrect, ...c }, idx) => ({
      ...c,
      rank: idx + 1,
      accuracy: c.totalAnswered > 0 ? Math.round((totalCorrect * 100) / c.totalAnswered) : 0,
    }));
}
