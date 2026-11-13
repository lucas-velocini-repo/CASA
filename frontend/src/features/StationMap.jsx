import { useEffect, useRef, useState } from "react";
import { Focus, MapPin, X } from "lucide-react";
import { LngLatBounds, Map, Marker, NavigationControl, Popup, setWorkerUrl } from "maplibre-gl";
import workerUrl from "maplibre-gl/dist/maplibre-gl-worker.mjs?worker&url";
import { createPortal } from "react-dom";
import "maplibre-gl/dist/maplibre-gl.css";
import "../styles/station-map.css";
import logo from "../../assets/t2p-logo.png";
import { fetchJson } from "../services/api";
import { formatTimestamp } from "../utils/dates";

const apiKey = import.meta.env.VITE_MAPTILER_KEY;
setWorkerUrl(workerUrl);
const states = { active: "Ativa", inactive: "Inativa", old: "Antiga" };
const modes = ["Somente ativas", "Ativas e inativas", "Ativas, inativas e antigas"];
const enabled = Object.keys(states);
const point = (pin) => [pin.longitude, pin.latitude];

function fit(map, pins) {
  if (!pins.length) return;
  if (pins.length === 1) {
    map.jumpTo({ center: point(pins[0]), zoom: 16 });
    return;
  }
  const bounds = new LngLatBounds();
  pins.forEach((pin) => bounds.extend(point(pin)));
  map.fitBounds(bounds, { padding: 55, maxZoom: 16, duration: 0 });
}

function radius(pin) {
  if (!pin) return { type: "FeatureCollection", features: [] };
  const lat = pin.latitude * Math.PI / 180;
  const angular = 100 / 6371008.8;
  const coordinates = Array.from({ length: 65 }, (_, index) => {
    const bearing = index * Math.PI / 32;
    const y = Math.asin(Math.sin(lat) * Math.cos(angular) + Math.cos(lat) * Math.sin(angular) * Math.cos(bearing));
    const x = Math.atan2(Math.sin(bearing) * Math.sin(angular) * Math.cos(lat), Math.cos(angular) - Math.sin(lat) * Math.sin(y));
    return [pin.longitude + x * 180 / Math.PI, y * 180 / Math.PI];
  });
  return { type: "Feature", geometry: { type: "Polygon", coordinates: [coordinates] }, properties: {} };
}

function Details({ pin, timeZone, onVisit, onDismiss }) {
  const compact = Boolean(onDismiss);
  const format = (stamp) => formatTimestamp(stamp, false, timeZone);
  const visits = compact ? pin.visits.slice(0, 1) : pin.visits;
  return (
    <div className="station-map-details">
      <div className="station-map-details-heading">
        <h3>{pin.device_name}</h3>
        {onDismiss && (
          <button type="button" onClick={onDismiss} aria-label="Fechar card da estação">
            <X size={16} aria-hidden="true" />
          </button>
        )}
      </div>
      <p>{pin.name || "Local da coleta"} · {states[pin.status]}</p>
      <p>Última medição da estação: {format(pin.last_measurement)}</p>
      <h4>Períodos de coleta neste local</h4>
      <ul>
        {visits.map((visit) => (
          <li key={visit.start}>
            <span>{format(visit.start)}{visit.end !== visit.start && ` — ${format(visit.end)}`}</span>
            {!compact && <button type="button" onClick={() => onVisit(pin, visit)}>Abrir este período</button>}
          </li>
        ))}
      </ul>
      {compact && pin.visits.length > 1 && <p>Mais {pin.visits.length - 1} no painel</p>}
      <button className="primary" type="button" onClick={() => onVisit(pin, pin.visits[0])}>Ir para a estação</button>
    </div>
  );
}

