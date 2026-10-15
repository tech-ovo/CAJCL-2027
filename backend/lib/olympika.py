"""Olympika: events, heats, brackets, and the push to the master schedule.

The endpoints in api.py do the authorization; this module holds the rules, so
the tests can reach them without HTTP:

    what an event may be                  check_event, check_team_name
    dealing entrants into heats           deal_heats, assign_heats
    drawing a bracket                     draw_bracket, form_bracket
    recording a game's result             record_result
    timing the games                      time_games
    writing it all onto the schedule      sync_schedule

TWO KINDS OF EVENT, TWO BUTTONS.
    An `individual` event (a track race, chess) is entered by each delegate;
    the Director sets how many heats there are and when, and "Assign heats"
    deals the entrants into them.

    A `team` event (Ultimate Frisbee) is entered ONE DELEGATE PER TEAM: that
    delegate is the captain and is the only person recorded. "Form bracket"
    draws a single-elimination bracket of the teams.

THE MASTER SCHEDULE FOLLOWS. `sync_schedule` runs in the same transaction as
every change to a heat, a game's time, an event's name or place, so the master
schedule cannot disagree with them. A heat becomes one entry; a bracket
becomes one entry per ROUND ("Ultimate Frisbee — Quarterfinals"), spanning
that round's games, so forty games do not bury the Logistics chair's entries.
The rows it writes are marked source = 'olympika', and only this module
touches them.

Randomness is passed in (`rng`) so the tests can fix it. Production code uses
a fresh `random.Random()`, which is seeded from the operating system.
"""

from __future__ import annotations

import datetime as _dt
import math
import random
import re

from . import clock
from .catalog import ValidationError

MAX_NAME = 80
MAX_DESCRIPTION = 1000
MAX_LOCATION = 120
MAX_LABEL = 40
MAX_TEAM_NAME = 60
MAX_HEATS = 40
MAX_FIELDS = 12

KINDS = ("individual", "team")


def _clean(value) -> str:
    return " ".join(str(value or "").split())


def _whole(value, what: str, errors: list, *, minimum=0, maximum=None):
    try:
        number = int(value)
    except (TypeError, ValueError):
        errors.append(f"{what} must be a whole number.")
        return None
    if number < minimum or (maximum is not None and number > maximum):
        errors.append(
            f"{what} must be "
            + (f"between {minimum} and {maximum}." if maximum is not None
               else f"at least {minimum}."))
        return None
    return number


# ---------------------------------------------------------------------------
# Events and teams
# ---------------------------------------------------------------------------

def check_event(payload: dict, current: dict | None = None) -> dict:
    """The columns for a new or edited event. A field left out of an edit
    keeps its current value."""
    current = current or {}
    errors: list[str] = []

    def given(key):
        return key in payload or key not in current

    name = _clean(payload.get("name", current.get("name")))
    if not name:
        errors.append("Give the event a name, like “100-meter dash”.")
    elif len(name) > MAX_NAME:
        errors.append(f"Keep the name under {MAX_NAME} characters.")

    description = (str(payload.get("description") or "").strip()
                   if given("description") else current.get("description") or "")
    if len(description) > MAX_DESCRIPTION:
        errors.append(f"Keep the description under {MAX_DESCRIPTION} characters.")

    location = (_clean(payload.get("location"))
                if given("location") else current.get("location") or "")
    if len(location) > MAX_LOCATION:
        errors.append(f"Keep the location under {MAX_LOCATION} characters.")

    kind = payload.get("kind", current.get("kind", "individual"))
    if kind not in KINDS:
        errors.append("Say whether delegates enter this one by one or as teams.")

    signup_open = (bool(payload.get("signup_open", False)) if given("signup_open")
                   else bool(current.get("signup_open")))

    limit = current.get("max_per_school")
    if "max_per_school" in payload:
        raw = payload["max_per_school"]
        limit = None if raw in (None, "") else _whole(
            raw, "The limit per chapter", errors, minimum=1, maximum=1000)

    sort_order = current.get("sort_order", 0)
    if "sort_order" in payload:
        sort_order = _whole(payload["sort_order"], "The order", errors,
                            minimum=-100000, maximum=100000)

    if errors:
        raise ValidationError(errors)
    return {"name": name, "description": description or None, "kind": kind,
            "location": location or None,
            "signup_open": 1 if signup_open else 0,
            "max_per_school": limit, "sort_order": sort_order}


