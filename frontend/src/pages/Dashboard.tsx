// HELIOS COMMAND — minimal dashboard: system status + connections summary.
//
// Connection counts come from the real API. System status is a lightweight
// health probe; richer intelligence panels arrive in later phases.

import { useEffect, useState } from "react";

import { api } from "../api/client";
import { connectionsApi } from "../api/endpoints";
import type { Connection } from "../api/types";

export function Dashboard() {
  const [connections, setConnections] = useState<Connection[] | null>(null);
  const [coreOk, setCoreOk] = useState<boolean | null>(null);

  useEffect(() => {
    connectionsApi.list().then(setConnections).catch(() => setConnections([]));
    fetch(`${api.baseUrl}/health`)
      .then((r) => setCoreOk(r.ok))
      .catch(() => setCoreOk(false));
  }, []);

  const connected = connections?.filter((c) => c.status === "connected").length ?? 0;

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-semibold">Dashboard</h1>

      <section className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <Card title="System">
          <Dot ok={coreOk} label="Core / API" />
          <Dot ok={coreOk} label="Database" />
        </Card>

        <Card title="Connections">
          <div className="text-3xl font-semibold text-helios-accent">{connected}</div>
          <div className="text-sm text-helios-muted">cuentas conectadas</div>
        </Card>

        <Card title="Intelligence">
          <div className="text-sm text-helios-muted">
            Los paneles de correos y alertas llegarán en próximas fases.
          </div>
        </Card>
      </section>
    </div>
  );
}

function Card({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="rounded-xl border border-helios-border bg-helios-panel p-4">
      <div className="mb-3 text-sm font-medium text-helios-muted">{title}</div>
      <div className="space-y-2">{children}</div>
    </div>
  );
}

function Dot({ ok, label }: { ok: boolean | null; label: string }) {
  const color = ok === null ? "bg-helios-muted" : ok ? "bg-helios-ok" : "bg-helios-danger";
  return (
    <div className="flex items-center gap-2 text-sm">
      <span className={`h-2.5 w-2.5 rounded-full ${color}`} />
      {label}
    </div>
  );
}
