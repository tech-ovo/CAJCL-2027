"""Tests for Certamen Arena API endpoints and Turso database proxy."""

import pytest
from fastapi.testclient import TestClient

from backend import api
from backend.lib import certamen_db


@pytest.fixture
def certamen_client(tmp_path, monkeypatch):
    test_db_path = str(tmp_path / "test_certamen.db")
    monkeypatch.setenv("TURSO_CERTAMEN_DATABASE_URL", test_db_path)
    monkeypatch.delenv("TURSO_CERTAMEN_AUTH_TOKEN", raising=False)
    certamen_db._reset_connection()
    certamen_db._schema_initialized = False

    with TestClient(api.app, raise_server_exceptions=True) as client:
        yield client

    certamen_db._reset_connection()
    certamen_db._schema_initialized = False


def test_certamen_ping(certamen_client):
    res = certamen_client.get("/certamen/ping")
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert data["count"] > 0
    assert data["is_remote"] is False


def test_certamen_questions(certamen_client):
    res = certamen_client.get("/certamen/questions?limit=10")
    assert res.status_code == 200
    data = res.json()
    assert "questions" in data
    assert len(data["questions"]) <= 10
    if data["questions"]:
        q = data["questions"][0]
        assert "id" in q
        assert "category" in q
        assert "difficulty" in q
        assert "tossup" in q
        assert isinstance(q["answers"], list)

    # Test category filter
    cat_res = certamen_client.get("/certamen/questions?category=grammar&limit=5")
    assert cat_res.status_code == 200
    for q in cat_res.json()["questions"]:
        assert q["category"] == "grammar"


def test_certamen_sync_and_login(certamen_client):
    user_payload = {
        "user": {
            "username": "CiceroTest",
            "pin": "1234",
            "school": "Tusculum Academy",
            "level": "intermediate",
            "stats": {
                "totalPoints": 250,
                "totalAnswered": 25,
                "totalCorrect": 20,
                "bestStreak": 7,
                "powerBuzzes": 3,
                "averageBuzzPercentage": 65,
                "byCategory": {
                    "grammar": {"points": 100},
                    "mythology": {"points": 80},
                    "history": {"points": 70},
                },
            },
        }
    }
    sync_res = certamen_client.post("/certamen/sync-user", json=user_payload)
    assert sync_res.status_code == 200
    assert sync_res.json()["success"] is True

    # Login with correct PIN
    login_res = certamen_client.post("/certamen/login", json={"username": "cicerotest", "pin": "1234"})
    assert login_res.status_code == 200
    login_data = login_res.json()
    assert login_data["user"] is not None
    assert login_data["user"]["username"] == "CiceroTest"
    assert login_data["user"]["school"] == "Tusculum Academy"
    assert login_data["user"]["stats"]["totalPoints"] == 250

    # Login with incorrect PIN
    bad_login = certamen_client.post("/certamen/login", json={"username": "CiceroTest", "pin": "9999"})
    assert bad_login.status_code == 200
    assert bad_login.json()["user"] is None


def _seed_player(client, username, school, level, points, answered, correct):
    client.post("/certamen/sync-user", json={
        "user": {
            "username": username,
            "pin": "1111",
            "school": school,
            "level": level,
            "stats": {"totalPoints": points, "totalAnswered": answered, "totalCorrect": correct},
        }
    })


def test_certamen_leaderboard_ranks_chapters(certamen_client):
    _seed_player(certamen_client, "Leader1", "Rome High", "advanced", 500, 50, 45)
    _seed_player(certamen_client, "Leader2", "rome high ", "advanced", 400, 50, 35)
    _seed_player(certamen_client, "Leader3", "Athens Academy", "advanced", 800, 80, 75)
    _seed_player(certamen_client, "Novice1", "Athens Academy", "novice", 100, 10, 5)
    _seed_player(certamen_client, "Guest", "Roma Antiqua Academy", "advanced", 9000, 10, 10)

    res = certamen_client.get("/certamen/leaderboard?level=advanced")
    assert res.status_code == 200
    entries = res.json()["leaderboard"]

    # One row per chapter, whatever the case or spacing players typed.
    assert [e["school"].lower() for e in entries] == ["rome high", "athens academy"]
    rome, athens = entries
    assert (rome["rank"], rome["players"], rome["totalPoints"]) == (1, 2, 900)
    assert rome["accuracy"] == 80  # 80 of 100, not the mean of 90% and 70%
    assert (athens["players"], athens["totalPoints"]) == (1, 800)

    # No individual appears anywhere in the response.
    assert all("username" not in e for e in entries)
    assert "Leader" not in res.text

    everyone = certamen_client.get("/certamen/leaderboard").json()["leaderboard"]
    assert [e["totalPoints"] for e in everyone] == [900, 900]
    assert {e["school"].lower(): e["players"] for e in everyone}["athens academy"] == 2


def test_certamen_log_attempt(certamen_client):
    res = certamen_client.post("/certamen/log-attempt", json={
        "attempt": {
            "id": "att-12345",
            "timestamp": 1720000000,
            "username": "CiceroTest",
            "category": "grammar",
            "difficulty": "novice",
            "questionText": "What is amo?",
            "userAnswer": "love",
            "acceptableAnswers": ["to love", "love"],
            "isCorrect": True,
            "pointsEarned": 10,
            "buzzPercentage": 40,
        }
    })
    assert res.status_code == 200
    assert res.json()["success"] is True
