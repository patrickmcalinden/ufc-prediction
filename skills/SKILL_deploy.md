# SKILL: Deployment

## Purpose
Deploy the FastAPI backend + PostgreSQL to Render.com and the React frontend to Vercel.

## Files It Owns
```
api/
└── requirements.txt       # Python dependencies for Render

frontend/
└── .env.production        # VITE_API_URL set to the live Render URL

docker-compose.yml         # Local dev only — not used in production
.env.example               # Always kept up to date
```

## Render.com Setup (API + Database)

### PostgreSQL
1. Create a new PostgreSQL instance on Render (free tier: 1GB storage, 90-day retention on free plan — upgrade if needed)
2. Copy the `Internal Database URL` for use within Render services
3. Copy the `External Database URL` for running migrations from your local machine

### FastAPI Web Service
- **Build command:** `pip install -r api/requirements.txt`
- **Start command:** `uvicorn api.main:app --host 0.0.0.0 --port $PORT`
- **Root directory:** leave blank (run from repo root)
- **Environment variables to set in Render dashboard:**
  ```
  DATABASE_URL=<Internal Database URL from above>
  ENV=production
  FRONTEND_URL=https://your-app.vercel.app
  MODEL_ARTIFACT_PATH=model/artifacts/xgb_v1.json
  ```

### requirements.txt Template
```
fastapi==0.111.0
uvicorn[standard]==0.29.0
sqlalchemy==2.0.30
psycopg2-binary==2.9.9
python-dotenv==1.0.1
python-frontmatter==1.1.0
xgboost==2.0.3
pandas==2.2.2
scikit-learn==1.4.2
pydantic==2.7.1
```

## Vercel Setup (React Frontend)

1. Connect GitHub repo to Vercel
2. Set **Root Directory** to `frontend`
3. Vercel auto-detects Vite — no build command changes needed
4. Set environment variable in Vercel dashboard:
   ```
   VITE_API_URL=https://your-api.onrender.com
   ```
5. Deploy. Vercel rebuilds on every push to `main`.

## Docker Compose (Local Dev Only)

```yaml
# docker-compose.yml
version: "3.9"
services:
  db:
    image: postgres:16
    environment:
      POSTGRES_USER: ufc
      POSTGRES_PASSWORD: ufc
      POSTGRES_DB: ufc_predictor
    ports:
      - "5432:5432"
    volumes:
      - pgdata:/var/lib/postgresql/data

  api:
    build: .
    command: uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload
    ports:
      - "8000:8000"
    env_file: .env
    depends_on:
      - db

volumes:
  pgdata:
```

Local `.env` for Docker:
```
DATABASE_URL=postgresql://ufc:ufc@db:5432/ufc_predictor
ENV=development
MODEL_ARTIFACT_PATH=model/artifacts/xgb_v1.json
```

## Gotchas
- Render free tier spins down after 15 minutes of inactivity. The first request after sleep takes ~30 seconds. Acceptable for v1.
- Render's free PostgreSQL expires after 90 days. Back up data before expiry or upgrade.
- `psycopg2-binary` is fine for deployment. Do not use `psycopg2` without binary on Render — it requires system dependencies that may not be present.
- The `FRONTEND_URL` env var on Render must exactly match the Vercel deployment URL (including `https://`) for CORS to work.
- Model artifacts (`.json` files) are committed to the repo and deployed with the code. Keep them small — XGBoost models are typically under 5MB.

## LLM Instructions
- See spec Section 14 for the hosting decisions and rationale.
- Target Render.com for API + database and Vercel for the frontend. Do not write AWS/GCP/Azure-specific config unless the user explicitly requests it.
- Never hard-code the API URL in frontend code. It must come from `import.meta.env.VITE_API_URL`.
- The `ENV` variable controls CORS behavior: `development` allows all origins, `production` restricts to `FRONTEND_URL`.
- Docker Compose is for local development only. Do not reference it in production deployment instructions.

## Status
NOT STARTED
