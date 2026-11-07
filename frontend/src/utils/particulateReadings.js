import { particulateBands } from "./metrics.js";

export function particulateReadingMax(readings) {
  return readings.reduce(
    (max, { complete, bands }) => complete ? Math.max(max, bands.at(-1).value) : max,
    0,
  );
}

export function prepareParticulateReadings(rows, keys) {
  let hasData = false;
  let hasMissing = false;
  const readings = rows.map((row) => {
    const bands = particulateBands(row.values, keys);
    const complete = bands.every(({ difference }) => difference !== null);
    if (complete) hasData = true;
    else hasMissing = true;
    return { id: row.measurement_id, time: row.time, bands, complete };
  });
  return { readings, max: particulateReadingMax(readings), hasData, hasMissing };
}
