import calendar
import datetime
import os
import sqlite3
import uuid

from flask import Flask, g, jsonify, render_template, request

app = Flask(__name__)

WEEKLY_WINDOW = 4  # how many recent ISO weeks the "weekly" grid shows

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
DB_PATH = os.path.join(DATA_DIR, "tracker.db")

DEFAULT_DAILY = [
    ("Wake up early", 25),
    ("Make bed", 20),
    ("Meditation", 15),
    ("Morning skincare", 28),
    ("Take vitamins", 31),
    ("Work out", 15),
    ("Water intake", 25),
    ("No sugar during day", 20),
    ("No junk food", 18),
    ("Smoothie salad", 20),
    ("Piano practice", 15),
    ("Evening skincare", 28),
    ("Floss", 20),
    ("Write in journal", 18),
    ("Make a plan for tomorrow", 25),
]
DEFAULT_WEEKLY = [
    ("Trim finger and toe nails", 4),
    ("Mop the floors", 4),
    ("Wash the clothes", 4),
    ("Prepare meals", 4),
    ("Declutter and organize", 4),
    ("Do some gardening", 2),
    ("Take a long shower", 4),
    ("Visit new places", 2),
    ("Eat favorite meal", 4),
    ("Call parents", 4),
]


# ---------------------------------------------------------------------------
# DB connection (one per request, closed on teardown)
# ---------------------------------------------------------------------------
def get_db():
    if "db" not in g:
        os.makedirs(DATA_DIR, exist_ok=True)
        g.db = sqlite3.connect(DB_PATH, timeout=10)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA journal_mode=WAL")
        g.db.execute("PRAGMA foreign_keys=ON")
    return g.db


