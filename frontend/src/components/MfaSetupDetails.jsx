import { QRCodeSVG } from "qrcode.react";

export default function MfaSetupDetails({ setup }) {
  return (
    <div className="mfa-setup">
      <p>Escaneie o QR Code com seu aplicativo autenticador. Depois informe o código de seis dígitos.</p>
      <div className="mfa-qr">
        <QRCodeSVG value={setup.uri} size={220} level="M" marginSize={4} title="QR Code para cadastrar o autenticador CASA" />
      </div>
      <p className="mfa-same-device">Se estiver usando este mesmo celular, use a chave manual abaixo.</p>
      <details>
        <summary>Não consigo escanear o QR Code</summary>
        <p>No autenticador, adicione uma conta por chave de configuração, do tipo baseado em tempo.</p>
        <code className="setup-key">{setup.secret}</code>
      </details>
    </div>
  );
}
