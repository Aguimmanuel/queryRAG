import psycopg
from fastapi import FastAPI
from fastapi.responses import JSONResponse

from queryrag.api.documents import router as documents_router
from queryrag.config import get_settings
from queryrag.observability import RequestIDMiddleware, configure_logging

settings = get_settings()
configure_logging(settings.log_level)

app = FastAPI(
    title="QueryRAG API",
    version="0.1.0",
)

app.add_middleware(RequestIDMiddleware)
app.include_router(documents_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {
        "status": "ok",
        "service": "queryrag",
    }


@app.get("/ready", response_model=None)
def ready() -> dict[str, str] | JSONResponse:
    settings = get_settings()

    if not settings.database_url:
        return JSONResponse(
            status_code=503,
            content={
                "status": "not_ready",
                "database": "missing_configuration",
            },
        )

    try:
        with psycopg.connect(
            settings.database_url,
            connect_timeout=2,
        ) as connection:
            connection.execute("SELECT 1")
    except psycopg.Error:
        return JSONResponse(
            status_code=503,
            content={
                "status": "not_ready",
                "database": "unavailable",
            },
        )

    return {
        "status": "ready",
        "database": "ok",
    }
