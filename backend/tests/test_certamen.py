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


def test_certamen_leaderboard(certamen_client):
    # Seed two users
    certamen_client.post("/certamen/sync-user", json={
        "user": {
            "username": "Leader1",
            "pin": "1111",
            "school": "Rome High",
            "level": "advanced",
            "stats": {"totalPoints": 500, "totalAnswered": 50, "totalCorrect": 45},
        }
    })
    certamen_client.post("/certamen/sync-user", json={
        "user": {
            "username": "Leader2",
            "pin": "2222",
            "school": "Athens Academy",
            "level": "advanced",
            "stats": {"totalPoints": 800, "totalAnswered": 80, "totalCorrect": 75},
        }
    })

    res = certamen_client.get("/certamen/leaderboard?level=advanced")
    assert res.status_code == 200
    entries = res.json()["leaderboard"]
    assert len(entries) >= 2
    # Leader2 should be ranked higher than Leader1
    usernames = [e["username"] for e in entries]
    assert usernames.index("Leader2") < usernames.index("Leader1")


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
