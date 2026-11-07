import { useCallback, useId, useLayoutEffect, useMemo, useRef, useState } from "react";
import { ChevronFirst, ChevronLast, Download } from "lucide-react";
import { integerAxis } from "../utils/chartAxes";
import { formatTimestamp } from "../utils/dates";
import { exportParticulateChart } from "../utils/export";
import { formatValue, metrics, NC_KEYS, PM_KEYS } from "../utils/metrics";
import { particulateReadingMax, prepareParticulateReadings } from "../utils/particulateReadings";

const COLUMN_WIDTH = 32;
const AXIS_WIDTH = 52;
const OVERSCAN = 3;
const SCALE_SETTLE_MS = 160;

function visibleReadingRange(left, width) {
  const plotWidth = Math.max(0, width - AXIS_WIDTH);
  return {
    start: Math.floor(left / COLUMN_WIDTH),
    end: Math.ceil((left + plotWidth) / COLUMN_WIDTH),
    plotWidth,
  };
}

function ReadingDetails({ reading, timeZone, unit, left }) {
  return (
    <div className={`pm-day-tooltip ${left ? "pm-day-tooltip-left" : ""}`} role="status">
      <strong>{formatTimestamp(reading.time, false, timeZone, true)}</strong>
      <small>Concentração acumulada · {unit}</small>
      <dl>
        {[...reading.bands].reverse().map(({ key, value }) => (
          <div key={key}>
            <dt style={{ color: metrics[key].color }}>{metrics[key].label}</dt>
            <dd>{formatValue(value)}</dd>
          </div>
        ))}
      </dl>
      {!reading.complete && <small>Empilhamento indisponível para esta leitura</small>}
    </div>
  );
}

