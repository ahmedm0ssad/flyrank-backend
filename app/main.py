import os
from contextlib import asynccontextmanager

import redis.asyncio as redis_ai
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.database import close_pool, get_pool, is_postgres_enabled
from app.routers import scrape, tasks
from app.routers.ai import router as ai_router
from app.routers.auth import auth_router, protected_router
from app.supabase_client import get_client_credentials

load_dotenv()

_redis_client: redis_ai.Redis | None = None


def get_redis() -> redis_ai.Redis | None:
    global _redis_client
    return _redis_client


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _redis_client

    supa_url, supa_key = get_client_credentials()
    if supa_url and supa_key:
        print("Supabase client configured")
    else:
        print("FATAL: SUPABASE_URL and SUPABASE_KEY must be set in .env")
        raise RuntimeError("Missing Supabase credentials")

    port = os.getenv("PORT", "8000")
    print(f"Server starting on port {port}")

    if is_postgres_enabled():
        pool = await get_pool()
        async with pool.acquire() as conn:
            await conn.execute("SELECT 1")
        print("Postgres connected")

    redis_url = os.getenv("REDIS_URL")
    if redis_url:
        _redis_client = redis_ai.from_url(redis_url, decode_responses=True)
        try:
            pong = await _redis_client.ping()
            print(f"Redis ping: {pong}")
        except Exception as e:
            print(f"Redis unavailable: {e}")
            _redis_client = None
    else:
        print("Redis not configured")

    yield

    if _redis_client:
        await _redis_client.close()
    await close_pool()


app = FastAPI(
    title="FlyRank API",
    version="0.3.0",
    lifespan=lifespan,
    swagger_ui_parameters={"persistAuthorization": True},
)

app.include_router(tasks.router)
app.include_router(tasks.stats_router)
app.include_router(scrape.router)
app.include_router(ai_router)
app.include_router(auth_router)
app.include_router(protected_router)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request, exc):
    first_error = exc.errors()[0] if exc.errors() else {}
    msg = first_error.get("msg", "Invalid request body")
    return JSONResponse(status_code=400, content={"error": msg})


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request, exc):
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": exc.detail},
    )


@app.get("/")
async def home():
    info = {
        "name": "Task API",
        "version": "1.0",
        "endpoints": ["/tasks", "/scrape"],
    }
    if get_redis():
        info["redis"] = "connected"
    return info


@app.get("/public/info")
async def public_info():
    return {"message": "Welcome stranger! This info is public."}


@app.get("/health")
async def health():
    status = {"status": "ok"}
    if get_redis():
        status["redis"] = "connected"
    return status
