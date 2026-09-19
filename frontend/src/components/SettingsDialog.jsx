import { useEffect, useRef, useState } from "react";
import { X, Globe } from "lucide-react";
import { TIME_ZONE } from "../utils/dates";

const zones = [
  ...new Set([
    TIME_ZONE,
    "UTC",
    ...(Intl.supportedValuesOf?.("timeZone") || [
      "America/Manaus",
      "America/Rio_Branco",
      "Europe/Lisbon",
      "Europe/Oslo",
    ]),
  ]),
];

export default function SettingsDialog({ timeZone, onSave, onClose }) {
  const ref = useRef(null);
  const [draft, setDraft] = useState(timeZone);
  useEffect(() => {
    ref.current.showModal();
  }, []);
  return (
    <dialog
      className="settings-dialog"
      ref={ref}
      onCancel={onClose}
      onClick={(event) => {
        if (event.target === event.currentTarget) onClose();
      }}
    >
      <form
        onSubmit={(event) => {
          event.preventDefault();
          onSave(draft);
          onClose();
        }}
      >
        <div className="settings-heading">
          <h2>Configurações</h2>
          <button
            type="button"
            aria-label="Fechar configurações"
            onClick={onClose}
          >
            <X size={20} />
          </button>
        </div>
        <label htmlFor="time-zone">
          <Globe size={18} /> Fuso horário
        </label>
        <select
          id="time-zone"
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
        >
          {zones.map((zone) => (
            <option key={zone} value={zone}>
              {zone === TIME_ZONE
                ? "Brasília — America/Sao_Paulo (padrão)"
                : zone.replaceAll("_", " ")}
            </option>
          ))}
        </select>
        <p>
          Define os dias e horários dos filtros, gráficos, tabela e exportações.
          Os registros originais continuam armazenados em UTC.
        </p>
        <p>
          A preferência fica salva neste navegador. Ao trocar o fuso, o período
          será reiniciado para hoje no fuso escolhido.
        </p>
        <div className="settings-actions">
          <button type="button" onClick={onClose}>
            Cancelar
          </button>
          <button className="primary" type="submit">
            Salvar configurações
          </button>
        </div>
      </form>
    </dialog>
  );
}
