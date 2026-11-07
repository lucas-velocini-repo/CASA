import test from "node:test";
import assert from "node:assert/strict";
import { formatTimestamp, periodBounds, today } from "../src/utils/dates.js";
import { fetchHistory } from "../src/services/api.js";
import {
  automaticDomain,
  chartRows,
  formatValue,
  particulateBands,
  formatParticulateDifference,
  NC_KEYS,
} from "../src/utils/metrics.js";
import { integerAxis } from "../src/utils/chartAxes.js";
import { latestParticulateDay } from "../src/utils/particulateDay.js";
import { makeCsv } from "../src/utils/export.js";
const period = {
  startDate: "2026-09-19",
  endDate: "2026-09-20",
  useTime: false,
  startTime: "00:00",
  endTime: "23:59",
};

test("full days use selected timezone and exclusive midnight, independent of host", () => {
  const br = periodBounds(period);
  assert.equal(new Date(br.start).toISOString(), "2026-09-19T03:00:00.000Z");
  assert.equal(new Date(br.end).toISOString(), "2026-09-21T03:00:00.000Z");
  assert.equal(
    new Date(periodBounds(period, "Asia/Kolkata").start).toISOString(),
    "2026-09-18T18:30:00.000Z",
  );
  assert.equal(today(new Date("2026-09-19T01:00:00Z")), "2026-09-18");
});
test("final minute included; inverted ranges rejected", () => {
  const bounds = periodBounds({
    ...period,
    useTime: true,
    endDate: period.startDate,
    startTime: "10:00",
    endTime: "10:00",
  });
  assert.equal(bounds.end - bounds.start, 60_000);
  assert.throws(() => periodBounds({ ...period, startDate: "2026-09-21" }));
});
test("DST days have 23/25 hours and nonexistent wall times are rejected", () => {
  const spring = periodBounds(
    { ...period, startDate: "2026-03-08", endDate: "2026-03-08" },
    "America/New_York",
  );
  const autumn = periodBounds(
    { ...period, startDate: "2026-11-01", endDate: "2026-11-01" },
    "America/New_York",
  );
  assert.equal(spring.end - spring.start, 23 * 3600_000);
  assert.equal(autumn.end - autumn.start, 25 * 3600_000);
  assert.throws(() =>
    periodBounds(
      {
        ...period,
        startDate: "2026-03-08",
        endDate: "2026-03-08",
        useTime: true,
        startTime: "02:30",
      },
      "America/New_York",
    ),
  );
});
test("loads >10,000 records without losing or duplicating inclusive page boundaries", async () => {
  const rows = Array.from({ length: 12001 }, (_, i) => ({
    measurement_id: i,
    timestamp: new Date(1700000000000 + i * 300000).toISOString(),
    values: { pressure: 950 + i / 100000 },
  }));
  const start = Date.parse(rows[0].timestamp),
    end = Date.parse(rows.at(-1).timestamp);
  let calls = 0;
  const result = await fetchHistory(
    "test",
    { start, end },
    undefined,
    async (path) => {
      calls++;
      const p = new URL(path, "http://localhost").searchParams;
      return rows
        .filter(
          (r) =>
            Date.parse(r.timestamp) >= Date.parse(p.get("start")) &&
            Date.parse(r.timestamp) <= Date.parse(p.get("end")),
        )
        .slice(-Number(p.get("limit")));
    },
  );
  assert.equal(result.length, 12000);
  assert.ok(calls > 10);
  assert.equal(result[0].measurement_id, 0);
  assert.equal(result.at(-1).measurement_id, 11999);
});
test("history empty, abort and later-page error do not become partial exports", async () => {
  const bounds = { start: 0, end: Date.now() };
  assert.deepEqual(
    await fetchHistory("test", bounds, undefined, async () => []),
    [],
  );
  const controller = new AbortController();
  controller.abort();
  await assert.rejects(
    fetchHistory("test", bounds, controller.signal, async () => []),
  );
  let calls = 0;
  await assert.rejects(
    fetchHistory("test", bounds, undefined, async () => {
      if (calls++) throw new Error("offline");
      return Array.from({ length: 1000 }, (_, i) => ({
        measurement_id: i,
        timestamp: new Date(1000000 + i * 1000).toISOString(),
      }));
    }),
    /offline/,
  );
});
test("pressure axis shows small variation, constant and zero values remain valid", () => {
  const rows = [
    { values: { pressure: 948.6 } },
    { values: { pressure: 948.8 } },
  ];
  const [min, max] = automaticDomain(rows, ["pressure"]);
  assert.ok(min < 948.6 && min > 948);
  assert.ok(max > 948.8 && max < 949);
  assert.deepEqual(
    automaticDomain([{ values: { light: 0 } }], ["light"]),
    [0, 0.01],
  );
});
test("non-negative charts start no lower than zero, while temperature can be negative", () => {
  for (const key of ["light", "pressure", "humidity", "pm1", "nc05"]) {
    const rows = [{ values: { [key]: 0 } }, { values: { [key]: 5 } }];
    const { ticks } = integerAxis(automaticDomain(rows, [key]));
    assert.equal(ticks[0], 0);
  }
  const domain = automaticDomain([{ values: { temperature: -1 } }], ["temperature"]);
  assert.ok(integerAxis(domain).ticks[0] < 0);
});
test("measurement display rounds to one decimal and latest reading can show seconds", () => {
  assert.deepEqual([3.456, 3.4, 3, null].map(formatValue), ["3,5", "3,4", "3", "—"]);
  assert.match(formatTimestamp("2026-09-19T03:12:34Z", false, "UTC", true), /03:12:34/);
});
test("PM segments use adjacent cumulative differences and flag missing or decreasing readings", () => {
  const differences = (values) => particulateBands(values).map(({ difference }) => difference);
  assert.deepEqual(differences({ pm1: 2, pm25: 5, pm4: 5, pm10: 6.5 }), [2, 3, 0, 1.5]);
  assert.deepEqual(differences({ pm1: 0, pm4: 5, pm10: 4 }), [0, null, null, null]);
});
test("PM differences distinguish exact zero from positive values that round to zero", () => {
  assert.deepEqual(
    [0, 0.01, 0.05, 0.123, null].map(formatParticulateDifference),
    ["0", "< 0,1", "0,1", "0,1", "—"],
  );
});
test("daily PM columns keep the last local day and distinguish incomplete readings from zero", () => {
  const rows = [
    ["2026-09-20T02:59:00Z", { pm1: 20, pm25: 20, pm4: 20, pm10: 20 }],
    ["2026-09-20T03:00:00Z", { pm1: 0, pm25: 0, pm4: 0, pm10: 0 }],
    ["2026-09-20T04:00:00Z", { pm1: 3, pm25: 5, pm4: 5, pm10: 8 }],
    ["2026-09-20T05:00:00Z", { pm1: 8, pm10: 15 }],
  ].map(([timestamp, values], measurement_id) => ({ measurement_id, time: Date.parse(timestamp), values }));
  const day = latestParticulateDay(rows, "America/Sao_Paulo");
  assert.equal(day.date, "20/09/2026");
  assert.equal(day.max, 8);
  assert.equal(day.hasMissing, true);
  assert.deepEqual(day.readings.map(({ id, complete }) => [id, complete]), [[1, true], [2, true], [3, false]]);
  assert.deepEqual(day.readings[1].bands.map(({ difference }) => difference), [3, 2, 0, 3]);
  assert.equal(latestParticulateDay(rows, "UTC").readings.length, 4);
});
test("daily NC columns stack five adjacent differences and scale to NC 10,0", () => {
  const time = Date.parse("2026-09-20T03:00:00Z");
  const values = { nc05: 21, nc10: 30, nc25: 34, nc40: 34, nc100: 36 };
  const rows = [
    { measurement_id: 1, time, values },
    { measurement_id: 2, time: time + 60_000, values: { ...values, nc40: 33, nc100: 90 } },
  ];
  const { max, readings } = latestParticulateDay(rows, "UTC", NC_KEYS);
  assert.equal(max, 36);
  assert.equal(readings[0].complete, true);
  assert.deepEqual(readings[0].bands.map(({ difference }) => difference), [21, 9, 4, 0, 2]);
  assert.equal(readings[1].complete, false);
});
test("value axis has evenly spaced integer ticks and contains decimal readings", () => {
  assert.deepEqual(integerAxis([948.55, 948.86]), {
    domain: [948, 949],
    ticks: [948, 949],
  });
  assert.deepEqual(integerAxis([-2.3, 14.7]), {
    domain: [-5, 15],
    ticks: [-5, 0, 5, 10, 15],
  });
  assert.deepEqual(integerAxis([0, 0]), { domain: [0, 1], ticks: [0, 1] });
});
test("visual reduction keeps extrema and does not change source records", () => {
  const rows = Array.from({ length: 10000 }, (_, i) => ({
    time: i,
    values: { pressure: i === 5151 ? 2000 : 950 },
  }));
  const result = chartRows(rows, ["pressure"]);
  assert.ok(result.length < rows.length);
  assert.ok(result.some((r) => r.values.pressure === 2000));
  assert.equal(rows.length, 10000);
});
test("CSV preserves original precision, zero, UTC, chosen timezone and formula safety", () => {
  const csv = makeCsv(
    [
      {
        measurement_id: 1,
        device_name: "=danger",
        timestamp: "2026-09-19T03:00:00Z",
        values: { pressure: 948.612345, light: 0 },
      },
    ],
    "UTC",
  );
  assert.ok(csv.startsWith("\uFEFF"));
  assert.match(csv, /948\.612345/);
  assert.match(csv, /"0"/);
  assert.match(csv, /'=danger/);
  assert.match(csv, /data_hora \(UTC\)/);
  assert.match(csv, /03:00/);
});

test("station activity expires after six minutes even when registration is enabled", async () => {
  const { isStationActive, ACTIVITY_WINDOW_MS } =
    await import("../src/utils/stationStatus.js");
  const now = Date.parse("2026-09-19T18:00:00Z");
  assert.equal(
    isStationActive(new Date(now - ACTIVITY_WINDOW_MS).toISOString(), now),
    true,
  );
  assert.equal(
    isStationActive(new Date(now - ACTIVITY_WINDOW_MS - 1).toISOString(), now),
    false,
  );
  assert.equal(isStationActive(null, now), false);
  assert.equal(isStationActive("invalid", now), false);
});

test("CSV exports only the tab metrics while history includes every metric", async () => {
  const { exportKeys, metrics } = await import("../src/utils/metrics.js");
  const rows = [
    {
      measurement_id: 7,
      timestamp: "2026-09-19T03:00:00Z",
      values: { temperature: 25, pressure: 949, pm1: 2 },
    },
  ];
  const csv = makeCsv(rows, "UTC", exportKeys("temperature"));
  assert.match(csv, /temperature/);
  assert.doesNotMatch(csv, /pressure|pm1/);
  assert.deepEqual(exportKeys("history"), Object.keys(metrics));
  assert.ok(exportKeys("overview").includes("pm10"));
});


test("station activity follows confirmed long acquisition intervals", async () => {
  const { isStationActive } = await import("../src/utils/stationStatus.js");
  const now = Date.now();
  const ago = (seconds) => new Date(now - seconds * 1000).toISOString();
  assert.equal(isStationActive(ago(600), now, 900), true);
  assert.equal(isStationActive(ago(1081), now, 900), false);
  assert.equal(isStationActive(ago(361), now, 30), false);
  assert.equal(isStationActive(ago(361), now, null), false);
});
