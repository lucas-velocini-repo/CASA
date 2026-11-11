export function locationLabel(location) {
  return location.name || `${location.latitude.toFixed(5)}, ${location.longitude.toFixed(5)}`;
}