@app.teardown_appcontext
def close_db(exception=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def mk_id():
    return "h" + uuid.uuid4().hex[:7]


def init_db():
    """Create tables if missing, and seed the default habit set once."""
    os.makedirs(DATA_DIR, exist_ok=True)
    db = sqlite3.connect(DB_PATH, timeout=10)
    db.row_factory = sqlite3.Row
    db.executescript(
        """
        CREATE TABLE IF NOT EXISTS habits (
            id TEXT PRIMARY KEY,
            kind TEXT NOT NULL CHECK (kind IN ('daily','weekly')),
            name TEXT NOT NULL,
            goal INTEGER NOT NULL DEFAULT 1,
            position INTEGER NOT NULL DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS completions (
            habit_id TEXT NOT NULL REFERENCES habits(id) ON DELETE CASCADE,
            period TEXT NOT NULL,
            done INTEGER NOT NULL DEFAULT 1,
            PRIMARY KEY (habit_id, period)
        );
        """
    )
    db.commit()
    count = db.execute("SELECT COUNT(*) c FROM habits").fetchone()["c"]
    if count == 0:
        seed_defaults(db)
    db.close()


def seed_defaults(db):
    pos = 0
    for name, goal in DEFAULT_DAILY:
        db.execute(
            "INSERT INTO habits (id, kind, name, goal, position) VALUES (?,?,?,?,?)",
            (mk_id(), "daily", name, goal, pos),
        )
        pos += 1
    pos = 0
    for name, goal in DEFAULT_WEEKLY:
        db.execute(
            "INSERT INTO habits (id, kind, name, goal, position) VALUES (?,?,?,?,?)",
            (mk_id(), "weekly", name, goal, pos),
        )
        pos += 1
    db.commit()


# ---------------------------------------------------------------------------
# Period helpers — daily periods are real calendar dates for the current
# month; weekly periods are the last WEEKLY_WINDOW real ISO weeks. Because
# completions are keyed by real date/week strings, history is never lost:
# rolling into a new month or week just changes which periods are shown.
# ---------------------------------------------------------------------------
def daily_periods(today=None):
    today = today or datetime.date.today()
    days_in_month = calendar.monthrange(today.year, today.month)[1]
    out = []
    for day in range(1, days_in_month + 1):
        d = today.replace(day=day)
        out.append({"key": d.isoformat(), "label": str(day)})
    return out


def iso_week_key(d):
    y, w, _ = d.isocalendar()
    return f"{y}-W{w:02d}"


def week_monday(d):
    return d - datetime.timedelta(days=d.isoweekday() - 1)


def weekly_periods(n=WEEKLY_WINDOW, today=None):
    today = today or datetime.date.today()
    this_monday = week_monday(today)
    out = []
    for i in range(n - 1, -1, -1):
        monday = this_monday - datetime.timedelta(weeks=i)
        out.append({"key": iso_week_key(monday), "label": monday.strftime("%b %d")})
    return out


def goal_max_for(kind):
    return len(daily_periods()) if kind == "daily" else WEEKLY_WINDOW


# ---------------------------------------------------------------------------
# State assembly
# ---------------------------------------------------------------------------
def build_state(db):
    d_periods = daily_periods()
    w_periods = weekly_periods()

    habits = db.execute("SELECT * FROM habits ORDER BY kind, position").fetchall()
    comp_rows = db.execute("SELECT habit_id, period, done FROM completions").fetchall()
    comp_map = {(r["habit_id"], r["period"]): bool(r["done"]) for r in comp_rows}

    def to_dict(row, periods):
        checks = [comp_map.get((row["id"], p["key"]), False) for p in periods]
        return {"id": row["id"], "name": row["name"], "goal": row["goal"], "checks": checks}

    daily = [to_dict(h, d_periods) for h in habits if h["kind"] == "daily"]
    weekly = [to_dict(h, w_periods) for h in habits if h["kind"] == "weekly"]

    return {
        "daily": daily,
        "weekly": weekly,
        "dailyPeriods": d_periods,
        "weeklyPeriods": w_periods,
    }


def get_habit(db, kind, habit_id):
    return db.execute(
        "SELECT * FROM habits WHERE id=? AND kind=?", (habit_id, kind)
    ).fetchone()


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/state", methods=["GET"])
def get_state():
    return jsonify(build_state(get_db()))


@app.route("/api/habit/toggle", methods=["POST"])
def toggle_check():
    body = request.get_json(force=True)
    kind, habit_id, period = body.get("kind"), body.get("id"), body.get("period")
    if kind not in ("daily", "weekly") or not period:
        return jsonify({"error": "invalid"}), 400
    db = get_db()
    if not get_habit(db, kind, habit_id):
        return jsonify({"error": "not found"}), 404
    row = db.execute(
        "SELECT done FROM completions WHERE habit_id=? AND period=?", (habit_id, period)
    ).fetchone()
    new_val = 0 if (row and row["done"]) else 1
    db.execute(
        """INSERT INTO completions (habit_id, period, done) VALUES (?,?,?)
           ON CONFLICT(habit_id, period) DO UPDATE SET done=excluded.done""",
        (habit_id, period, new_val),
    )
    db.commit()
    return jsonify(build_state(db))


@app.route("/api/habit/goal", methods=["POST"])
def update_goal():
    body = request.get_json(force=True)
    kind, habit_id, goal = body.get("kind"), body.get("id"), body.get("goal")
    db = get_db()
    if not get_habit(db, kind, habit_id):
        return jsonify({"error": "not found"}), 404
    try:
        goal = int(goal)
    except (TypeError, ValueError):
        goal = 1
    goal = max(1, min(goal, goal_max_for(kind)))
    db.execute("UPDATE habits SET goal=? WHERE id=?", (goal, habit_id))
    db.commit()
    return jsonify(build_state(db))


@app.route("/api/habit", methods=["POST"])
def add_habit():
    body = request.get_json(force=True)
    kind, name, goal = body.get("kind"), (body.get("name") or "").strip(), body.get("goal")
    if kind not in ("daily", "weekly") or not name:
        return jsonify({"error": "invalid"}), 400
    try:
        goal = int(goal)
    except (TypeError, ValueError):
        goal = 1
    goal = max(1, min(goal, goal_max_for(kind)))
    db = get_db()
    max_pos = db.execute(
        "SELECT COALESCE(MAX(position), -1) m FROM habits WHERE kind=?", (kind,)
    ).fetchone()["m"]
    db.execute(
        "INSERT INTO habits (id, kind, name, goal, position) VALUES (?,?,?,?,?)",
        (mk_id(), kind, name, goal, max_pos + 1),
    )
    db.commit()
    return jsonify(build_state(db))


@app.route("/api/habit", methods=["DELETE"])
def delete_habit():
    body = request.get_json(force=True)
    kind, habit_id = body.get("kind"), body.get("id")
    if kind not in ("daily", "weekly"):
        return jsonify({"error": "invalid"}), 400
    db = get_db()
    db.execute("DELETE FROM habits WHERE id=? AND kind=?", (habit_id, kind))
    db.commit()
    return jsonify(build_state(db))


@app.route("/api/habit/reorder", methods=["POST"])
def reorder_habits():
    body = request.get_json(force=True)
    kind, ids = body.get("kind"), body.get("ids")
    if kind not in ("daily", "weekly") or not isinstance(ids, list):
        return jsonify({"error": "invalid"}), 400
    db = get_db()
    existing = {r["id"] for r in db.execute("SELECT id FROM habits WHERE kind=?", (kind,))}
    ordered = [i for i in ids if i in existing]
    ordered += [i for i in existing if i not in ordered]
    for pos, habit_id in enumerate(ordered):
        db.execute("UPDATE habits SET position=? WHERE id=?", (pos, habit_id))
    db.commit()
    return jsonify(build_state(db))


@app.route("/api/reset", methods=["POST"])
def reset_state():
    db = get_db()
    db.execute("DELETE FROM completions")
    db.execute("DELETE FROM habits")
    db.commit()
    seed_defaults(db)
    return jsonify(build_state(db))


# ---------------------------------------------------------------------------
# History (rolling N real days) and the "story" day-flip view
# ---------------------------------------------------------------------------
@app.route("/api/history", methods=["GET"])
def api_history():
    try:
        days = int(request.args.get("days", 30))
    except (TypeError, ValueError):
        days = 30
    days = max(1, min(days, 365))

    db = get_db()
    today = datetime.date.today()
    daily_ids = [r["id"] for r in db.execute("SELECT id FROM habits WHERE kind='daily'")]
    total = len(daily_ids)

    out = []
    if total:
        placeholders = ",".join("?" * total)
        for i in range(days - 1, -1, -1):
            d = today - datetime.timedelta(days=i)
            key = d.isoformat()
            row = db.execute(
                f"""SELECT COUNT(*) c FROM completions
                    WHERE period=? AND done=1 AND habit_id IN ({placeholders})""",
                [key, *daily_ids],
            ).fetchone()
            out.append(
                {
                    "date": key,
                    "label": d.strftime("%a %b %d"),
                    "done": row["c"],
                    "total": total,
                    "isToday": d == today,
                }
            )
    else:
        for i in range(days - 1, -1, -1):
            d = today - datetime.timedelta(days=i)
            out.append(
                {"date": d.isoformat(), "label": d.strftime("%a %b %d"), "done": 0, "total": 0, "isToday": d == today}
            )
    return jsonify(out)


@app.route("/api/history/day", methods=["GET"])
def api_history_day():
    date_str = request.args.get("date") or datetime.date.today().isoformat()
    try:
        d = datetime.date.fromisoformat(date_str)
    except ValueError:
        return jsonify({"error": "invalid date"}), 400

    db = get_db()
    week_key = iso_week_key(week_monday(d))

    daily_habits = db.execute(
        "SELECT * FROM habits WHERE kind='daily' ORDER BY position"
    ).fetchall()
    weekly_habits = db.execute(
        "SELECT * FROM habits WHERE kind='weekly' ORDER BY position"
    ).fetchall()

    daily_done_ids = {
        r["habit_id"]
        for r in db.execute(
            "SELECT habit_id FROM completions WHERE period=? AND done=1", (date_str,)
        )
    }
    weekly_done_ids = {
        r["habit_id"]
        for r in db.execute(
            "SELECT habit_id FROM completions WHERE period=? AND done=1", (week_key,)
        )
    }

    daily_list = [
        {"id": h["id"], "name": h["name"], "done": h["id"] in daily_done_ids}
        for h in daily_habits
    ]
    weekly_list = [
        {"id": h["id"], "name": h["name"], "done": h["id"] in weekly_done_ids}
        for h in weekly_habits
    ]
    done = sum(1 for x in daily_list if x["done"])
    total = len(daily_list)

    today = datetime.date.today()
    return jsonify(
        {
            "date": date_str,
            "label": d.strftime("%A, %B %-d, %Y") if os.name != "nt" else d.strftime("%A, %B %d, %Y"),
            "weekKey": week_key,
            "daily": daily_list,
            "weekly": weekly_list,
            "dailyDone": done,
            "dailyTotal": total,
            "ratio": (done / total) if total else 0,
            "isToday": d == today,
            "isFuture": d > today,
        }
    )


@app.route("/healthz")
def healthz():
    return jsonify({"status": "ok"})


init_db()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True, use_reloader=False)
