import test from "node:test";
import assert from "node:assert/strict";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { createServer } from "vite";
import react from "@vitejs/plugin-react";

test("station card shows GPS acquisition date in the selected timezone", async () => {
  const server = await createServer({
    configFile: false,
    plugins: [react()],
    server: { middlewareMode: true },
  });
  try {
    const { default: StationSelector } = await server.ssrLoadModule(
      "/src/components/StationSelector.jsx",
    );
    const device = {
      device_id: "CASA-000001", name: "Teste",
      latitude: 0, longitude: 0,
      location_updated_at: "2026-10-05T18:00:00Z",
    };
    const render = (station, timeZone) => renderToStaticMarkup(createElement(
      StationSelector,
      { devices: [station], selectedId: station.device_id, onSelect() {}, timeZone },
    ));
    assert.match(render(device, "America/Sao_Paulo"), /05\/10\/2026.*15:00/);
    assert.match(render(device, "UTC"), /05\/10\/2026.*18:00/);
    assert.match(render(device, "UTC"), /0\.0000, 0\.0000/);
    assert.match(render({ ...device, location_updated_at: null }, "UTC"),
      /Data da localização indisponível/);
    const missing = render({ ...device, latitude: null, longitude: null }, "UTC");
    assert.match(missing, /Localização indisponível/);
    assert.doesNotMatch(missing, /Localização obtida em/);
  } finally {
    await server.close();
  }
});
