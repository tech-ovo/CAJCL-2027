import { LeaderboardEntry, UserProfile, QuestionAttemptLog, Category, DifficultyLevel, Question } from '../types/certamen';

// Fallback seed leaderboard data to display when no Google Sheet is connected yet
export const MOCK_LEADERBOARD: LeaderboardEntry[] = [
  {
    rank: 1,
    username: 'MarcusTullius',
    school: 'Boston Latin School',
    level: 'advanced',
    totalPoints: 1420,
    grammarPoints: 380,
    mythologyPoints: 290,
    historyPoints: 340,
    culturePoints: 210,
    literaturePoints: 200,
    accuracy: 91,
    totalAnswered: 156,
    lastActive: new Date(Date.now() - 3600000 * 4).toISOString(),
  },
  {
    rank: 2,
    username: 'Julia_Augusta',
    school: 'St. Albans Classics',
    level: 'intermediate',
    totalPoints: 1190,
    grammarPoints: 260,
    mythologyPoints: 350,
    historyPoints: 280,
    culturePoints: 190,
    literaturePoints: 110,
    accuracy: 88,
    totalAnswered: 135,
    lastActive: new Date(Date.now() - 3600000 * 12).toISOString(),
  },
  {
    rank: 3,
    username: 'Publius_Scipio',
    school: 'Roxbury Latin',
    level: 'advanced',
    totalPoints: 980,
    grammarPoints: 210,
    mythologyPoints: 220,
    historyPoints: 310,
    culturePoints: 130,
    literaturePoints: 110,
    accuracy: 84,
    totalAnswered: 116,
    lastActive: new Date(Date.now() - 3600000 * 24).toISOString(),
  },
  {
    rank: 4,
    username: 'LucretiaV',
    school: 'Phillips Academy',
    level: 'intermediate',
    totalPoints: 780,
    grammarPoints: 190,
    mythologyPoints: 210,
    historyPoints: 160,
    culturePoints: 120,
    literaturePoints: 100,
    accuracy: 79,
    totalAnswered: 98,
    lastActive: new Date(Date.now() - 3600000 * 48).toISOString(),
  },
  {
    rank: 5,
    username: 'NoviceGladiator',
    school: 'Westminster Classical',
    level: 'novice',
    totalPoints: 540,
    grammarPoints: 150,
    mythologyPoints: 140,
    historyPoints: 120,
    culturePoints: 80,
    literaturePoints: 50,
    accuracy: 75,
    totalAnswered: 72,
    lastActive: new Date(Date.now() - 3600000 * 72).toISOString(),
  },
];

export async function pingAppsScript(url: string): Promise<{ success: boolean; message?: string; error?: string }> {
  if (!url || !url.startsWith('http')) {
    return { success: false, error: 'Please enter a valid Google Apps Script Web App URL.' };
  }

  try {
    const target = `${url}${url.includes('?') ? '&' : '?'}action=ping&_t=${Date.now()}`;
    const res = await fetch(target, { method: 'GET', mode: 'cors' });
    if (!res.ok) {
      return { success: false, error: `HTTP ${res.status}: ${res.statusText}` };
    }
    const data = await res.json();
    return { success: true, message: data.message || 'Connected successfully to Google Sheets!' };
  } catch (err) {
    return { success: false, error: err instanceof Error ? err.message : 'Network error connecting to Apps Script.' };
  }
}

export async function fetchLeaderboardFromCloud(
  url: string,
  category: Category | 'all' = 'all',
  level: DifficultyLevel | 'all' = 'all'
): Promise<LeaderboardEntry[]> {
  if (!url || !url.startsWith('http')) {
    // Return mock leaderboard filtered by category and level
    return getFilteredMockLeaderboard(category, level);
  }

  try {
    const query = new URLSearchParams({
      action: 'getLeaderboard',
      category,
      level,
      _t: Date.now().toString(),
    });

    const res = await fetch(`${url}${url.includes('?') ? '&' : '?'}${query.toString()}`, {
      method: 'GET',
      mode: 'cors',
    });

    if (!res.ok) {
      console.warn('Google Apps Script request failed, using local data');
      return getFilteredMockLeaderboard(category, level);
    }

    const data = await res.json();
    if (data && data.success && Array.isArray(data.leaderboard)) {
      return data.leaderboard;
    }
    return getFilteredMockLeaderboard(category, level);
  } catch (err) {
    console.warn('Failed to fetch remote leaderboard, using local fallback:', err);
    return getFilteredMockLeaderboard(category, level);
  }
}

export async function syncUserToCloud(url: string, user: UserProfile): Promise<{ success: boolean; message?: string }> {
  if (!url || !url.startsWith('http')) {
    // Local storage only
    return { success: true, message: 'Saved locally (Cloud URL not set)' };
  }

  try {
    const payload = {
      action: 'syncUser',
      user: {
        username: user.username,
        pin: user.pin,
        school: user.school || 'Independent',
        level: user.level,
        stats: user.stats,
      },
    };

    const res = await fetch(url, {
      method: 'POST',
      mode: 'cors',
      headers: {
        'Content-Type': 'text/plain;charset=utf-8', // Plain text avoids CORS preflight OPTIONS in Apps Script
      },
      body: JSON.stringify(payload),
    });

    const data = await res.json();
    return { success: !!data.success, message: data.message || 'Synced to Google Sheets!' };
  } catch (err) {
    console.warn('Failed to sync to cloud:', err);
    return { success: false, message: 'Could not reach Google Sheets backend' };
  }
}

