import { useMemo, useRef, useState } from "react";
import { Download } from "lucide-react";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import {
  metrics,
  formatValue,
  automaticDomain,
  chartRows,
} from "../utils/metrics";
import { formatTimestamp } from "../utils/dates";
import { exportChart } from "../utils/export";

export default function MeasurementChart({
  rows,
  keys,
  title,
  station,
  period,
  timeZone,
  compact = false,
}) {
  const ref = useRef(null);
  const [exporting, setExporting] = useState(false);
  const [error, setError] = useState("");
  const [zero, setZero] = useState(false);
  const data = useMemo(() => chartRows(rows, keys), [rows, keys]);
  const domain = useMemo(() => automaticDomain(rows, keys), [rows, keys]);
  const hasData = rows.some((row) =>
    keys.some((key) => Number.isFinite(row.values?.[key])),
  );
  const reduced = data.length < rows.length;
  async function save() {
    setExporting(true);
    setError("");
    try {
      await exportChart(ref.current, {
        title,
        station,
        period,
        filename: `${station}_${title}`,
        reduced,
        timeZone,
        series: keys.map(
          (key) => `${metrics[key].label} (${metrics[key].unit})`,
        ),
      });
    } catch (err) {
      setError(err.message || "Não foi possível salvar o gráfico.");
    } finally {
      setExporting(false);
    }
  }
  return (
    <section className={`chart-card ${compact ? "compact" : ""}`}>
      <div className="chart-heading">
        <div>
          <h3>{title}</h3>
          <small>
            {metrics[keys[0]].unit} ·{" "}
            {zero ? "Escala inclui zero" : "Escala automática"}
          </small>
        </div>
        <button
          className="icon-button"
          disabled={!hasData || exporting}
          onClick={save}
          title="Salvar gráfico em PNG"
          aria-label={`Salvar gráfico de ${title} em PNG`}
        >
          <Download size={17} />
          <span>{exporting ? "Salvando…" : "PNG"}</span>
        </button>
      </div>
      {hasData ? (
        <>
          <div
            ref={ref}
            className="chart-canvas"
            role="img"
            aria-label={`${title}: ${rows.length} registros, ${period}. Valores disponíveis na aba Dados históricos.`}
          >
            <ResponsiveContainer width="100%" height="100%" minWidth={0}>
              <LineChart
                data={data}
                margin={{ top: 14, right: 16, left: 0, bottom: 4 }}
                accessibilityLayer
              >
                <CartesianGrid
                  stroke="#e4eeec"
                  vertical={false}
                  strokeDasharray="3 4"
                />
                <XAxis
                  dataKey="time"
                  type="number"
                  scale="time"
                  domain={["dataMin", "dataMax"]}
                  tickFormatter={(value) =>
                    formatTimestamp(value, true, timeZone)
                  }
                  minTickGap={44}
                  tick={{ fill: "#637c82", fontSize: 11 }}
                  axisLine={false}
                  tickLine={false}
                />
                <YAxis
                  domain={
                    zero
                      ? [Math.min(0, domain[0]), Math.max(0, domain[1])]
                      : domain
                  }
                  width={65}
                  tickFormatter={(value) => formatValue(value, 2)}
                  tick={{ fill: "#637c82", fontSize: 11 }}
                  axisLine={false}
                  tickLine={false}
                />
                <Tooltip
                  labelFormatter={(value) =>
                    formatTimestamp(value, false, timeZone)
                  }
                  formatter={(value, name) => [formatValue(value, 4), name]}
                  contentStyle={{
                    borderRadius: 10,
                    border: "1px solid #dce8e5",
                    fontSize: 12,
                  }}
                />
                {keys.map((key, index) => (
                  <Line
                    key={key}
                    dataKey={`values.${key}`}
                    name={`${metrics[key].label} (${metrics[key].unit})`}
                    type="linear"
                    stroke={metrics[key].color}
                    strokeWidth={1.8}
                    strokeDasharray={index > 1 ? `${index * 2} 2` : undefined}
                    dot={data.length === 1 ? { r: 4 } : false}
                    activeDot={{ r: 4 }}
                    connectNulls={false}
                    isAnimationActive={false}
                  />
                ))}
              </LineChart>
            </ResponsiveContainer>
          </div>
          <div className="chart-footer">
            <div className="chart-legend">
              {keys.map((key) => (
                <span key={key}>
                  <i style={{ background: metrics[key].color }} />
                  {metrics[key].label}
                </span>
              ))}
            </div>
            <label className="checkbox">
              <input
                type="checkbox"
                checked={zero}
                onChange={(e) => setZero(e.target.checked)}
              />{" "}
              Incluir zero
            </label>
          </div>
          {reduced && (
            <p className="chart-note">
              {data.length.toLocaleString("pt-BR")} de{" "}
              {rows.length.toLocaleString("pt-BR")} pontos desenhados,
              preservando extremos por faixa. O CSV contém todos os registros.
            </p>
          )}
        </>
      ) : (
        <div className="metric-empty">
          Não há valores de {title.toLowerCase()} neste período.
        </div>
      )}
      {error && (
        <p role="alert" className="error-text">
          {error}
        </p>
      )}
    </section>
  );
}
