import { useEffect, useRef, useState } from "react";
import { RadioTower, Search, MapPin, Map } from "lucide-react";

export default function StationSelector({ devices, selectedId, onSelect, onOpenMap }) {
  const [search, setSearch] = useState("");
  const list = useRef(null);
  const filtered = devices.filter((device) =>
    `${device.name} ${device.device_id}`
      .toLocaleLowerCase("pt-BR")
      .includes(search.toLocaleLowerCase("pt-BR")),
  );
  useEffect(() => {
    const element = list.current;
    if (element.scrollWidth <= element.clientWidth) return;
    const card = element.querySelector(".selected");
    if (!card) return;
    const bounds = element.getBoundingClientRect();
    const selected = card.getBoundingClientRect();
    if (selected.left < bounds.left) element.scrollLeft += selected.left - bounds.left - 4;
    else if (selected.right > bounds.right) element.scrollLeft += selected.right - bounds.right + 4;
  }, [selectedId, search]);

  return (
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
        <div className="station-list" ref={list}>
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
        {onOpenMap && (
          <button type="button" className="station-map-button" onClick={onOpenMap}>
            <Map size={17} aria-hidden="true" /> Buscar no mapa
          </button>
        )}
        <div className="sidebar-footer">
          <span className="eyebrow">PROJETO CASA</span>
          <p>Monitoramento ambiental</p>
        </div>
      </aside>
  );
}
