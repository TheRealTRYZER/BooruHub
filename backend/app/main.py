"""BooruHub — FastAPI main application."""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from sqlalchemy import text
from app.core.config import get_settings
from app.db.database import engine
from app.db.models import Base

from app.api.auth import router as auth_router
from app.api.posts import router as posts_router
from app.api.favorites import router as favorites_router
from app.api.bookmarks import router as bookmarks_router
from app.api.blacklist_api import router as blacklist_router
from app.api.mappings import router as mappings_router
from app.api.users import router as users_router

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown events."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        
        # Apply rudimentary schema updates safely
        try:
            await conn.execute(text("ALTER TABLE favorites ADD COLUMN is_dislike BOOLEAN DEFAULT FALSE;"))
        except Exception:
            pass  # Ignore if it already exists or isn't supported
            
    logger.info("Database tables ready")
    yield
    await engine.dispose()
    logger.info("Database connections closed")


settings = get_settings()

app = FastAPI(
    title="BooruHub API",
    description="Imageboard aggregator API",
    version="1.1.0",
    lifespan=lifespan,
    docs_url="/api/docs" if settings.CORS_ORIGINS == "*" else None,
    redoc_url=None,
)

# CORS — configurable per environment
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)

# Routers
app.include_router(auth_router)
app.include_router(posts_router)
app.include_router(favorites_router)
app.include_router(bookmarks_router)
app.include_router(blacklist_router)
app.include_router(mappings_router)
app.include_router(users_router)


@app.get("/api/health")
async def health():
    return {"status": "ok", "version": app.version}
