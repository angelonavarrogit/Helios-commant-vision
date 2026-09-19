// HELIOS COMMAND — Connections page.
//
// Lists available providers and the user's connected accounts. "Connect" starts
// the OAuth flow (backend returns the authorization URL; we redirect the
// browser to the provider). "Disconnect" revokes the stored token server-side.
// The frontend never sees tokens or client secrets.

import { useCallback, useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";

import { connectionsApi } from "../api/endpoints";
import type { Connection, Provider } from "../api/types";
import { StatusBadge } from "../components/StatusBadge";

export function Connections() {
  const [providers, setProviders] = useState<Provider[]>([]);
  const [connections, setConnections] = useState<Connection[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [params] = useSearchParams();

  const reload = useCallback(async () => {
    try {
      const [p, c] = await Promise.all([connectionsApi.providers(), connectionsApi.list()]);
      setProviders(p);
      setConnections(c);
    } catch {
      setError("No se pudieron cargar las conexiones.");
    }
  }, []);

  useEffect(() => {
    void reload();
  }, [reload]);

  // Surface the callback result (?status=connected|error) after OAuth returns.
  const callbackStatus = params.get("status");

  async function onConnect(provider: string) {
    setError(null);
    try {
      const { authorization_url } = await connectionsApi.connect(provider);
      window.location.href = authorization_url; // hand off to the provider
    } catch {
      setError("No se pudo iniciar la conexión.");
    }
  }

  async function onDisconnect(id: number) {
    setError(null);
    try {
      await connectionsApi.disconnect(id);
      await reload();
    } catch {
      setError("No se pudo desconectar la cuenta.");
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold">Connections</h1>
        <p className="text-sm text-helios-muted">
          Conecta los servicios que HELIOS puede analizar (solo lectura).
        </p>
      </div>

      {callbackStatus === "connected" && (
        <div className="rounded-md bg-helios-ok/15 px-4 py-2 text-sm text-helios-ok">
          Cuenta conectada correctamente.
        </div>
      )}
      {callbackStatus === "error" && (
        <div className="rounded-md bg-helios-danger/15 px-4 py-2 text-sm text-helios-danger">
          No se pudo completar la conexión. Intenta reconectar.
        </div>
      )}
      {error && (
        <div className="rounded-md bg-helios-danger/15 px-4 py-2 text-sm text-helios-danger">
          {error}
        </div>
      )}

      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        {providers.map((provider) => {
          const accounts = connections.filter((c) => c.provider === provider.provider);
          return (
            <div
              key={provider.provider}
              className="rounded-xl border border-helios-border bg-helios-panel p-4"
            >
              <div className="mb-2 flex items-center justify-between">
                <div className="font-medium">{provider.name}</div>
                <button
                  onClick={() => void onConnect(provider.provider)}
                  className="rounded-md bg-helios-accent px-3 py-1 text-xs font-medium text-helios-bg"
                >
                  + Conectar
                </button>
              </div>

              <div className="mb-3 text-xs text-helios-muted">
                Permisos: {provider.capabilities.join(", ") || "—"}
              </div>

              {accounts.length === 0 ? (
                <div className="text-sm text-helios-muted">No conectado.</div>
              ) : (
                <ul className="space-y-2">
                  {accounts.map((account) => (
                    <li
                      key={account.id}
                      className="flex items-center justify-between rounded-md border border-helios-border px-3 py-2"
                    >
                      <div>
                        <div className="text-sm">{account.email_address}</div>
                        <StatusBadge status={account.status} />
                      </div>
                      <button
                        onClick={() => void onDisconnect(account.id)}
                        className="text-xs text-helios-muted hover:text-helios-danger"
                      >
                        Desconectar
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
