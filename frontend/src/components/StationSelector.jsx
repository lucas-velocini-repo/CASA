import { useState } from "react";
import { RadioTower, Search, MapPin } from "lucide-react";

export default function StationSelector({ devices, selectedId, onSelect }) {
  const [search, setSearch] = useState("");
  const filtered = devices.filter((device) =>
    `${device.name} ${device.device_id}`
      .toLocaleLowerCase("pt-BR")
      .includes(search.toLocaleLowerCase("pt-BR")),
  );
  return (
    <>
      <div className="mobile-stations">
        <label htmlFor="station-mobile">Estação</label>
        <select
          id="station-mobile"
          value={selectedId || ""}
          onChange={(event) => onSelect(event.target.value)}
        >
          {devices.map((device) => (
            <option key={device.device_id} value={device.device_id}>
              {device.name || device.device_id}
            </option>
          ))}
        </select>
      </div>
      <aside className="sidebar" aria-label="Estações">
        <div className="sidebar-heading">
          <h2>Estações</h2>
          <span>{devices.length}</span>
        </div>
        <label className="search">
          <Search size={17} />
          <input
            type="search"
            aria-label="Buscar estação"
            placeholder="Buscar estação…"
            value={search}
            onChange={(event) => setSearch(event.target.value)}
          />
        </label>
        <div className="station-list">
          {filtered.map((device) => (
            <button
              key={device.device_id}
              className={`station-card ${selectedId === device.device_id ? "selected" : ""}`}
              aria-pressed={selectedId === device.device_id}
              onClick={() => onSelect(device.device_id)}
            >
              <span className="station-icon">
                <RadioTower size={21} />
              </span>
              <span className="station-description">
                <strong>{device.name || device.device_id}</strong>
                <small>
                  <MapPin size={12} />
                  {Number.isFinite(device.latitude) &&
                  Number.isFinite(device.longitude)
                    ? `${device.latitude.toFixed(4)}, ${device.longitude.toFixed(4)}`
                    : "Localização indisponível"}
                </small>
              </span>
            </button>
          ))}
        </div>
        {!filtered.length && (
          <p className="muted">Nenhuma estação encontrada.</p>
        )}
        <div className="sidebar-footer">
          <span className="eyebrow">PROJETO CASA</span>
          <p>Monitoramento ambiental</p>
        </div>
      </aside>
    </>
  );
}
