# OddsEye

Self-hosted prediction market radar and paper trading system for Crypto and
Macro/Economics markets.

## Local Backend

```bash
docker compose up -d postgres redis
cd backend
uv sync
cp ../config/app.example.yaml ../config/app.yaml
cp ../.env.example ../.env
python -m app.tools.hash_password
alembic upgrade head
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

`python -m app.tools.seed_watchlist` is only for local demo data. Do not run it
for production data checks.

Only `/health` and `/auth/login` are public. All other API routes require
`Authorization: Bearer <token>`.

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

Codex usage is advisory only. Requests are logged to `api_usage_ledger`; requests
are not blocked by budget code.

Paper trading review endpoints:

- `GET /paper/review` returns strategy/category rollups and trade rows.
- `GET /paper/trades.csv` exports fills with `signal_id` and `snapshot_id` traceability.

## Production Deployment

Production uses containers for the OddsEye API and workers. PostgreSQL and Redis
run on the host and are passed through `DATABASE_URL` and `REDIS_URL`.

1. Pull the repo on the server:

```bash
cd /root/oddseye
git pull --ff-only
```

2. Create `/root/oddseye/.env` from `.env.example` and set:

```bash
APP_ENV=prod
APP_CONFIG_PATH=/config/app.yaml
DATABASE_URL=postgresql+psycopg://USER:PASSWORD@HOST:5432/DB
REDIS_URL=redis://HOST:6379/0
CODEX_API_KEY=...
JWT_SECRET=...
JWT_EXPIRES_DAYS=7
API_BIND_HOST=127.0.0.1
API_PORT=8000
```

3. Provision host PostgreSQL and Redis. Production compose intentionally does not
start PostgreSQL or Redis; keep them bound to localhost/private networking and
point `DATABASE_URL` / `REDIS_URL` at those host services.

4. Create `config/app.yaml` from `config/app.example.yaml`, generate a bcrypt
password hash, set it in `auth.users`, and keep secrets out of mobile files:

```bash
cd /root/oddseye/backend
python -m app.tools.hash_password
```

For public deployments, also set `auth.ip_allowlist` to your allowed public
CIDR(s), plus any trusted proxy/loopback ranges you need for local health checks.
Leave it empty only on a private network or while intentionally testing public
access.

5. Run migrations and start services:

```bash
docker compose -f docker-compose.prod.yml run --rm api alembic upgrade head
docker compose -f docker-compose.prod.yml up -d --build
```

6. Add the domain to Caddy on the same host. Caddy is the HTTPS reverse proxy for
this deployment and replaces the Nginx example in the V1 engineering document:

```caddyfile
oddseye.fun {
  reverse_proxy 127.0.0.1:8000
}
```

If `API_BIND_HOST` is set to a different local interface, use that same host in
`reverse_proxy`.

7. Configure the iOS app API base URL:

```bash
cd mobile
printf 'EXPO_PUBLIC_API_BASE_URL=https://oddseye.fun\n' > .env
```

## Production Verification

```bash
curl -fsS https://oddseye.fun/health
```

Login and check live data:

```bash
TOKEN="$(
  curl -fsS -X POST https://oddseye.fun/auth/login \
    -H 'Content-Type: application/json' \
    --data '{"username":"admin","password":"REPLACE_WITH_PASSWORD"}' \
  | python3 -c 'import json,sys; print(json.load(sys.stdin)["access_token"])'
)"

curl -fsS "https://oddseye.fun/radar/markets?limit=3" \
  -H "Authorization: Bearer $TOKEN"

curl -fsS "https://oddseye.fun/signals?limit=3" \
  -H "Authorization: Bearer $TOKEN"

curl -fsS "https://oddseye.fun/paper/performance" \
  -H "Authorization: Bearer $TOKEN"
```

Expected production state:

- containers `api`, `worker-ingest`, `worker-signal`, `worker-paper`,
  `worker-resolution`, and `worker-usage` are running.
- `api_usage_ledger` records Codex calls with status, duration, and kind.
- `prediction_events`, `prediction_markets`, and `market_snapshots` contain
  real Codex data, not `seed-*` demo rows.
- `/signals` returns `BUY` and/or `OBSERVE` signals once crypto threshold markets
  have been enriched with public BTC/ETH/SOL market data.
- Paper orders use bid/ask based fills and can be traced through
  `signal_id` and `snapshot_id`.

## Mobile

```bash
cd mobile
npm install
cp .env.example .env
npx expo start
```

For Expo Go on an iPhone against local dev, set `EXPO_PUBLIC_API_BASE_URL` to
the computer LAN IP, not `localhost`. For the deployed backend, set it to
`https://oddseye.fun`.

V1's supported mobile development path is Expo Go. Any generated `mobile/ios`
directory is local-only for ad hoc native/Xcode experiments and is intentionally
ignored by git.

## Verification

```bash
cd backend
uv run pytest
uv run ruff check .

cd ../mobile
npm run typecheck
```

## Security Notes

- Keep `CODEX_API_KEY` and `JWT_SECRET` only in backend `.env`.
- Mobile `.env` only uses public `EXPO_PUBLIC_*` values.
- The app stores JWT in SecureStore and never stores the Codex API key.
- V1 paper trading uses bid/ask based fills, never last price fills.
