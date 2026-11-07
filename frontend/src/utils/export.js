import { formatValue, metrics } from "./metrics.js";
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

export function makeCsv(
  rows,
  timeZone = TIME_ZONE,
  keys = Object.keys(metrics),
) {
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

export function exportCsv(
  rows,
  name,
  timeZone = TIME_ZONE,
  keys = Object.keys(metrics),
) {
  download(
    new Blob([makeCsv(rows, timeZone, keys)], {
      type: "text/csv;charset=utf-8;",
    }),
    `${safeFilename(name)}.csv`,
  );
}

async function downloadPng(canvas, filename) {
  const blob = await new Promise((resolve) => canvas.toBlob(resolve, "image/png"));
  if (!blob) throw new Error("Não foi possível gerar a imagem.");
  download(blob, `${safeFilename(filename)}.png`);
}

export async function exportParticulateChart({
  readings,
  axis,
  seriesKeys,
  title,
  station,
  date,
  timeZone,
  unit,
}) {
  if (!readings.length) throw new Error("O gráfico ainda não está pronto para exportar.");
  const width = Math.max(900, 100 + readings.length * 24);
  const height = 506;
  const canvas = document.createElement("canvas");
  canvas.width = width * 2;
  canvas.height = height * 2;
  const context = canvas.getContext("2d");
  if (!context) throw new Error("Não foi possível gerar a imagem.");
  context.scale(2, 2);
  context.fillStyle = "#ffffff";
  context.fillRect(0, 0, width, height);

  const from = formatTimestamp(readings[0].time, false, timeZone, true);
  const to = formatTimestamp(readings.at(-1).time, false, timeZone, true);
  context.fillStyle = "#153449";
  context.font = "bold 17px Arial, sans-serif";
  context.fillText(title, 18, 27);
  context.font = "12px Arial, sans-serif";
  context.fillText(station, 18, 48, width - 36);
  context.fillText(`Trecho visível · ${from} — ${to}`, 18, 67);
  context.fillText(`Fuso: ${timeZone} · ${unit}`, 18, 86);

  let legendX = 18;
  for (const key of seriesKeys) {
    context.fillStyle = metrics[key].color;
    context.fillRect(legendX, 101, 11, 8);
    context.fillStyle = "#153449";
    context.fillText(metrics[key].label, legendX + 16, 109);
    legendX += 30 + context.measureText(metrics[key].label).width;
  }

  const left = 72;
  const right = width - 24;
  const bottom = 464;
  const plotHeight = 328;
  const scale = plotHeight / axis.domain[1];
  context.fillStyle = "#536b73";
  context.strokeStyle = "#dce8e5";
  context.setLineDash([3, 4]);
  context.textAlign = "right";
  for (const tick of axis.ticks) {
    const y = bottom - tick * scale;
    context.beginPath();
    context.moveTo(left, y);
    context.lineTo(right, y);
    context.stroke();
    context.fillText(formatValue(tick), left - 8, y + 4);
  }

  const slot = (right - left) / readings.length;
  const barWidth = Math.min(36, slot - 6);
  const tickInterval = Math.max(1, Math.ceil(64 / slot));
  const clock = new Intl.DateTimeFormat("pt-BR", {
    timeZone, hour: "2-digit", minute: "2-digit", second: "2-digit",
  });
  context.textAlign = "center";
  readings.forEach(({ time, complete, bands }, index) => {
    const x = left + (index + 0.5) * slot;
    if (complete) {
      let y = bottom;
      for (const { key, difference } of bands) {
        const bandHeight = difference * scale;
        y -= bandHeight;
        context.fillStyle = metrics[key].color;
        context.fillRect(x - barWidth / 2, y, barWidth, bandHeight);
      }
    }
    if (index % tickInterval === 0) {
      context.fillStyle = "#536b73";
      context.fillText(clock.format(time), x, bottom + 19);
    }
  });

  await downloadPng(canvas, `${station}_${title}_${date.replaceAll("/", "-")}`);
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
    await downloadPng(canvas, filename);
  } finally {
    URL.revokeObjectURL(url);
  }
}
