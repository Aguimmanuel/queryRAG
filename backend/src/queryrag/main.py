import os

import psycopg
from fastapi import FastAPI
from fastapi.responses import JSONResponse

app = FastAPI(
    title="QueryRAG API",
    version="0.1.0",
)


@app.get("/health")
def health() -> dict[str, str]:
    return {
        "status": "ok",
        "service": "queryrag",
    }


@app.get("/ready", response_model=None)
def ready() -> dict[str, str] | JSONResponse:
    database_url = os.getenv("DATABASE_URL")

    if not database_url:
        return JSONResponse(
            status_code=503,
            content={
                "status": "not_ready",
                "database": "missing_configuration",
            },
        )

    try:
        with psycopg.connect(database_url, connect_timeout=2) as connection:
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
