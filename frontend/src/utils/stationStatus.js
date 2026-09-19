export const ACTIVITY_WINDOW_MS = 6 * 60 * 1000;

export function isStationActive(lastSeen, now = Date.now()) {
  if (!lastSeen) return false;
  const age = now - Date.parse(lastSeen);
  return Number.isFinite(age) && age >= 0 && age <= ACTIVITY_WINDOW_MS;
}
