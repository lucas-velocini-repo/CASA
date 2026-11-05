function axisWithStep(min, max, step) {
  const first = Math.floor(min / step);
  const last = Math.max(first + 1, Math.ceil(max / step));
  const ticks = Array.from({ length: last - first + 1 }, (_, i) => (first + i) * step);
  return { domain: [ticks[0], ticks.at(-1)], ticks };
}

export function integerAxis([min, max]) {
  const target = Math.max(1, (max - min) / 4);
  const magnitude = 10 ** Math.floor(Math.log10(target));
  const factor = [1, 2, 5, 10].find((value) => value * magnitude >= target);
  const step = factor * magnitude;
  return axisWithStep(min, max, step);
}

const MINUTE = 60_000;
const WEEK = 7 * 24 * 60;
const TIME_STEPS = [1, 2, 5, 10, 15, 30, 60, 120, 180, 360, 720, 1440, 2880, WEEK];

export function timeAxis(min, max) {
  if (!Number.isFinite(min) || !Number.isFinite(max)) return undefined;
  const target = (max - min) / (4 * MINUTE);
  const minutes = TIME_STEPS.find((step) => step >= target) ?? Math.ceil(target / WEEK) * WEEK;
  return axisWithStep(min, max, minutes * MINUTE);
}
