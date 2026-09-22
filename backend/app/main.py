from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import CORS_ORIGINS
from app.database.connection import get_conn
from app.routers import analytics, anomalies, forecast, risk, uploads

app = FastAPI(title="Operon API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(uploads.router)
app.include_router(analytics.router)
app.include_router(forecast.router)
app.include_router(risk.router)
app.include_router(anomalies.router)


@app.on_event("startup")
def _startup() -> None:
    get_conn()  # ensure DuckDB schema is initialized


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}
