from datetime import datetime

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    status,
)
from fastapi.security import (
    HTTPAuthorizationCredentials,
    HTTPBearer,
)
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.schemas.measurement import (
    MeasurementCreate,
    MeasurementDataResponse,
    MeasurementResponse,
)
from app.services.device_auth_service import (
    authenticate_device,
)
from app.services.measurement_service import (
    create_measurement,
    get_latest_measurements,
    get_measurement_history,
)

router = APIRouter(
    prefix="/measurements",
    tags=["measurements"],
)

bearer_scheme = HTTPBearer(auto_error=False)


@router.post(
    "",
    response_model=MeasurementResponse,
    status_code=201,
)
def receive_measurement(
    data: MeasurementCreate,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
):
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    device = authenticate_device(
        db=db,
        token=credentials.credentials,
    )

    if device is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not device.active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Device is inactive",
        )

    if device.device_id != data.device_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=("Token does not belong to this device"),
        )

    measurement = create_measurement(
        db,
        data,
    )

    return MeasurementResponse(
        measurement_id=measurement.id,
        device_id=device.device_id,
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
