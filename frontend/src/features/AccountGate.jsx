import { useEffect, useRef, useState } from "react";
import { Eye, EyeOff } from "lucide-react";
import { apiRequest } from "../services/session";
import logo from "../../assets/t2p-logo.png";
import "../styles/accounts.css";
import MfaSetupDetails from "../components/MfaSetupDetails";

// Capture once, then remove account secrets from the address bar before any requests.
const initialAction = (() => {
  const params = new URLSearchParams(window.location.hash.slice(1));
  const kind = params.has("invite")
    ? "invite"
    : params.has("reset")
      ? "reset"
      : null;
  const token = kind ? params.get(kind) : "";
  if (kind) window.history.replaceState(null, "", window.location.pathname);
  return { kind, token };
})();

const MFA_REQUIRED_MESSAGE =
  "Informe um código de autenticação válido ou um código de recuperação.";

function login(credentials, mfaCode = "") {
  return apiRequest("/auth/login", {
    method: "POST",
    body: { ...credentials, mfa_code: mfaCode, client: "web" },
  });
}

function LoginPassword() {
  const [visible, setVisible] = useState(false);
  const Icon = visible ? EyeOff : Eye;
  const action = visible ? "Ocultar senha" : "Mostrar senha";
  return (
    <div className="account-password">
      <label htmlFor="login-password">Senha</label>
      <input
        id="login-password"
        name="password"
        type={visible ? "text" : "password"}
        autoComplete="current-password"
        maxLength={128}
        required
      />
      <button
        type="button"
        aria-label={action}
        title={action}
        aria-controls="login-password"
        onClick={() => setVisible((value) => !value)}
      >
        <Icon size={19} aria-hidden="true" />
      </button>
    </div>
  );
}

function AccountCard({ children }) {
  return (
    <main className="account-page">
      <section className="account-card">
        <img
          src={logo}
          alt="T2P — Tecnologia que cuida"
          className="account-logo"
        />
        {children}
      </section>
    </main>
  );
}

