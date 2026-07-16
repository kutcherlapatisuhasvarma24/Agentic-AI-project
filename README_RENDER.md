Render deployment instructions for Smart Timetable Assistant

1) Create a New Web Service on Render
- Go to Render dashboard → New → Web Service → Connect GitHub and select this repository.
- Branch: choose the branch you want to deploy (e.g., `main` or `render-quick`).

2) Build & Start
- Option A: Python service
  - Environment: Python
  - Build command: `pip install -r requirements.txt`
  - Start command: `uvicorn backend.main:app --host 0.0.0.0 --port $PORT`

- Option B: Docker service
  - Choose Docker on Render
  - Render will build using the included `Dockerfile`
  - No custom build/start command is needed

3) Environment variables
- `OPENAI_API_KEY` — (optional) your OpenAI key.
- `GEMINI_API_KEY` — (optional) your Gemini key.
- `DATABASE_URL` — (recommended) use a managed Postgres DB URL (eg. `postgres://...`) instead of SQLite for persistence.

4) Database recommendation
- For production, provision a managed Postgres database (Render offers managed DBs) and set `DATABASE_URL`. The backend falls back to SQLite when `DATABASE_URL` is not provided, but SQLite data is ephemeral on cloud instances.

5) Health check
- Set Render Health Check path to `/api/events` so Render can monitor service health.

6) After deployment
- You'll get a public URL like `https://smart-timetable-backend.onrender.com`.
- Update the frontend's `DEPLOYED_BACKEND` (in `frontend/app.js`) to this URL, or update `vercel.json` to proxy to this Render URL.

7) Local testing (optional)
- Run locally with:
  ```bash
  pip install -r requirements.txt
  uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
  ```
  Then open `http://localhost:8000/api/events` to verify JSON responses.

If you want, I can add a Dockerfile or create a branch with these changes and a short PR.
