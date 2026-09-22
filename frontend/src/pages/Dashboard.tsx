// HELIOS COMMAND — dashboard. Every number here is a real read from the API
// (KPIs, activity feed and system status); nothing is estimated or faked.

import { useEffect, useState } from "react";

import { dashboardApi } from "../api/endpoints";
import type { ActivityItem, DashboardKpis, SystemStatus } from "../api/types";

// Friendly Spanish labels for audit-log actions (no internal jargon leaked).
const ACTION_LABELS: Record<string, string> = {
  email_stored: "Correo recibido",
  email_classified: "Correo clasificado",
  email_processed: "Correo analizado",
  alert_sent: "Alerta enviada",
  CONNECTION_INITIATED: "Conexión iniciada",
  CONNECTION_COMPLETED: "Conexión completada",
  CONNECTION_DISCONNECTED: "Conexión desconectada",
};

function labelFor(action: string): string {
  return ACTION_LABELS[action] ?? action.replace(/[_.]/g, " ");
}

function formatWhen(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleString("es-MX", {
    day: "2-digit",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function Dashboard() {
  const [kpis, setKpis] = useState<DashboardKpis | null>(null);
  const [system, setSystem] = useState<SystemStatus | null>(null);
  const [activity, setActivity] = useState<ActivityItem[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    dashboardApi.kpis().then(setKpis).catch(() => setError("No pude cargar los indicadores."));
    dashboardApi.system().then(setSystem).catch(() => setSystem(null));
    dashboardApi.activity(10).then(setActivity).catch(() => setActivity([]));
  }, []);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold">Dashboard</h1>
        <p className="text-sm text-helios-muted">Tu centro personal de inteligencia, en tiempo real.</p>
      </div>

      {error && (
        <div className="rounded-lg border border-helios-danger/40 bg-helios-danger/10 px-4 py-3 text-sm text-helios-danger">
          {error}
        </div>
      )}

      {/* KPIs — real counts */}
      <section className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <Kpi label="Cuentas conectadas" value={kpis?.connections_connected} loading={!kpis} />
        <Kpi label="Correos analizados" value={kpis?.emails_total} loading={!kpis} />
        <Kpi
          label="Requieren tu acción"
          value={kpis?.action_required}
          loading={!kpis}
          highlight={(kpis?.action_required ?? 0) > 0}
        />
        <Kpi label="Alertas enviadas" value={kpis?.alerts_sent} loading={!kpis} />
      </section>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        {/* Recent activity */}
        <section className="lg:col-span-2">
          <Panel title="Actividad reciente">
            {activity === null ? (
              <Skeleton rows={4} />
            ) : activity.length === 0 ? (
              <Empty text="Aún no hay actividad registrada." />
            ) : (
              <ul className="divide-y divide-helios-border/60">
                {activity.map((item) => (
                  <li key={item.id} className="flex items-center justify-between py-2.5 text-sm">
                    <span>{labelFor(item.action)}</span>
                    <span className="text-xs text-helios-muted">{formatWhen(item.timestamp)}</span>
                  </li>
                ))}
              </ul>
            )}
          </Panel>
        </section>

        {/* System status + breakdown */}
        <section className="space-y-4">
          <Panel title="Estado del sistema">
            <Dot ok={system ? system.core : null} label="Núcleo / API" />
            <Dot ok={system ? system.database : null} label="Base de datos" />
            {system?.providers.map((p) => (
              <Dot
                key={`${p.provider}-${p.email}`}
                ok={p.status === "connected"}
                label={`${p.provider} · ${p.email}`}
              />
            ))}
          </Panel>

          {kpis && Object.keys(kpis.category_counts).length > 0 && (
            <Panel title="Correos por área">
              <ul className="space-y-1.5 text-sm">
                {Object.entries(kpis.category_counts)
                  .sort((a, b) => b[1] - a[1])
                  .map(([category, count]) => (
                    <li key={category} className="flex items-center justify-between">
                      <span className="capitalize">{category}</span>
                      <span className="text-helios-accent">{count}</span>
                    </li>
                  ))}
              </ul>
            </Panel>
          )}
        </section>
      </div>
    </div>
  );
}

function Kpi({
  label,
  value,
  loading,
  highlight = false,
}: {
  label: string;
  value: number | undefined;
  loading: boolean;
  highlight?: boolean;
}) {
  return (
    <div className="rounded-xl border border-helios-border bg-helios-panel p-4">
      <div
        className={`text-3xl font-semibold ${highlight ? "text-helios-warn" : "text-helios-accent"}`}
      >
        {loading ? <span className="text-helios-muted">…</span> : (value ?? 0)}
      </div>
      <div className="mt-1 text-sm text-helios-muted">{label}</div>
    </div>
  );
}

function Panel({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="rounded-xl border border-helios-border bg-helios-panel p-4">
      <div className="mb-3 text-sm font-medium text-helios-muted">{title}</div>
      <div>{children}</div>
    </div>
  );
}

function Dot({ ok, label }: { ok: boolean | null; label: string }) {
  const color = ok === null ? "bg-helios-muted" : ok ? "bg-helios-ok" : "bg-helios-danger";
  return (
    <div className="flex items-center gap-2 py-0.5 text-sm">
      <span className={`h-2.5 w-2.5 shrink-0 rounded-full ${color}`} />
      <span className="truncate">{label}</span>
    </div>
  );
}

function Empty({ text }: { text: string }) {
  return <div className="py-2 text-sm text-helios-muted">{text}</div>;
}

function Skeleton({ rows }: { rows: number }) {
  return (
    <div className="space-y-2">
      {Array.from({ length: rows }).map((_, i) => (
        <div key={i} className="h-4 w-full animate-pulse rounded bg-helios-border/50" />
      ))}
    </div>
  );
}
