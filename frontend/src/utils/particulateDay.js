import { particulateBands } from "./metrics.js";

export function particulateReadingMax(readings) {
  return readings.reduce(
    (max, { complete, bands }) => complete ? Math.max(max, bands.at(-1).value) : max,
    0,
  );
}

export function latestParticulateDay(rows, timeZone, keys) {
  if (!rows.length) return { date: "", readings: [], max: 0, hasMissing: false };
  const dateFormat = new Intl.DateTimeFormat("pt-BR", { dateStyle: "short", timeZone });
  const date = dateFormat.format(rows.at(-1).time);
  let start = rows.length - 1;
  while (start > 0 && dateFormat.format(rows[start - 1].time) === date) start--;

  const readings = rows.slice(start).map((row) => {
    const bands = particulateBands(row.values, keys);
    const complete = bands.every(({ difference }) => difference !== null);
    return { id: row.measurement_id, time: row.time, bands, complete };
  });
  return {
    date,
    readings,
    max: particulateReadingMax(readings),
    hasMissing: readings.some(({ complete }) => !complete),
  };
}
