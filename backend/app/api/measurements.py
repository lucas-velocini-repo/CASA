from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.database import get_db

from app.schemas.measurement import (
    MeasurementCreate,
    MeasurementResponse,
    MeasurementDataResponse,
)

from app.services.measurement_service import (
    create_measurement,
    get_measurement_history,
    get_latest_measurements,
)

from datetime import datetime


router = APIRouter(
    prefix="/measurements",
    tags=["measurements"],
)


@router.post(
    "",
    response_model=MeasurementResponse,
    status_code=201,
)
def receive_measurement(
    data: MeasurementCreate,
    db: Session = Depends(get_db),
):
    measurement = create_measurement(
        db,
        data,
    )

    return MeasurementResponse(
        measurement_id=measurement.id,
        device_id=data.device_id,
        status="stored",
    )

@router.get(
    "/history",
    response_model=list[MeasurementDataResponse],
)
def measurement_history(
    device_id: str,
    start: datetime | None = None,
    end: datetime | None = None,
    limit: int = Query(
        default=1000,
        ge=1,
        le=10000,
    ),
    db: Session = Depends(get_db),
):
    return get_measurement_history(
        db=db,
        device_id=device_id,
        start=start,
        end=end,
        limit=limit,
    )

@router.get(
    "/latest",
    response_model=list[MeasurementDataResponse],
)
def latest_measurements(
    db: Session = Depends(get_db),
):
    return get_latest_measurements(db)