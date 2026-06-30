# Matchup Advantage

An NBA opponent advance-scouting dashboard: pick a team, season, and opponent to
see who to attack, where to attack them, and how to defend their best scorers.

## Required files

These files must be present in the same folder to run the app:

- `app.py` — the dashboard (the file you run)
- `data_pipeline.py` — the data layer `app.py` imports (NBA Stats API + caching)
- `.streamlit/config.toml` — the app's theme settings
- `requirements.txt` — the Python packages to install
- `README.md` — this file

## Setup

You need Python 3.9 or newer.

1. **Create and activate a virtual environment** (from inside the project folder):

   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```

   On Windows (PowerShell), activate with:

   ```powershell
   .venv\Scripts\Activate.ps1
   ```

2. **Install the dependencies:**

   ```bash
   pip install -r requirements.txt
   ```

## Running the app

From the project folder, with the virtual environment activated:

```bash
streamlit run app.py
```

Streamlit will open the dashboard in your web browser automatically (usually at
`http://localhost:8501`). If it doesn't open on its own, copy that address from
the terminal into your browser.

## Note on the internet connection

The app **requires an internet connection** — it pulls live data from the NBA
Stats API the first time you load each team and season. That first load for a
given team/season may take a few moments while it fetches and caches the data;
after that, the same selection loads instantly from the local cache.
