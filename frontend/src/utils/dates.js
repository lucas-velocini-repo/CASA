// One explicit time zone for filters, axes and exports, independent of the browser.
export const TIME_ZONE = "America/Sao_Paulo";
export const TIME_ZONE_LABEL = "Brasília (America/Sao_Paulo)";

export function today(now = new Date(), timeZone = TIME_ZONE) {
  const parts = new Intl.DateTimeFormat("en-CA", {
    timeZone,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).formatToParts(now);
  const value = (type) => parts.find((part) => part.type === type).value;
  return `${value("year")}-${value("month")}-${value("day")}`;
}

export function shiftDay(day, amount) {
  const date = new Date(`${day}T12:00:00Z`);
  date.setUTCDate(date.getUTCDate() + amount);
  return date.toISOString().slice(0, 10);
}

export function initialPeriod(timeZone = TIME_ZONE) {
  return {
    startDate: today(new Date(), timeZone),
    endDate: today(new Date(), timeZone),
    useTime: false,
    startTime: "00:00",
    endTime: "23:59",
  };
}

function zonedDate(day, time, timeZone) {
  const target = Date.parse(`${day}T${time}:00Z`);
  if (!Number.isFinite(target))
    throw new Error("Preencha datas e horários válidos.");
  // Resolve the IANA offset, including historical daylight-saving transitions.
  let guess = target;
  for (let i = 0; i < 4; i++) {
    const parts = new Intl.DateTimeFormat("en-CA", {
      timeZone,
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
      hourCycle: "h23",
    }).formatToParts(guess);
    const p = Object.fromEntries(parts.map(({ type, value }) => [type, value]));
    const represented = Date.parse(
      `${p.year}-${p.month}-${p.day}T${p.hour}:${p.minute}:${p.second}Z`,
    );
    if (represented === target) return guess;
    guess += target - represented;
  }
  throw new Error(
    "Este horário não existe no fuso selecionado. Escolha outro horário.",
  );
}

export function periodBounds(period, timeZone = TIME_ZONE) {
  if (
    !/^\d{4}-\d{2}-\d{2}$/.test(period.startDate) ||
    !/^\d{4}-\d{2}-\d{2}$/.test(period.endDate)
  ) {
    throw new Error("Preencha as duas datas.");
  }
  const start = zonedDate(
    period.startDate,
    period.useTime ? period.startTime : "00:00",
    timeZone,
  );
  // The selected final minute is inclusive; requests/filters use an exclusive end.
  const end = period.useTime
    ? zonedDate(period.endDate, period.endTime, timeZone) + 60_000
    : zonedDate(shiftDay(period.endDate, 1), "00:00", timeZone);
  if (start >= end)
    throw new Error("O início deve ser anterior ao fim do período.");
  return { start, end };
}

export function formatTimestamp(value, short = false, timeZone = TIME_ZONE) {
  if (!value) return "Sem registro";
  const date = new Date(value);
  if (!Number.isFinite(date.getTime())) return "Data inválida";
  return date.toLocaleString("pt-BR", {
    timeZone,
    day: "2-digit",
    month: "2-digit",
    ...(short ? {} : { year: "numeric" }),
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function periodLabel(period) {
  const day = (value) => value.split("-").reverse().join("/");
  return `${day(period.startDate)} ${period.useTime ? period.startTime : "00:00"} — ${day(period.endDate)} ${period.useTime ? period.endTime : "23:59"}`;
}
