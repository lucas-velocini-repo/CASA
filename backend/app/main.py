from fastapi import FastAPI
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.api.devices import router as devices_router
from app.api.measurements import router as measurements_router
from app.db.database import engine
from app.api.auth import router as auth_router
from app.api.admin import router as admin_router
from app.api.station_configuration import router as configuration_router

app = FastAPI(title="CASA API", version="0.1.0", root_path="/api")

app.include_router(devices_router)
app.include_router(measurements_router)
app.include_router(auth_router)
app.include_router(admin_router)
app.include_router(configuration_router)


@app.middleware("http")
async def private_responses(request, call_next):
    response = await call_next(request)
    response.headers["Cache-Control"] = "no-store"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response


@app.get("/")
def root():
    return {"message": "CASA API funcionando"}


@app.get("/health")
def health():
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))

        return {
            "status": "ok",
            "database": "connected",
        }

    except SQLAlchemyError:
        return {
            "status": "error",
            "database": "disconnected",
        }
