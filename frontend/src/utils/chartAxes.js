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
