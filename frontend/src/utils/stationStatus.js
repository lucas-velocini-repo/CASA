export const ACTIVITY_WINDOW_MS = 6 * 60 * 1000;

export function activityWindowMs(intervalSeconds) {
  return Number.isFinite(intervalSeconds) && intervalSeconds >= 30 && intervalSeconds <= 86400
    ? Math.max(ACTIVITY_WINDOW_MS, intervalSeconds * 1200)
    : ACTIVITY_WINDOW_MS;
}

export function isStationActive(lastSeen, now = Date.now(), intervalSeconds = null) {
  if (!lastSeen) return false;
  const age = now - Date.parse(lastSeen);
  return Number.isFinite(age) && age >= 0 && age <= activityWindowMs(intervalSeconds);
}
