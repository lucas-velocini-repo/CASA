import { Clock, Thermometer, Droplets, Gauge, Sun } from "lucide-react";
import ParticulateSnapshot from "./ParticulateSnapshot";
import ParticulateReadingChart from "./ParticulateReadingChart";
import MeasurementChart from "./MeasurementChart";
import { metrics, formatValue, PM_KEYS } from "../utils/metrics";
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
        <div className="latest-reading">
          <Clock size={16} aria-hidden="true" />
          <span>Última leitura no período</span>
          <time dateTime={last.timestamp}>
            {formatTimestamp(last.timestamp, false, timeZone, true)}
          </time>
        </div>
      </div>
      <div className="metric-grid">
        {cards.map(({ key, Icon }) => (
          <div className="metric-card" key={key}>
            <div>
              <span>{metrics[key].label}</span>
              <Icon size={19} style={{ color: metrics[key].color }} />
            </div>
            <strong>
              {formatValue(last.values?.[key])}{" "}
              <small>{metrics[key].unit}</small>
            </strong>
            <span className="metric-caption">Última leitura do período</span>
          </div>
        ))}
      </div>
      <ParticulateSnapshot reading={last} timeZone={timeZone} />
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
      <div className="overview-charts overview-pm-history">
        <MeasurementChart
          rows={rows}
          keys={PM_KEYS}
          title="Histórico de particulados PM"
          station={station}
          period={period}
          timeZone={timeZone}
        />
        <ParticulateReadingChart rows={rows} station={station} timeZone={timeZone} />
      </div>
    </>
  );
}
