import { useEffect, useState } from "react";
import { isStationActive } from "../utils/stationStatus";

export default function StationStatus({ lastSeen }) {
  const [now, setNow] = useState(Date.now);
  useEffect(() => {
    const timer = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(timer);
  }, []);
  const active = isStationActive(lastSeen, now);
  return (
    <span
      className={`registration ${active ? "" : "inactive"}`}
      role="status"
      title="Ativa quando há comunicação nos últimos 6 minutos"
    >
      {active ? "Estação ativa" : "Estação inativa"}
    </span>
  );
}
