import { useEffect, useId, useRef, useState } from "react";
import { X } from "lucide-react";
import { saveLocationName, updateLocationLink } from "../services/api";
import { locationLabel } from "../utils/location";

export default function LocationDialog({ deviceId, location, options, onSaved, onClose }) {
  const ref = useRef(null);
  const input = useRef(null);
  const titleId = useId();
  const nameId = useId();
  const relatedId = useId();
  const [name, setName] = useState(location.name || "");
  const [related, setRelated] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const candidates = options.filter((option) => option.location_id !== location.location_id && !option.grouped);

  useEffect(() => {
    const dialog = ref.current;
    dialog.showModal();
    input.current.focus();
    return () => dialog.close();
  }, []);

  async function changeLocation(request, refreshHistory = false) {
    if (busy) return;
    setBusy(true);
    setError("");
    try {
      const result = await request();
      onSaved(result.location_id, refreshHistory);
      onClose();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  function save(event) {
    event.preventDefault();
    const draft = name.trim();
    if (related && !draft) {
      setError("Informe um nome para o grupo de locais.");
      input.current?.focus();
      return;
    }
    changeLocation(() => related
      ? updateLocationLink(deviceId, location.location_id, related, draft)
      : saveLocationName(deviceId, location.location_id, draft || null), Boolean(related));
  }

  return (
    <dialog
      ref={ref}
      className="settings-dialog location-dialog"
      aria-labelledby={titleId}
      onCancel={(event) => {
        event.preventDefault();
        if (!busy) onClose();
      }}
    >
      <form onSubmit={save}>
        <div className="settings-heading">
          <h2 id={titleId}>Gerenciar local da coleta</h2>
          <button type="button" aria-label="Fechar" onClick={onClose} disabled={busy}>
            <X size={20} aria-hidden="true" />
          </button>
        </div>
        <label htmlFor={nameId}>{related || location.grouped ? "Nome do grupo" : "Nome do local"}</label>
        <input
          ref={input}
          id={nameId}
          type="text"
          maxLength={80}
          value={name}
          onChange={(event) => setName(event.target.value)}
          readOnly={busy}
        />
        {candidates.length > 0 && (
          <>
            <label htmlFor={relatedId}>Vincular a outro local</label>
            <select
              id={relatedId}
              value={related}
              onChange={(event) => setRelated(event.target.value)}
              disabled={busy}
            >
              <option value="">Selecione um local</option>
              {candidates.map((option) => (
                <option key={option.location_id} value={option.location_id}>
                  {locationLabel(option)}
                </option>
              ))}
            </select>
          </>
        )}
        {location.links?.length > 0 && (
          <div className="linked-locations">
            <h3>Locais vinculados</h3>
            <ul>
              {location.links.map((child) => (
                <li key={child.location_id}>
                  <span>{locationLabel(child)}</span>
                  <button
                    type="button"
                    disabled={busy}
                    onClick={() => changeLocation(() => updateLocationLink(
                      deviceId, location.location_id, child.location_id,
                    ), true)}
                  >
                    Desvincular
                  </button>
                </li>
              ))}
            </ul>
          </div>
        )}
        {error && <small className="error-text" role="alert">{error}</small>}
        <div className="settings-actions">
          <button type="button" onClick={onClose} disabled={busy}>Cancelar</button>
          <button type="submit" className="primary" disabled={busy}>
            {related ? "Salvar vínculo" : "Salvar nome"}
          </button>
        </div>
      </form>
    </dialog>
  );
}