function ScrollableReadings({
  readings, axis, timeZone, multipleDates, kind, seriesKeys, unit, scrollRef, setScaleRange, children,
}) {
  const followLatest = useRef(true);
  const previousReadings = useRef(readings);
  const scaleTimer = useRef(null);
  const [viewport, setViewport] = useState({ left: 0, width: 0 });
  const [activeId, setActiveId] = useState(null);
  const scrollId = useId();
  const hintId = useId();
  const tickTime = useMemo(
    () => new Intl.DateTimeFormat("pt-BR", {
      timeZone,
      ...(multipleDates ? { day: "2-digit", month: "2-digit" } : {}),
      hour: "2-digit",
      minute: "2-digit",
    }),
    [timeZone, multipleDates],
  );

  const updateViewport = useCallback((element, scrolling = false) => {
    const { scrollLeft: left, clientWidth: width } = element;
    setViewport((previous) =>
      previous.left === left && previous.width === width ? previous : { left, width },
    );
    clearTimeout(scaleTimer.current);
    const { start, end } = visibleReadingRange(left, width);
    const settleScale = () => {
      scaleTimer.current = null;
      setScaleRange((previous) =>
        previous?.start === start && previous.end === end ? previous : { start, end },
      );
    };
    if (scrolling) scaleTimer.current = setTimeout(settleScale, SCALE_SETTLE_MS);
    else settleScale();
  }, [setScaleRange]);

  useLayoutEffect(() => {
    const element = scrollRef.current;
    const previous = previousReadings.current;
    if (followLatest.current) {
      element.scrollLeft = element.scrollWidth;
    } else if (previous !== readings) {
      // A delayed reading can be inserted before the visible measurements.
      const first = Math.floor(element.scrollLeft / COLUMN_WIDTH);
      const anchor = readings.findIndex(({ id }) => id === previous[first]?.id);
      if (anchor >= 0) element.scrollLeft += (anchor - first) * COLUMN_WIDTH;
    }
    previousReadings.current = readings;
    updateViewport(element, scaleTimer.current !== null);
  }, [readings, scrollRef, updateViewport]);

  useLayoutEffect(() => {
    const element = scrollRef.current;
    const observer = new ResizeObserver(() => {
      if (followLatest.current) element.scrollLeft = element.scrollWidth;
      updateViewport(element, scaleTimer.current !== null);
    });
    observer.observe(element);
    return () => {
      observer.disconnect();
      clearTimeout(scaleTimer.current);
      scaleTimer.current = null;
    };
  }, [scrollRef, updateViewport]);

  function onScroll(event) {
    const element = event.currentTarget;
    followLatest.current = element.scrollWidth - element.clientWidth - element.scrollLeft <= 2;
    updateViewport(element, true);
  }

  const last = readings.length - 1;
  const { start: visibleStart, end: visibleEnd, plotWidth } = visibleReadingRange(
    viewport.left,
    viewport.width,
  );
  const firstRendered = Math.max(0, visibleStart - OVERSCAN);
  const rendered = readings.slice(firstRendered, visibleEnd + OVERSCAN);
  const activeOffset = activeId === null ? -1 : rendered.findIndex(({ id }) => id === activeId);
  const active = activeOffset < 0 ? -1 : firstRendered + activeOffset;
  const top = axis.domain[1];
  const labelMargin = multipleDates ? 33 : 16;
  const showDetails = active >= visibleStart && active < visibleEnd;

  function goTo(index) {
    const element = scrollRef.current;
    const left = index * COLUMN_WIDTH;
    if (index === 0) element.scrollLeft = 0;
    else if (index === last) element.scrollLeft = element.scrollWidth;
    else if (left < element.scrollLeft) element.scrollLeft = left;
    else if (left + COLUMN_WIDTH > element.scrollLeft + element.clientWidth - AXIS_WIDTH)
      element.scrollLeft = left + COLUMN_WIDTH - element.clientWidth + AXIS_WIDTH;
    followLatest.current = element.scrollWidth - element.clientWidth - element.scrollLeft <= 2;
    updateViewport(element);
    setActiveId(readings[index].id);
  }

  function onKeyDown(event) {
    const current = showDetails ? active : Math.min(last, visibleEnd - 1);
    let next;
    if (event.key === "ArrowLeft") next = Math.max(0, current - 1);
    else if (event.key === "ArrowRight") next = Math.min(last, current + 1);
    else if (event.key === "Home") next = 0;
    else if (event.key === "End") next = last;
    else return;
    event.preventDefault();
    goTo(next);
  }

  return (
    <>
      <div className="chart-canvas pm-day-frame" style={{ "--pm-day-axis-width": `${AXIS_WIDTH}px` }}>
        <div
          className="pm-day-scroll"
          ref={scrollRef}
          id={scrollId}
          tabIndex={0}
          role="region"
          aria-label={`Medições de particulados ${kind} em ordem cronológica`}
          aria-describedby={hintId}
          onScroll={onScroll}
          onKeyDown={onKeyDown}
        >
          <div className="pm-day-track" style={{ width: AXIS_WIDTH + readings.length * COLUMN_WIDTH }}>
            <div className="pm-day-axis" aria-hidden="true">
              <div className="pm-day-axis-ticks">
                {axis.ticks.map((tick) => (
                  <span key={tick} style={{ bottom: `${tick / top * 100}%` }}>{formatValue(tick)}</span>
                ))}
              </div>
            </div>
            <div className="pm-day-grid" aria-hidden="true">
              {axis.ticks.map((tick) => <i key={tick} style={{ bottom: `${tick / top * 100}%` }} />)}
            </div>
            {rendered.map((reading, offset) => {
              const index = firstRendered + offset;
              const center = (index + 0.5) * COLUMN_WIDTH - viewport.left;
              const showHour = index % 3 === 0 && center >= labelMargin && center <= plotWidth - labelMargin;
              return (
                <button
                  type="button"
                  className="pm-day-column"
                  tabIndex={-1}
                  key={reading.id}
                  style={{ left: AXIS_WIDTH + index * COLUMN_WIDTH, width: COLUMN_WIDTH }}
                  aria-label={formatTimestamp(reading.time, false, timeZone, true)}
                  aria-pressed={reading.id === activeId}
                  onPointerEnter={(event) => {
                    if (event.pointerType === "mouse") setActiveId(reading.id);
                  }}
                  onPointerLeave={(event) => {
                    if (event.pointerType === "mouse") setActiveId(null);
                  }}
                  onClick={() => setActiveId(reading.id)}
                >
                  <span className="pm-day-stack" aria-hidden="true">
                    {reading.complete && reading.bands.map(({ key, difference }) => (
                      <i key={key} style={{ height: `${difference / top * 100}%`, background: metrics[key].color }} />
                    ))}
                  </span>
                  {showHour && <span className="pm-day-hour" aria-hidden="true">{tickTime.format(reading.time)}</span>}
                </button>
              );
            })}
          </div>
        </div>
        {showDetails && (
          <ReadingDetails
            reading={readings[active]}
            timeZone={timeZone}
            unit={unit}
            left={active * COLUMN_WIDTH - viewport.left >= plotWidth / 2}
          />
        )}
      </div>
      <div className="pm-day-actions">
        <button type="button" className="icon-button" aria-controls={scrollId} onClick={() => goTo(0)}>
          <ChevronFirst size={16} aria-hidden="true" /> Ir para a primeira leitura
        </button>
        <button type="button" className="icon-button" aria-controls={scrollId} onClick={() => goTo(last)}>
          Ir para a última leitura <ChevronLast size={16} aria-hidden="true" />
        </button>
      </div>
      <div className="chart-footer">
        <div className="chart-legend">
          {seriesKeys.map((key) => (
            <span key={key}><i style={{ background: metrics[key].color }} />{metrics[key].label}</span>
          ))}
        </div>
        {children}
      </div>
      <p className="chart-note" id={hintId}>
        Role para ver outras leituras. Use as setas do teclado ou toque em uma barra para ver os valores.
      </p>
    </>
  );
}

