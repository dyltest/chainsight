# ChainSight 🧬

A real-time cryptocurrency data dashboard with an elegant single-page UI. Live market data from CoinGecko, proxied through a caching FastAPI backend. Zero frontend build step — pure HTML + ECharts.

<p align="center">
  <img src="https://img.shields.io/badge/python-3.12-blue" alt="Python 3.12">
  <img src="https://img.shields.io/badge/fastapi-0.115-green" alt="FastAPI">
  <img src="https://img.shields.io/badge/docker-compose-blue" alt="Docker">
</p>

---

## Features

- **📊 Live Market Dashboard** — Total market cap, 24h volume, BTC dominance, DeFi TVL, BTC price chart, top movers
- **🪙 Token Explorer** — Sortable token table with candlestick (K-line) and volume charts
- **⛓️ On-Chain Analytics** — Active addresses, gas trends, DEX volume visualizations
- **📈 DeFi Indices** — Blue-chip / L1 / AI & Data index NAV trends and holdings
- **💼 Portfolio Tracker** — Wallet asset allocation and P&L overview
- **⚡ In-Memory Cache** — 30-second TTL cache keeps upstream calls well below CoinGecko's free-tier rate limit
- **🛡️ Graceful Degradation** — Falls back to cached data when CoinGecko is unavailable; UI is never blank
- **🐳 Docker-First** — Single container, single `docker compose up`

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | Vanilla HTML5 / CSS3 / JavaScript (ES6+) |
| Charts | ECharts 5 (CDN) |
| Backend | FastAPI (Python) |
| Server | Uvicorn |
| HTTP Client | httpx (async) |
| Data Source | CoinGecko Public API |
| Container | Docker + Docker Compose |

## Quick Start

### Docker (Recommended)

```bash
git clone https://github.com/YOUR_USERNAME/chainsight-deploy.git
cd chainsight-deploy
docker compose up -d --build
```

Open [http://localhost:8000](http://localhost:8000).

### Local (No Docker)

```bash
pip install -r backend/requirements.txt
cd backend
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### Verify

```bash
curl http://localhost:8000/api/health
# {"status":"ok","ts":1716652800.0}
```

## API Endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /` | Frontend dashboard SPA |
| `GET /api/health` | Health check |
| `GET /api/tokens?vs_currency=usd&per_page=10` | Top tokens by market cap |
| `GET /api/global` | Global market stats (total mcap, BTC dominance, volume) |
| `GET /api/ohlc/{coin_id}?days=30` | OHLC candlestick data for any CoinGecko coin ID |

All market data endpoints use a **30-second TTL in-memory cache** and **retry with exponential backoff** on CoinGecko rate limits (HTTP 429).

## Project Structure

```
chainsight-deploy/
├── docker-compose.yml          # Docker orchestration
├── backend/
│   ├── Dockerfile              # Python 3.12-slim image
│   ├── main.py                 # FastAPI app — proxy + cache + static serving
│   └── requirements.txt        # fastapi, uvicorn, httpx
├── static/
│   └── index.html              # Full SPA (5 modules, ECharts-powered)
├── DEPLOY.md                   # Tencent Cloud deployment guide (中文)
└── README.md
```

## Architecture

```
Browser (index.html)
    │  fetch() → same origin
    ▼
FastAPI Backend (main.py)
    │  30s TTL cache
    │  httpx.AsyncClient
    ▼
CoinGecko Public API
```

The backend acts as a **BFF (Backend-for-Frontend) proxy**: it normalizes CoinGecko responses, caches them to avoid rate limiting, and serves the static frontend — all from a single container.

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `COINGECKO_BASE` | `https://api.coingecko.com/api/v3` | Upstream API base URL |
| `CACHE_TTL` | `30` (seconds) | In-memory cache duration |
| `HTTP_TIMEOUT` | `15` (seconds) | Upstream request timeout |

These are hardcoded in `backend/main.py` (lines 27–30) — adjust as needed before building.

## Deployment

See **[DEPLOY.md](./DEPLOY.md)** for a step-by-step Tencent Cloud Lighthouse deployment guide (in Chinese), including:

- Server sizing & firewall setup
- Docker installation
- Nginx reverse proxy + HTTPS (Certbot)
- Daily ops commands & cost breakdown

## License

MIT
