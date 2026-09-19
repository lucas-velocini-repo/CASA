import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from "recharts";
import { metrics, formatValue, PM_KEYS } from "../utils/metrics";
import { formatTimestamp } from "../utils/dates";

export default function ParticulateSnapshot({ reading, timeZone }) {
  const data = PM_KEYS.map((key) => ({
    key,
    name: metrics[key].label,
    value: reading.values?.[key] ?? null,
  }));
  const hasData = data.some((item) => Number.isFinite(item.value));
  return (
    <section className="chart-card particulate-snapshot">
      <div className="chart-heading">
        <div>
          <h3>Particulados · última leitura no período</h3>
          <small>
            {formatTimestamp(reading.timestamp, false, timeZone)} · µg/m³
          </small>
        </div>
      </div>
      {hasData ? (
        <>
          <div
            className="snapshot-canvas"
            role="img"
            aria-label="Concentrações PM da última leitura do período; valores apresentados abaixo"
          >
            <ResponsiveContainer width="100%" height="100%" minWidth={0}>
              <BarChart
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
                  dataKey="name"
                  tick={{ fill: "#637c82", fontSize: 11 }}
                  axisLine={false}
                  tickLine={false}
                />
                <YAxis
                  width={60}
                  tickFormatter={(value) => formatValue(value, 2)}
                  tick={{ fill: "#637c82", fontSize: 11 }}
                  axisLine={false}
                  tickLine={false}
                />
                <Tooltip
                  formatter={(value) => [
                    `${formatValue(value, 3)} µg/m³`,
                    "Concentração",
                  ]}
                />
                <Bar
                  dataKey="value"
                  name="Concentração"
                  maxBarSize={72}
                  radius={[5, 5, 0, 0]}
                  isAnimationActive={false}
                >
                  {data.map((item) => (
                    <Cell key={item.key} fill={metrics[item.key].color} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
          <dl className="snapshot-values">
            {data.map((item) => (
              <div key={item.key}>
                <dt>{item.name}</dt>
                <dd>
                  {formatValue(item.value, 3)} <small>µg/m³</small>
                </dd>
              </div>
            ))}
          </dl>
          <p className="chart-note">
            As classes PM são cumulativas; as barras não devem ser somadas.
          </p>
        </>
      ) : (
        <div className="metric-empty">
          A última leitura do período não contém valores de PM.
        </div>
      )}
    </section>
  );
}
