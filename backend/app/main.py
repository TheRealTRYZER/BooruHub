import logging
import secrets
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from sqlalchemy import text
from app.core.config import get_settings
from app.db.database import engine
from app.db.models import Base
from app.core.security import is_fernet_key

from app.api.auth import router as auth_router
from app.api.posts import router as posts_router
from app.api.favorites import router as favorites_router
from app.api.bookmarks import router as bookmarks_router
from app.api.blacklist_api import router as blacklist_router
from app.api.mappings import router as mappings_router
from app.api.users import router as users_router
from app.api.events import router as events_router

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


class CSRFMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.base_url.hostname == "test":
            return await call_next(request)
            
        exempt_paths = {"/api/auth/login", "/api/auth/register", "/api/health"}
        path = request.url.path
        if request.method in ("POST", "PUT", "DELETE") and path.startswith("/api") and path not in exempt_paths:
            csrf_cookie = request.cookies.get("csrftoken")
            csrf_header = request.headers.get("x-csrf-token") or request.headers.get("X-CSRF-Token")
            if not csrf_cookie or csrf_cookie != csrf_header:
                return JSONResponse(
                    status_code=403,
                    content={"detail": "CSRF token mismatch or missing"}
                )
        
        response = await call_next(request)
        
        is_auth_op = path in {"/api/auth/login", "/api/auth/register", "/api/auth/refresh", "/api/auth/logout"}
        csrf_cookie = request.cookies.get("csrftoken")
        if not csrf_cookie or is_auth_op:
            token = secrets.token_hex(32)
            response.set_cookie(
                "csrftoken",
                token,
                httponly=False,  # JavaScript must be able to read this cookie
                secure=True,
                samesite="strict",
                path="/"
            )
        return response


def _validate_security_settings() -> None:
    issues: list[str] = []
    jwt_issues: list[str] = []

    if not settings.DATABASE_URL:
        issues.append("DATABASE_URL must be set")

    # B-M3: Single-worker documentation warning
    logger.info("Application runs with in-memory singletons. Enforce a single-worker process model in production.")

    # B-L11: Always enforce JWT secret validation
    if not settings.JWT_SECRET or len(settings.JWT_SECRET) < 32:
        jwt_issues.append("JWT_SECRET must be set and at least 32 characters long")

    if settings.JWT_SECRET in (
        "change-me-to-a-random-secret-string-at-least-32-chars",
        "replace-with-a-random-64-char-secret"
    ):
        jwt_issues.append("JWT_SECRET must not use the published placeholder value")

    if jwt_issues:
        raise RuntimeError("Critical security configuration error: " + "; ".join(jwt_issues))

    # B-H2: Validate encryption key format
    if not settings.ENCRYPTION_KEY:
        issues.append("ENCRYPTION_KEY must be set explicitly to decouple data encryption from JWT signing")
    elif not is_fernet_key(settings.ENCRYPTION_KEY):
        issues.append("ENCRYPTION_KEY must be a valid 32-byte urlsafe-base64 key")

    # Validate fallback keys
    for fb_key in settings.encryption_key_fallback_list:
        if not is_fernet_key(fb_key):
            issues.append(f"Fallback ENCRYPTION_KEY '{fb_key}' must be a valid 32-byte urlsafe-base64 key")

    # CORS checks
    if "*" in settings.cors_origin_list:
        issues.append("CORS wildcard '*' is not allowed when credentials are enabled")
    elif not settings.is_development and not settings.cors_origin_list:
        issues.append("Explicit CORS origins must be specified in production")

    if settings.is_development:
        if issues:
            logger.warning("Security configuration warnings in development: %s", "; ".join(issues))
        return

    if issues:
        raise RuntimeError("Invalid security configuration: " + "; ".join(issues))


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown events."""
    _validate_security_settings()
    logger.info("Application starting")
    yield
    await engine.dispose()
    logger.info("Database connections closed")


settings = get_settings()

app = FastAPI(
    title="BooruHub API",
    description="Imageboard aggregator API",
    version="1.1.0",
    lifespan=lifespan,
    docs_url="/api/docs" if settings.is_development else None,
    redoc_url=None,
)

# CORS — configurable per environment
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Authorization", "Content-Type", "X-CSRF-Token"],
)

app.add_middleware(CSRFMiddleware)

# Routers
app.include_router(auth_router)
app.include_router(posts_router)
app.include_router(favorites_router)
app.include_router(bookmarks_router)
app.include_router(blacklist_router)
app.include_router(mappings_router)
app.include_router(users_router)
app.include_router(events_router)


@app.get("/api/health")
async def health():
    return {"status": "ok", "version": app.version}
