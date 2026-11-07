import { particulateBands } from "./metrics.js";

export function latestParticulateDay(rows, timeZone) {
  if (!rows.length) return { date: "", readings: [], max: 0, hasMissing: false };
  const dateFormat = new Intl.DateTimeFormat("pt-BR", { dateStyle: "short", timeZone });
  const date = dateFormat.format(rows.at(-1).time);
  let start = rows.length - 1;
  while (start > 0 && dateFormat.format(rows[start - 1].time) === date) start--;

  let max = 0;
  let hasMissing = false;
  const readings = rows.slice(start).map((row) => {
    const bands = particulateBands(row.values);
    const complete = bands.every(({ difference }) => difference !== null);
    if (complete) max = Math.max(max, bands.at(-1).value);
    else hasMissing = true;
    return { id: row.measurement_id, time: row.time, bands, complete };
  });
  return { date, readings, max, hasMissing };
}
