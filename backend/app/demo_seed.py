"""Create clearly marked synthetic stations in the isolated development DB only."""

import json
from datetime import timedelta
from urllib.request import Request, urlopen

from sqlalchemy import select
from sqlalchemy.engine import make_url

from app.core.config import DATABASE_URL
from app.core.security import ENV, utcnow
from app.db.database import SessionLocal
from app.models.accounts import User
from app.services.device_service import register_device


def seed():
    if ENV != "development" or make_url(DATABASE_URL).database != "casa_teste":
        raise RuntimeError(
            "Dados fictícios permitidos somente em development e no banco casa_teste."
        )
    with SessionLocal() as db:
        admin = db.scalar(
            select(User)
            .where(User.role == "admin", User.status == "active")
            .order_by(User.id)
        )
        if admin is None:
            raise RuntimeError(
                "Crie primeiro o administrador de testes com app.cli create-admin."
            )
        for index, suffix in enumerate(("A", "B")):
            device, token = register_device(
                db, f"DEMO-CASA-{suffix}", f"DEMO Estação {suffix}", actor=admin
            )
            if token is None:
                print(
                    f"{device.device_id}: demonstração já existente; dados preservados."
                )
                continue

            def send(path, method, body):
                request = Request(
                    f"http://127.0.0.1:8000/{path}",
                    method=method,
                    data=json.dumps(body).encode(),
                    headers={
                        "Content-Type": "application/json",
                        "Authorization": f"Bearer {token}",
                    },
                )
                with urlopen(request, timeout=15) as response:
                    if response.status not in (200, 201):
                        raise RuntimeError("A API recusou os dados de demonstração.")

            acquired_at = utcnow().replace(microsecond=0)
            for position in range(24):
                send(
                    "measurements",
                    "POST",
                    {
                        "device_id": device.device_id,
                        "timestamp": int(
                            (
                                acquired_at - timedelta(minutes=5 * (23 - position))
                            ).timestamp()
                        ),
                        "temperature": 23 + index + (position % 5) * 0.2,
                        "humidity": 50 + index * 5 + position % 8,
                        "pressure": 1013,
                        "light": 100 + position,
                        "pm": {"1.0": 2, "2.5": 3, "4.0": 4, "10.0": 5},
                        "nc": {},
                    },
                )
            send(
                "devices/location",
                "PATCH",
                {
                    "latitude": 0,
                    "longitude": index,
                    "acquired_at": acquired_at.isoformat(),
                },
            )
            print(
                f"{device.device_id}: DEMO Estação {suffix}, 24 medições fictícias e coordenadas de demonstração."
            )


if __name__ == "__main__":
    seed()
