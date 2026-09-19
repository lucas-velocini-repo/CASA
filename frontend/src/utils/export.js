import { metrics } from "./metrics.js";
import { formatTimestamp, TIME_ZONE } from "./dates.js";

export function download(blob, filename) {
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 10_000);
}

export function safeFilename(value) {
  return String(value)
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/[^a-zA-Z0-9_-]/g, "_")
    .slice(0, 80);
}

function csvCell(value) {
  let text = value == null ? "" : String(value);
  // Prevent spreadsheet formula execution from names/IDs. Numeric measurements stay numeric.
  if (typeof value === "string" && /^[=+\-@\t\r\n]/.test(text))
    text = `'${text}`;
  return `"${text.replace(/"/g, '""')}"`;
}

export function makeCsv(rows, timeZone = TIME_ZONE) {
  const keys = Object.keys(metrics);
  const headers = [
    "measurement_id",
    "device_id",
    "device_name",
    "timestamp_iso",
    `data_hora (${timeZone})`,
    "received_at",
    "latitude",
    "longitude",
    ...keys.map((key) => `${key} (${metrics[key].unit})`),
  ];
  const lines = rows.map((row) => [
    row.measurement_id,
    row.device_id,
    row.device_name,
    row.timestamp,
    formatTimestamp(row.timestamp, false, timeZone),
    row.received_at,
    row.latitude,
    row.longitude,
    ...keys.map((key) => row.values?.[key]),
  ]);
  return (
    "\uFEFF" +
    [headers, ...lines].map((line) => line.map(csvCell).join(";")).join("\r\n")
  );
}

export function exportCsv(rows, name, timeZone = TIME_ZONE) {
  download(
    new Blob([makeCsv(rows, timeZone)], { type: "text/csv;charset=utf-8;" }),
    `${safeFilename(name)}.csv`,
  );
}

export async function exportChart(
  container,
  {
    title,
    station,
    period,
    filename,
    reduced,
    timeZone = TIME_ZONE,
    series = [],
  },
) {
  const source = container.querySelector("svg.recharts-surface");
  if (!source)
    throw new Error("O gráfico ainda não está pronto para exportar.");
  const width = Math.max(900, source.getBoundingClientRect().width);
  const height =
    (source.getBoundingClientRect().height * width) /
    source.getBoundingClientRect().width;
  const ns = "http://www.w3.org/2000/svg";
  const root = document.createElementNS(ns, "svg");
  root.setAttribute("xmlns", ns);
  root.setAttribute("width", width);
  root.setAttribute("height", height + 156);
  const background = document.createElementNS(ns, "rect");
  background.setAttribute("width", "100%");
  background.setAttribute("height", "100%");
  background.setAttribute("fill", "#ffffff");
  root.appendChild(background);
  const lines = [
    title,
    station,
    period,
    series.join(" · "),
    `Fuso: ${timeZone}${reduced ? " • Visualização reduzida; CSV completo" : ""}`,
  ];
  lines.forEach((line, i) => {
    const text = document.createElementNS(ns, "text");
    text.setAttribute("x", "14");
    text.setAttribute("y", 24 + i * 22);
    text.setAttribute("font-family", "Arial, sans-serif");
    text.setAttribute("font-size", i === 0 ? "16" : "11");
    text.setAttribute("fill", "#153449");
    text.textContent = line;
    root.appendChild(text);
  });
  const clone = source.cloneNode(true);
  const originals = [source, ...source.querySelectorAll("*")];
  const copies = [clone, ...clone.querySelectorAll("*")];
  originals.forEach((node, i) => {
    const style = getComputedStyle(node);
    for (const prop of [
      "font-family",
      "font-size",
      "font-weight",
      "fill",
      "stroke",
      "stroke-width",
      "opacity",
    ]) {
      copies[i].style.setProperty(prop, style.getPropertyValue(prop));
    }
  });
  clone.setAttribute("x", "0");
  clone.setAttribute("y", "140");
  clone.setAttribute("width", width);
  clone.setAttribute("height", height);
  root.appendChild(clone);
  const url = URL.createObjectURL(
    new Blob([new XMLSerializer().serializeToString(root)], {
      type: "image/svg+xml;charset=utf-8",
    }),
  );
  try {
    const img = new Image();
    img.src = url;
    await img.decode();
    const canvas = document.createElement("canvas");
    canvas.width = width * 2;
    canvas.height = (height + 156) * 2;
    const context = canvas.getContext("2d");
    context.scale(2, 2);
    context.drawImage(img, 0, 0);
    const blob = await new Promise((resolve) =>
      canvas.toBlob(resolve, "image/png"),
    );
    if (!blob) throw new Error("Não foi possível gerar a imagem.");
    download(blob, `${safeFilename(filename)}.png`);
  } finally {
    URL.revokeObjectURL(url);
  }
}
