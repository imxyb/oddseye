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
- `GET /paper/positions` returns current paper positions with mark price and PnL.
- `GET /paper/performance` returns cash, position value, PnL, win rate, and drawdown.
- `GET /paper/trades.csv` exports fills with `signal_id` and `snapshot_id` traceability.
- `POST /markets/{market_id}/refresh` refreshes the current market event from
  Codex and records the request as `manual_refresh`.

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
client CIDR(s). `auth.trusted_proxy_cidrs` controls which local reverse proxies
may supply `X-Forwarded-For`/`X-Real-IP`; keep loopback there for Caddy when it
proxies to `127.0.0.1:8000`. Leave `ip_allowlist` empty only on a private
network or while intentionally testing public access.

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

After migrations and service startup, run the production verifier from the built
API image. It checks health, login, authenticated `/auth/me` identity, Radar live
data, Crypto and Macro/Economics category data, documented Radar sort
dimensions, market detail quotes, quality score explanations, chart bars, active
`crypto_threshold_v1` crypto threshold signals, `macro_calendar_v1`
Macro/Economics OBSERVE-only signals, usage counters, recent ingestion job runs,
paper performance metrics, strategy/category review rollups, paper positions,
and paper trade traceability in one repeatable command:

The verifier creates tiny paper BUY orders through both the manual order API and
the signal order API, then sells the manual position back through the manual
order API. This checks that BUY fills use ask-side pricing and SELL fills use
bid-side pricing against production quotes. These orders are paper-only but they
do update the paper account.

```bash
docker compose -f docker-compose.prod.yml run --rm \
  -e ODDSEYE_VERIFY_PASSWORD='REPLACE_WITH_PASSWORD' \
  api python -m app.tools.verify_production \
  --base-url https://oddseye.fun \
  --username admin \
  --password-env ODDSEYE_VERIFY_PASSWORD
```

The command prints one `[ok]` line per check and exits non-zero on the first
failed production invariant.

For targeted troubleshooting, the equivalent manual checks are:

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

curl -fsS "https://oddseye.fun/auth/me" \
  -H "Authorization: Bearer $TOKEN" \
  | python3 -c 'import json,sys; d=json.load(sys.stdin); assert d["username"]=="admin"; assert d["role"]; print("auth me ok")'

curl -fsS "https://oddseye.fun/radar/markets?category=crypto&sort=quality&limit=5" \
  -H "Authorization: Bearer $TOKEN"

curl -fsS "https://oddseye.fun/radar/markets?category=crypto&sort=volume&limit=5" \
  -H "Authorization: Bearer $TOKEN"

curl -fsS "https://oddseye.fun/radar/markets?category=crypto&sort=liquidity&limit=5" \
  -H "Authorization: Bearer $TOKEN"

curl -fsS "https://oddseye.fun/radar/markets?category=crypto&sort=closingSoon&limit=5" \
  -H "Authorization: Bearer $TOKEN"

MARKET_ID="$(
  curl -fsS "https://oddseye.fun/radar/markets?limit=1" \
    -H "Authorization: Bearer $TOKEN" \
  | python3 -c 'import json,sys; print(json.load(sys.stdin)["items"][0]["market_id"])'
)"

curl -fsS "https://oddseye.fun/markets/$MARKET_ID" \
  -H "Authorization: Bearer $TOKEN" \
  | python3 -c 'import json,sys; d=json.load(sys.stdin); q=d["quality"]; c=q["components"]; assert d["market_quality_score"] is not None; assert all(k in c for k in ("liquidity","spread","resolution_clarity","modelability","time","activity")); assert isinstance(q["reason_codes"], list); assert isinstance(q["risk_flags"], list); assert isinstance(q["passes_paper_gate"], bool); print("quality explanation ok")'

curl -fsS "https://oddseye.fun/signals?limit=3" \
  -H "Authorization: Bearer $TOKEN"

curl -fsS "https://oddseye.fun/signals?category=crypto&limit=20" \
  -H "Authorization: Bearer $TOKEN" \
  | python3 -c 'import json,sys; items=json.load(sys.stdin)["items"]; assert any(i.get("strategy_code")=="crypto_threshold_v1" and i.get("category")=="crypto" and any(asset in i.get("question","").upper() for asset in ("BTC","ETH","SOL")) for i in items); print("crypto threshold signal ok")'

curl -fsS -X POST "https://oddseye.fun/paper/orders" \
  -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  --data '{"market_id":"REPLACE_WITH_MARKET_ID","side":"BUY","outcome_index":0,"limit_price":"REPLACE_WITH_ASK","quantity":"0.01"}'

curl -fsS -X POST "https://oddseye.fun/paper/orders" \
  -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  --data '{"market_id":"REPLACE_WITH_MARKET_ID","side":"SELL","outcome_index":0,"limit_price":"REPLACE_WITH_BID","quantity":"0.01"}'

curl -fsS "https://oddseye.fun/signals?action=BUY&limit=5" \
  -H "Authorization: Bearer $TOKEN"