export async function logAttemptToCloud(url: string, attempt: QuestionAttemptLog & { username: string }): Promise<void> {
  if (!url || !url.startsWith('http')) return;

  try {
    await fetch(url, {
      method: 'POST',
      mode: 'cors',
      headers: {
        'Content-Type': 'text/plain;charset=utf-8',
      },
      body: JSON.stringify({
        action: 'logAttempt',
        attempt,
      }),
    });
  } catch {
    // Fail silently for background logging
  }
}

export async function loginUserFromCloud(url: string, username: string, pin: string): Promise<UserProfile | null> {
  if (!url || !url.startsWith('http')) {
    return null;
  }

  try {
    const query = new URLSearchParams({
      action: 'getUser',
      username,
      pin,
      _t: Date.now().toString(),
    });

    const res = await fetch(`${url}${url.includes('?') ? '&' : '?'}${query.toString()}`, {
      method: 'GET',
      mode: 'cors',
    });

    if (!res.ok) return null;
    const data = await res.json();
    if (data && data.success && data.user) {
      return {
        username: data.user.username,
        pin: data.user.pin,
        school: data.user.school,
        level: data.user.level,
        stats: data.user.stats,
        history: [],
        lastSyncedAt: Date.now(),
      };
    }
    return null;
  } catch (err) {
    console.error('Error logging in from cloud:', err);
    return null;
  }
}

function getFilteredMockLeaderboard(category: Category | 'all', level: DifficultyLevel | 'all'): LeaderboardEntry[] {
  let list = [...MOCK_LEADERBOARD];

  if (level !== 'all') {
    list = list.filter((item) => item.level === level);
  }

  list.sort((a, b) => {
    if (category === 'grammar') return b.grammarPoints - a.grammarPoints;
    if (category === 'mythology') return b.mythologyPoints - a.mythologyPoints;
    if (category === 'history') return b.historyPoints - a.historyPoints;
    if (category === 'culture') return b.culturePoints - a.culturePoints;
    if (category === 'literature') return b.literaturePoints - a.literaturePoints;
    return b.totalPoints - a.totalPoints;
  });

  return list.map((item, idx) => ({ ...item, rank: idx + 1 }));
}

export async function fetchQuestionsFromCloud(
  url: string,
  category: Category | 'all' = 'all',
  level: DifficultyLevel | 'all' = 'all',
  limit = 50,
  random = true,
  excludeIds?: string[]
): Promise<Question[]> {
  if (!url || !url.startsWith('http')) {
    return [];
  }

  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 25000);

  try {
    const params: Record<string, string> = {
      action: 'getQuestions',
      category,
      level,
      limit: limit.toString(),
      random: random ? 'true' : 'false',
      _t: `${Date.now()}_${Math.random().toString(36).substr(2, 6)}`,
    };

    if (excludeIds && excludeIds.length > 0) {
      params.exclude = excludeIds.slice(-80).join(',');
    }

    const query = new URLSearchParams(params);

    const res = await fetch(`${url}${url.includes('?') ? '&' : '?'}${query.toString()}`, {
      method: 'GET',
      mode: 'cors',
      redirect: 'follow',
      signal: controller.signal,
    });

    clearTimeout(timeoutId);

    if (!res.ok) return [];
    const data = await res.json();
    if (data && data.success && Array.isArray(data.questions)) {
      const list = [...data.questions];
      if (random && list.length > 0) {
        for (let i = list.length - 1; i > 0; i--) {
          const j = Math.floor(Math.random() * (i + 1));
          const temp = list[i];
          list[i] = list[j];
          list[j] = temp;
        }
      }
      return list;
    }
    return [];
  } catch (err) {
    clearTimeout(timeoutId);
    console.warn('Failed to fetch remote questions from Google Sheets:', err);
    return [];
  }
}

export async function uploadQuestionsBatchToCloud(
  url: string,
  questions: Question[],
  replace = false
): Promise<{ success: boolean; imported?: number; error?: string }> {
  if (!url || !url.startsWith('http')) {
    return { success: false, error: 'Invalid Google Apps Script URL' };
  }

  try {
    const payload = {
      action: 'importQuestions',
      replace,
      questions,
    };

    const res = await fetch(url, {
      method: 'POST',
      mode: 'cors',
      headers: {
        'Content-Type': 'text/plain;charset=utf-8',
      },
      body: JSON.stringify(payload),
    });

    const data = await res.json();
    return {
      success: !!data.success,
      imported: data.imported,
      error: data.error,
    };
  } catch (err) {
    console.warn('Failed to upload questions to Google Sheets:', err);
    return {
      success: false,
      error: err instanceof Error ? err.message : 'Network error uploading questions',
    };
  }
}

