import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import "./index.css";
import App from "./App.jsx";
import AccountGate from "./features/AccountGate.jsx";

createRoot(document.getElementById("root")).render(
  <StrictMode>
    <AccountGate>{(user, logout) => <App key={user.id} user={user} onLogout={logout} />}</AccountGate>
  </StrictMode>,
);
