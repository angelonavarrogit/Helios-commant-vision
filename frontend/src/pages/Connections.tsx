// HELIOS COMMAND — Connections Center.
//
// Providers are grouped by category. Each connected account shows a rich status
// card (state, when it connected, last sync, last error) with Reconnect (for
// degraded states) and Disconnect actions. "Connect" starts the OAuth flow
// (backend returns the authorization URL; we redirect to the provider). The
// frontend never sees tokens or client secrets. Only real providers HELIOS can
// actually connect are listed — nothing is fabricated.

import { useCallback, useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";

import { connectionsApi } from "../api/endpoints";
import type { Connection, ConnectionStatus, Provider } from "../api/types";
import { StatusBadge } from "../components/StatusBadge";

// Friendly, human labels for provider categories.
const CATEGORY_LABELS: Record<string, string> = {
  email: "Correo",
  calendar: "Calendario",
  storage: "Almacenamiento",
  messaging: "Mensajería",
};

// States that warrant a "Reconnect" affordance (the token is no longer usable).
const RECONNECT_STATES: ReadonlySet<ConnectionStatus> = new Set<ConnectionStatus>([
  "expired",
  "error",
  "revoked",
  "reauth_required",
]);

function categoryLabel(category: string): string {
  return CATEGORY_LABELS[category] ?? category;
}

function formatWhen(iso: string | null): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "—";
  return d.toLocaleString("es-MX", {
    day: "2-digit",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function Connections() {
  const [providers, setProviders] = useState<Provider[]>([]);
  const [connections, setConnections] = useState<Connection[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
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
    setBusy(provider);
    try {
      const { authorization_url } = await connectionsApi.connect(provider);
      window.location.href = authorization_url; // hand off to the provider
    } catch {
      setError("No se pudo iniciar la conexión.");
      setBusy(null);
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

  // Group providers by category so the center reads as an organized catalog.
  const categories = Array.from(new Set(providers.map((p) => p.category)));

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold">Connections Center</h1>
        <p className="text-sm text-helios-muted">
          Conecta los servicios que HELIOS puede analizar. Todo el acceso es de solo lectura.
        </p>
      </div>

      {callbackStatus === "connected" && (
        <Banner tone="ok">Cuenta conectada correctamente.</Banner>
      )}
      {callbackStatus === "error" && (
        <Banner tone="danger">No se pudo completar la conexión. Intenta reconectar.</Banner>
      )}
      {error && <Banner tone="danger">{error}</Banner>}

      {providers.length === 0 && !error ? (
        <div className="rounded-xl border border-helios-border bg-helios-panel p-6 text-sm text-helios-muted">
          Cargando servicios disponibles…
        </div>
      ) : (
        categories.map((category) => (
          <section key={category} className="space-y-3">
            <h2 className="text-xs font-semibold uppercase tracking-widest text-helios-muted">
              {categoryLabel(category)}
            </h2>
            <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
              {providers
                .filter((p) => p.category === category)
                .map((provider) => {
                  const accounts = connections.filter((c) => c.provider === provider.provider);
                  return (
                    <ProviderCard
                      key={provider.provider}
                      provider={provider}
                      accounts={accounts}
                      busy={busy === provider.provider}
                      onConnect={() => void onConnect(provider.provider)}
                      onReconnect={() => void onConnect(provider.provider)}
                      onDisconnect={(id) => void onDisconnect(id)}
                    />
                  );
                })}
            </div>
          </section>
        ))
      )}
    </div>
  );
}

function ProviderCard({
  provider,
  accounts,
  busy,
  onConnect,
  onReconnect,
  onDisconnect,
}: {
  provider: Provider;
  accounts: Connection[];
  busy: boolean;
  onConnect: () => void;
  onReconnect: () => void;
  onDisconnect: (id: number) => void;
}) {
  return (
    <div className="rounded-xl border border-helios-border bg-helios-panel p-4">
      <div className="mb-2 flex items-center justify-between">
        <div className="font-medium">{provider.name}</div>
        <button
          onClick={onConnect}
          disabled={busy}
          className="rounded-md bg-helios-accent px-3 py-1 text-xs font-medium text-helios-bg disabled:opacity-50"
        >
          {busy ? "Abriendo…" : accounts.length > 0 ? "+ Añadir cuenta" : "+ Conectar"}
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
            <li key={account.id} className="rounded-md border border-helios-border px-3 py-2.5">
              <div className="flex items-center justify-between">
                <div className="truncate text-sm">{account.email_address}</div>
                <StatusBadge status={account.status} />
              </div>

              <dl className="mt-2 grid grid-cols-2 gap-x-3 gap-y-0.5 text-[11px] text-helios-muted">
                <dt>Conectada</dt>
                <dd className="text-right">{formatWhen(account.connected_at)}</dd>
                <dt>Última sincronización</dt>
                <dd className="text-right">{formatWhen(account.last_sync_at)}</dd>
              </dl>

              {account.last_error && (
                <div className="mt-2 text-[11px] text-helios-danger">{account.last_error}</div>
              )}

              <div className="mt-2 flex items-center justify-end gap-3 text-xs">
                {RECONNECT_STATES.has(account.status) && (
                  <button
                    onClick={onReconnect}
                    className="text-helios-warn hover:opacity-80"
                  >
                    Reconectar
                  </button>
                )}
                <button
                  onClick={() => onDisconnect(account.id)}
                  className="text-helios-muted hover:text-helios-danger"
                >
                  Desconectar
                </button>
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function Banner({ tone, children }: { tone: "ok" | "danger"; children: React.ReactNode }) {
  const cls =
    tone === "ok"
      ? "bg-helios-ok/15 text-helios-ok"
      : "bg-helios-danger/15 text-helios-danger";
  return <div className={`rounded-md px-4 py-2 text-sm ${cls}`}>{children}</div>;
}