def check_team_name(raw) -> str | None:
    name = _clean(raw)
    if len(name) > MAX_TEAM_NAME:
        raise ValidationError([f"Keep the team name under {MAX_TEAM_NAME} characters."])
    return name or None


def default_team_name(school_name: str, taken: list[str]) -> str:
    """The chapter's name, with a number once it is taken: a captain who does
    not name the team is not made to think of one."""
    base = _clean(school_name)[:MAX_TEAM_NAME - 3]
    lowered = {name.lower() for name in taken}
    if base.lower() not in lowered:
        return base
    number = 2
    while f"{base} {number}".lower() in lowered:
        number += 1
    return f"{base} {number}"


# ---------------------------------------------------------------------------
# Heats
# ---------------------------------------------------------------------------

def check_heat_label(raw) -> str | None:
    label = _clean(raw)
    if len(label) > MAX_LABEL:
        raise ValidationError([f"Keep the heat's name under {MAX_LABEL} characters."])
    return label or None


def heat_title(event_name: str, heat: dict, heat_count: int) -> str:
    """"100 m Dash — Heat 2", or just the event when it is run once."""
    if heat.get("label"):
        return f"{event_name} — {heat['label']}"
    if heat_count == 1:
        return event_name
    return f"{event_name} — Heat {heat['number']}"


def deal_heats(entrants: list[dict], heat_ids: list[int],
               rng: random.Random) -> list[tuple[int, int, int]]:
    """[(signup id, heat id, lane)] -- everybody dealt into the heats.

    Heats differ in size by at most one. Entrants are grouped by chapter
    before the deal, so one chapter's runners go into consecutive heats
    rather than the same one: a chapter with three runners in four heats has
    one in each of three. Lanes within a heat are a shuffle.
    """
    if not heat_ids:
        raise ValueError("there are no heats to deal into")
    by_school: dict[int, list[dict]] = {}
    for entrant in entrants:
        by_school.setdefault(entrant["school_id"], []).append(entrant)
    schools = list(by_school)
    rng.shuffle(schools)

    heats: list[list[dict]] = [[] for _ in heat_ids]
    position = 0
    for school in schools:
        group = by_school[school]
        rng.shuffle(group)
        for entrant in group:
            heats[position % len(heat_ids)].append(entrant)
            position += 1

    dealt = []
    for heat_id, members in zip(heat_ids, heats):
        rng.shuffle(members)
        for lane, entrant in enumerate(members, start=1):
            dealt.append((entrant["id"], heat_id, lane))
    return dealt


# ---------------------------------------------------------------------------
# Brackets
# ---------------------------------------------------------------------------

def rounds_for(team_count: int) -> int:
    return max(1, math.ceil(math.log2(team_count))) if team_count > 1 else 0


def round_name(round_number: int, rounds: int) -> str:
    remaining = rounds - round_number
    if remaining == 0:
        return "Final"
    if remaining == 1:
        return "Semifinals"
    if remaining == 2:
        return "Quarterfinals"
    return f"Round of {2 ** (rounds - round_number + 1)}"


def bracket_positions(size: int) -> list[int]:
    """Seeds in the order they stand in a bracket of `size`, so that adjacent
    pairs are the first-round games and the top seeds can only meet late:
    8 -> [1, 8, 4, 5, 2, 7, 3, 6]."""
    order = [1]
    while len(order) < size:
        double = len(order) * 2
        order = [seed for s in order for seed in (s, double + 1 - s)]
    return order


