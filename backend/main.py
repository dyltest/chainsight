"""
ChainSight — FastAPI Backend
Proxies CoinGecko API with in-memory TTL cache.
Serves static frontend files.
"""
import time
import asyncio
from pathlib import Path
from typing import Optional

import httpx
from fastapi import FastAPI, Query, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="ChainSight API", version="0.1.0")

# ---- CORS ----
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---- Config ----
COINGECKO_BASE = "https://api.coingecko.com/api/v3"
CACHE_TTL = 30  # seconds — CoinGecko free tier: 30 req/min
HTTP_TIMEOUT = 15.0

# ---- In-Memory Cache ----
_cache: dict[str, tuple[float, dict]] = {}

def cache_get(key: str) -> Optional[dict]:
    entry = _cache.get(key)
    if entry is None:
        return None
    ts, data = entry
    if time.time() - ts > CACHE_TTL:
        del _cache[key]
        return None
    return data

def cache_set(key: str, data: dict):
    _cache[key] = (time.time(), data)

# ---- HTTP Client (reuse) ----
_client: Optional[httpx.AsyncClient] = None

async def get_client() -> httpx.AsyncClient:
    global _client
    if _client is None:
        _client = httpx.AsyncClient(timeout=HTTP_TIMEOUT)
    return _client

async def fetch_coingecko(path: str, params: dict = None) -> dict:
    """Fetch from CoinGecko with simple retry logic."""
    client = await get_client()
    url = f"{COINGECKO_BASE}{path}"
    for attempt in range(3):
        try:
            resp = await client.get(url, params=params)
            if resp.status_code == 429:
                await asyncio.sleep(2 ** attempt)
                continue
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 429:
                await asyncio.sleep(2 ** attempt)
                continue
            raise HTTPException(status_code=502, detail=f"Upstream error: {e.response.status_code}")
        except httpx.RequestError:
            if attempt == 2:
                raise HTTPException(status_code=502, detail="Upstream unreachable")
            await asyncio.sleep(1)
    raise HTTPException(status_code=502, detail="Upstream rate limited")


# ==================== API Endpoints ====================

@app.get("/api/health")
async def health():
    return {"status": "ok", "ts": time.time()}


@app.get("/api/tokens")
async def get_tokens(
    vs_currency: str = Query("usd"),
    per_page: int = Query(10, ge=1, le=50),
    page: int = Query(1, ge=1),
):
    """Proxy CoinGecko /coins/markets — with cache."""
    cache_key = f"tokens:{vs_currency}:{per_page}:{page}"
    cached = cache_get(cache_key)
    if cached is not None:
        return cached

    raw = await fetch_coingecko("/coins/markets", {
        "vs_currency": vs_currency,
        "order": "market_cap_desc",
        "per_page": per_page,
        "page": page,
        "sparkline": "false",
        "price_change_percentage": "24h",
    })
    result = [
        {
            "id": t["id"],
            "rank": i + 1 + (page - 1) * per_page,
            "symbol": str(t["symbol"]).upper(),
            "name": t["name"],
            "price": t.get("current_price"),
            "mcap": t.get("market_cap"),
            "change24": t.get("price_change_percentage_24h") or 0,
            "vol24": t.get("total_volume"),
            "image": t.get("image", ""),
        }
        for i, t in enumerate(raw)
    ]
    cache_set(cache_key, result)
    return result


@app.get("/api/global")
async def get_global():
    """Proxy CoinGecko /global."""
    cache_key = "global"
    cached = cache_get(cache_key)
    if cached is not None:
        return cached

    raw = await fetch_coingecko("/global")
    d = raw.get("data", {})
    result = {
        "totalMcap": d.get("total_market_cap", {}).get("usd", 0),
        "mcapChange24": d.get("market_cap_change_percentage_24h_usd", 0),
        "totalVol24": d.get("total_volume", {}).get("usd", 0),
        "btcDominance": d.get("market_cap_percentage", {}).get("btc", 0),
        "btcDomChange": 0,
    }
    cache_set(cache_key, result)
    return result


@app.get("/api/ohlc/{coin_id}")
async def get_ohlc(
    coin_id: str,
    vs_currency: str = Query("usd"),
    days: int = Query(30, ge=1, le=90),
):
    """Proxy CoinGecko /coins/{id}/ohlc."""
    cache_key = f"ohlc:{coin_id}:{days}"
    cached = cache_get(cache_key)
    if cached is not None:
        return cached

    raw = await fetch_coingecko(f"/coins/{coin_id}/ohlc", {
        "vs_currency": vs_currency,
        "days": days,
    })
    result = [
        {
            "date": r[0],   # timestamp ms
            "open": r[1],
            "high": r[2],
            "low": r[3],
            "close": r[4],
        }
        for r in raw
    ]
    cache_set(cache_key, result)
    return result


# ==================== Static Files ====================

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"

if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    @app.get("/")
    async def serve_index():
        index_path = STATIC_DIR / "index.html"
        if index_path.exists():
            return FileResponse(str(index_path))
        return {"message": "ChainSight API is running. Place index.html in static/ folder."}


# ==================== Startup / Shutdown ====================

@app.on_event("shutdown")
async def shutdown():
    global _client
    if _client:
        await _client.aclose()
        _client = None
