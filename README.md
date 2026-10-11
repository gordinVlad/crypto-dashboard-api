# Crypto Dashboard API

A backend API for a cryptocurrency dashboard. It lets users browse current
cryptocurrency rates, view details for a specific coin, manage a personal
watchlist (per authenticated user), and retrieve historical price data.
There is no UI — this is a pure backend/API project, built as a home
assignment.

## Overview

- **Language / Framework:** Python 3.12 + [FastAPI](https://fastapi.tiangolo.com/)
- **Database:** SQLite, accessed through the [SQLAlchemy](https://www.sqlalchemy.org/) ORM
- **Authentication:** JWT (email + password), passwords hashed with bcrypt
- **External data provider:** [CoinGecko](https://www.coingecko.com/en/api) public API (no API key required)
- **API docs:** Auto-generated Swagger UI (`/docs`) and ReDoc (`/redoc`), plus a Postman collection
- **Tests:** `pytest`, with the external provider mocked so tests don't depend on network access

### How data flows

1. `POST /api/cryptocurrencies/refresh` pulls the current top coins (by market
   cap) from CoinGecko and stores/updates them in the local database.
2. `GET /api/cryptocurrencies` and `GET /api/cryptocurrencies/:id` read from
   the local database (fast, no external calls on every request).
3. `GET /api/cryptocurrencies/:id/history` returns locally stored history if
   present; otherwise it fetches it from CoinGecko once, persists it, and
   returns it. Subsequent calls are served from the database.
4. The watchlist is a many-to-many relation between users and
   cryptocurrencies, scoped to the authenticated user via their JWT.

## Project structure

```
app/
├── main.py                    # FastAPI app setup, routers, error handling
├── core/
│   ├── config.py               # Settings loaded from environment variables
│   └── security.py             # Password hashing, JWT creation/validation
├── db/
│   ├── database.py             # SQLAlchemy engine/session
│   └── models.py                # User, Cryptocurrency, PriceHistoryEntry, WatchlistItem
├── schemas/                    # Pydantic request/response models
├── crud/                       # Database access functions
├── services/
│   └── coingecko_client.py     # External provider integration
└── api/
    ├── deps.py                  # Auth dependencies (current user from JWT)
    └── routes/                  # auth.py, cryptocurrencies.py, watchlist.py
tests/                          # pytest test suite
```

## Setup instructions

### Prerequisites

- Python 3.11+
- `pip`

### 1. Clone the repository

```bash
git clone <your-repo-url>
cd crypto-dashboard-api
```

### 2. Create a virtual environment and install dependencies

```bash
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Configure environment variables

```bash
cp .env.example .env
```

Then edit `.env` if needed (see [Environment variables](#environment-variables)
below). Account and watchlist flows work locally with the defaults. To enable
CoinGecko refreshes, set `INTERNAL_API_TOKEN` to a dedicated random value and
send that value in the `X-Internal-Token` header.

### 4. Run the app locally

```bash
uvicorn app.main:app --reload
```

The API will be available at `http://127.0.0.1:8000`.

On startup, the app automatically creates the SQLite database file
(`crypto_dashboard.db`) and all required tables — no manual database setup
is needed.

- Interactive Swagger docs: `http://127.0.0.1:8000/docs`
- ReDoc docs: `http://127.0.0.1:8000/redoc`

### 5. Run tests

```bash
pytest tests/ -v
```

All external calls to CoinGecko are mocked in the test suite, so tests run
fully offline and won't be affected by external API rate limits.

## Environment variables

| Variable | Description | Default |
|---|---|---|
| `APP_NAME` | Display name of the app (used in Swagger title) | `Crypto Dashboard API` |
| `ENVIRONMENT` | Free-form environment label (`development`, `production`, ...) | `development` |
| `DATABASE_URL` | SQLAlchemy database URL | `sqlite:///./crypto_dashboard.db` |
| `SECRET_KEY` | Secret used to sign JWT tokens — **must** be changed in production | `change-this-secret-in-production` |
| `ALGORITHM` | JWT signing algorithm | `HS256` |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | JWT token lifetime, in minutes | `1440` (24h) |
| `CORS_ORIGINS` | JSON array of exact browser origins allowed to access the API | `[]` |
| `INTERNAL_API_TOKEN` | Dedicated secret required by scheduled jobs to refresh provider data; must be at least 32 characters | Unset (refresh unavailable) |
| `COINGECKO_BASE_URL` | Base URL of the CoinGecko API | `https://api.coingecko.com/api/v3` |
| `COINGECKO_REQUEST_TIMEOUT_SECONDS` | Timeout for external API requests | `15` |
| `DEFAULT_COINS_LIMIT` | Number of coins fetched on refresh, by default | `50` |

In production, startup fails unless `SECRET_KEY` is at least 32 characters,
has high character diversity, and is not a known placeholder. Generate a
cryptographically random key with the command below. Configure `CORS_ORIGINS`
as a JSON array of exact origins, for example
`["https://dashboard.example.com"]`. CORS is disabled for browser origins by
default; methods and headers are limited to those used by the API.

Set `INTERNAL_API_TOKEN` to a separate cryptographically random value to enable
scheduled data refreshes. Send it in the `X-Internal-Token` header when calling
`POST /api/cryptocurrencies/refresh`. If it is unset, refresh requests fail
closed with `503`; missing or incorrect tokens receive `401`.

To generate a strong `SECRET_KEY`:

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(32))"
```

## API usage

### Typical flow

1. `POST /api/auth/register` — create an account.
2. `POST /api/auth/login` — log in, receive a JWT `access_token`.
3. `POST /api/cryptocurrencies/refresh` — populate the local database with
   current data from CoinGecko; a scheduled job must supply `X-Internal-Token`.
4. `GET /api/cryptocurrencies` — browse the dashboard-style list.
5. `POST /api/watchlist` (with `Authorization: Bearer <token>`) — add a coin
   to your watchlist.
6. `GET /api/watchlist` — view your saved coins.
7. `GET /api/cryptocurrencies/:id/history` — view historical prices.

### Endpoints

| Method | Path | Auth required | Description |
|---|---|---|---|
| POST | `/api/auth/register` | No | Register a new user |
| POST | `/api/auth/login` | No | Log in, get a JWT (form fields: `username`, `password`) |
| GET | `/api/cryptocurrencies` | No | List cryptocurrencies from the local DB |
| GET | `/api/cryptocurrencies/:id` | No | Get details for one cryptocurrency |
| GET | `/api/cryptocurrencies/:id/history?days=7` | Yes | Get cached points in the requested date range; missing coverage is fetched and cached |
| POST | `/api/cryptocurrencies/refresh?limit=50` | `X-Internal-Token` | Sync data from CoinGecko into the local DB |
| GET | `/api/watchlist` | Yes | Get the current user's watchlist |
| POST | `/api/watchlist` | Yes | Add a coin to the watchlist (`cryptocurrency_id` or `external_provider_id`) |
| DELETE | `/api/watchlist/:id` | Yes | Remove an item from the watchlist |
| GET | `/health` | No | Health check |

> Registration and login remain public so users can create accounts and obtain
> credentials. Watchlist writes and price-history requests require a logged-in
> user. The refresh endpoint uses a dedicated internal token so scheduled jobs
> can sync provider data without exposing a public trigger.

### Authentication

Send the JWT as a Bearer token:

```
Authorization: Bearer <access_token>
```

In Swagger UI, click **Authorize** and paste the token (or use the
`/api/auth/login` form directly, since it implements the standard OAuth2
password flow that Swagger understands natively).

### Example requests (curl)

```bash
# Register
curl -X POST http://127.0.0.1:8000/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email": "user@example.com", "password": "password123"}'

# Login
curl -X POST http://127.0.0.1:8000/api/auth/login \
  -d "username=user@example.com&password=password123"

# Refresh coin data from CoinGecko
curl -X POST http://127.0.0.1:8000/api/cryptocurrencies/refresh \
  -H "X-Internal-Token: $INTERNAL_API_TOKEN"

# List cryptocurrencies
curl http://127.0.0.1:8000/api/cryptocurrencies

# Add to watchlist (replace TOKEN and 1 with a real token/id)
curl -X POST http://127.0.0.1:8000/api/watchlist \
  -H "Authorization: Bearer TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"cryptocurrency_id": 1}'

# Get watchlist
curl http://127.0.0.1:8000/api/watchlist -H "Authorization: Bearer TOKEN"

# Get price history
curl "http://127.0.0.1:8000/api/cryptocurrencies/1/history?days=7" \
  -H "Authorization: Bearer TOKEN"
```

### Error handling

All errors are returned as JSON with a consistent shape:

```json
{ "detail": "Cryptocurrency not found" }
```

Validation errors (422) include per-field details:

```json
{ "detail": "Validation error", "errors": [ ... ] }
```

Relevant status codes used throughout the API: `400`, `401`, `404`, `409`
(duplicate registration / duplicate watchlist entry), `422` (validation),
`502` (external provider failure), `500` (unexpected error).

## API documentation

- **Swagger / OpenAPI**: available live at `/docs` once the app is running
  (and at `/openapi.json` as raw JSON).
- **Postman collection**: [`postman_collection.json`](./postman_collection.json)
  in this repository. Import it into Postman; it includes a collection
  variable `base_url` (defaults to `http://127.0.0.1:8000`) and an
  `access_token` variable that is filled in automatically after running the
  **Login** request.

## Deployment

The app is container-friendly (a `Dockerfile` is included) and also works
with buildpack-based platforms via the included `Procfile`.

### Deploying to Render (example)

1. Push this repository to GitHub.
2. In the [Render dashboard](https://dashboard.render.com/), create a new
   **Web Service** and connect your GitHub repo.
3. Configure:
   - **Environment:** Docker (Render will detect the `Dockerfile`), or
     Python if you prefer the buildpack + `Procfile` path.
   - **Build command** (if not using Docker): `pip install -r requirements.txt`
   - **Start command** (if not using Docker): `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
4. Add environment variables from the [table above](#environment-variables)
   in the Render dashboard (at minimum, set a strong `SECRET_KEY`).
5. Deploy. Render will expose a public URL, e.g. `https://crypto-dashboard-api.onrender.com`.
6. Visit `https://<your-app>.onrender.com/docs` to confirm it's live.

### Deploying to Railway (example)

1. Push this repository to GitHub.
2. In [Railway](https://railway.app/), create a new project from your
   GitHub repo. Railway will detect the `Dockerfile` (or `Procfile`)
   automatically.
3. Add the environment variables from the table above in the Railway
   project settings.
4. Railway assigns a public domain automatically; deploy and visit
   `https://<your-app>.up.railway.app/docs`.

> **Note on SQLite in production:** SQLite is used here for simplicity, as
> allowed by the assignment. On most free hosting tiers the filesystem is
> ephemeral, so the database resets on redeploy/restart. For a persistent
> production setup, point `DATABASE_URL` at a managed PostgreSQL instance
> (e.g. Render's free Postgres) — no code changes are required beyond the
> connection string, since SQLAlchemy abstracts the database engine.

### Deployed application URL

_Add the live URL here after deploying, e.g.:_
`https://crypto-dashboard-api.onrender.com`

### CI/CD

A GitHub Actions workflow (`.github/workflows/ci.yml`) runs the test suite
automatically on every push and pull request to `main`.

## Data model

| Model | Key fields |
|---|---|
| `User` | `id`, `email`, `hashed_password`, `created_at` |
| `Cryptocurrency` | `id`, `name`, `symbol`, `external_provider_id`, `current_price`, `market_cap`, `price_change_percentage_24h`, `image_url`, `last_updated_at` |
| `PriceHistoryEntry` | `id`, `cryptocurrency_id`, `price`, `timestamp` |
| `WatchlistItem` | `id`, `user_id`, `cryptocurrency_id`, `added_at` |

## Technical decisions

- **SQLite + SQLAlchemy ORM**: simplest possible persistent storage for a
  time-boxed assignment, with zero external setup. Because access goes
  through the ORM, swapping to PostgreSQL later is a one-line change to
  `DATABASE_URL`.
- **CoinGecko** was chosen over CoinMarketCap because it doesn't require an
  API key, which keeps setup friction near zero for reviewers.
- **Local caching of market/history data**: `GET` endpoints read from the
  local DB instead of calling the external provider on every request, which
  is both faster and avoids hitting CoinGecko's public rate limits. A
  dedicated `POST /refresh` endpoint controls when to sync.
- **JWT auth** with a standard OAuth2 password flow so it plugs directly
  into Swagger UI's built-in "Authorize" button with no custom tooling.
- **Consistent JSON error handling** via global FastAPI exception handlers,
  so every error (validation, HTTP, or unexpected) has the same response
  shape.

## Git repositry
https://github.com/gordinVlad/crypto-dashboard-api.git
