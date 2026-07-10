# Habit Tracker (Flask)

A Flask port of the Habit Tracker, backed by a real SQLite database, with
daily/weekly habit grids, editable goals, progress rings, an advanced focus
timer, streak/heatmap insights, a 30-day history view, a flip-through "story"
of past days, drag-to-reorder habits, and dark mode.

## Features

- **Real database** — SQLite (`data/tracker.db`), not a flat JSON file.
  Completions are keyed by actual calendar dates (daily) and real ISO weeks
  (weekly), so nothing resets when the month or week rolls over — your full
  history just keeps accumulating.
- **30-day history** — the heatmap's "30 Days" tab pulls from a dedicated
  `/api/history` endpoint showing a true rolling 30-day window, independent
  of calendar-month boundaries.
- **Previous story** — a day-by-day recap card (`◄` / `►` to flip through
  past days, or "Jump to today") showing exactly which daily habits you
  completed and your weekly status for that day, backed by
  `/api/history/day`. Click any cell in the 30-day heatmap to jump straight
  to that day's story.
- **Advanced focus timer** — Simple mode with quick presets (5/10/15/25/45m
  or custom) and a full Pomodoro mode (work/break/long-break cycles, cycle
  dots, optional auto-start of the next session). Both modes support a sound
  chime (generated in-browser), optional browser desktop notifications, and
  auto-check today's box for an attached habit when a session finishes.
- **Streaks dashboard** — current streak per habit (🔥), a "longest active
  streak" banner, and a top-streaks leaderboard.
- **Drag-to-reorder** — grab the `⋮⋮` handle (mouse/trackpad) or the ▲▼
  buttons (touch) to reorder habits; persisted via `/api/habit/reorder`.
- **Dark mode** — toggle in the top-right corner; remembers your choice.
- **Mobile & tablet friendly** — responsive layout, sticky habit-name
  column, bigger tap targets, and 16px inputs to avoid iOS auto-zoom.

## Data model

- `habits(id, kind, name, goal, position)` — one row per habit.
- `completions(habit_id, period, done)` — one row per completed
  day/week. `period` is an ISO date (`2026-07-10`) for daily habits or an
  ISO week key (`2026-W28`) for weekly habits. This is what makes the
  history genuinely permanent — nothing is ever overwritten when a new
  month starts, it's just a different set of `period` values.

## Project structure

```
habit-tracker-flask/
├── app.py                 # Flask app + SQLite-backed REST API
├── templates/
│   └── index.html         # Frontend (fetches /api/state, /api/history, etc.)
├── data/
│   └── tracker.db          # Created automatically on first run (SQLite)
├── requirements.txt
├── Procfile                # gunicorn start command
├── railway.json             # Railway build/deploy config
├── runtime.txt
└── .gitignore
```

## Run locally

```bash
python -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python app.py                  # http://localhost:5000
```

Or with gunicorn (closer to production):

```bash
gunicorn app:app --bind 0.0.0.0:5000
```

## API

| Method | Route                | Body / Query                              | Description                                  |
|--------|----------------------|---------------------------------------------|-----------------------------------------------|
| GET    | `/api/state`         | –                                            | Full current state (habits + today's periods) |
| POST   | `/api/habit/toggle`  | `{kind, id, period}`                         | Toggle one day/week cell                       |
| POST   | `/api/habit/goal`    | `{kind, id, goal}`                           | Update a habit's goal                          |
| POST   | `/api/habit`         | `{kind, name, goal}`                         | Add a new habit                                |
| DELETE | `/api/habit`         | `{kind, id}`                                 | Remove a habit                                  |
| POST   | `/api/habit/reorder` | `{kind, ids}` (ordered list of habit ids)    | Persist a new habit order                       |
| GET    | `/api/history`       | `?days=30`                                   | Rolling N-day completion counts (for the heatmap)|
| GET    | `/api/history/day`   | `?date=YYYY-MM-DD` (defaults to today)       | Full recap for one day (for the Story card)     |
| POST   | `/api/reset`         | –                                             | Wipe and reseed the default habit set           |
| GET    | `/healthz`           | –                                             | Health check                                    |

`kind` is `"daily"` or `"weekly"`. `period` is an ISO date for daily habits
(`2026-07-10`) or an ISO week key for weekly habits (`2026-W28`) — get the
valid values for the current grid from `dailyPeriods`/`weeklyPeriods` in the
`/api/state` response.

## Deploy to Railway

**Option A — Railway CLI**
```bash
npm i -g @railway/cli
railway login
cd habit-tracker-flask
railway init
railway up
```

**Option B — GitHub**
1. Push this folder to a GitHub repo.
2. In Railway: New Project → Deploy from GitHub repo → select the repo.
3. Railway auto-detects Python via Nixpacks, installs `requirements.txt`,
   and runs the `Procfile`/`railway.json` start command.
4. Once deployed, click the generated domain (or add one) to open the app.

No environment variables are required. Railway sets `PORT` automatically,
and `app.py` / `Procfile` already read it.

### Persisting data across deploys

By default, the SQLite database lives at `data/tracker.db` on local disk,
which is fine while the container is running but is **wiped on every
redeploy** (Railway's filesystem is ephemeral). To keep your history across
deploys:

- Add a **Railway Volume** and mount it at `/app/data` (recommended — no
  code changes needed, SQLite keeps working as-is), or
- Swap SQLite for a managed database (e.g. add a Railway PostgreSQL plugin
  and update the `get_db()`/`init_db()` functions in `app.py`).

## Notes

- The focus timer runs client-side; if it's attached to a habit, completing
  a work/simple session checks off *today's* date for that habit (or the
  current week, for weekly habits) via the toggle endpoint — it won't
  uncheck something you already marked done.
- Because completions are stored against real dates/weeks rather than
  array positions, your history is permanent: scrolling into a new month
  or week just changes which periods the grid displays, nothing is lost.