curl -fsS -X POST "https://oddseye.fun/signals/REPLACE_WITH_SIGNAL_ID/paper-order" \
  -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  --data '{"notional":"0.01","limit_price":"REPLACE_WITH_EXECUTABLE_PRICE"}'

curl -fsS "https://oddseye.fun/paper/performance" \
  -H "Authorization: Bearer $TOKEN" \
  | python3 -c 'import json,sys; d=json.load(sys.stdin); assert all(k in d for k in ("cash","equity","position_value","realized_pnl","unrealized_pnl","win_rate","max_drawdown","total_trades")); print("paper performance ok")'

curl -fsS "https://oddseye.fun/paper/positions" \
  -H "Authorization: Bearer $TOKEN" \
  | python3 -c 'import json,sys; items=json.load(sys.stdin)["items"]; assert items; assert all(all(k in i for k in ("position_id","market_id","outcome_index","quantity","avg_price","realized_pnl","unrealized_pnl","status")) for i in items); print("paper positions ok")'

curl -fsS "https://oddseye.fun/paper/trades.csv" \
  -H "Authorization: Bearer $TOKEN"

curl -fsS "https://oddseye.fun/settings/usage" \
  -H "Authorization: Bearer $TOKEN" \
  | python3 -c 'import json,sys; d=json.load(sys.stdin); jobs={j["job_name"]: j for j in d["recent_jobs"] if j["status"]=="success"}; assert "discover_events" in jobs; assert "compute_quality" in jobs; assert any(name in jobs and jobs[name]["records_processed"] > 0 for name in ("sync_hot_markets","sync_warm_markets","sync_cold_markets")); print("scheduled ingestion jobs ok")'
```

Expected production state:

- containers `api`, `worker-ingest`, `worker-signal`, `worker-paper`,
  `worker-resolution`, and `worker-usage` are running.
- `/auth/login` issues a bearer token for the configured admin user, and
  `/auth/me` resolves that token back to the configured username and role.
- `api_usage_ledger` records Codex calls with status, duration, and kind.
- `/settings/usage` reports daily/monthly request counters plus recent successful
  `discover_events`, `sync_*_markets`, and `compute_quality` job runs.
- `prediction_events`, `prediction_markets`, and `market_snapshots` contain
  real Codex data, not `seed-*` demo rows.
- Market detail includes `market_quality_score` plus quality components,
  `reason_codes`, `risk_flags`, and `passes_paper_gate`.
- `/signals` returns `crypto_threshold_v1` signals for crypto threshold markets
  once supported assets are enriched with public BTC/ETH/SOL market data.
- `/signals?category=economics` returns `macro_calendar_v1` OBSERVE-only
  signals for Macro/Economics markets without auto-trade fields.
- Market detail exposes a manual refresh action for stale prices; it should write
  a `manual_refresh` row to `api_usage_ledger`.
- `/paper/performance` exposes cash, position value, realized/unrealized PnL,
  win rate, drawdown, and trade count; `/paper/positions` exposes current
  position quantity, average price, mark price, and PnL.
- `/paper/review` exposes strategy/category rollups with trade count, average
  edge, realized PnL, win rate, and max drawdown.
- Paper orders use bid/ask based fills and can be traced through
  `signal_id`, `snapshot_id`, and `price` in `/paper/trades.csv`.

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

Before opening Expo Go, run the deployed-login smoke check from the mobile
workspace. It verifies the public API URL, Expo config, backend health,
`/auth/login`, and `/auth/me` using the same API base URL compiled into the app:

```bash
cd mobile
ODDSEYE_MOBILE_SMOKE_PASSWORD='REPLACE_WITH_PASSWORD' npm run verify:expo-go
```

The final V1 mobile acceptance still requires a physical iPhone running Expo Go:
start `npx expo start`, open the project in Expo Go, log in with the configured
admin credentials, and confirm the app reaches the authenticated tabs without a
`Could not load` or login error state.

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
npm test -- --run
ODDSEYE_MOBILE_SMOKE_PASSWORD='REPLACE_WITH_PASSWORD' npm run verify:expo-go
npx expo export --platform ios --output-dir dist/ios-public-bundle
npm run verify:public-bundle -- app app.json babel.config.js src/api src/components src/stores src/theme.ts src/utils dist/ios-public-bundle
```

The public bundle scan checks text assets and Expo iOS Hermes `.hbc` bundles.
To verify real secret values are absent from the mobile source and exported
bundle without writing them to the repo, pass them at runtime:

```bash
ODDSEYE_FORBIDDEN_BUNDLE_STRINGS='SECRET_1,SECRET_2' \
  npm run verify:public-bundle -- app src dist/ios-public-bundle
```

## Security Notes

- Keep `CODEX_API_KEY` and `JWT_SECRET` only in backend `.env`.
- Mobile `.env` only uses public `EXPO_PUBLIC_*` values.
- The app stores JWT in SecureStore and never stores the Codex API key.
- V1 paper trading uses bid/ask based fills, never last price fills.
