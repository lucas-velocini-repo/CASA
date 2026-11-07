export const metrics = {
  temperature: {
    label: "Temperatura",
    unit: "°C",
    color: "#0a8585",
  },
  humidity: { label: "Umidade", unit: "%", color: "#5268bc" },
  pressure: { label: "Pressão", unit: "hPa", color: "#a15d28" },
  light: { label: "Luminosidade", unit: "lx", color: "#84702b" },
  pm1: { label: "PM 1,0", unit: "µg/m³", color: "#0a8585" },
  pm25: { label: "PM 2,5", unit: "µg/m³", color: "#d36a33" },
  pm4: { label: "PM 4,0", unit: "µg/m³", color: "#7561b1" },
  pm10: { label: "PM 10,0", unit: "µg/m³", color: "#b63d67" },
  nc05: { label: "NC 0,5", unit: "#/cm³", color: "#0a8585" },
  nc10: { label: "NC 1,0", unit: "#/cm³", color: "#d36a33" },
  nc25: { label: "NC 2,5", unit: "#/cm³", color: "#7561b1" },
  nc40: { label: "NC 4,0", unit: "#/cm³", color: "#b63d67" },
  nc100: { label: "NC 10,0", unit: "#/cm³", color: "#406fab" },
  typical_particle_size: {
    label: "Tamanho típico",
    unit: "µm",
    color: "#0a8585",
  },
};

export const tabs = [
  { id: "overview", label: "Visão geral" },
  { id: "temperature", label: "Temperatura", keys: ["temperature"] },
  { id: "pressure", label: "Pressão", keys: ["pressure"] },
  { id: "humidity", label: "Umidade", keys: ["humidity"] },
  { id: "light", label: "Luminosidade", keys: ["light"] },
  { id: "pm", label: "Particulados PM", keys: ["pm1", "pm25", "pm4", "pm10"] },
  {
    id: "nc",
    label: "Particulados NC",
    keys: ["nc05", "nc10", "nc25", "nc40", "nc100"],
  },
  { id: "history", label: "Dados históricos" },
];

export function formatValue(value) {
  return Number.isFinite(value)
    ? value.toLocaleString("pt-BR", { maximumFractionDigits: 1 })
    : "—";
}

export function automaticDomain(rows, keys) {
  let min = Infinity;
  let max = -Infinity;
  for (const row of rows)
    for (const key of keys) {
      const value = row.values?.[key];
      if (Number.isFinite(value)) {
        min = Math.min(min, value);
        max = Math.max(max, value);
      }
    }
  if (!Number.isFinite(min)) return [0, 1];
  const padding = Math.max(
    (max - min) * 0.12,
    max === min ? Math.abs(min) * 0.005 : 0,
    0.01,
  );
  if (keys.includes("temperature")) return [min - padding, max + padding];
  return [Math.max(0, min - padding), Math.max(0, max + padding)];
}

// Keep bucket extrema of each visible series. Only chart rendering is reduced.
export function chartRows(rows, keys, budget = 1800) {
  if (rows.length <= budget) return rows;
  const bucketCount = Math.max(1, Math.floor(budget / (2 + keys.length * 2)));
  const size = Math.ceil(rows.length / bucketCount);
  const indexes = new Set([0, rows.length - 1]);
  for (let start = 0; start < rows.length; start += size) {
    const end = Math.min(rows.length, start + size);
    indexes.add(start);
    indexes.add(end - 1);
    for (const key of keys) {
      let minIndex = -1,
        maxIndex = -1,
        missing = -1;
      for (let i = start; i < end; i++) {
        const value = rows[i].values?.[key];
        if (!Number.isFinite(value)) {
          missing = i;
          continue;
        }
        if (minIndex < 0 || value < rows[minIndex].values[key]) minIndex = i;
        if (maxIndex < 0 || value > rows[maxIndex].values[key]) maxIndex = i;
      }
      if (minIndex >= 0) indexes.add(minIndex);
      if (maxIndex >= 0) indexes.add(maxIndex);
      if (missing >= 0) indexes.add(missing);
    }
  }
  return [...indexes].sort((a, b) => a - b).map((i) => rows[i]);
}

export const PM_KEYS = ["pm1", "pm25", "pm4", "pm10"];

export function particulateBands(values) {
  return PM_KEYS.map((key, index) => {
    const value = values?.[key];
    const previous = index === 0 ? 0 : values?.[PM_KEYS[index - 1]];
    const difference =
      Number.isFinite(value) && Number.isFinite(previous) && previous >= 0 && value >= previous
        ? value - previous
        : null;
    return { key, value, difference };
  });
}

export function formatParticulateDifference(value) {
  const formatted = formatValue(value);
  return value > 0 && formatted === "0" ? "< 0,1" : formatted;
}
export const OVERVIEW_KEYS = [
  "temperature",
  "humidity",
  "pressure",
  "light",
  ...PM_KEYS,
];

export function exportKeys(tabId) {
  if (tabId === "history") return Object.keys(metrics);
  if (tabId === "overview") return OVERVIEW_KEYS;
  return tabs.find((tab) => tab.id === tabId)?.keys || [];
}
