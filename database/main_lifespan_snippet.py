"""
main.py  (snippet — shows how to wire the database into your existing lifespan)

Drop the lifespan block below into your existing main.py.
Everything else in your file stays the same.
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI

from database import init_db, cleanup_old_data


# ── Lifespan: runs once on startup and once on shutdown ──────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── STARTUP ──────────────────────────────────────────────────
    # 1. Create all tables / indexes / triggers (safe if they exist)
    await init_db()

    # 2. Prune stale predictions, match_context, activation_attempts
    await cleanup_old_data()

    yield  # app is now running and handling requests

    # ── SHUTDOWN ─────────────────────────────────────────────────
    # Add any teardown here (close connection pools, flush queues, etc.)


# ── FastAPI app ──────────────────────────────────────────────────
app = FastAPI(
    title="Football Prediction API",
    lifespan=lifespan,
)


# ── Your existing routes go here (unchanged) ─────────────────────
# @app.post("/predict")
# @app.post("/fixtures")
# etc.
