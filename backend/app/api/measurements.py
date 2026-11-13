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
    LocationFilter,
    MeasurementCreate,
    MeasurementDataResponse,
    MeasurementLocationNameUpdate,
    MeasurementLocationLinkUpdate,
    MeasurementLocationResponse,
    MeasurementLocationSelection,
    MeasurementResponse,
    StationMapPin,
)
from app.services.device_auth_service import (
    authenticate_device,
)
from app.services.measurement_service import (
    create_measurement,
    get_latest_measurements,
    get_measurement_history,
)
from app.services.measurement_location_service import (
    get_measurement_locations,
    link_measurement_locations,
    set_measurement_location_name,
    unlink_measurement_location,
)
from app.api.dependencies import current_user
from app.models.accounts import User
from app.services.station_map_service import station_map

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
    user: User = Depends(current_user),
    start: datetime | None = None,
    end: datetime | None = None,
    location_id: LocationFilter | None = None,
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
        location_id=location_id,
        user=user,
    )


@router.get("/locations", response_model=list[MeasurementLocationResponse])
def measurement_locations(
    device_id: str,
    latest_first: bool = False,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    return get_measurement_locations(db, device_id, user=user, latest_first=latest_first)


@router.put("/locations/{location_id}/name", response_model=MeasurementLocationResponse)
def update_location_name(
    location_id: int,
    device_id: str,
    data: MeasurementLocationNameUpdate,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    return set_measurement_location_name(db, device_id, location_id, data.name, user=user)


@router.put("/locations/{root_id}/links/{child_id}", response_model=MeasurementLocationSelection)
def link_locations(
    root_id: int,
    child_id: int,
    device_id: str,
    data: MeasurementLocationLinkUpdate,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    return link_measurement_locations(db, device_id, root_id, child_id, data.name, user=user)


@router.delete("/locations/{root_id}/links/{child_id}", response_model=MeasurementLocationSelection)
def unlink_location(
    root_id: int,
    child_id: int,
    device_id: str,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    return unlink_measurement_location(db, device_id, root_id, child_id, user=user)


@router.get("/station-map", response_model=list[StationMapPin])
def station_map_data(user: User = Depends(current_user), db: Session = Depends(get_db)):
    return station_map(db, user)


@router.get(
    "/latest",
    response_model=list[MeasurementDataResponse],
)
def latest_measurements(
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    return get_latest_measurements(db, user)
