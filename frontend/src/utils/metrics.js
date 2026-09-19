export const metrics = {
  temperature: {
    label: "Temperatura",
    unit: "°C",
    color: "#0a8585",
    precision: 2,
  },
  humidity: { label: "Umidade", unit: "%", color: "#5268bc", precision: 2 },
  pressure: { label: "Pressão", unit: "hPa", color: "#a15d28", precision: 2 },
  light: { label: "Luminosidade", unit: "lx", color: "#84702b", precision: 1 },
  pm1: { label: "PM 1,0", unit: "µg/m³", color: "#0a8585", precision: 3 },
  pm25: { label: "PM 2,5", unit: "µg/m³", color: "#d36a33", precision: 3 },
  pm4: { label: "PM 4,0", unit: "µg/m³", color: "#7561b1", precision: 3 },
  pm10: { label: "PM 10,0", unit: "µg/m³", color: "#b63d67", precision: 3 },
  nc05: { label: "NC 0,5", unit: "#/cm³", color: "#0a8585", precision: 3 },
  nc10: { label: "NC 1,0", unit: "#/cm³", color: "#d36a33", precision: 3 },
  nc25: { label: "NC 2,5", unit: "#/cm³", color: "#7561b1", precision: 3 },
  nc40: { label: "NC 4,0", unit: "#/cm³", color: "#b63d67", precision: 3 },
  nc100: { label: "NC 10,0", unit: "#/cm³", color: "#406fab", precision: 3 },
  typical_particle_size: {
    label: "Tamanho típico",
    unit: "µm",
    color: "#0a8585",
    precision: 3,
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

export function formatValue(value, precision = 2) {
  return Number.isFinite(value)
    ? value.toLocaleString("pt-BR", { maximumFractionDigits: precision })
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
  return [min - padding, max + padding];
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