def draw_bracket(teams: list[dict], rng: random.Random,
                 attempts: int = 300) -> tuple[list[dict], list[dict]]:
    """(teams in seed order, games).

    The seeding is a shuffle, and of `attempts` shuffles the one that puts
    the fewest first-round games between two teams of the same chapter wins
    (usually none). A game is {round, slot, team_a_id, team_b_id, winner_id}.
    A first-round game with one team is a BYE: that team has already won and
    already stands in the second round. With a power-of-two number of teams
    there are none; otherwise the best seeds get them.
    """
    count = len(teams)
    if count < 2:
        raise ValidationError(["A bracket needs at least two teams."])
    rounds = rounds_for(count)
    size = 2 ** rounds
    positions = bracket_positions(size)
    pairs = [(positions[i], positions[i + 1]) for i in range(0, size, 2)]

    best = None
    for _ in range(attempts):
        order = list(teams)
        rng.shuffle(order)
        clashes = sum(1 for a, b in pairs
                      if a <= count and b <= count
                      and order[a - 1]["school_id"] == order[b - 1]["school_id"])
        if best is None or clashes < best[0]:
            best = (clashes, order)
        if clashes == 0:
            break
    order = best[1]

    games = []
    for round_number in range(1, rounds + 1):
        for slot in range(size // 2 ** round_number):
            games.append({"round": round_number, "slot": slot,
                          "team_a_id": None, "team_b_id": None,
                          "winner_id": None})
    grid = {(g["round"], g["slot"]): g for g in games}

    for slot, (a, b) in enumerate(pairs):
        game = grid[(1, slot)]
        game["team_a_id"] = order[a - 1]["id"] if a <= count else None
        game["team_b_id"] = order[b - 1]["id"] if b <= count else None
        # Never both empty: byes go to the top seeds and there are fewer than
        # half as many as there are games.
        if game["team_a_id"] is None or game["team_b_id"] is None:
            game["winner_id"] = game["team_a_id"] or game["team_b_id"]
            nxt = grid[(2, slot // 2)] if rounds > 1 else None
            if nxt is not None:
                nxt["team_a_id" if slot % 2 == 0 else "team_b_id"] = game["winner_id"]
    return order, games


def is_bye(game) -> bool:
    return game["round"] == 1 and (game["team_a_id"] is None) != (game["team_b_id"] is None)


def parse_fields(raw) -> list[str]:
    """Field names from a list or a comma-separated line. No names is one
    unnamed field."""
    if isinstance(raw, str):
        raw = raw.split(",")
    names = []
    for item in raw or []:
        name = _clean(item)
        if name and name.lower() not in {n.lower() for n in names}:
            names.append(name)
    if len(names) > MAX_FIELDS:
        raise ValidationError([f"Keep it to {MAX_FIELDS} fields or fewer."])
    return names


def time_games(games: list[dict], starts_at: str, minutes: int,
               fields: list[str]) -> dict[int, tuple[str, str, str | None]]:
    """{game id: (starts_at, ends_at, field)}.

    Round by round: as many games at once as there are fields, then the next
    wave `minutes` later, and the next round starts when the last wave of the
    one before has finished. A bye is not a game and gets no time.
    """
    slots = fields or [None]
    cursor = clock.parse_iso(starts_at)
    length = _dt.timedelta(minutes=minutes)
    timed: dict[int, tuple[str, str, str | None]] = {}
    rounds = sorted({g["round"] for g in games})
    for round_number in rounds:
        playable = sorted((g for g in games
                           if g["round"] == round_number and not is_bye(g)),
                          key=lambda g: g["slot"])
        waves = 0
        for index, game in enumerate(playable):
            wave, lane = divmod(index, len(slots))
            begin = cursor + length * wave
            timed[game["id"]] = (clock.to_iso(begin), clock.to_iso(begin + length),
                                 slots[lane])
            waves = wave + 1
        cursor += length * waves
    return timed


def check_game_plan(payload: dict) -> dict | None:
    """The optional timing for a bracket: {starts_at, minutes, fields}, or
    None when the Director only wants the draw."""
    from .schedule import parse_span
    if not (payload.get("date") or payload.get("start")):
        return None
    starts_at, _ = parse_span({"date": payload.get("date"),
                               "start": payload.get("start")})
    errors: list[str] = []
    minutes = _whole(payload.get("minutes", 40), "The minutes per game", errors,
                     minimum=5, maximum=600)
    if errors:
        raise ValidationError(errors)
    return {"starts_at": starts_at, "minutes": minutes,
            "fields": parse_fields(payload.get("fields"))}


# ---------------------------------------------------------------------------
# Database operations -- all take a transaction, none commit
# ---------------------------------------------------------------------------

def assign_heats(tx, event: dict, rng: random.Random, now: str) -> dict:
    """Deal every entrant of an individual event into its heats."""
    heats = tx.all("olympika.heats", (event["id"],))
    if not heats:
        raise ValidationError(["Set up the heats first: say how many there are."])
    entrants = [dict(r) for r in tx.all("olympika.signups_for_event", (event["id"],))]
    if not entrants:
        raise ValidationError(["Nobody has signed up for this event yet."])
    dealt = deal_heats(entrants, [h["id"] for h in heats], rng)
    for signup_id, heat_id, lane in dealt:
        tx.run("olympika.signup_set_heat", (heat_id, lane, signup_id))
    return {"entrants": len(dealt), "heats": len(heats)}


def set_heat_count(tx, event: dict, count: int, plan: dict | None, now: str) -> None:
    """Make the event have exactly `count` heats, newest removed first, and
    when `plan` ({starts_at, minutes_between, minutes_long}) is given, time
    them all: the first at `starts_at`, the rest `minutes_between` apart."""
    existing = list(tx.all("olympika.heats", (event["id"],)))
    for heat in existing[count:]:
        tx.run("olympika.signups_unassign_heat", (heat["id"],))
        tx.run("olympika.heat_delete", (heat["id"],))
    for number in range(len(existing) + 1, count + 1):
        tx.insert("olympika.heat_create",
                  (event["id"], number, None, None, None, now, now))
    if plan:
        begin = clock.parse_iso(plan["starts_at"])
        for index, heat in enumerate(tx.all("olympika.heats", (event["id"],))):
            start = begin + _dt.timedelta(minutes=plan["minutes_between"] * index)
            end = (start + _dt.timedelta(minutes=plan["minutes_long"])
                   if plan.get("minutes_long") else None)
            tx.run("olympika.heat_update", (
                heat["label"], clock.to_iso(start),
                clock.to_iso(end) if end else None, now, heat["id"]))


def check_heat_plan(payload: dict) -> dict | None:
    """The optional timing for a set of heats."""
    from .schedule import parse_span
    if not (payload.get("date") or payload.get("start")):
        return None
    starts_at, _ = parse_span({"date": payload.get("date"),
                               "start": payload.get("start")})
    errors: list[str] = []
    between = _whole(payload.get("minutes_between", 15), "The minutes between heats",
                     errors, minimum=0, maximum=600)
    length = payload.get("minutes_long")
    length = None if length in (None, "") else _whole(
        length, "The length of a heat", errors, minimum=1, maximum=600)
    if errors:
        raise ValidationError(errors)
    return {"starts_at": starts_at, "minutes_between": between,
            "minutes_long": length}


def reset_bracket(tx, event_id: int, now: str) -> None:
    tx.run("olympika.matches_delete_for_event", (event_id,))
    tx.run("olympika.teams_clear_seeds", (now, event_id))


def form_bracket(tx, event: dict, rng: random.Random, plan: dict | None,
                 now: str) -> dict:
    """Draw the bracket for a team event, replacing any earlier one, and when
    `plan` is given time the games."""
    teams = [dict(r) for r in tx.all("olympika.teams_for_event", (event["id"],))]
    order, games = draw_bracket(teams, rng)      # raises with fewer than two
    reset_bracket(tx, event["id"], now)
    for seed, team in enumerate(order, start=1):
        tx.run("olympika.team_set_seed", (seed, now, team["id"]))
    for game in games:
        game["id"] = tx.insert("olympika.match_create", (
            event["id"], game["round"], game["slot"], game["team_a_id"],
            game["team_b_id"], game["winner_id"], now))
    if plan:
        apply_times(tx, games, plan, now)
    return {"teams": len(order), "rounds": rounds_for(len(order)),
            "games": sum(1 for g in games if not is_bye(g))}


def apply_times(tx, games: list[dict], plan: dict, now: str) -> int:
    """Write the timing `time_games` works out onto the matches."""
    timed = time_games(games, plan["starts_at"], plan["minutes"], plan["fields"])
    for game_id, (starts_at, ends_at, field) in timed.items():
        row = tx.one("olympika.match_get", (game_id,))
        tx.run("olympika.match_update", (
            row["team_a_id"], row["team_b_id"], row["winner_id"], row["score_a"],
            row["score_b"], starts_at, ends_at, field, now, game_id))
    return len(timed)


def record_result(tx, match: dict, winner_id: int | None, score_a, score_b,
                  now: str) -> None:
    """Record who won a game, and move the winner into the next round.

    Changing or clearing a result is allowed until the next round's game has
    itself been played; after that the later result has to be cleared first,
    or the bracket would say two things at once.
    """
    errors: list[str] = []
    scores = []
    for value, what in ((score_a, "The first score"), (score_b, "The second score")):
        scores.append(None if value in (None, "") else
                      _whole(value, what, errors, minimum=0, maximum=10000))
    if errors:
        raise ValidationError(errors)

    if is_bye(match):
        raise ValidationError(["That team has a bye. There is no game to score."])
    if winner_id is not None:
        if match["team_a_id"] is None or match["team_b_id"] is None:
            raise ValidationError([
                "This game is still waiting on the games before it."])
        if winner_id not in (match["team_a_id"], match["team_b_id"]):
            raise ValidationError(["The winner has to be one of the two teams playing."])

    following = tx.one("olympika.match_at",
                       (match["event_id"], match["round"] + 1, match["slot"] // 2))
    changed = match["winner_id"] != winner_id
    if changed and following is not None and following["winner_id"] is not None:
        raise ValidationError([
            "The next round has already been played from this result. Clear "
            "that result first."])

    tx.run("olympika.match_update", (
        match["team_a_id"], match["team_b_id"], winner_id, scores[0], scores[1],
        match["starts_at"], match["ends_at"], match["field"], now, match["id"]))
    if changed and following is not None:
        a, b = following["team_a_id"], following["team_b_id"]
        if match["slot"] % 2 == 0:
            a = winner_id
        else:
            b = winner_id
        tx.run("olympika.match_update", (
            a, b, following["winner_id"], following["score_a"], following["score_b"],
            following["starts_at"], following["ends_at"], following["field"],
            now, following["id"]))


def forget_person(tx, person_id: int, now: str) -> None:
    """A redacted delegate's sign-ups are deleted. A team they captained is
    deleted too -- unless a bracket has been drawn, when it stays, nameless,
    so the bracket keeps its shape."""
    tx.run("olympika.signups_delete_for_person", (person_id,))
    for team in tx.all("olympika.teams_for_captain", (person_id,)):
        if tx.one("olympika.matches_for_team", (team["id"], team["id"])):
            tx.run("olympika.team_orphan",
                   (f"Withdrawn team {team['id']}", now, team["id"]))
        else:
            tx.run("olympika.team_delete", (team["id"],))
        sync_schedule(tx, team["event_id"], now)


def delete_event(tx, event_id: int) -> None:
    """The event and everything hanging off it, children first."""
    tx.run("schedule.delete_for_event", (event_id,))
    tx.run("olympika.matches_delete_for_event", (event_id,))
    tx.run("olympika.teams_delete_for_event", (event_id,))
    tx.run("olympika.signups_delete_for_event", (event_id,))
    tx.run("olympika.heats_delete_for_event", (event_id,))
    tx.run("olympika.event_delete", (event_id,))


# ---------------------------------------------------------------------------
# The push to the master schedule
# ---------------------------------------------------------------------------

def _wanted_rows(tx, event: dict) -> dict[str, tuple]:
    """{source_key: (title, location, starts_at, ends_at)} -- what this event
    should currently have on the master schedule."""
    wanted: dict[str, tuple] = {}

    heats = tx.all("olympika.heats", (event["id"],))
    for heat in heats:
        if heat["starts_at"]:
            wanted[f"heat:{heat['id']}"] = (
                heat_title(event["name"], dict(heat), len(heats)),
                event["location"], heat["starts_at"], heat["ends_at"])

    matches = tx.all("olympika.matches_for_event", (event["id"],))
    rounds = max((m["round"] for m in matches), default=0)
    for round_number in range(1, rounds + 1):
        timed = [m for m in matches if m["round"] == round_number and m["starts_at"]]
        if not timed:
            continue
        begin = min(m["starts_at"] for m in timed)
        end = max(m["ends_at"] or m["starts_at"] for m in timed)
        fields = sorted({m["field"] for m in timed if m["field"]})
        place = " · ".join(filter(None, [event["location"], ", ".join(fields)])) or None
        wanted[f"round:{event['id']}:{round_number}"] = (
            f"{event['name']} — {round_name(round_number, rounds)}",
            place, begin, end if end != begin else None)
    return wanted


def sync_schedule(tx, event_id: int, now: str) -> None:
    """Make the master schedule's Olympika rows for this event match its heats
    and bracket exactly: add what is new, change what moved, remove what is
    gone. Idempotent, and quiet when nothing changed."""
    event = tx.one("olympika.event_get", (event_id,))
    existing = {r["source_key"]: r for r in tx.all("schedule.for_event", (event_id,))}
    wanted = _wanted_rows(tx, dict(event)) if event is not None else {}

    for key, (title, location, starts_at, ends_at) in wanted.items():
        row = existing.get(key)
        if row is None:
            tx.run("schedule.sync_insert", (title, location, starts_at, ends_at,
                                            key, event_id, now, now))
        elif (row["title"], row["location"], row["starts_at"], row["ends_at"]) != (
                title, location, starts_at, ends_at):
            tx.run("schedule.sync_update",
                   (title, location, starts_at, ends_at, now, row["id"]))
    for key, row in existing.items():
        if key not in wanted:
            tx.run("schedule.delete", (row["id"],))
