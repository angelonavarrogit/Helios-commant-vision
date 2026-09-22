// HELIOS COMMAND — Settings (V0.2): sectioned, write-only, with connection tests.
//
// Security model:
// - Secret fields are WRITE-ONLY. The backend never returns their values, so we
//   only show "● Configurado" (+ source) and offer Replace/Test — never the value.
// - Infrastructure secrets (Google) are separated from user-facing config.
// - "Probar conexión" verifies a saved credential against the real service.

import { useCallback, useEffect, useState } from "react";

import { ApiError } from "../api/client";
import { settingsApi } from "../api/endpoints";
import type { SettingStatus } from "../api/endpoints";

type TestState = { ok: boolean; detail: string } | null;

export function Settings() {
  const [status, setStatus] = useState<Record<string, SettingStatus>>({});
  const [banner, setBanner] = useState<string | null>(null);

  const reload = useCallback(async () => {
    try {
      setStatus(await settingsApi.status());
    } catch {
      setBanner("No se pudo cargar la configuración.");
    }
  }, []);

  useEffect(() => {
    void reload();
  }, [reload]);

  return (
    <div className="max-w-2xl space-y-8">
      <div>
        <h1 className="text-xl font-semibold">Settings</h1>
        <p className="text-sm text-helios-muted">
          Configura HELIOS de forma segura. Los secretos se cifran antes de guardarse y nunca se
          muestran de vuelta.
        </p>
      </div>

      {banner && (
        <div className="rounded-md bg-helios-border/40 px-4 py-2 text-sm text-helios-text">
          {banner}
        </div>
      )}

      <Section title="Notificaciones" description="Canal por el que HELIOS te avisa.">
        <SecretField
          settingKey="telegram_bot_token"
          label="Telegram Bot Token"
          placeholder="123456:AA…"
          status={status["telegram_bot_token"]}
          testProvider="telegram"
          onSaved={reload}
          onBanner={setBanner}
        />
        <PlainField
          settingKey="telegram_allowed_user_ids"
          label="Telegram User IDs (coma-separados)"
          placeholder="12345,67890"
          status={status["telegram_allowed_user_ids"]}
          onSaved={reload}
          onBanner={setBanner}
        />
      </Section>

      <Section title="Inteligencia (IA)" description="Proveedor de análisis. Ollama es local; OpenAI es opcional.">
        <SecretField
          settingKey="openai_api_key"
          label="OpenAI API Key"
          placeholder="sk-…"
          status={status["openai_api_key"]}
          testProvider="openai"
          onSaved={reload}
          onBanner={setBanner}
        />
        <TestOnly provider="ollama" label="Ollama (local)" />
      </Section>

      <Section
        title="Infraestructura · Google"
        description="Identidad de la app OAuth. Son credenciales del sistema, no tu cuenta."
      >
        <PlainField
          settingKey="google_client_id"
          label="Google Client ID"
          placeholder="…apps.googleusercontent.com"
          status={status["google_client_id"]}
          onSaved={reload}
          onBanner={setBanner}
        />
        <SecretField
          settingKey="google_client_secret"
          label="Google Client Secret"
          placeholder="GOCSPX-…"
          status={status["google_client_secret"]}
          onSaved={reload}
          onBanner={setBanner}
        />
      </Section>

      <Section title="Seguridad" description="Tu acceso a HELIOS COMMAND.">
        <ChangePassword onBanner={setBanner} />
      </Section>
    </div>
  );
}

// --- layout helpers ----------------------------------------------------------

function Section({
  title,
  description,
  children,
}: {
  title: string;
  description: string;
  children: React.ReactNode;
}) {
  return (
    <section className="space-y-3">
      <div>
        <h2 className="text-sm font-semibold text-helios-text">{title}</h2>
        <p className="text-xs text-helios-muted">{description}</p>
      </div>
      <div className="space-y-3">{children}</div>
    </section>
  );
}

function StatusPill({ st }: { st: SettingStatus | undefined }) {
  if (!st?.configured) {
    return (
      <span className="rounded-full bg-helios-border px-2 py-0.5 text-xs text-helios-muted">
        No configurado
      </span>
    );
  }
  const label = st.source === "db" ? "● Configurado" : "● Configurado (entorno)";
  return (
    <span className="rounded-full bg-helios-accent/15 px-2 py-0.5 text-xs text-helios-accent">
      {label}
    </span>
  );
}

