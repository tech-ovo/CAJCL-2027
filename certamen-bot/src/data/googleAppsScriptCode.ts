export const GOOGLE_APPS_SCRIPT_CODE = `/**
 * CERTAMEN MASTER - Google Apps Script Backend
 * 
 * Instructions:
 * 1. Open Google Sheets (create a new blank spreadsheet: "Certamen Master Database").
 * 2. Click Extensions > Apps Script.
 * 3. Delete any default code in Code.gs and PASTE THIS ENTIRE SCRIPT.
 * 4. Click the Blue "Deploy" button (top right) > "New deployment".
 * 5. Select type: "Web app".
 * 6. Set:
 *    - Description: "Certamen Master API v1"
 *    - Execute as: "Me"
 *    - Who has access: "Anyone" (Required so your app can sync scores without OAuth popups)
 * 7. Click "Deploy", authorize permissions when prompted.
 * 8. Copy the Web App URL (starts with https://script.google.com/macros/s/.../exec)
 * 9. Paste that URL into the Certamen Master App Settings!
 */

function doGet(e) {
  try {
    const params = e ? e.parameter : {};
    const action = params.action || 'getLeaderboard';
    const ss = SpreadsheetApp.getActiveSpreadsheet();
    setupSheetsIfNeeded(ss);

    if (action === 'getQuestions' || action === 'getRandomQuestions') {
      const category = params.category || 'all';
      const level = params.level || params.difficulty || 'all';
      const rawLimit = params.limit;
      const limit = (rawLimit === 'all' || rawLimit === '0') ? 0 : parseInt(rawLimit || '50', 10);
      const isRandom = action === 'getRandomQuestions' || params.random === 'true' || params.random === '1';
      const excludeStr = params.exclude || params.excludeIds || '';
      const questions = getQuestionsData(ss, category, level, limit, isRandom, excludeStr);
      return jsonResponse({ success: true, count: questions.length, questions: questions });
    }

    if (action === 'getLeaderboard') {
      const category = params.category || 'all';
      const level = params.level || 'all';
      const leaderboard = getLeaderboardData(ss, category, level);
      return jsonResponse({ success: true, leaderboard: leaderboard });
    }

    if (action === 'getUser') {
      const username = (params.username || '').trim().toLowerCase();
      const pin = (params.pin || '').trim();
      const user = getUserData(ss, username, pin);
      if (!user) {
        return jsonResponse({ success: false, message: 'User not found or invalid PIN' });
      }
      return jsonResponse({ success: true, user: user });
    }

    if (action === 'ping') {
      return jsonResponse({ success: true, message: 'Certamen Master Google Apps Script is active!' });
    }

    return jsonResponse({ success: false, message: 'Unknown action: ' + action });
  } catch (err) {
    return jsonResponse({ success: false, error: err.toString() });
  }
}

function doPost(e) {
  try {
    const ss = SpreadsheetApp.getActiveSpreadsheet();
    setupSheetsIfNeeded(ss);

    let data;
    if (e && e.postData && e.postData.contents) {
      data = JSON.parse(e.postData.contents);
    } else if (e && e.parameter) {
      data = e.parameter;
    } else {
      return jsonResponse({ success: false, error: 'No post payload received' });
    }

    const action = data.action || 'syncUser';

    if (action === 'syncUser') {
      const result = saveOrUpdateUser(ss, data.user);
      return jsonResponse({ success: true, result: result });
    }

    if (action === 'logAttempt') {
      logQuestionAttempt(ss, data.attempt);
      return jsonResponse({ success: true });
    }

    if (action === 'importQuestions') {
      const count = importQuestionsBatch(ss, data.questions, !!data.replace);
      return jsonResponse({ success: true, imported: count });
    }

    return jsonResponse({ success: false, error: 'Unknown POST action: ' + action });
  } catch (err) {
    return jsonResponse({ success: false, error: err.toString() });
  }
}

function setupSheetsIfNeeded(ss) {
  // 1. Users Sheet
  let usersSheet = ss.getSheetByName('Users');
  if (!usersSheet) {
    usersSheet = ss.insertSheet('Users');
    usersSheet.appendRow([
      'Username',
      'PIN',
      'School',
      'Level',
      'Total Points',
      'Grammar Pts',
      'Mythology Pts',
      'History Pts',
      'Culture Pts',
      'Literature Pts',
      'Total Answered',
      'Total Correct',
      'Accuracy %',
      'Best Streak',
      'Power Buzzes',
      'Avg Buzz %',
      'Last Active',
      'Raw Stats JSON'
    ]);
    usersSheet.getRange(1, 1, 1, 18).setFontWeight('bold').setBackground('#E8EAED');
    usersSheet.setFrozenRows(1);
  }

  // 2. Attempts Log Sheet
  let logSheet = ss.getSheetByName('Attempts_Log');
  if (!logSheet) {
    logSheet = ss.insertSheet('Attempts_Log');
    logSheet.appendRow([
      'Timestamp',
      'Username',
      'Category',
      'Difficulty',
      'Question',
      'User Answer',
      'Acceptable Answers',
      'Result',
      'Points Earned',
      'Buzz %'
    ]);
    logSheet.getRange(1, 1, 1, 10).setFontWeight('bold').setBackground('#E8EAED');
    logSheet.setFrozenRows(1);
  }

  // 3. Questions Sheet
  let questionsSheet = ss.getSheetByName('Questions');
  if (!questionsSheet) {
    questionsSheet = ss.insertSheet('Questions');
    questionsSheet.appendRow([
      'ID',
      'Category',
      'Difficulty',
      'Tossup',
      'Answers (JSON)',
      'Explanation',
      'Source'
    ]);
    questionsSheet.getRange(1, 1, 1, 7).setFontWeight('bold').setBackground('#E8EAED');
    questionsSheet.setFrozenRows(1);
  }
}

function importQuestionsBatch(ss, questions, replace) {
  if (!questions || !questions.length) return 0;
  let sheet = ss.getSheetByName('Questions');
  if (!sheet) {
    setupSheetsIfNeeded(ss);
    sheet = ss.getSheetByName('Questions');
  }

  if (replace) {
    sheet.clearContents();
    sheet.appendRow(['ID', 'Category', 'Difficulty', 'Tossup', 'Answers (JSON)', 'Explanation', 'Source']);
    sheet.getRange(1, 1, 1, 7).setFontWeight('bold').setBackground('#E8EAED');
    sheet.setFrozenRows(1);
  }

  const rows = questions.map(function(q) {
    return [
      q.id || '',
      q.category || '',
      q.difficulty || '',
      q.tossup || '',
      JSON.stringify(q.answers || []),
      q.explanation || '',
      q.source || ''
    ];
  });

  sheet.getRange(sheet.getLastRow() + 1, 1, rows.length, 7).setValues(rows);
  return rows.length;
}

function getQuestionsData(ss, category, levelFilter, limit, isRandom, excludeStr) {
  const sheet = ss.getSheetByName('Questions');
  if (!sheet) return [];
  const lastRow = sheet.getLastRow();
  if (lastRow <= 1) return [];

  const totalRows = lastRow - 1;
  const targetLimit = (limit && limit > 0) ? limit : totalRows;
  const list = [];

  const catFilter = (category && category !== 'all') ? category.toLowerCase().trim() : null;
  const diffFilter = (levelFilter && levelFilter !== 'all') ? levelFilter.toLowerCase().trim() : null;

  const excludeSet = {};
  if (excludeStr) {
    const parts = String(excludeStr).split(',');
    for (let p = 0; p < parts.length; p++) {
      const trimmed = parts[p].trim();
      if (trimmed) excludeSet[trimmed] = true;
    }
  }

  // 1. Fast metadata scan on ID, Category & Difficulty columns (cols 1, 2 & 3)
  const meta = sheet.getRange(2, 1, totalRows, 3).getValues();
  let matchRowOffsets = []; // 0-based offset from row 2

  for (let i = 0; i < meta.length; i++) {
    const rowId = String(meta[i][0] || '').trim();
    const rowCat = String(meta[i][1] || '').toLowerCase().trim();
    const rowDiff = String(meta[i][2] || '').toLowerCase().trim();

    if (rowId && excludeSet[rowId]) continue;
    if (catFilter && rowCat !== catFilter) continue;
    if (diffFilter && rowDiff !== diffFilter) continue;

    matchRowOffsets.push(i);
  }

  // If exclusions left no matching rows, retry without exclusions so user is never stuck
  if (matchRowOffsets.length === 0 && Object.keys(excludeSet).length > 0) {
    for (let i = 0; i < meta.length; i++) {
      const rowCat = String(meta[i][1] || '').toLowerCase().trim();
      const rowDiff = String(meta[i][2] || '').toLowerCase().trim();

      if (catFilter && rowCat !== catFilter) continue;
      if (diffFilter && rowDiff !== diffFilter) continue;

      matchRowOffsets.push(i);
    }
  }

  if (matchRowOffsets.length === 0) return [];

  // 2. If random, shuffle the matched row offsets
  if (isRandom) {
    for (let i = matchRowOffsets.length - 1; i > 0; i--) {
      const j = Math.floor(Math.random() * (i + 1));
      const temp = matchRowOffsets[i];
      matchRowOffsets[i] = matchRowOffsets[j];
      matchRowOffsets[j] = temp;
    }
  }

  const selectedOffsets = matchRowOffsets.slice(0, targetLimit);

  // 3. Fast Data Fetch for matched rows
  let minOffset = selectedOffsets[0];
  let maxOffset = selectedOffsets[0];
  for (let m = 1; m < selectedOffsets.length; m++) {
    if (selectedOffsets[m] < minOffset) minOffset = selectedOffsets[m];
    if (selectedOffsets[m] > maxOffset) maxOffset = selectedOffsets[m];
  }
  const span = maxOffset - minOffset + 1;

  if (span <= 4000) {
    const blockData = sheet.getRange(minOffset + 2, 1, span, 7).getValues();
    for (let k = 0; k < selectedOffsets.length; k++) {
      const relIdx = selectedOffsets[k] - minOffset;
      const row = blockData[relIdx];
      if (!row || (!row[0] && !row[3])) continue;

      let answers = [];
      try {
        answers = JSON.parse(row[4]);
      } catch (e) {
        answers = [String(row[4] || '')];
      }

      list.push({
        id: String(row[0]),
        category: String(row[1] || '').toLowerCase().trim(),
        difficulty: String(row[2] || '').toLowerCase().trim(),
        tossup: String(row[3] || ''),
        answers: answers,
        explanation: String(row[5] || ''),
        source: String(row[6] || '')
      });
    }
  } else {
    for (let k = 0; k < selectedOffsets.length; k++) {
      const rowNum = selectedOffsets[k] + 2;
      const row = sheet.getRange(rowNum, 1, 1, 7).getValues()[0];
      if (!row || (!row[0] && !row[3])) continue;

      let answers = [];
      try {
        answers = JSON.parse(row[4]);
      } catch (e) {
        answers = [String(row[4] || '')];
      }

      list.push({
        id: String(row[0]),
        category: String(row[1] || '').toLowerCase().trim(),
        difficulty: String(row[2] || '').toLowerCase().trim(),
        tossup: String(row[3] || ''),
        answers: answers,
        explanation: String(row[5] || ''),
        source: String(row[6] || '')
      });
    }
  }

  return list;
}

function saveOrUpdateUser(ss, user) {
  if (!user || !user.username) throw new Error('User profile missing');
  const sheet = ss.getSheetByName('Users');
  const data = sheet.getDataRange().getValues();
  const usernameClean = (user.username || '').trim().toLowerCase();
  
  const stats = user.stats || {};
  const byCat = stats.byCategory || {};
  const grammarPts = (byCat.grammar && byCat.grammar.points) || 0;
  const mythPts = (byCat.mythology && byCat.mythology.points) || 0;
  const histPts = (byCat.history && byCat.history.points) || 0;
  const cultPts = (byCat.culture && byCat.culture.points) || 0;
  const litPts = (byCat.literature && byCat.literature.points) || 0;
  
  const totalAnswered = stats.totalAnswered || 0;
  const totalCorrect = stats.totalCorrect || 0;
  const accuracy = totalAnswered > 0 ? Math.round((totalCorrect / totalAnswered) * 100) : 0;
  const nowStr = new Date().toISOString();

  let rowIndex = -1;
  for (let i = 1; i < data.length; i++) {
    if (String(data[i][0]).trim().toLowerCase() === usernameClean) {
      rowIndex = i + 1; // 1-indexed for Sheets
      break;
    }
  }

  const rowData = [
    user.username,
    user.pin || '0000',
    user.school || 'Independent',
    user.level || 'novice',
    stats.totalPoints || 0,
    grammarPts,
    mythPts,
    histPts,
    cultPts,
    litPts,
    totalAnswered,
    totalCorrect,
    accuracy,
    stats.bestStreak || 0,
    stats.powerBuzzes || 0,
    stats.averageBuzzPercentage || 0,
    nowStr,
    JSON.stringify(stats)
  ];

  if (rowIndex > 0) {
    sheet.getRange(rowIndex, 1, 1, rowData.length).setValues([rowData]);
    return { status: 'updated', username: user.username };
  } else {
    sheet.appendRow(rowData);
    return { status: 'created', username: user.username };
  }
}

function getUserData(ss, username, pin) {
  const sheet = ss.getSheetByName('Users');
  const data = sheet.getDataRange().getValues();
  
  for (let i = 1; i < data.length; i++) {
    const row = data[i];
    if (String(row[0]).trim().toLowerCase() === username) {
      if (pin && String(row[1]).trim() !== pin) {
        return null; // PIN mismatch
      }
      let parsedStats = null;
      try {
        parsedStats = JSON.parse(row[17]);
      } catch (e) {
        parsedStats = null;
      }

      return {
        username: row[0],
        pin: row[1],
        school: row[2],
        level: row[3],
        stats: parsedStats || {
          totalPoints: Number(row[4]) || 0,
          totalAnswered: Number(row[10]) || 0,
          totalCorrect: Number(row[11]) || 0,
          bestStreak: Number(row[13]) || 0,
          powerBuzzes: Number(row[14]) || 0,
          averageBuzzPercentage: Number(row[15]) || 0,
          byCategory: {
            grammar: { points: Number(row[5]) || 0, answered: 0, correct: 0 },
            mythology: { points: Number(row[6]) || 0, answered: 0, correct: 0 },
            history: { points: Number(row[7]) || 0, answered: 0, correct: 0 },
            culture: { points: Number(row[8]) || 0, answered: 0, correct: 0 },
            literature: { points: Number(row[9]) || 0, answered: 0, correct: 0 }
          }
        },
        lastSyncedAt: new Date(row[16]).getTime()
      };
    }
  }
  return null;
}

function getLeaderboardData(ss, category, levelFilter) {
  const sheet = ss.getSheetByName('Users');
  const data = sheet.getDataRange().getValues();
  if (data.length <= 1) return [];

  const list = [];
  for (let i = 1; i < data.length; i++) {
    const row = data[i];
    const userLevel = String(row[3] || 'novice').toLowerCase();

    if (levelFilter && levelFilter !== 'all' && userLevel !== levelFilter.toLowerCase()) {
      continue;
    }

    list.push({
      username: String(row[0]),
      school: String(row[2] || 'Independent'),
      level: userLevel,
      totalPoints: Number(row[4]) || 0,
      grammarPoints: Number(row[5]) || 0,
      mythologyPoints: Number(row[6]) || 0,
      historyPoints: Number(row[7]) || 0,
      culturePoints: Number(row[8]) || 0,
      literaturePoints: Number(row[9]) || 0,
      totalAnswered: Number(row[10]) || 0,
      totalCorrect: Number(row[11]) || 0,
      accuracy: Number(row[12]) || 0,
      lastActive: String(row[16])
    });
  }

  // Sort based on category
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

function logQuestionAttempt(ss, attempt) {
  if (!attempt) return;
  const sheet = ss.getSheetByName('Attempts_Log');
  sheet.appendRow([
    new Date(attempt.timestamp || Date.now()).toISOString(),
    attempt.username || 'Anonymous',
    attempt.category || '',
    attempt.difficulty || '',
    attempt.questionText || '',
    attempt.userAnswer || '',
    Array.isArray(attempt.acceptableAnswers) ? attempt.acceptableAnswers.join(' | ') : '',
    attempt.isCorrect ? 'CORRECT' : 'INCORRECT',
    attempt.pointsEarned || 0,
    attempt.buzzPercentage || 0
  ]);
}

function jsonResponse(obj) {
  return ContentService.createTextOutput(JSON.stringify(obj))
    .setMimeType(ContentService.MimeType.JSON);
}
`;
