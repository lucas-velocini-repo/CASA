import test from "node:test";
import assert from "node:assert/strict";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { QRCodeSVG } from "qrcode.react";
import { createServer } from "vite";
import react from "@vitejs/plugin-react";

test("MFA setup renders the local authenticator URI as a QR code with manual fallback", async () => {
  const server = await createServer({configFile: false, plugins: [react()], server: {middlewareMode: true, hmr: false, ws: false}, optimizeDeps: {noDiscovery: true, entries: []}});
  try {
    const {default: Details} = await server.ssrLoadModule("/src/components/MfaSetupDetails.jsx");
    const setup = {secret: "TESTONLYJBSWY3DP", uri: "otpauth://totp/CASA:test%40example.com?secret=TESTONLYJBSWY3DP&issuer=CASA"};
    const html = renderToStaticMarkup(createElement(Details, {setup}));
    const qr = renderToStaticMarkup(createElement(QRCodeSVG, {value: setup.uri, size: 220, level: "M", marginSize: 4, title: "QR Code para cadastrar o autenticador CASA"}));
    assert.ok(html.includes(qr));
    assert.match(html, /<details>.*<summary>Não consigo escanear/s);
    assert.match(html, /TESTONLYJBSWY3DP/);
    assert.doesNotMatch(html, /<img|https:\/\//);
  } finally { await server.close(); }
});

test("dashboard puts logout last and makes administration an explicit button", async () => {
  const server = await createServer({configFile: false, plugins: [react()], server: {middlewareMode: true, hmr: false, ws: false}, optimizeDeps: {noDiscovery: true, entries: []}});
  try {
    const {default: App} = await server.ssrLoadModule("/src/App.jsx");
    const html = renderToStaticMarkup(createElement(App, {user: {name: "Teste", email: "test@example.com", role: "admin"}, onLogout() {}}));
    const header = html.match(/<header class="topbar">(.*?)<\/header>/s)[1];
    assert.doesNotMatch(header, /Interface de monitoramento/);
    assert.match(header, /class="account-nav" aria-pressed="false"/);
    assert.ok(header.indexOf('aria-label="Sair da conta"') > header.indexOf('aria-label="Configurações"'));
    assert.match(header, /aria-label="Sair da conta"[^]*<\/button><\/div>$/);
  } finally { await server.close(); }
});
