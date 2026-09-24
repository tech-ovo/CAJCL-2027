"""Turso database connection and operations for Certamen Arena.

Provides dedicated access to the Certamen Turso database configured via
TURSO_CERTAMEN_DATABASE_URL and TURSO_CERTAMEN_AUTH_TOKEN (set in Modal secrets).
Falls back to a local SQLite database (certamen.db) when no remote URL is set.
"""

from __future__ import annotations

import json
import os
import random
import re
import sqlite3
import threading
from pathlib import Path
from typing import Any

REMOTE_SCHEMES = ("libsql://", "https://", "http://")
_HEADER_SAFE = re.compile(r"^[\x20-\x7e]*$")

_tls = threading.local()
_schema_initialized = False
_init_lock = threading.Lock()

INITIAL_QUESTIONS_PATH = Path(__file__).resolve().parent / "certamen_initial_questions.json"


def _clean_credential(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned if _HEADER_SAFE.match(cleaned) else None


def get_certamen_db_config() -> tuple[str, str | None, bool]:
    url = os.environ.get("TURSO_CERTAMEN_DATABASE_URL")
    token = os.environ.get("TURSO_CERTAMEN_AUTH_TOKEN")
    if url:
        cleaned_url = url.strip()
        cleaned_token = _clean_credential(token)
        is_remote = any(cleaned_url.startswith(s) for s in REMOTE_SCHEMES)
        return cleaned_url, cleaned_token, is_remote
    # Local fallback
    return "certamen.db", None, False


def _get_connection():
    if not hasattr(_tls, "conn") or _tls.conn is None:
        url, token, is_remote = get_certamen_db_config()
        if is_remote:
            import libsql
            _tls.conn = libsql.connect(url, auth_token=token or "", isolation_level=None)
        else:
            local_path = url[5:] if url.startswith("file:") else url
            conn = sqlite3.connect(local_path, timeout=10.0, check_same_thread=False, isolation_level=None)
            conn.execute("PRAGMA foreign_keys = ON")
            conn.execute("PRAGMA journal_mode = WAL")
            _tls.conn = conn
    return _tls.conn


def _reset_connection():
    if hasattr(_tls, "conn") and _tls.conn is not None:
        try:
            _tls.conn.close()
        except Exception:
            pass
        _tls.conn = None


def query(sql: str, params: tuple = ()) -> list[dict[str, Any]]:
    conn = _get_connection()
    try:
        cursor = conn.execute(sql, params)
        cols = [c[0] for c in (cursor.description or ())]
        if not cols:
            return []
        rows = cursor.fetchall() or ()
        return [dict(zip(cols, row)) for row in rows]
    except Exception:
        _reset_connection()
        # Retry once on reconnect
        conn = _get_connection()
        cursor = conn.execute(sql, params)
        cols = [c[0] for c in (cursor.description or ())]
        if not cols:
            return []
        rows = cursor.fetchall() or ()
        return [dict(zip(cols, row)) for row in rows]


def execute(sql: str, params: tuple = ()) -> int:
    conn = _get_connection()
    try:
        cursor = conn.execute(sql, params)
        return cursor.rowcount
    except Exception:
        _reset_connection()
        conn = _get_connection()
        cursor = conn.execute(sql, params)
        return cursor.rowcount


def init_schema():
    global _schema_initialized
    if _schema_initialized:
        return
    with _init_lock:
        if _schema_initialized:
            return

        conn = _get_connection()
        conn.execute("""
            CREATE TABLE IF NOT EXISTS certamen_questions (
                id TEXT PRIMARY KEY,
                category TEXT NOT NULL,
                difficulty TEXT NOT NULL,
                tossup TEXT NOT NULL,
                answers TEXT NOT NULL,
                explanation TEXT,
                source TEXT,
                power_mark_index INTEGER
            );
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS certamen_users (
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
            );
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS certamen_attempts (
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
            );
        """)

        # Auto-seed if questions table is empty
        try:
            cursor = conn.execute("SELECT COUNT(*) as count FROM certamen_questions;")
            row = cursor.fetchone()
            count = row[0] if row else 0
            if count == 0 and INITIAL_QUESTIONS_PATH.exists():
                with open(INITIAL_QUESTIONS_PATH, "r", encoding="utf-8") as f:
                    seed_questions = json.load(f)
                rows_to_insert = [
                    (
                        q["id"],
                        q["category"],
                        q["difficulty"],
                        q["tossup"],
                        json.dumps(q.get("answers", [])),
                        q.get("explanation"),
                        q.get("source"),
                        q.get("powerMarkIndex"),
                    )
                    for q in seed_questions
                ]
                if rows_to_insert:
                    conn.executemany(
                        """INSERT OR IGNORE INTO certamen_questions (
                            id, category, difficulty, tossup, answers, explanation, source, power_mark_index
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?);""",
                        rows_to_insert,
                    )
        except Exception as err:
            print(f"[certamen_db] Warning during auto-seed: {err}")

        _schema_initialized = True


def ping() -> dict[str, Any]:
    try:
        init_schema()
        rows = query("SELECT COUNT(*) as count FROM certamen_questions;")
        count = rows[0]["count"] if rows else 0
        _, _, is_remote = get_certamen_db_config()
        return {
            "success": True,
            "count": count,
            "is_remote": is_remote,
            "message": f"Connected to {'Turso' if is_remote else 'SQLite'} ({count} questions ready)",
        }
    except Exception as err:
        return {
            "success": False,
            "count": 0,
            "is_remote": False,
            "error": str(err),
        }


def get_questions(
    category: str = "all",
    difficulty: str = "all",
    limit: int = 50,
    random_order: bool = True,
    exclude_ids: list[str] | None = None,
) -> list[dict[str, Any]]:
    init_schema()
    conditions: list[str] = []
    args: list[Any] = []

    if category and category != "all":
        conditions.append("category = ?")
        args.append(category)

    if difficulty and difficulty != "all":
        conditions.append("difficulty = ?")
        args.append(difficulty)

    where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    order_clause = "ORDER BY RANDOM()" if random_order else "ORDER BY id ASC"
    limit_clause = f"LIMIT {int(limit)}" if limit and limit > 0 else ""

    sql = f"""SELECT id, category, difficulty, tossup, answers, explanation, source, power_mark_index
              FROM certamen_questions {where_clause} {order_clause} {limit_clause};"""

    rows = query(sql, tuple(args))
    exclude_set = set(exclude_ids or [])

    result: list[dict[str, Any]] = []
    for r in rows:
        if r["id"] in exclude_set:
            continue
        answers_raw = r.get("answers", "")
        answers: list[str] = []
        try:
            answers = json.loads(answers_raw)
        except Exception:
            answers = [a.strip() for a in str(answers_raw).split(",") if a.strip()]

        result.append({
            "id": r["id"],
            "category": r["category"],
            "difficulty": r["difficulty"],
            "tossup": r["tossup"],
            "answers": answers,
            "explanation": r.get("explanation"),
            "source": r.get("source"),
            "powerMarkIndex": r.get("power_mark_index"),
        })

    return result


def get_leaderboard(
    category: str = "all",
    level: str = "all",
    limit: int = 100,
) -> list[dict[str, Any]]:
    init_schema()
    conditions: list[str] = []
    args: list[Any] = []

    if level and level != "all":
        conditions.append("level = ?")
        args.append(level)

    sort_col = "total_points"
    cat_map = {
        "grammar": "grammar_pts",
        "mythology": "mythology_pts",
        "history": "history_pts",
        "culture": "culture_pts",
        "literature": "literature_pts",
    }
    if category in cat_map:
        sort_col = cat_map[category]

    where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    sql = f"""SELECT username, school, level, total_points, grammar_pts, mythology_pts,
                     history_pts, culture_pts, literature_pts, accuracy, total_answered, last_active
              FROM certamen_users {where_clause}
              ORDER BY {sort_col} DESC LIMIT {int(limit)};"""

    rows = query(sql, tuple(args))
    leaderboard = []
    for idx, r in enumerate(rows):
        leaderboard.append({
            "rank": idx + 1,
            "username": r["username"],
            "school": r.get("school") or "Independent",
            "level": r.get("level") or "novice",
            "totalPoints": r.get("total_points") or 0,
            "grammarPoints": r.get("grammar_pts") or 0,
            "mythologyPoints": r.get("mythology_pts") or 0,
            "historyPoints": r.get("history_pts") or 0,
            "culturePoints": r.get("culture_pts") or 0,
            "literaturePoints": r.get("literature_pts") or 0,
            "accuracy": r.get("accuracy") or 0,
            "totalAnswered": r.get("total_answered") or 0,
            "lastActive": r.get("last_active") or "",
        })
    return leaderboard


def sync_user(user: dict[str, Any]) -> dict[str, Any]:
    init_schema()
    username = str(user.get("username", "")).strip()
    pin = str(user.get("pin", "")).strip()
    if not username or not pin:
        return {"success": False, "message": "Username and PIN are required"}

    school = user.get("school") or "Independent"
    level = user.get("level") or "novice"
    stats = user.get("stats") or {}
    by_cat = stats.get("byCategory") or {}

    total_answered = stats.get("totalAnswered") or 0
    total_correct = stats.get("totalCorrect") or 0
    accuracy = round((total_correct / total_answered) * 100) if total_answered > 0 else 0

    sql = """INSERT INTO certamen_users (
        username, pin, school, level,
        total_points, grammar_pts, mythology_pts, history_pts, culture_pts, literature_pts,
        total_answered, total_correct, accuracy, best_streak, power_buzzes, avg_buzz_pct,
        last_active, raw_stats_json
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'), ?)
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
        last_active = datetime('now'),
        raw_stats_json = excluded.raw_stats_json;"""

    params = (
        username,
        pin,
        school,
        level,
        stats.get("totalPoints", 0),
        by_cat.get("grammar", {}).get("points", 0),
        by_cat.get("mythology", {}).get("points", 0),
        by_cat.get("history", {}).get("points", 0),
        by_cat.get("culture", {}).get("points", 0),
        by_cat.get("literature", {}).get("points", 0),
        total_answered,
        total_correct,
        accuracy,
        stats.get("bestStreak", 0),
        stats.get("powerBuzzes", 0),
        stats.get("averageBuzzPercentage", 0),
        json.dumps(stats),
    )

    execute(sql, params)
    return {"success": True, "message": "Synced to Turso database"}


def log_attempt(attempt: dict[str, Any]) -> dict[str, Any]:
    init_schema()
    sql = """INSERT OR REPLACE INTO certamen_attempts (
        id, timestamp, username, category, difficulty,
        question_text, user_answer, acceptable_answers,
        is_correct, points_earned, buzz_percentage
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);"""

    params = (
        str(attempt.get("id", "")),
        int(attempt.get("timestamp", 0)),
        str(attempt.get("username", "")),
        str(attempt.get("category", "")),
        str(attempt.get("difficulty", "")),
        str(attempt.get("questionText", "")),
        str(attempt.get("userAnswer", "")),
        json.dumps(attempt.get("acceptableAnswers", [])),
        1 if attempt.get("isCorrect") else 0,
        int(attempt.get("pointsEarned", 0)),
        int(attempt.get("buzzPercentage", 0)),
    )
    execute(sql, params)
    return {"success": True}


def login_user(username: str, pin: str) -> dict[str, Any] | None:
    init_schema()
    uname = username.strip()
    upin = pin.strip()
    rows = query(
        "SELECT username, pin, school, level, raw_stats_json FROM certamen_users WHERE LOWER(username) = LOWER(?) AND pin = ?;",
        (uname, upin),
    )
    if not rows:
        return None

    r = rows[0]
    stats = None
    if r.get("raw_stats_json"):
        try:
            stats = json.loads(r["raw_stats_json"])
        except Exception:
            pass

    return {
        "username": r["username"],
        "pin": r["pin"],
        "school": r.get("school") or "Independent",
        "level": r.get("level") or "novice",
        "stats": stats,
    }


def import_questions(questions: list[dict[str, Any]], replace: bool = False) -> dict[str, Any]:
    init_schema()
    conn = _get_connection()
    if replace:
        conn.execute("DELETE FROM certamen_questions;")

    rows_to_insert = [
        (
            q["id"],
            q["category"],
            q["difficulty"],
            q["tossup"],
            json.dumps(q.get("answers", [])),
            q.get("explanation"),
            q.get("source"),
            q.get("powerMarkIndex"),
        )
        for q in questions
    ]

    if rows_to_insert:
        conn.executemany(
            """INSERT OR REPLACE INTO certamen_questions (
                id, category, difficulty, tossup, answers, explanation, source, power_mark_index
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?);""",
            rows_to_insert,
        )

    return {"success": True, "imported": len(rows_to_insert)}
