import { lazy, Suspense, useCallback, useState } from "react";
import { Download, RefreshCw, Settings, LogOut, ShieldCheck, LayoutDashboard } from "lucide-react";
import AdminPanel from "./features/AdminPanel";
import SettingsDialog from "./components/SettingsDialog";
import { readTimeZone } from "./utils/settings";
import logo from "../assets/t2p-logo.png";
import StationHeader from "./components/StationHeader";
import StationSelector from "./components/StationSelector";
import PeriodFilter from "./components/PeriodFilter";
import LocationFilter from "./components/LocationFilter";
import StatusPanel from "./components/StatusPanel";
import Overview from "./features/Overview";
import HistoryTable from "./features/HistoryTable";
import MeasurementChart from "./features/MeasurementChart";
import ParticulateReadingChart from "./features/ParticulateReadingChart";
import { usePolling } from "./hooks/usePolling";
import { fetchHistory, fetchLocations, fetchStations } from "./services/api";
import { tabs, exportKeys } from "./utils/metrics";
import {
  initialPeriod,
  periodBounds,
  periodLabel,
  today,
} from "./utils/dates";
import { exportCsv } from "./utils/export";
import "./styles/dashboard.css";

const StationMap = lazy(() => import("./features/StationMap"));

function StationData({ device, timeZone, mapSelection }) {
  const [period, setPeriod] = useState(() => mapSelection?.period || initialPeriod(timeZone));
  const [tab, setTab] = useState("overview");
  const [revision, setRevision] = useState(0);
  const [locationRevision, setLocationRevision] = useState(0);
  const [locationsByStation, setLocationsByStation] = useState({});
  const deviceId = device.device_id;
  const loadLocations = useCallback((signal) => fetchLocations(deviceId, signal), [deviceId]);
  const locations = usePolling(
    `locations:${deviceId}`, loadLocations, 60_000, `${revision}:${locationRevision}`,
  );
  const latestLocationId = locations.data?.[0]?.location_id;
  const defaultLocationId = device.location_pending ? "unknown" : locations.status === "loading" ? null : String(latestLocationId ?? "");
  const locationId = locationsByStation[deviceId] ?? (
    mapSelection?.deviceId === deviceId ? mapSelection.locationId : defaultLocationId
  );
  const { start, end } = periodBounds(period, timeZone);
  const load = useCallback(
    (signal) => fetchHistory(deviceId, { start, end, locationId }, signal),
    [deviceId, start, end, locationId],
  );
  const requestKey = locationId === null ? null : `${deviceId}:${start}:${end}:${locationId}:${revision}`;
  const history = usePolling(requestKey, load, 60_000);
  const rows = history.data || [];
  const definition = tabs.find((item) => item.id === tab);
  const label = periodLabel(period);
  const name = device.name || device.device_id;
  return (
    <main className="content-area">
      <StationHeader device={device} timeZone={timeZone} />
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
        <PeriodFilter value={period} onApply={setPeriod} timeZone={timeZone}>
          <LocationFilter
            key={deviceId}
            deviceId={deviceId}
            value={locationId}
            onChange={(value) => setLocationsByStation((previous) => ({ ...previous, [deviceId]: value }))}
            locations={locations}
            onSaved={(savedLocationId, refreshHistory) => {
              setLocationsByStation((previous) => ({ ...previous, [deviceId]: String(savedLocationId) }));
              if (refreshHistory) setRevision((value) => value + 1);
              else setLocationRevision((value) => value + 1);
            }}
          />
        </PeriodFilter>
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
                  `${name}_${tab}_${period.startDate}_${period.endDate}${locationId ? `_local-${locationId}` : ""}`,
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
            key={`${deviceId}:${start}:${end}:${locationId}`}
            rows={rows}
            timeZone={timeZone}
          />
        ) : (
          <>
            <MeasurementChart
              key={tab}
              rows={rows}
              keys={definition.keys}
              title={definition.label}
              station={name}
              period={label}
              timeZone={timeZone}
            />
            {(tab === "pm" || tab === "nc") && (
              <div className="particulate-tab-day">
                <ParticulateReadingChart key={tab} rows={rows} station={name} timeZone={timeZone} kind={tab.toUpperCase()} />
              </div>
            )}
          </>
        )}
      </div>
    </main>
  );
}

