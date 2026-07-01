# Prediction Radar

Self-hosted prediction market radar and paper trading system for Crypto and Macro/Economics markets.

## Local Backend

```bash
docker compose up -d postgres redis
cd backend
uv sync
cp ../config/app.example.yaml ../config/app.yaml
cp ../.env.example ../.env
python -m app.tools.hash_password
alembic upgrade head
python -m app.tools.seed_watchlist
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Only `/health` and `/auth/login` are public. All other API routes require `Authorization: Bearer <token>`.

## Workers

Run workers outside the FastAPI process:

```bash
cd backend
python -m app.workers.ingest
python -m app.workers.signal
python -m app.workers.paper_mark
python -m app.workers.resolution
python -m app.workers.usage
```

Codex usage is advisory only. Requests are logged to `api_usage_ledger`; requests are not blocked by budget code.

Paper trading review endpoints:

- `GET /paper/review` returns strategy/category rollups and trade rows.
- `GET /paper/trades.csv` exports fills with `signal_id` and `snapshot_id` traceability.

## Mobile

```bash
cd mobile
npm install
cp .env.example .env
npx expo start
```

For Expo Go on an iPhone, set `EXPO_PUBLIC_API_BASE_URL` to the computer LAN IP, not `localhost`.

## Verification

```bash
cd backend
uv run pytest
uv run ruff check .

cd ../mobile
npx tsc --noEmit
```

## Security Notes

- Keep `CODEX_API_KEY` and `JWT_SECRET` only in backend `.env`.
- Mobile `.env` only uses public `EXPO_PUBLIC_*` values.
- The app stores JWT in SecureStore and never stores the Codex API key.
- V1 paper trading uses bid/ask based fills, never last price fills.
