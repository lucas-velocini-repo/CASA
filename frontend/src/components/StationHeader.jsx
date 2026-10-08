import StationStatus from "./StationStatus";
import { formatTimestamp } from "../utils/dates";

export default function StationHeader({ device, latest, timeZone }) {
  const hasLocation =
    Number.isFinite(device.latitude) && Number.isFinite(device.longitude);

  return (
    <div className="station-header">
      <div>
        <span className="eyebrow">MONITORAMENTO AMBIENTAL</span>
        <h1>{device.name || device.device_id}</h1>
        <p>
          {hasLocation
            ? `Localização: ${device.latitude.toFixed(4)}, ${device.longitude.toFixed(4)}`
            : "Localização indisponível"}
        </p>
      </div>
      <div className="station-meta">
        <StationStatus lastSeen={device.last_seen || latest?.received_at} />
        <small>
          Última comunicação:{" "}
          {formatTimestamp(device.last_seen, false, timeZone)}
        </small>
        {hasLocation && (
          <small>
            {device.location_updated_at
              ? `Localização obtida em: ${formatTimestamp(device.location_updated_at, false, timeZone)}`
              : "Data da localização indisponível"}
          </small>
        )}
      </div>
    </div>
  );
}
