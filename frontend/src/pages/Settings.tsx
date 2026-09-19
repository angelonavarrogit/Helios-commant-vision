// HELIOS COMMAND — Settings page (Phase 5.8).
//
// Lets the owner configure Class-B secrets (Telegram, OpenAI, Google) and change
// the login password. Secret fields are WRITE-ONLY: the backend never returns
// their values, so inputs are always blank and we only show "configured".

import { useCallback, useEffect, useState } from "react";

import { ApiError } from "../api/client";
import { settingsApi } from "../api/endpoints";
import type { SettingStatus } from "../api/endpoints";

interface Field {
  key: string;
  label: string;
  placeholder: string;
  secret: boolean;
}

const FIELDS: Field[] = [
  { key: "telegram_bot_token", label: "Telegram Bot Token", placeholder: "1234:AA…", secret: true },
  {
    key: "telegram_allowed_user_ids",
    label: "Telegram User IDs (coma-separados)",
    placeholder: "12345,67890",
    secret: false,
  },
  { key: "openai_api_key", label: "OpenAI API Key", placeholder: "sk-…", secret: true },
  {
    key: "google_client_id",
    label: "Google Client ID",
    placeholder: "…apps.googleusercontent.com",
    secret: false,
  },
  { key: "google_client_secret", label: "Google Client Secret", placeholder: "GOCSPX-…", secret: true },
];

export function Settings() {
  const [status, setStatus] = useState<Record<string, SettingStatus>>({});
  const [values, setValues] = useState<Record<string, string>>({});
  const [msg, setMsg] = useState<string | null>(null);

  const reload = useCallback(async () => {
    try {
      setStatus(await settingsApi.status());
    } catch {
      setMsg("No se pudo cargar la configuración.");
    }
  }, []);

  useEffect(() => {
    void reload();
  }, [reload]);

  async function save(key: string) {
    setMsg(null);
    const value = values[key] ?? "";
    if (!value) return;
    try {
      await settingsApi.set(key, value);
      setValues((v) => ({ ...v, [key]: "" })); // clear the input after saving
      await reload();
      setMsg("Guardado correctamente.");
    } catch (err) {
      setMsg(err instanceof ApiError ? err.message : "No se pudo guardar.");
    }
  }

  return (
    <div className="max-w-2xl space-y-8">
      <div>
        <h1 className="text-xl font-semibold">Settings</h1>
        <p className="text-sm text-helios-muted">
          Configura tus conexiones de forma segura. Los secretos se cifran antes de guardarse y
          nunca se muestran de vuelta.
        </p>
      </div>

      {msg && (
        <div className="rounded-md bg-helios-border/40 px-4 py-2 text-sm text-helios-text">{msg}</div>
      )}

      <section className="space-y-4">
        <h2 className="text-sm font-medium text-helios-muted">Conexiones</h2>
        {FIELDS.map((f) => {
          const st = status[f.key];
          return (
            <div key={f.key} className="rounded-lg border border-helios-border bg-helios-panel p-4">
              <div className="mb-2 flex items-center justify-between">
                <label className="text-sm">{f.label}</label>
                <StatusPill st={st} />
              </div>
              <div className="flex gap-2">
                <input
                  type={f.secret ? "password" : "text"}
                  value={values[f.key] ?? ""}
                  placeholder={f.placeholder}
                  onChange={(e) => setValues((v) => ({ ...v, [f.key]: e.target.value }))}
                  className="flex-1 rounded-md border border-helios-border bg-helios-bg px-3 py-2 text-sm outline-none focus:border-helios-accent"
                />
                <button
                  onClick={() => void save(f.key)}
                  className="rounded-md bg-helios-accent px-3 py-2 text-sm font-medium text-helios-bg"
                >
                  Guardar
                </button>
              </div>
            </div>
          );
        })}
      </section>

      <ChangePassword onMessage={setMsg} />
    </div>
  );
}

function StatusPill({ st }: { st: SettingStatus | undefined }) {
  if (!st?.configured) {
    return <span className="rounded-full bg-helios-border px-2 py-0.5 text-xs text-helios-muted">No configurado</span>;
  }
  const label = st.source === "db" ? "Configurado" : "Desde .env";
  return <span className="rounded-full bg-helios-ok/20 px-2 py-0.5 text-xs text-helios-ok">{label}</span>;
}

function ChangePassword({ onMessage }: { onMessage: (m: string) => void }) {
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit() {
    setBusy(true);
    try {
      await settingsApi.changePassword(current, next);
      setCurrent("");
      setNext("");
      onMessage("Contraseña actualizada.");
    } catch (err) {
      onMessage(err instanceof ApiError ? err.message : "No se pudo cambiar la contraseña.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="space-y-3">
      <h2 className="text-sm font-medium text-helios-muted">Cambiar contraseña</h2>
      <div className="rounded-lg border border-helios-border bg-helios-panel p-4">
        <input
          type="password"
          value={current}
          placeholder="Contraseña actual"
          onChange={(e) => setCurrent(e.target.value)}
          className="mb-2 w-full rounded-md border border-helios-border bg-helios-bg px-3 py-2 text-sm outline-none focus:border-helios-accent"
        />
        <input
          type="password"
          value={next}
          placeholder="Nueva contraseña (mín. 8)"
          onChange={(e) => setNext(e.target.value)}
          className="mb-3 w-full rounded-md border border-helios-border bg-helios-bg px-3 py-2 text-sm outline-none focus:border-helios-accent"
        />
        <button
          onClick={() => void submit()}
          disabled={busy || !current || next.length < 8}
          className="rounded-md bg-helios-accent px-3 py-2 text-sm font-medium text-helios-bg disabled:opacity-60"
        >
          {busy ? "Actualizando…" : "Cambiar contraseña"}
        </button>
      </div>
    </section>
  );
}
