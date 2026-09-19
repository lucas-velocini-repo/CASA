import { Thermometer, Droplets, Gauge, Sun } from "lucide-react";
import MeasurementChart from "./MeasurementChart";
import { metrics, formatValue } from "../utils/metrics";
import { formatTimestamp } from "../utils/dates";

const cards = [
  { key: "temperature", Icon: Thermometer },
  { key: "humidity", Icon: Droplets },
  { key: "pressure", Icon: Gauge },
  { key: "light", Icon: Sun },
];

export default function Overview({ rows, station, period, timeZone }) {
  const last = rows.at(-1);
  return (
    <>
      <div className="section-heading">
        <h2>Visão geral</h2>
        <span>
          Última leitura no período:{" "}
          {formatTimestamp(last.timestamp, false, timeZone)}
        </span>
      </div>
      <div className="metric-grid">
        {cards.map(({ key, Icon }) => (
          <div className="metric-card" key={key}>
            <div>
              <span>{metrics[key].label}</span>
              <Icon size={19} style={{ color: metrics[key].color }} />
            </div>
            <strong>
              {formatValue(last.values?.[key], key === "pressure" ? 2 : 1)}{" "}
              <small>{metrics[key].unit}</small>
            </strong>
            <span className="metric-caption">Última leitura do período</span>
          </div>
        ))}
      </div>
      <div className="overview-charts">
        {cards.map(({ key }) => (
          <MeasurementChart
            key={key}
            rows={rows}
            keys={[key]}
            title={metrics[key].label}
            station={station}
            period={period}
            timeZone={timeZone}
            compact
          />
        ))}
      </div>
      <p className="muted overview-hint">
        Consulte as abas de particulados para acompanhar PM e NC ao longo do
        tempo.
      </p>
    </>
  );
}
