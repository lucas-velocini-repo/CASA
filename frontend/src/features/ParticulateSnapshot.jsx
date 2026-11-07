import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import {
  metrics,
  formatValue,
  particulateBands,
  formatParticulateDifference,
  PM_KEYS,
} from "../utils/metrics";
import { integerAxis } from "../utils/chartAxes";
import { formatTimestamp } from "../utils/dates";

export default function ParticulateSnapshot({ reading, timeZone }) {
  const bands = particulateBands(reading.values);
  const hasData = bands.some(({ value }) => Number.isFinite(value));
  const canStack = bands.every(({ difference }) => difference !== null);
  const stack = Object.fromEntries(bands.map(({ key, difference }) => [key, difference]));
  const valueAxis = integerAxis([0, canStack ? bands.at(-1).value : 0]);
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
          {canStack ? (
            <div
              className="snapshot-canvas"
              role="img"
              aria-label="Barra empilhada com a concentração de cada faixa de tamanho. Valores abaixo."
            >
              <ResponsiveContainer width="100%" height="100%" minWidth={0}>
                <BarChart
                  layout="vertical"
                  data={[stack]}
                  margin={{ top: 8, right: 24, left: 12, bottom: 0 }}
                  accessibilityLayer
                >
                  <CartesianGrid
                    stroke="#e4eeec"
                    horizontal={false}
                    strokeDasharray="3 4"
                  />
                  <XAxis
                    type="number"
                    domain={valueAxis.domain}
                    ticks={valueAxis.ticks}
                    allowDecimals={false}
                    tickFormatter={formatValue}
                    tick={{ fill: "#637c82", fontSize: 11 }}
                    axisLine={false}
                    tickLine={false}
                  />
                  <YAxis type="category" hide />
                  <Tooltip
                    labelFormatter={() => "Concentração acumulada"}
                    itemSorter={({ dataKey }) => PM_KEYS.indexOf(dataKey)}
                    formatter={(_, name, { dataKey }) => [
                      `${formatValue(reading.values[dataKey])} µg/m³`,
                      name,
                    ]}
                  />
                  {bands.map(({ key }) => (
                    <Bar
                      key={key}
                      dataKey={key}
                      name={metrics[key].label}
                      stackId="pm"
                      fill={metrics[key].color}
                      maxBarSize={32}
                      isAnimationActive={false}
                    />
                  ))}
                </BarChart>
              </ResponsiveContainer>
            </div>
          ) : (
            <p className="chart-note">
              A barra precisa de valores cumulativos completos e em ordem crescente de tamanho.
            </p>
          )}
          <dl className="snapshot-values">
            {bands.map(({ key, value, difference }) => (
              <div key={key}>
                <dt><i style={{ background: metrics[key].color }} />{metrics[key].label}</dt>
                <dd>
                  {formatValue(value)} <small>µg/m³ acumulados</small>
                </dd>
                <dd className="snapshot-difference">
                  Diferença: {formatParticulateDifference(difference)} µg/m³
                </dd>
              </div>
            ))}
          </dl>
          <p className="chart-note">
            Cada segmento mostra a diferença em relação à classe anterior, começando em zero.
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
