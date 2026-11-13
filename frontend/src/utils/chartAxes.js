export function integerAxis([min, max]) {
  const target = Math.max(1, (max - min) / 4);
  const magnitude = 10 ** Math.floor(Math.log10(target));
  const factor = [1, 2, 5, 10].find((value) => value * magnitude >= target);
  const step = factor * magnitude;
  const first = Math.floor(min / step);
  const last = Math.max(first + 1, Math.ceil(max / step));
  const ticks = Array.from({ length: last - first + 1 }, (_, i) => (first + i) * step);
  return { domain: [ticks[0], ticks.at(-1)], ticks };
}

const HOUR = 3_600_000;

function clockTicks(start, end, timeZone, step = 60) {
  const local = new Intl.DateTimeFormat("en-CA", {
    timeZone, hourCycle: "h23", minute: "2-digit", hour: "2-digit",
  });
  const ticks = [];
  let time = Math.ceil(start / 60_000) * 60_000;
  while (time <= end) {
    const minute = Number(local.formatToParts(time).find(({ type }) => type === "minute").value);
    const offset = minute % step;
    if (offset === 0) ticks.push(time);
    time += (step - offset) * 60_000;
  }
  return ticks;
}

function guideStep(start, end) {
  if (end - start >= HOUR) return 60;
  const target = (end - start) / 60_000 / 4;
  return [1, 2, 5, 10, 15].find((step) => step >= target);
}

export function chartTimeAxis(start, end, timeZone, maxTicks) {
  const step = guideStep(start, end);
  let domain = [start, end];
  let guides = clockTicks(start, end, timeZone, step);
  if (step < 60 || guides.length < 2) {
    const surrounding = clockTicks(start - HOUR, end + HOUR, timeZone, step);
    const left = surrounding.findLast((tick) => tick <= start);
    const right = surrounding.find((tick) => tick >= end && tick !== left);
    domain = [left ?? start, right ?? end];
    guides = surrounding.filter((tick) => tick >= domain[0] && tick <= domain[1]);
  }
  const count = Math.min(maxTicks, guides.length);
  const stride = Math.max(1, Math.floor(guides.length / count));
  const first = Math.floor((guides.length - 1 - (count - 1) * stride) / 2);
  const labels = Array.from({ length: count }, (_, index) => guides[first + index * stride]);
  return { domain, guides, labels };
}

// The stacked reading chart uses equal-width columns. Locate each hour between
// adjacent readings, keeping the timestamps and widths of the readings intact.
export function readingHourGuides(readings, timeZone, minColumns) {
  const start = readings[0].time;
  const end = readings.at(-1).time;
  const ticks = clockTicks(start, end, timeZone, guideStep(start, end));
  const guides = [];
  let index = 0;
  for (const time of ticks) {
    while (index + 1 < readings.length && readings[index + 1].time <= time) index++;
    const left = readings[index].time;
    const right = readings[index + 1]?.time;
    const column = index + 0.5 + (right > left ? (time - left) / (right - left) : 0);
    guides.push({ time, column });
  }
  const labels = [];
  for (const guide of guides) {
    if (!labels.length || guide.column - labels.at(-1).column >= minColumns) labels.push(guide);
  }
  return { guides, labels };
}
