from fastapi import FastAPI
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.db.database import engine
from app.models.device import Device

from app.db.database import engine

from app.api.devices import router as devices_router
from app.api.measurements import router as measurements_router

app = FastAPI(
    title="CASA API",
    version="0.1.0",
)

app.include_router(devices_router)
app.include_router(measurements_router)

@app.get("/")
def root():
    return {
        "message": "CASA API funcionando"
    }


@app.get("/health")
def health():
    try:
        with engine.connect() as connection:
            connection.execute(
                text("SELECT 1")
            )

        return {
            "status": "ok",
            "database": "connected",
        }

    except SQLAlchemyError:
        return {
            "status": "error",
            "database": "disconnected",
        }