function TestButton({ provider }: { provider: string }) {
  const [state, setState] = useState<TestState>(null);
  const [busy, setBusy] = useState(false);

  async function run() {
    setBusy(true);
    setState(null);
    try {
      const r = await settingsApi.test(provider);
      setState(r);
    } catch (err) {
      setState({ ok: false, detail: err instanceof ApiError ? err.message : "Error al probar." });
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex items-center gap-2">
      <button
        onClick={() => void run()}
        disabled={busy}
        className="rounded-md border border-helios-border px-3 py-2 text-sm text-helios-text hover:border-helios-accent disabled:opacity-60"
      >
        {busy ? "Probando…" : "Probar conexión"}
      </button>
      {state && (
        <span className={`text-xs ${state.ok ? "text-helios-accent" : "text-helios-danger"}`}>
          {state.ok ? "✓ " : "✕ "}
          {state.detail}
        </span>
      )}
    </div>
  );
}

// --- fields ------------------------------------------------------------------

interface FieldProps {
  settingKey: string;
  label: string;
  placeholder: string;
  status: SettingStatus | undefined;
  onSaved: () => Promise<void>;
  onBanner: (m: string) => void;
}

function useSaver(settingKey: string, onSaved: () => Promise<void>, onBanner: (m: string) => void) {
  const [value, setValue] = useState("");
  const [busy, setBusy] = useState(false);

  async function save() {
    if (!value) return;
    setBusy(true);
    try {
      await settingsApi.set(settingKey, value);
      setValue("");
      await onSaved();
      onBanner("Guardado correctamente.");
    } catch (err) {
      onBanner(err instanceof ApiError ? err.message : "No se pudo guardar.");
    } finally {
      setBusy(false);
    }
  }
  return { value, setValue, busy, save };
}

function SecretField({
  testProvider,
  ...props
}: FieldProps & { testProvider?: string }) {
  const { value, setValue, busy, save } = useSaver(props.settingKey, props.onSaved, props.onBanner);
  return (
    <div className="rounded-lg border border-helios-border bg-helios-panel p-4">
      <div className="mb-2 flex items-center justify-between">
        <label className="text-sm">{props.label}</label>
        <StatusPill st={props.status} />
      </div>
      <div className="mb-2 flex gap-2">
        <input
          type="password"
          value={value}
          placeholder={props.status?.configured ? "•••••••••• (escribe para reemplazar)" : props.placeholder}
          onChange={(e) => setValue(e.target.value)}
          className="flex-1 rounded-md border border-helios-border bg-helios-bg px-3 py-2 text-sm outline-none focus:border-helios-accent"
        />
        <button
          onClick={() => void save()}
          disabled={busy || !value}
          className="rounded-md bg-helios-accent px-3 py-2 text-sm font-medium text-helios-bg disabled:opacity-60"
        >
          {props.status?.configured ? "Reemplazar" : "Guardar"}
        </button>
      </div>
      {testProvider && <TestButton provider={testProvider} />}
    </div>
  );
}

function PlainField(props: FieldProps) {
  const { value, setValue, busy, save } = useSaver(props.settingKey, props.onSaved, props.onBanner);
  return (
    <div className="rounded-lg border border-helios-border bg-helios-panel p-4">
      <div className="mb-2 flex items-center justify-between">
        <label className="text-sm">{props.label}</label>
        <StatusPill st={props.status} />
      </div>
      <div className="flex gap-2">
        <input
          type="text"
          value={value}
          placeholder={props.placeholder}
          onChange={(e) => setValue(e.target.value)}
          className="flex-1 rounded-md border border-helios-border bg-helios-bg px-3 py-2 text-sm outline-none focus:border-helios-accent"
        />
        <button
          onClick={() => void save()}
          disabled={busy || !value}
          className="rounded-md bg-helios-accent px-3 py-2 text-sm font-medium text-helios-bg disabled:opacity-60"
        >
          Guardar
        </button>
      </div>
    </div>
  );
}

function TestOnly({ provider, label }: { provider: string; label: string }) {
  return (
    <div className="rounded-lg border border-helios-border bg-helios-panel p-4">
      <div className="mb-2 text-sm">{label}</div>
      <TestButton provider={provider} />
    </div>
  );
}

function ChangePassword({ onBanner }: { onBanner: (m: string) => void }) {
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit() {
    setBusy(true);
    try {
      await settingsApi.changePassword(current, next);
      setCurrent("");
      setNext("");
      onBanner("Contraseña actualizada.");
    } catch (err) {
      onBanner(err instanceof ApiError ? err.message : "No se pudo cambiar la contraseña.");
    } finally {
      setBusy(false);
    }
  }

  return (
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
  );
}
