from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse

from app.api.v1 import ai_reports, car, simulation
from app.core.config import get_settings
from app.db.models import Base
from app.db.repository import seed
from app.db.session import SessionLocal, engine
from app.simulation.assumptions import VehicleAssumptions
from app.simulation.vehicle import MODEL_VERSION, baseline

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("apexvision")
settings = get_settings()


@asynccontextmanager
async def lifespan(_: FastAPI):
    # Alembic owns the schema in production; create_all is a no-op when tables exist
    # and gives zero-setup local runs on SQLite.
    try:
        Base.metadata.create_all(engine)
        with SessionLocal() as db:
            seed(db)
    except Exception as e:  # API stays usable for stateless simulation even if DB is down
        log.error("Database initialisation failed: %s", e)
    baseline(VehicleAssumptions())  # warm the baseline cache
    yield


app = FastAPI(
    title=settings.app_name,
    version="1.0.0",
    description="Engineering API for the ApexVision 3D F1-style car: components, damage simulation, "
                "aerodynamics, lap-time performance, AI assistant and reports. All values are MODEL-ESTIMATED.",
    lifespan=lifespan,
)
app.add_middleware(GZipMiddleware, minimum_size=1024)
app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origin_list, allow_methods=["GET", "POST"],
                   allow_headers=["*"], allow_credentials=False)


@app.exception_handler(RequestValidationError)
async def validation_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
    errors = [{"field": ".".join(str(p) for p in e["loc"] if p != "body"), "message": e["msg"]} for e in exc.errors()]
    return JSONResponse(status_code=422, content={"error": "validation_error", "details": errors})


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "model_version": MODEL_VERSION}


for r in (car.router, simulation.router, ai_reports.router):
    app.include_router(r, prefix="/api/v1")
