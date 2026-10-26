import { useCallback, useState } from "react";
import { usePolling } from "../hooks/usePolling";
import { apiRequest } from "../services/session";

const labels = {
  "account.invited": "Convite criado",
  "account.invite.resent": "Convite reenviado",
  "account.updated": "Conta atualizada",
  "station.access.granted": "Acesso concedido",
  "station.access.revoked": "Acesso revogado",
  "station.updated": "Estação atualizada",
  "account.login": "Entrada na conta",
  "account.logout": "Saída da conta",
  "account.mfa.enabled": "Segundo fator ativado",
  "account.invite.completed": "Conta ativada",
  "account.reset.completed": "Senha redefinida",
  "station.provisioning.started": "Cadastro de estação iniciado",
  "station.provisioning.resumed": "Cadastro de estação retomado",
  "station.provisioning.restarted": "Cadastro pendente reiniciado",
  "station.provisioning.confirmed": "Cadastro de estação confirmado",
  "cli.admin.created": "Primeiro administrador criado",
  "cli.mfa.reset": "Segundo fator redefinido pela equipe",
};
const statusLabel = {
  active: "Ativa",
  pending: "Convite pendente",
  disabled: "Bloqueada",
};

export default function AdminPanel({ currentUser, devices, onChange }) {
  const [revision, setRevision] = useState(0);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);
  const loader = useCallback(async (signal) => {
    const [users, access, audit, mail] = await Promise.all(
      ["users", "access", "audit", "mail-status"].map((path) =>
        apiRequest(`/admin/${path}`, { signal }),
      ),
    );
    return { users, access, audit, mail };
  }, []);
  const state = usePolling(`admin:${revision}`, loader, 30_000);
  async function run(task, message) {
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await task();
      setNotice(message);
      setRevision((v) => v + 1);
      onChange();
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }
  const users = state.data?.users || [];
  const currentAccess = state.data?.access.filter((a) => !a.revoked_at) || [];
  return (
    <main className="admin-panel">
      <h1>Administração</h1>
      <p>Gerencie as contas e os períodos de acesso às estações.</p>
      {error && (
        <p role="alert" className="account-error">
          {error}
        </p>
      )}
      {notice && (
        <p role="status" className="account-notice">
          {notice}
        </p>
      )}
      {state.status === "error" && (
        <p role="alert">
          {state.error}
          <button onClick={() => setRevision((v) => v + 1)}>
            Tentar novamente
          </button>
        </p>
      )}
      <section className="admin-section">
        <h2>Convidar uma pessoa</h2>
        <form
          className="admin-form"
          onSubmit={(event) => {
            event.preventDefault();
            const form = event.currentTarget;
            const values = new FormData(form);
            run(async () => {
              await apiRequest("/admin/invitations", {
                method: "POST",
                body: Object.fromEntries(values),
              });
              form.reset();
            }, "Convite colocado na fila de envio.");
          }}
        >
          <label>
            Nome
            <input name="name" required maxLength={100} />
          </label>
          <label>
            E-mail
            <input name="email" type="email" required maxLength={254} />
          </label>
          <label>
            Perfil
            <select name="role">
              <option value="user">Usuário</option>
              <option value="admin">Administrador</option>
            </select>
          </label>
          <button disabled={busy}>Enviar convite</button>
        </form>
      </section>
      <section className="admin-section">
        <h2>Contas</h2>
        <div className="admin-table-scroll">
          <table>
            <thead>
              <tr>
                <th>Pessoa</th>
                <th>Perfil</th>
                <th>Situação</th>
                <th>Ações</th>
              </tr>
            </thead>
            <tbody>
              {users.map((user) => (
                <tr key={user.id}>
                  <td>
                    {user.name}
                    <small>{user.email}</small>
                  </td>
                  <td>
                    <select
                      aria-label={`Perfil de ${user.name}`}
                      value={user.role}
                      disabled={busy || user.id === currentUser.id}
                      onChange={(event) => {
                        const role = event.target.value;
                        if (
                          window.confirm(
                            `Alterar o perfil de ${user.name} para ${role === "admin" ? "administrador" : "usuário"}?`,
                          )
                        )
                          run(
                            () =>
                              apiRequest(`/admin/users/${user.id}`, {
                                method: "PATCH",
                                body: { role },
                              }),
                            "Perfil atualizado. As sessões anteriores foram encerradas.",
                          );
                      }}
                    >
                      <option value="user">Usuário</option>
                      <option value="admin">Administrador</option>
                    </select>
                  </td>
                  <td>{statusLabel[user.status]}</td>
                  <td>
                    {user.status === "pending" ? (
                      <button
                        disabled={busy}
                        onClick={() =>
                          run(
                            () =>
                              apiRequest(
                                `/admin/users/${user.id}/resend-invite`,
                                { method: "POST" },
                              ),
                            "Novo convite colocado na fila.",
                          )
                        }
                      >
                        Reenviar convite
                      </button>
                    ) : (
                      <button
                        disabled={busy || user.id === currentUser.id}
                        onClick={() => {
                          const status =
                            user.status === "disabled"
                              ? user.activated
                                ? "active"
                                : "pending"
                              : "disabled";
                          if (
                            window.confirm(
                              `${status === "disabled" ? "Bloquear" : "Reativar"} a conta de ${user.name}?`,
                            )
                          )
                            run(
                              () =>
                                apiRequest(`/admin/users/${user.id}`, {
                                  method: "PATCH",
                                  body: { status },
                                }),
                              "Conta atualizada.",
                            );
                        }}
                      >
                        {user.status === "disabled" ? "Reativar" : "Bloquear"}
                      </button>
                    )}
                    {user.status === "pending" && (
                      <button
                        disabled={busy}
                        onClick={() => {
                          if (
                            window.confirm(
                              `Cancelar o convite de ${user.name}?`,
                            )
                          )
                            run(
                              () =>
                                apiRequest(`/admin/users/${user.id}`, {
                                  method: "PATCH",
                                  body: { status: "disabled" },
                                }),
                              "Convite cancelado.",
                            );
                        }}
                      >
                        Cancelar convite
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
      <section className="admin-section">
        <h2>Vincular uma estação</h2>
        <p>
          O início é inclusivo e o fim é exclusivo. Os horários abaixo seguem o
          fuso deste dispositivo. Ao salvar um novo período para a mesma pessoa
          e estação, o vínculo anterior é substituído.
        </p>
        <form
          className="admin-form"
          onSubmit={(event) => {
            event.preventDefault();
            const values = new FormData(event.currentTarget);
            run(
              () =>
                apiRequest("/admin/access", {
                  method: "POST",
                  body: {
                    user_id: Number(values.get("user_id")),
                    device_id: Number(values.get("device_id")),
                    data_from: new Date(values.get("data_from")).toISOString(),
                    data_until: values.get("data_until")
                      ? new Date(values.get("data_until")).toISOString()
                      : null,
                  },
                }),
              "Acesso atualizado.",
            );
          }}
        >
          <label>
            Pessoa
            <select name="user_id" required defaultValue="">
              <option value="" disabled>
                Selecione
              </option>
              {users
                .filter((u) => u.role === "user" && u.status !== "disabled")
                .map((u) => (
                  <option key={u.id} value={u.id}>
                    {u.name} — {u.email}
                  </option>
                ))}
            </select>
          </label>
          <label>
            Estação
            <select name="device_id" required defaultValue="">
              <option value="" disabled>
                Selecione
              </option>
              {devices.map((d) => (
                <option key={d.id} value={d.id}>
                  {d.name} — {d.device_id}
                </option>
              ))}
            </select>
          </label>
          <label>
            Dados a partir de
            <input name="data_from" type="datetime-local" required />
          </label>
          <label>
            Dados até (opcional)
            <input name="data_until" type="datetime-local" />
          </label>
          <button disabled={busy}>Salvar vínculo</button>
        </form>
        <div className="admin-table-scroll">
          <table>
            <thead>
              <tr>
                <th>Pessoa</th>
                <th>Estação</th>
                <th>Período autorizado</th>
                <th>Ação</th>
              </tr>
            </thead>
            <tbody>
              {currentAccess.map((a) => (
                <tr key={a.id}>
                  <td>{users.find((u) => u.id === a.user_id)?.name}</td>
                  <td>{devices.find((d) => d.id === a.device_id)?.name}</td>
                  <td>
                    {new Date(a.data_from).toLocaleString("pt-BR")} até{" "}
                    {a.data_until
                      ? new Date(a.data_until).toLocaleString("pt-BR")
                      : "sem data final"}
                  </td>
                  <td>
                    <button
                      disabled={busy}
                      onClick={() => {
                        if (window.confirm("Revogar este acesso à estação?"))
                          run(
                            () =>
                              apiRequest(`/admin/access/${a.id}`, {
                                method: "DELETE",
                              }),
                            "Acesso revogado.",
                          );
                      }}
                    >
                      Revogar
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
      <section className="admin-section">
        <h2>Estações</h2>
        <p>Desativar uma estação faz o servidor recusar novas medições dela.</p>
        <div className="admin-table-scroll">
          <table>
            <thead>
              <tr>
                <th>Estação</th>
                <th>Recebimento de dados</th>
                <th>Ações</th>
              </tr>
            </thead>
            <tbody>
              {devices.map((d) => (
                <tr key={d.id}>
                  <td>
                    {d.name}
                    <small>{d.device_id}</small>
                  </td>
                  <td>{d.active ? "Habilitado" : "Desativado"}</td>
                  <td className="admin-actions">
                    <button
                      disabled={busy}
                      onClick={() => {
                        const name = window.prompt("Nome da estação", d.name);
                        if (name?.trim())
                          run(
                            () =>
                              apiRequest(`/admin/devices/${d.id}`, {
                                method: "PATCH",
                                body: { name: name.trim() },
                              }),
                            "Nome atualizado.",
                          );
                      }}
                    >
                      Renomear
                    </button>
                    <button
                      disabled={busy}
                      onClick={() => {
                        if (
                          window.confirm(
                            "Reiniciar apenas um cadastro pendente? Esta ação não pode ser aplicada a estações já configuradas ou com medições.",
                          )
                        )
                          run(
                            () =>
                              apiRequest(
                                `/admin/devices/${d.id}/restart-provisioning`,
                                { method: "POST" },
                              ),
                            "Cadastro pendente reiniciado. Conclua pelo aplicativo.",
                          );
                      }}
                    >
                      Recuperar cadastro pendente
                    </button>
                    <button
                      disabled={busy}
                      onClick={() => {
                        if (
                          window.confirm(
                            `${d.active ? "Desativar" : "Reativar"} o recebimento de dados de ${d.name}?`,
                          )
                        )
                          run(
                            () =>
                              apiRequest(`/admin/devices/${d.id}`, {
                                method: "PATCH",
                                body: { active: !d.active },
                              }),
                            "Estação atualizada.",
                          );
                      }}
                    >
                      {d.active ? "Desativar" : "Reativar"}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
      <section className="admin-section">
        <h2>Envio de e-mails</h2>
        <p>
          {state.data?.mail.filter((j) =>
            ["pending", "processing"].includes(j.status),
          ).length || 0}{" "}
          na fila ·{" "}
          {state.data?.mail.filter((j) => j.status === "failed").length || 0}{" "}
          com falha ·{" "}
          {state.data?.mail.filter((j) => j.status === "sent").length || 0}{" "}
          enviados (últimos 100 envios)
        </p>
      </section>
      <section className="admin-section">
        <h2>Atividade recente</h2>
        <div className="admin-table-scroll">
          <table>
            <thead>
              <tr>
                <th>Data</th>
                <th>Pessoa</th>
                <th>Ação</th>
                <th>Referência</th>
              </tr>
            </thead>
            <tbody>
              {state.data?.audit.map((e) => (
                <tr key={e.id}>
                  <td>{new Date(e.created_at).toLocaleString("pt-BR")}</td>
                  <td>
                    {users.find((u) => u.id === e.actor_id)?.name ||
                      "Manutenção na VM"}
                  </td>
                  <td>{labels[e.action] || "Alteração administrativa"}</td>
                  <td>{e.target}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <small>Exibindo as últimas 100 ações.</small>
      </section>
    </main>
  );
}
