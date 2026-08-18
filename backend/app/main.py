import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.core.logging_config import RequestLoggingMiddleware, configure_logging
from app.database import Base, engine
from app.routers import auth, invites, leads, newsletter, resources

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging()
    Base.metadata.create_all(bind=engine)
    logging.getLogger("app").info(
        "startup", extra={"environment": settings.environment, "app": settings.app_name}
    )
    yield
    logging.getLogger("app").info("shutdown")


app = FastAPI(title=settings.app_name, version="0.1.0", lifespan=lifespan)

app.add_middleware(RequestLoggingMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Request-ID"],
)

app.include_router(auth.router)
app.include_router(resources.router)
app.include_router(leads.router)
app.include_router(invites.router)
app.include_router(newsletter.router)


@app.get("/api/health", tags=["system"])
def health() -> dict[str, str]:
    return {"status": "ok", "environment": settings.environment}