function MfaSetup({ onComplete }) {
  const [setup, setSetup] = useState(null);
  const [codes, setCodes] = useState(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  async function run(task) {
    setError("");
    setBusy(true);
    try {
      await task();
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <AccountCard>
      <h1>Proteja sua conta administrativa</h1>
      {codes ? (
        <>
          <p>
            Guarde os códigos de recuperação em um lugar seguro. Cada código
            funciona uma vez e permite entrar se você perder o autenticador.
          </p>
          <div className="recovery-codes">
            {codes.map((code) => (
              <code key={code}>{code}</code>
            ))}
          </div>
          <button onClick={onComplete}>
            Guardei os códigos. Ir para o login
          </button>
        </>
      ) : (
        <>
          <p>
            Adicione uma conta no seu aplicativo autenticador, como Google
            Authenticator ou Microsoft Authenticator.
          </p>
          {!setup ? (
            <button
              disabled={busy}
              onClick={() =>
                run(async () =>
                  setSetup(
                    await apiRequest("/auth/mfa/setup", { method: "POST" }),
                  ),
                )
              }
            >
              Configurar autenticador
            </button>
          ) : (
            <>
              <MfaSetupDetails setup={setup} />
              <form
                onSubmit={(event) => {
                  event.preventDefault();
                  const form = new FormData(event.currentTarget);
                  run(async () => {
                    const result = await apiRequest("/auth/mfa/enable", {
                      method: "POST",
                      body: { code: form.get("code") },
                    });
                    setCodes(result.recovery_codes);
                  });
                }}
              >
                <label>
                  Código do autenticador
                  <input
                    name="code"
                    inputMode="numeric"
                    autoComplete="one-time-code"
                    pattern="[0-9]{6}"
                    required
                    maxLength={6}
                  />
                </label>
                <button disabled={busy}>Ativar segundo fator</button>
              </form>
            </>
          )}
        </>
      )}
      {error && (
        <p role="alert" className="account-error">
          {error}
        </p>
      )}
    </AccountCard>
  );
}

export default function AccountGate({ children }) {
  const [session, setSession] = useState(null);
  const [checking, setChecking] = useState(!initialAction.kind);
  const [mode, setMode] = useState(initialAction.kind || "login");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);
  // The current API requires resending credentials with the second factor.
  const pendingLogin = useRef(null);
  const codeInput = useRef(null);
  useEffect(() => {
    if (mode === "mfa") codeInput.current?.focus();
  }, [mode]);
  useEffect(() => {
    const controller = new AbortController();
    if (!initialAction.kind)
      apiRequest("/auth/me", { signal: controller.signal })
        .then(setSession)
        .catch((e) => {
          if (e.name !== "AbortError") setSession(null);
        })
        .finally(() => {
          if (!controller.signal.aborted) setChecking(false);
        });
    const expired = () => {
      pendingLogin.current = null;
      setSession(null);
      setMode("login");
      setNotice("Entre para continuar.");
    };
    window.addEventListener("casa:session-expired", expired);
    return () => {
      controller.abort();
      window.removeEventListener("casa:session-expired", expired);
    };
  }, []);
  async function logout() {
    setError("");
    try {
      await apiRequest("/auth/logout", { method: "POST" });
      setSession(null);
    } catch (e) {
      setError(e.message);
    }
  }
  async function submit(event) {
    event.preventDefault();
    setError("");
    setNotice("");
    setBusy(true);
    const form = new FormData(event.currentTarget);
    try {
      if (mode === "login") {
        const credentials = { email: form.get("email"), password: form.get("password") };
        try {
          setSession(await login(credentials));
        } catch (e) {
          if (e.status !== 401 || e.message !== MFA_REQUIRED_MESSAGE) throw e;
          pendingLogin.current = credentials;
          setMode("mfa");
        }
      } else if (mode === "mfa") {
        setSession(await login(pendingLogin.current, form.get("mfa_code")));
        pendingLogin.current = null;
        setMode("login");
      } else if (mode === "forgot") {
        const result = await apiRequest("/auth/forgot-password", {
          method: "POST",
          body: { email: form.get("email") },
        });
        setNotice(result.message);
      } else {
        if (form.get("password") !== form.get("confirmation"))
          throw new Error("As senhas precisam ser iguais.");
        const result = await apiRequest(
          mode === "invite" ? "/auth/accept-invite" : "/auth/reset-password",
          {
            method: "POST",
            body: {
              token: initialAction.token,
              password: form.get("password"),
            },
          },
        );
        initialAction.token = "";
        setNotice(result.message);
        setMode("login");
      }
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }
  if (checking)
    return (
      <AccountCard>
        <p role="status">Verificando seu acesso…</p>
      </AccountCard>
    );
  if (session?.mfa_setup_required)
    return (
      <MfaSetup
        onComplete={() => {
          setSession(null);
          setMode("login");
        }}
      />
    );
  if (session)
    return (
      <>
        {error && (
          <p role="alert" className="account-error">
            {error}
          </p>
        )}
        {children(session.user, logout)}
      </>
    );
  const settingPassword = mode === "invite" || mode === "reset";
  const mfaStep = mode === "mfa";
  return (
    <AccountCard>
      <h1>
        {mode === "invite"
          ? "Ative sua conta"
          : mode === "reset"
            ? "Defina uma nova senha"
            : mode === "forgot"
              ? "Recupere seu acesso"
              : mfaStep
                ? "Confirme seu acesso"
                : "Entre no CASA"}
      </h1>
      <p>
        {mode === "login"
          ? "Acompanhe as estações vinculadas à sua conta."
          : settingPassword
            ? "Use uma senha com pelo menos 8 caracteres. Você pode usar uma frase."
            : mfaStep
              ? "Digite o código do seu autenticador ou use um código de recuperação."
              : "Informe o e-mail da sua conta para receber as instruções."}
      </p>
      <form onSubmit={submit} key={mode}>
        {!settingPassword && !mfaStep && (
          <label>
            E-mail
            <input
              name="email"
              type="email"
              autoComplete="username"
              required
              maxLength={254}
            />
          </label>
        )}
        {mode === "login" && <LoginPassword />}
        {settingPassword && (
          <label>
            Nova senha
            <input
              name="password"
              type="password"
              autoComplete="new-password"
              minLength={8}
              maxLength={128}
              required
            />
          </label>
        )}
        {settingPassword && (
          <label>
            Confirme a senha
            <input
              name="confirmation"
              type="password"
              autoComplete="new-password"
              required
              minLength={8}
              maxLength={128}
            />
          </label>
        )}
        {mfaStep && (
          <label>
            Código de autenticação
            <input
              ref={codeInput}
              name="mfa_code"
              autoComplete="one-time-code"
              autoCapitalize="none"
              spellCheck={false}
              required
              maxLength={64}
            />
          </label>
        )}
        {error && (
          <p className="account-error" role="alert">
            {error}
          </p>
        )}
        {notice && (
          <p className="account-notice" role="status">
            {notice}
          </p>
        )}
        <button disabled={busy}>
          {busy
            ? "Aguarde…"
            : mode === "login"
              ? "Entrar"
              : mode === "forgot"
                ? "Enviar instruções"
                : mfaStep
                  ? "Verificar código"
                  : "Salvar senha"}
        </button>
      </form>
      <button
        className="account-link"
        disabled={busy}
        onClick={() => {
          pendingLogin.current = null;
          setMode(mode === "login" ? "forgot" : "login");
          setError("");
          setNotice("");
        }}
      >
        {mode === "login" ? "Esqueci minha senha" : "Voltar para o login"}
      </button>
      {mode === "login" && (
        <small>
          Precisa de uma conta? Solicite um convite à equipe do projeto.
        </small>
      )}
    </AccountCard>
  );
}
