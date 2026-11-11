from math import asin, atan2, cos, hypot, radians, degrees, sin, sqrt


LOCATION_RADIUS_METERS = 100
LOCATION_REFERENCE_SAMPLES = 5
EARTH_RADIUS_METERS = 6_371_008.8


def valid_coordinates(latitude, longitude):
    return (
        latitude is not None and -90 <= latitude <= 90
        and longitude is not None and -180 <= longitude <= 180
    )


def distance_meters(latitude, longitude, location):
    lat, ref_lat = radians(latitude), radians(location.latitude)
    delta_lon = radians(longitude - location.longitude)
    haversine = sin((lat - ref_lat) / 2) ** 2 + cos(lat) * cos(ref_lat) * sin(delta_lon / 2) ** 2
    return 2 * EARTH_RADIUS_METERS * asin(sqrt(min(1, haversine)))


def closest_location(locations, latitude, longitude, radius_meters):
    closest = None
    for location in locations:
        distance = distance_meters(latitude, longitude, location)
        if distance <= radius_meters:
            candidate = (distance, location.id)
            if closest is None or candidate < closest[0]:
                closest = (candidate, location)
    return closest[1] if closest else None


def add_reference_sample(location, latitude, longitude):
    # JSON arrays load as lists. Assign a new list for SQLAlchemy change tracking.
    point = [latitude, longitude]
    if len(location.samples) >= LOCATION_REFERENCE_SAMPLES or point in location.samples:
        return False
    location.samples = [*location.samples, point]
    if len(location.samples) == LOCATION_REFERENCE_SAMPLES:
        # Average unit vectors to handle coordinates on either side of ±180°.
        angles = [(radians(lat), radians(lon)) for lat, lon in location.samples]
        x = sum(cos(lat) * cos(lon) for lat, lon in angles)
        y = sum(cos(lat) * sin(lon) for lat, lon in angles)
        z = sum(sin(lat) for lat, _ in angles)
        location.latitude = degrees(atan2(z, hypot(x, y)))
        location.longitude = degrees(atan2(y, x))
    return True
