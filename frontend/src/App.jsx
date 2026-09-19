import { useCallback, useState } from "react";
import { Download, RefreshCw, UserRound, Settings } from "lucide-react";
import SettingsDialog from "./components/SettingsDialog";
import { readTimeZone } from "./utils/settings";
import logo from "../assets/t2p-logo.png";
import StationStatus from "./components/StationStatus";
import StationSelector from "./components/StationSelector";
import PeriodFilter from "./components/PeriodFilter";
import StatusPanel from "./components/StatusPanel";
import Overview from "./features/Overview";
import HistoryTable from "./features/HistoryTable";
import MeasurementChart from "./features/MeasurementChart";
import { usePolling } from "./hooks/usePolling";
import { fetchHistory, fetchStations } from "./services/api";
import { tabs, exportKeys } from "./utils/metrics";
import {
  initialPeriod,
  periodBounds,
  periodLabel,
  formatTimestamp,
} from "./utils/dates";
import { exportCsv } from "./utils/export";
import "./styles/dashboard.css";

function StationData({ device, latest, timeZone }) {
  const [period, setPeriod] = useState(() => initialPeriod(timeZone));
  const [tab, setTab] = useState("overview");
  const [revision, setRevision] = useState(0);
  const { start, end } = periodBounds(period, timeZone);
  const load = useCallback(
    (signal) => fetchHistory(device.device_id, { start, end }, signal),
    [device.device_id, start, end],
  );
  const requestKey = `${device.device_id}:${start}:${end}:${revision}`;
  const history = usePolling(requestKey, load, 60_000);
  const rows = history.data || [];
  const definition = tabs.find((item) => item.id === tab);
  const label = periodLabel(period);
  const name = device.name || device.device_id;
  return (
    <main className="content-area">
      <div className="station-header">
        <div>
          <span className="eyebrow">MONITORAMENTO AMBIENTAL</span>
          <h1>{name}</h1>
          <p>
            Última medição:{" "}
            {formatTimestamp(latest?.timestamp, false, timeZone)}
          </p>
        </div>
        <div className="station-meta">
          <StationStatus lastSeen={device.last_seen || latest?.received_at} />
          <small>
            Última comunicação:{" "}
            {formatTimestamp(device.last_seen, false, timeZone)}
          </small>
        </div>
      </div>
      <nav className="tabs" aria-label="Visualização dos dados">
        {tabs.map((item) => (
          <button
            key={item.id}
            aria-current={tab === item.id ? "page" : undefined}
            className={tab === item.id ? "selected" : ""}
            onClick={() => setTab(item.id)}
          >
            {item.label}
          </button>
        ))}
      </nav>
      <div className="content-body">
        <PeriodFilter value={period} onApply={setPeriod} timeZone={timeZone} />
        <div className="data-toolbar">
          <div>
            <strong>{label}</strong>
            <small>
              {history.status === "success"
                ? `${rows.length.toLocaleString("pt-BR")} registros no período`
                : history.status === "error"
                  ? "Consulta indisponível"
                  : "Consultando histórico…"}
            </small>
          </div>
          <div className="toolbar-actions">
            <button
              aria-label="Atualizar histórico"
              title="Atualizar histórico"
              onClick={() => setRevision((value) => value + 1)}
              disabled={history.status === "loading"}
            >
              <RefreshCw size={16} />
            </button>
            <button
              disabled={history.status !== "success" || !rows.length}
              onClick={() =>
                exportCsv(
                  rows,
                  `${name}_${tab}_${period.startDate}_${period.endDate}`,
                  timeZone,
                  exportKeys(tab),
                )
              }
            >
              <Download size={16} /> Exportar CSV
            </button>
          </div>
        </div>
        {history.status !== "success" || !rows.length ? (
          <StatusPanel
            status={history.status}
            error={history.error}
            onRetry={() => setRevision((value) => value + 1)}
          />
        ) : tab === "overview" ? (
          <Overview
            rows={rows}
            station={name}
            period={label}
            timeZone={timeZone}
          />
        ) : tab === "history" ? (
          <HistoryTable
            key={`${device.device_id}:${start}:${end}`}
            rows={rows}
            timeZone={timeZone}
          />
        ) : (
          <MeasurementChart
            key={tab}
            rows={rows}
            keys={definition.keys}
            title={definition.label}
            station={name}
            period={label}
            timeZone={timeZone}
          />
        )}
      </div>
    </main>
  );
}

export default function App() {
  const [timeZone, setTimeZone] = useState(readTimeZone);
  const [settingsOpen, setSettingsOpen] = useState(false);
  function saveTimeZone(value) {
    setTimeZone(value);
    try {
      localStorage.setItem("casa.timeZone", value);
    } catch {
      /* Session preference still works. */
    }
  }
  const [selectedId, setSelectedId] = useState(null);
  const [revision, setRevision] = useState(0);
  const stations = usePolling(`stations:${revision}`, fetchStations, 30_000);
  const devices = stations.data?.devices || [];
  const selected =
    devices.find((device) => device.device_id === selectedId) || devices[0];
  const latest = stations.data?.latest.find(
    (row) => row.device_id === selected?.device_id,
  );
  return (
    <div className="app-shell">
      <header className="topbar">
        <div className="brand-group">
          <span
            className="account-placeholder"
            title="Acesso de usuários previsto para a V3"
            aria-label="Acesso de usuários previsto para a V3"
          >
            <UserRound size={19} />
          </span>
          <a
            href="#main"
            className="brand"
            aria-label="T2P — Tecnologia que cuida"
          >
            <img
              src={logo}
              className="brand-logo"
              alt="T2P — Tecnologia que cuida"
            />
          </a>
        </div>
        <span className="topbar-title">Interface de monitoramento</span>
        <div className="header-actions">
          <span className="project-badge">CASA</span>
          <button
            aria-label="Configurações"
            title="Configurações"
            onClick={() => setSettingsOpen(true)}
          >
            <Settings size={19} />
          </button>
        </div>
      </header>
      <div className="main-layout" id="main">
        {stations.status !== "success" ? (
          <div className="global-status">
            <StatusPanel
              status={stations.status}
              error={stations.error}
              onRetry={() => setRevision((value) => value + 1)}
            />
          </div>
        ) : !devices.length ? (
          <div className="global-status">
            <StatusPanel
              status="success"
              emptyTitle="Nenhuma estação cadastrada"
              emptyText="As estações aparecerão aqui quando forem cadastradas no servidor."
            />
          </div>
        ) : (
          <>
            <StationSelector
              devices={devices}
              selectedId={selected.device_id}
              onSelect={setSelectedId}
            />
            <StationData
              key={timeZone}
              device={selected}
              latest={latest}
              timeZone={timeZone}
            />
          </>
        )}
      </div>
      {settingsOpen && (
        <SettingsDialog
          timeZone={timeZone}
          onSave={saveTimeZone}
          onClose={() => setSettingsOpen(false)}
        />
      )}
    </div>
  );
}
