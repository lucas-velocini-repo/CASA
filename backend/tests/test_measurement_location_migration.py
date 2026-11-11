from datetime import datetime, timedelta, timezone
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import sys

import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations


def test_location_migration_backfills_in_collection_order_across_pages(monkeypatch):
    path = (
        Path(__file__).resolve().parents[1] / "alembic" / "versions"
        / "e821locations01_measurement_locations.py"
    )
    spec = spec_from_file_location("location_migration", path)
    migration = module_from_spec(spec)
    monkeypatch.setitem(sys.modules, spec.name, migration)
    spec.loader.exec_module(migration)

    metadata = sa.MetaData()
    devices = sa.Table("devices", metadata, sa.Column("id", sa.Integer, primary_key=True))
    measurements = sa.Table(
        "measurements", metadata,
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("device_id", sa.ForeignKey(devices.c.id), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("latitude", sa.Float),
        sa.Column("longitude", sa.Float),
        sa.UniqueConstraint("device_id", "timestamp"),
    )
    engine = sa.create_engine("sqlite://")
    metadata.create_all(engine)
    first = datetime(2026, 9, 1, tzinfo=timezone.utc)
    longitudes = [0] * 1000 + [0.001, 0.00001, None]
    with engine.begin() as db:
        db.execute(devices.insert().values(id=1))
        db.execute(measurements.insert(), [
            {
                "device_id": 1,
                "timestamp": first + timedelta(seconds=i),
                "latitude": 0 if longitude is not None else None,
                "longitude": longitude,
            }
            for i, longitude in reversed(list(enumerate(longitudes)))
        ])
        with Operations.context(MigrationContext.configure(db)):
            migration.upgrade()
            location_ids = db.scalars(sa.text(
                "SELECT location_id FROM measurements ORDER BY timestamp"
            )).all()
            assert len(location_ids) == len(longitudes)
            assert location_ids[0] is not None
            assert location_ids[:1000] == [location_ids[0]] * 1000
            assert location_ids[1000] != location_ids[0]
            assert location_ids[1001:] == [location_ids[0], None]

            migration.downgrade()
            assert db.scalars(sa.text(
                "SELECT longitude FROM measurements ORDER BY timestamp"
            )).all() == longitudes
