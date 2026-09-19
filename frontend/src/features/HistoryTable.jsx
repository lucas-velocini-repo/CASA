import { useState } from "react";
import { ChevronLeft, ChevronRight } from "lucide-react";
import { metrics, formatValue } from "../utils/metrics";
import { formatTimestamp } from "../utils/dates";

const PAGE_SIZE = 50;
export default function HistoryTable({ rows, timeZone }) {
  const [page, setPage] = useState(0);
  const pages = Math.max(1, Math.ceil(rows.length / PAGE_SIZE));
  const current = Math.min(page, pages - 1);
  const keys = Object.keys(metrics);
  const visible = rows.slice(current * PAGE_SIZE, (current + 1) * PAGE_SIZE);
  return (
    <section className="history-card">
      <div className="section-heading">
        <h2>Dados históricos</h2>
        <span>
          {rows.length.toLocaleString("pt-BR")} registros · ordem cronológica
        </span>
      </div>
      <p className="muted">
        A exportação CSV inclui todas as páginas e a precisão original dos
        valores.
      </p>
      <div
        className="table-scroll"
        tabIndex={0}
        role="region"
        aria-label="Tabela de medições; role horizontalmente para ver todas as variáveis"
      >
        <table>
          <caption className="sr-only">Medições do período selecionado</caption>
          <thead>
            <tr>
              <th scope="col">Data e hora</th>
              {keys.map((key) => (
                <th scope="col" key={key}>
                  {metrics[key].label}
                  <small>{metrics[key].unit}</small>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {visible.map((row) => (
              <tr key={row.measurement_id}>
                <th scope="row">
                  {formatTimestamp(row.timestamp, false, timeZone)}
                </th>
                {keys.map((key) => (
                  <td key={key}>{formatValue(row.values?.[key], 5)}</td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="pagination">
        <span>
          {current * PAGE_SIZE + 1}–
          {Math.min((current + 1) * PAGE_SIZE, rows.length)} de{" "}
          {rows.length.toLocaleString("pt-BR")}
        </span>
        <div>
          <button
            aria-label="Página anterior"
            disabled={current === 0}
            onClick={() => setPage(current - 1)}
          >
            <ChevronLeft size={17} />
          </button>
          <span>
            Página {current + 1} de {pages}
          </span>
          <button
            aria-label="Próxima página"
            disabled={current + 1 >= pages}
            onClick={() => setPage(current + 1)}
          >
            <ChevronRight size={17} />
          </button>
        </div>
      </div>
    </section>
  );
}
