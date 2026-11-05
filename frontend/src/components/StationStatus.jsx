import { useEffect, useState } from "react";
import { isStationActive, activityWindowMs } from "../utils/stationStatus";

export default function StationStatus({ lastSeen, intervalSeconds }) {
  const [now, setNow] = useState(Date.now);
  useEffect(() => {
    const timer = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(timer);
  }, []);
  const active = isStationActive(lastSeen, now, intervalSeconds);
  return (
    <span
      className={`registration ${active ? "" : "inactive"}`}
      role="status"
      title={`Ativa quando há comunicação nos últimos ${Math.round(activityWindowMs(intervalSeconds) / 60000)} minutos`}
    >
      {active ? "Estação ativa" : "Estação inativa"}
    </span>
  );
}
