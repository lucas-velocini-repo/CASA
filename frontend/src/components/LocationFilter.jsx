import { useId, useState } from "react";
import { Pencil } from "lucide-react";
import { locationLabel } from "../utils/location";
import LocationDialog from "./LocationDialog";
import MapsLink from "./MapsLink";

export default function LocationFilter({ deviceId, value, onChange, locations, onSaved }) {
  const fieldId = useId();
  const [editing, setEditing] = useState(false);
  const options = locations.data || [];
  const selected = options.find((location) => String(location.location_id) === value);

  return (
    <div className="location-field">
      <label htmlFor={fieldId}>Local da coleta</label>
      <div className="location-controls">
        {selected && (
          <button
            type="button"
            className="location-name-button"
            aria-label="Gerenciar local da coleta"
            aria-haspopup="dialog"
            title="Gerenciar local da coleta"
            onClick={() => setEditing(true)}
          >
            <Pencil size={15} aria-hidden="true" />
          </button>
        )}
        <select
          id={fieldId}
          value={value ?? "loading"}
          disabled={value === null}
          onChange={(event) => onChange(event.target.value)}
        >
          {value === null && <option value="loading">Carregando locais…</option>}
          <option value="">Todos os locais</option>
          {options.map((location) => (
            <option key={location.location_id} value={location.location_id}>
              {locationLabel(location)}
            </option>
          ))}
          {value && value !== "unknown" && !selected && (
            <option value={value}>Local selecionado</option>
          )}
          <option value="unknown">Local desconhecido</option>
        </select>
        {selected && <MapsLink latitude={selected.latitude} longitude={selected.longitude} />}
      </div>
      {locations.status === "error" && (
        <small role="status">Não foi possível listar os locais.</small>
      )}
      {editing && selected && (
        <LocationDialog
          deviceId={deviceId}
          location={selected}
          options={options}
          onSaved={onSaved}
          onClose={() => setEditing(false)}
        />
      )}
    </div>
  );
}
