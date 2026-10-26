const base = (import.meta.env?.VITE_API_BASE_URL || "/api").replace(/\/$/, "");

function csrfToken() {
  for (const item of document.cookie.split(";")) {
    const [key, ...value] = item.trim().split("=");
    if (key === "__Host-casa_csrf" || key === "casa_csrf")
      return decodeURIComponent(value.join("="));
  }
  return "";
}

export async function apiRequest(path, { method = "GET", body, signal } = {}) {
  const response = await fetch(`${base}${path}`, {
    method,
    signal,
    credentials: "same-origin",
    cache: "no-store",
    headers: {
      ...(body === undefined ? {} : { "Content-Type": "application/json" }),
      ...(!["GET", "HEAD"].includes(method)
        ? { "X-CSRF-Token": csrfToken() }
        : {}),
    },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  const data = await response.json().catch(() => null);
  if (!response.ok) {
    if (response.status === 401 && path !== "/auth/login")
      window.dispatchEvent(new Event("casa:session-expired"));
    const detail = typeof data?.detail === "string" ? data.detail : null;
    throw new Error(
      detail ||
        `Não foi possível concluir a solicitação (HTTP ${response.status}).`,
    );
  }
  return data;
}