export default function StationMap({ timeZone, onClose, onVisit }) {
  const dialog = useRef(null);
  const container = useRef(null);
  const map = useRef(null);
  const [ready, setReady] = useState(false);
  const [pins, setPins] = useState(null);
  const [error, setError] = useState("");
  const [mode, setMode] = useState(0);
  const [selectedId, select] = useState(null);
  const [popup] = useState(() => document.createElement("div"));
  const visible = (pins || []).filter((pin) => enabled.indexOf(pin.status) <= mode);
  const selected = visible.find((pin) => pin.area_id === selectedId);

  useEffect(() => {
    const node = dialog.current;
    node.showModal();
    return () => node.close();
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    fetchJson("/measurements/station-map", controller.signal).then(setPins).catch((err) => {
      if (!controller.signal.aborted) setError(err.message);
    });
    return () => controller.abort();
  }, []);

  useEffect(() => {
    if (!apiKey) return;
    let instance;
    try {
      instance = new Map({
        container: container.current, zoom: 4, center: [-49, -19],
        style: `https://api.maptiler.com/maps/streets-v4/style.json?key=${encodeURIComponent(apiKey)}`,
      });
    } catch {
      return;
    }
    map.current = instance;
    instance.addControl(new NavigationControl({ showCompass: false }));
    instance.on("error", () => {
      if (!instance.isStyleLoaded()) setError("Não foi possível carregar o mapa de ruas.");
    });
    instance.on("load", () => {
      instance.addSource("station-radius", { type: "geojson", data: radius() });
      instance.addLayer({ id: "station-radius-fill", type: "fill", source: "station-radius",
        paint: { "fill-color": "#006e6c", "fill-opacity": 0.17 } });
      instance.addLayer({ id: "station-radius-line", type: "line", source: "station-radius",
        paint: { "line-color": "#006e6c", "line-width": 2 } });
      setReady(true);
    });
    return () => {
      instance.remove();
      map.current = null;
    };
  }, []);

  useEffect(() => {
    if (!ready || !pins) return;
    const shown = pins.filter((pin) => enabled.indexOf(pin.status) <= mode);
    fit(map.current, shown);
    const markers = shown.map((pin) => {
      const button = document.createElement("button");
      button.type = "button";
      button.className = `station-map-pin ${pin.status}`;
      button.setAttribute("aria-label", `${pin.device_name} · ${pin.name || "Local da coleta"} · ${states[pin.status]}`);
      button.title = button.getAttribute("aria-label");
      button.addEventListener("click", () => select(pin.area_id));
      return new Marker({ element: button }).setLngLat(point(pin)).addTo(map.current);
    });
    return () => markers.forEach((marker) => marker.remove());
  }, [ready, pins, mode]);

  useEffect(() => {
    if (!ready || !map.current) return;
    const instance = map.current;
    instance.getSource("station-radius").setData(radius(selected));
    if (!selected) return;
    instance.panTo(point(selected), { duration: 200 });
    const overlay = new Popup({ closeButton: false, closeOnClick: false, maxWidth: "260px", offset: 12 })
      .setLngLat(point(selected)).setDOMContent(popup).addTo(instance);
    return () => overlay.remove();
  }, [ready, selected, popup]);

  return (
    <dialog ref={dialog} className="station-map-dialog" aria-labelledby="station-map-title" onCancel={onClose}>
      <div className="station-map-frame">
        <div className="station-map-main">
          <div ref={container} className="station-map-canvas" aria-label="Mapa de ruas das estações" />
          <a className="station-map-attribution" href="https://www.maptiler.com/" target="_blank" rel="noreferrer">
            <img src="https://api.maptiler.com/resources/logo.svg" alt="MapTiler" />
          </a>
          {error && <p className="map-loading" role="alert">{error}</p>}
          {!apiKey && <p className="map-loading">Mapa de ruas indisponível.</p>}
          {apiKey && !ready && !error && <p className="map-loading" role="status">Carregando mapa…</p>}
        </div>
        <aside className="station-map-sidebar">
          <header>
            <img src={logo} alt="T2P — Tecnologia que cuida" />
            <button type="button" onClick={onClose} aria-label="Fechar mapa"><X size={20} /></button>
          </header>
          <h2 id="station-map-title">Mapa das estações</h2>
          <fieldset>
            <legend>Exibir locais</legend>
            {modes.map((label, index) => (
              <label key={label}>
                <input type="radio" name="station-map-mode" checked={mode === index}
                  onChange={() => { setMode(index); select(null); }} />
                {label}
              </label>
            ))}
          </fieldset>
          <ul className="station-map-legend" aria-label="Legenda">
            {enabled.map((status) => <li key={status}><i className={status} />{states[status]}</li>)}
          </ul>
          <button type="button" disabled={!ready || !visible.length} onClick={() => fit(map.current, visible)}>
            <Focus size={16} /> Ajustar aos marcadores visíveis
          </button>
          {selected && <Details pin={selected} timeZone={timeZone} onVisit={onVisit} />}
          <ul className="station-map-list">
            {visible.map((pin) => (
              <li key={pin.area_id}>
                <button type="button" aria-pressed={selectedId === pin.area_id} onClick={() => select(pin.area_id)}>
                  <MapPin size={17} /><span><strong>{pin.device_name}</strong><small>{pin.name || states[pin.status]}</small></span>
                </button>
              </li>
            ))}
          </ul>
          {pins && !visible.length && <p>Nenhum local encontrado para este filtro.</p>}
        </aside>
      </div>
      {selected && createPortal(
        <Details pin={selected} timeZone={timeZone} onVisit={onVisit} onDismiss={() => select(null)} />,
        popup,
      )}
    </dialog>
  );
}
