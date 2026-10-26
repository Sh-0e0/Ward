import sqlite3
from contextlib import contextmanager

from balance import LANES
from scoring import kda_value

DB_PATH = "wildrift.db"


@contextmanager
def session():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _ensure_column(conn, table, column, ddl):
    cols = [r["name"] for r in conn.execute(f"PRAGMA table_info({table})")]
    if column not in cols:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}")


def init_db() -> None:
    with session() as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            user_id   INTEGER PRIMARY KEY,
            name      TEXT NOT NULL,
            tier      TEXT NOT NULL,
            division  INTEGER NOT NULL DEFAULT 0,
            main_lane TEXT NOT NULL,
            sub_lane  TEXT
        );

        CREATE TABLE IF NOT EXISTS matches (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id    INTEGER NOT NULL,
            created_at  TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
            winner_team TEXT,                        -- 'blue' / 'red'
            status      TEXT NOT NULL DEFAULT 'open' -- open -> confirmed / cancelled
        );

        -- KDA는 누구나 누구의 것이든 입력할 수 있으므로 마지막 입력자를 기록
        CREATE TABLE IF NOT EXISTS match_players (
            match_id  INTEGER NOT NULL REFERENCES matches(id),
            user_id   INTEGER NOT NULL REFERENCES users(user_id),
            team      TEXT NOT NULL,
            lane      TEXT,
            kills     INTEGER,
            deaths    INTEGER,
            assists   INTEGER,
            edited_by INTEGER,
            PRIMARY KEY (match_id, user_id)
        );
        """)
        _ensure_column(conn, "matches", "host_id", "INTEGER")
        _ensure_column(conn, "matches", "title", "TEXT")


# ---------- users ----------
def upsert_user(user_id, name, tier, division, main_lane, sub_lane) -> None:
    with session() as conn:
        conn.execute("""
            INSERT INTO users (user_id, name, tier, division, main_lane, sub_lane)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                name=excluded.name, tier=excluded.tier, division=excluded.division,
                main_lane=excluded.main_lane, sub_lane=excluded.sub_lane
        """, (user_id, name, tier, division, main_lane, sub_lane))


def get_user(user_id):
    with session() as conn:
        return conn.execute("SELECT * FROM users WHERE user_id=?", (user_id,)).fetchone()


def list_users():
    with session() as conn:
        return conn.execute("SELECT * FROM users").fetchall()


def get_stats(user_id) -> tuple[int, int, float]:
    """확정된 내전 기준 (판수, 승수, 평균 KDA)"""
    with session() as conn:
        rows = conn.execute("""
            SELECT m.winner_team, mp.team, mp.kills, mp.deaths, mp.assists
            FROM match_players mp JOIN matches m ON m.id = mp.match_id
            WHERE mp.user_id = ? AND m.status = 'confirmed'
        """, (user_id,)).fetchall()
    games = len(rows)
    if games == 0:
        return 0, 0, 0.0
    wins = sum(1 for r in rows if r["winner_team"] == r["team"])
    kda_avg = sum(kda_value(r["kills"], r["deaths"], r["assists"]) for r in rows) / games
    return games, wins, kda_avg


# ---------- matches ----------
def create_match(guild_id, host_id, title, players) -> int:
    """players: [(user_id, team, lane), ...]"""
    with session() as conn:
        cur = conn.execute(
            "INSERT INTO matches (guild_id, host_id, title) VALUES (?, ?, ?)",
            (guild_id, host_id, title))
        match_id = cur.lastrowid
        conn.executemany(
            "INSERT INTO match_players (match_id, user_id, team, lane) VALUES (?, ?, ?, ?)",
            [(match_id, u, t, l) for u, t, l in players])
    return match_id


def get_match(match_id):
    with session() as conn:
        return conn.execute("SELECT * FROM matches WHERE id=?", (match_id,)).fetchone()


def get_open_match(guild_id):
    with session() as conn:
        return conn.execute(
            "SELECT * FROM matches WHERE guild_id=? AND status='open' ORDER BY id DESC LIMIT 1",
            (guild_id,)).fetchone()


def get_match_players(match_id):
    with session() as conn:
        rows = conn.execute("""
            SELECT mp.*, u.name FROM match_players mp
            JOIN users u ON u.user_id = mp.user_id WHERE mp.match_id = ?
        """, (match_id,)).fetchall()
    return sorted(rows, key=lambda r: (r["team"] != "blue", LANES.index(r["lane"])))


def set_kda(match_id, user_id, kills, deaths, assists, edited_by) -> None:
    with session() as conn:
        conn.execute("""
            UPDATE match_players SET kills=?, deaths=?, assists=?, edited_by=?
            WHERE match_id=? AND user_id=?
        """, (kills, deaths, assists, edited_by, match_id, user_id))


def set_winner(match_id, team) -> None:
    with session() as conn:
        conn.execute("UPDATE matches SET winner_team=? WHERE id=?", (team, match_id))


def confirm_match(match_id) -> None:
    with session() as conn:
        conn.execute("UPDATE matches SET status='confirmed' WHERE id=? AND status='open'", (match_id,))


def cancel_match(match_id) -> None:
    with session() as conn:
        conn.execute("UPDATE matches SET status='cancelled' WHERE id=? AND status='open'", (match_id,))
