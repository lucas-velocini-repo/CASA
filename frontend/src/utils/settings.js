import { TIME_ZONE } from "./dates.js";

export function readTimeZone() {
  try {
    const saved = localStorage.getItem("casa.timeZone") || TIME_ZONE;
    new Intl.DateTimeFormat("pt-BR", { timeZone: saved }).format();
    return saved;
  } catch {
    return TIME_ZONE;
  }
}
