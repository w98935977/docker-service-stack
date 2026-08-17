import os
from datetime import datetime, timezone

import psycopg
from fastapi import FastAPI, HTTPException

APP_NAME = os.getenv("APP_NAME", "docker-service-stack")
DATABASE_URL = os.getenv("DATABASE_URL")

app = FastAPI(title=APP_NAME)


def db_query(sql: str, params: tuple = ()):
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL is not configured")
    with psycopg.connect(DATABASE_URL, connect_timeout=3) as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            if cur.description:
                return cur.fetchall()
            conn.commit()
            return None


@app.on_event("startup")
def startup() -> None:
    db_query(
        """
        CREATE TABLE IF NOT EXISTS service_events (
            id SERIAL PRIMARY KEY,
            event_name TEXT NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )


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
