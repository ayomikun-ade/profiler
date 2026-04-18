from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import init_db
from app.errors import register_error_handlers
from app.routers import profiles as profiles_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    async with httpx.AsyncClient(timeout=settings.upstream_timeout_seconds) as client:
        app.state.http_client = client
        yield


app = FastAPI(title="Profiler API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

register_error_handlers(app)
app.include_router(profiles_router.router)


@app.get("/")
async def root():
    return {"status": "success", "message": "Profiler API is running"}


@app.get("/health")
async def health():
    return {"status": "success"}
