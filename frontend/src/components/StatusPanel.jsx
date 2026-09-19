import { Database, LoaderCircle, CircleAlert } from "lucide-react";

export default function StatusPanel({
  status,
  error,
  onRetry,
  emptyTitle = "Sem medições neste período",
  emptyText = "Escolha outro intervalo para consultar o histórico desta estação.",
}) {
  const Icon =
    status === "loading"
      ? LoaderCircle
      : status === "error"
        ? CircleAlert
        : Database;
  return (
    <div
      className={`status-panel ${status}`}
      role={status === "error" ? "alert" : "status"}
    >
      <Icon size={28} className={status === "loading" ? "spin" : ""} />
      <h3>
        {status === "loading"
          ? "Carregando dados"
          : status === "error"
            ? "Não foi possível carregar os dados"
            : emptyTitle}
      </h3>
      <p>
        {status === "loading"
          ? "Consultando todos os registros do período selecionado…"
          : status === "error"
            ? error
            : emptyText}
      </p>
      {status === "error" && onRetry && (
        <button onClick={onRetry}>Tentar novamente</button>
      )}
    </div>
  );
}