export default function ParticulateReadingChart({ rows, station, timeZone, kind = "PM" }) {
  const scrollRef = useRef(null);
  const [exporting, setExporting] = useState(false);
  const [error, setError] = useState("");
  const [fixedPeriodScale, setFixedPeriodScale] = useState(false);
  const [scaleRange, setScaleRange] = useState(null);
  const seriesKeys = kind === "NC" ? NC_KEYS : PM_KEYS;
  const unit = metrics[seriesKeys[0]].unit;
  const title = `Particulados ${kind} por leitura`;
  const { readings, max, hasData, hasMissing } = useMemo(
    () => prepareParticulateReadings(rows, seriesKeys),
    [rows, seriesKeys],
  );
  const dateRange = useMemo(() => {
    if (!readings.length) return { label: "", multipleDates: false };
    const dateFormat = new Intl.DateTimeFormat("pt-BR", { dateStyle: "short", timeZone });
    const first = dateFormat.format(readings[0].time);
    const last = dateFormat.format(readings.at(-1).time);
    return { label: first === last ? first : `${first} a ${last}`, multipleDates: first !== last };
  }, [readings, timeZone]);
  const scaleMax = fixedPeriodScale || !scaleRange
    ? max
    : particulateReadingMax(readings.slice(scaleRange.start, scaleRange.end));
  const axis = integerAxis([0, scaleMax]);

  async function save() {
    setExporting(true);
    setError("");
    try {
      const { scrollLeft, clientWidth } = scrollRef.current;
      const { start, end, plotWidth } = visibleReadingRange(scrollLeft, clientWidth);
      await exportParticulateChart({
        readings: plotWidth > 0 ? readings.slice(start, end) : [],
        axis,
        seriesKeys,
        title,
        station,
        timeZone,
        unit,
      });
    } catch (err) {
      setError(err.message || "Não foi possível salvar o gráfico.");
    } finally {
      setExporting(false);
    }
  }

  return (
    <section className="chart-card pm-day-card">
      <div className="chart-heading">
        <div>
          <h3>{title}</h3>
          <small>{dateRange.label} · {unit} · {readings.length.toLocaleString("pt-BR")} leituras</small>
        </div>
        <button
          type="button"
          className="icon-button"
          disabled={!hasData || exporting}
          onClick={save}
          title="Salvar trecho visível em PNG"
          aria-label={`Salvar gráfico de ${title} em PNG`}
        >
          <Download size={17} aria-hidden="true" />
          <span>{exporting ? "Salvando…" : "PNG"}</span>
        </button>
      </div>
      {hasData ? (
        <>
          <ScrollableReadings
            readings={readings}
            axis={axis}
            timeZone={timeZone}
            multipleDates={dateRange.multipleDates}
            kind={kind}
            seriesKeys={seriesKeys}
            unit={unit}
            scrollRef={scrollRef}
            setScaleRange={setScaleRange}
          >
            <label className="checkbox">
              <input
                type="checkbox"
                checked={fixedPeriodScale}
                onChange={(event) => setFixedPeriodScale(event.target.checked)}
              />
              Fixar escala do período
            </label>
          </ScrollableReadings>
          {hasMissing && <p className="chart-note">Leituras com dados incompletos ou inconsistentes aparecem sem barra.</p>}
        </>
      ) : (
        <div className="metric-empty">Não há leituras de {kind} com valores completos e cumulativos neste período.</div>
      )}
      {error && <p role="alert" className="error-text">{error}</p>}
    </section>
  );
}
