import test from "node:test";
import assert from "node:assert/strict";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { createServer } from "vite";
import react from "@vitejs/plugin-react";

test("GPS details appear in the header and cards keep only coordinates", async () => {
  const server = await createServer({
    configFile: false,
    plugins: [react()],
    server: { middlewareMode: true },
  });
  try {
    const { default: StationSelector } = await server.ssrLoadModule(
      "/src/components/StationSelector.jsx",
    );
    const { default: StationHeader } = await server.ssrLoadModule(
      "/src/components/StationHeader.jsx",
    );
    const device = {
      device_id: "CASA-000001", name: "Teste",
      latitude: 0, longitude: 0,
      location_updated_at: "2026-10-05T18:00:00Z",
      last_seen: "2026-10-05T17:55:00Z",
    };
    const renderCard = (station) => renderToStaticMarkup(createElement(
      StationSelector,
      { devices: [station], selectedId: station.device_id, onSelect() {} },
    ));
    const renderHeader = (station, timeZone) => renderToStaticMarkup(createElement(
      StationHeader,
      { device: station, latest: { timestamp: "2026-10-05T17:50:00Z" }, timeZone },
    ));
    const card = renderCard(device);
    assert.match(card, /0\.0000, 0\.0000/);
    assert.doesNotMatch(card, /Localização obtida em|05\/10\/2026/);
    const header = renderHeader(device, "America/Sao_Paulo");
    assert.match(header, /Localização: 0\.0000, 0\.0000/);
    assert.match(header, /class="station-meta".*Última comunicação:.*14:55.*Localização obtida em:.*15:00/);
    assert.doesNotMatch(header, /Última medição|14:50/);
    assert.match(renderHeader(device, "UTC"), /Localização obtida em:.*05\/10\/2026.*18:00/);
    assert.match(renderHeader({ ...device, location_updated_at: null }, "UTC"),
      /Data da localização indisponível/);
    const noLocation = { ...device, latitude: null, longitude: null };
    assert.match(renderCard(noLocation), /Localização indisponível/);
    const missing = renderHeader(noLocation, "UTC");
    assert.match(missing, /Localização indisponível/);
    assert.doesNotMatch(missing, /Localização obtida em/);
  } finally {
    await server.close();
  }
});
