import test from "node:test";
import assert from "node:assert/strict";
import { periodBounds, today } from "../src/utils/dates.js";
import { fetchHistory } from "../src/services/api.js";
import { automaticDomain, chartRows } from "../src/utils/metrics.js";
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
    [-0.01, 0.01],
  );
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
