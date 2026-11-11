import { MapPin } from "lucide-react";

export default function MapsLink({ latitude, longitude }) {
  const query = encodeURIComponent(`${latitude},${longitude}`);
  return (
    <a
      className="maps-link"
      href={`https://www.google.com/maps/search/?api=1&query=${query}`}
      target="_blank"
      rel="noopener noreferrer"
      aria-label="Abrir localização no Google Maps (nova aba ou aplicativo)"
      title="Abrir no Google Maps"
    >
      <MapPin size={15} aria-hidden="true" />
    </a>
  );
}
