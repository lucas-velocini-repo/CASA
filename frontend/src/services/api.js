const PAGE_SIZE = 1000;

export async function fetchJson(path, signal) {
  const base = (import.meta.env?.VITE_API_BASE_URL || "/api").replace(
    /\/$/,
    "",
  );
  const response = await fetch(`${base}${path}`, { signal });
  if (!response.ok)
    throw new Error(
      `Não foi possível consultar o servidor (HTTP ${response.status}).`,
    );
  const data = await response.json();
  if (!Array.isArray(data))
    throw new Error("O servidor retornou um formato de dados inesperado.");
  return data;
}

export async function fetchStations(signal) {
  const [devices, latest] = await Promise.all([
    fetchJson("/devices", signal),
    fetchJson("/measurements/latest", signal),
  ]);
  return { devices, latest };
}

// Existing API: latest N rows, ascending response, inclusive end, unique device+timestamp.
// Keep the exact ISO cursor (including microseconds) and overlap/deduplicate the boundary.
// This avoids OFFSET drift and works against the currently deployed backend.
export async function fetchHistory(
  deviceId,
  bounds,
  signal,
  request = fetchJson,
) {
  const all = new Map();
  let cursor = new Date(bounds.end).toISOString();
  while (true) {
    signal?.throwIfAborted();
    const params = new URLSearchParams({
      device_id: deviceId,
      start: new Date(bounds.start).toISOString(),
      end: cursor,
      limit: String(PAGE_SIZE),
    });
    const page = await request(`/measurements/history?${params}`, signal);
    for (const row of page) {
      const time = Date.parse(row.timestamp);
      if (!Number.isFinite(time) || row.measurement_id == null)
        throw new Error("O histórico contém um registro inválido.");
      if (time >= bounds.start && time < bounds.end)
        all.set(row.measurement_id, { ...row, time });
    }
    if (page.length < PAGE_SIZE) break;
    const next = page[0].timestamp;
    if (next === cursor)
      throw new Error(
        "Não foi possível carregar o histórico completo. Tente um período menor.",
      );
    cursor = next;
  }
  return [...all.values()].sort(
    (a, b) => a.time - b.time || a.measurement_id - b.measurement_id,
  );
}
