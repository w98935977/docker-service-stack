import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone

import psycopg
from fastapi import FastAPI, HTTPException

APP_NAME = os.getenv("APP_NAME", "docker-service-stack")


def db_connection_parameters() -> dict[str, object]:
    required = {
        "host": os.getenv("PGHOST"),
        "dbname": os.getenv("PGDATABASE"),
        "user": os.getenv("PGUSER"),
        "password": os.getenv("PGPASSWORD"),
    }
    missing = [name for name, value in required.items() if not value]
    if missing:
        raise RuntimeError(f"Missing PostgreSQL settings: {', '.join(missing)}")

    return {
        **required,
        "port": int(os.getenv("PGPORT", "5432")),
        "connect_timeout": 3,
    }


def db_query(sql: str, params: tuple = ()):
    with psycopg.connect(**db_connection_parameters()) as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            if cur.description:
                return cur.fetchall()
            conn.commit()
            return None


@asynccontextmanager
async def lifespan(_: FastAPI):
    db_query(
        """
        CREATE TABLE IF NOT EXISTS service_events (
            id SERIAL PRIMARY KEY,
            event_name TEXT NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    yield


app = FastAPI(title=APP_NAME, lifespan=lifespan)


@app.get("/")
def read_root():
    return {
        "service": APP_NAME,
        "message": "Nginx -> FastAPI/Uvicorn -> PostgreSQL is running",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@app.get("/health")
def health():
    try:
        result = db_query("SELECT 1")
        if result != [(1,)]:
            raise RuntimeError("unexpected database response")
        return {"status": "healthy", "database": "reachable"}
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"unhealthy: {exc}") from exc


@app.post("/events/{event_name}")
def create_event(event_name: str):
    db_query("INSERT INTO service_events (event_name) VALUES (%s)", (event_name,))
    return {"created": event_name}


@app.get("/events")
def list_events():
    rows = db_query("SELECT id, event_name, created_at FROM service_events ORDER BY id DESC LIMIT 20")
    return [
        {"id": row[0], "event_name": row[1], "created_at": row[2].isoformat()}
        for row in rows
    ]