export default function App({ user, onLogout }) {
  const [adminOpen, setAdminOpen] = useState(false);
  const [timeZone, setTimeZone] = useState(readTimeZone);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [mapOpen, setMapOpen] = useState(false);
  const [mapSelection, setMapSelection] = useState(null);
  function saveTimeZone(value) {
    setTimeZone(value);
    try {
      localStorage.setItem("casa.timeZone", value);
    } catch {
      /* Session preference still works. */
    }
  }
  const stationPreference = `casa.station.${user.id}`;
  const [selectedId, setSelectedId] = useState(() => {
    try {
      return localStorage.getItem(stationPreference);
    } catch {
      return null;
    }
  });
  function selectStation(id) {
    setSelectedId(id);
    try {
      localStorage.setItem(stationPreference, id);
    } catch {
      /* Session preference still works. */
    }
  }
  function openVisit(pin, visit) {
    selectStation(pin.device_id);
    const day = (stamp) => today(new Date(stamp), timeZone);
    const hour = (stamp) => new Intl.DateTimeFormat("pt-BR", {
      timeZone, hour: "2-digit", minute: "2-digit", hourCycle: "h23",
    }).format(new Date(stamp));
    setMapSelection((previous) => ({
      key: (previous?.key || 0) + 1,
      deviceId: pin.device_id,
      locationId: String(pin.location_id),
      period: {
        startDate: day(visit.start), endDate: day(visit.end),
        startTime: hour(visit.start), endTime: hour(visit.end), useTime: true,
      },
    }));
    setMapOpen(false);
  }
  const [revision, setRevision] = useState(0);
  const stations = usePolling(`stations:${revision}`, fetchStations, 30_000);
  const devices = stations.data?.devices || [];
  const selected =
    devices.find((device) => device.device_id === selectedId) || devices[0];
  return (
    <div className="app-shell">
      <header className="topbar">
        <div className="brand-group">
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
        <div className="header-actions">
          <span className="account-name" title={user.email}>{user.name}</span>
          {user.role === "admin" && <button className="account-nav" aria-pressed={adminOpen} onClick={() => setAdminOpen(v => !v)}>{adminOpen ? <LayoutDashboard size={17} /> : <ShieldCheck size={17} />}{adminOpen ? "Monitoramento" : "Administração"}</button>}
          <span className="project-badge">CASA</span>
          <button
            aria-label="Configurações"
            title="Configurações"
            onClick={() => setSettingsOpen(true)}
          >
            <Settings size={19} />
          </button>
          <button aria-label="Sair da conta" title="Sair da conta" onClick={onLogout}><LogOut size={19} /></button>
        </div>
      </header>
      <div className="main-layout" id="main">
        {adminOpen ? <AdminPanel currentUser={user} devices={devices} onChange={() => setRevision(v => v + 1)} /> : stations.status !== "success" ? (
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
              emptyTitle={user.role === "admin" ? "Nenhuma estação cadastrada" : "Nenhuma estação vinculada"}
              emptyText={user.role === "admin" ? "Cadastre uma estação pelo aplicativo de configuração." : "A equipe do projeto pode vincular as estações à sua conta."}
            />
          </div>
        ) : (
          <>
            <StationSelector
              devices={devices}
              selectedId={selected.device_id}
              onSelect={selectStation}
              onOpenMap={() => setMapOpen(true)}
            />
            <StationData
              key={`${timeZone}:${mapSelection?.key || 0}`}
              device={selected}
              timeZone={timeZone}
              mapSelection={mapSelection}
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
      {mapOpen && (
        <Suspense fallback={<p className="map-loading" role="status">Carregando mapa…</p>}>
          <StationMap timeZone={timeZone} onClose={() => setMapOpen(false)} onVisit={openVisit} />
        </Suspense>
      )}
    </div>
  );
}
