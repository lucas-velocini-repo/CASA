import { useState } from "react";
import { ChevronLeft, ChevronRight, CalendarDays } from "lucide-react";
import { initialPeriod, periodBounds, shiftDay, today } from "../utils/dates";

export default function PeriodFilter({ value, onApply, timeZone }) {
  const [draft, setDraft] = useState(value);
  const [error, setError] = useState("");
  const change = (key, value) => {
    setDraft((old) => ({ ...old, [key]: value }));
    setError("");
  };
  function apply(event) {
    event.preventDefault();
    try {
      periodBounds(draft, timeZone);
      onApply(draft);
      setError("");
    } catch (err) {
      setError(err.message);
    }
  }
  function preset(days) {
    const next = {
      ...initialPeriod(timeZone),
      startDate: shiftDay(today(new Date(), timeZone), -days + 1),
    };
    setDraft(next);
    onApply(next);
    setError("");
  }
  return (
    <form className="period-filter" onSubmit={apply}>
      <div className="filter-heading">
        <span>
          <CalendarDays size={16} /> Período de análise
        </span>
        <small>{timeZone}</small>
      </div>
      <div className="filter-fields">
        {[
          ["startDate", "Data inicial"],
          ["endDate", "Data final"],
        ].map(([key, label]) => (
          <div className="date-field" key={key}>
            <label htmlFor={key}>{label}</label>
            <div className="date-control">
              <button
                type="button"
                disabled={!draft[key]}
                aria-label={`${label}: dia anterior`}
                onClick={() => change(key, shiftDay(draft[key], -1))}
              >
                <ChevronLeft size={16} />
              </button>
              <input
                id={key}
                type="date"
                required
                value={draft[key]}
                onChange={(e) => change(key, e.target.value)}
              />
              <button
                type="button"
                disabled={!draft[key]}
                aria-label={`${label}: próximo dia`}
                onClick={() => change(key, shiftDay(draft[key], 1))}
              >
                <ChevronRight size={16} />
              </button>
            </div>
          </div>
        ))}
        <label className="checkbox">
          <input
            type="checkbox"
            checked={draft.useTime}
            onChange={(e) => change("useTime", e.target.checked)}
          />{" "}
          Filtrar por horário
        </label>
        {draft.useTime && (
          <>
            <label className="time-field">
              Hora inicial
              <input
                aria-label="Hora inicial"
                type="time"
                required
                value={draft.startTime}
                onChange={(e) => change("startTime", e.target.value)}
              />
            </label>
            <label className="time-field">
              Hora final
              <input
                aria-label="Hora final"
                type="time"
                required
                value={draft.endTime}
                onChange={(e) => change("endTime", e.target.value)}
              />
            </label>
          </>
        )}
        <button className="primary apply" type="submit">
          Aplicar período
        </button>
      </div>
      <div className="filter-bottom">
        <div className="presets">
          <button type="button" onClick={() => preset(1)}>
            Hoje
          </button>
          <button type="button" onClick={() => preset(7)}>
            Últimos 7 dias
          </button>
          <button type="button" onClick={() => preset(30)}>
            Últimos 30 dias
          </button>
        </div>
        {JSON.stringify(draft) !== JSON.stringify(value) && (
          <small>Alterações ainda não aplicadas</small>
        )}
      </div>
      {error && (
        <p className="error-text" role="alert">
          {error}
        </p>
      )}
    </form>
  );
}
