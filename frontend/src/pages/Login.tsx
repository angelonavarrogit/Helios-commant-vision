// HELIOS COMMAND — owner login screen.

import { useState } from "react";
import { useNavigate } from "react-router-dom";

import { ApiError } from "../api/client";
import { useAuth } from "../auth/AuthContext";

export function Login() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      await login(username, password);
      navigate("/");
    } catch (err) {
      // Neutral message; never reveal which field was wrong.
      setError(err instanceof ApiError ? "Credenciales inválidas." : "No se pudo iniciar sesión.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-helios-bg text-helios-text">
      <form
        onSubmit={onSubmit}
        className="w-80 rounded-xl border border-helios-border bg-helios-panel p-6"
      >
        <div className="mb-6 text-center text-xl font-semibold">
          <span className="text-helios-accent">☀️</span> HELIOS COMMAND
        </div>

        <label className="mb-1 block text-sm text-helios-muted">Usuario</label>
        <input
          value={username}
          onChange={(e) => setUsername(e.target.value)}
          className="mb-4 w-full rounded-md border border-helios-border bg-helios-bg px-3 py-2 text-sm outline-none focus:border-helios-accent"
          autoComplete="username"
        />

        <label className="mb-1 block text-sm text-helios-muted">Contraseña</label>
        <input
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          className="mb-4 w-full rounded-md border border-helios-border bg-helios-bg px-3 py-2 text-sm outline-none focus:border-helios-accent"
          autoComplete="current-password"
        />

        {error && <div className="mb-4 text-sm text-helios-danger">{error}</div>}

        <button
          type="submit"
          disabled={busy}
          className="w-full rounded-md bg-helios-accent py-2 text-sm font-medium text-helios-bg disabled:opacity-60"
        >
          {busy ? "Entrando…" : "Entrar"}
        </button>
      </form>
    </div>
  );
}
