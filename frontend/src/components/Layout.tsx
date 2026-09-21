// HELIOS COMMAND — app shell: sidebar navigation + header + content outlet.

import { NavLink, Outlet } from "react-router-dom";

import { useAuth } from "../auth/AuthContext";

const NAV = [
  { to: "/", label: "Dashboard", end: true },
  { to: "/connections", label: "Connections" },
  { to: "/settings", label: "Settings" },
];

export function Layout() {
  const { user, logout } = useAuth();

  return (
    <div className="flex min-h-screen bg-helios-bg text-helios-text">
      <aside className="w-56 shrink-0 border-r border-helios-border bg-helios-panel p-4">
        <div className="mb-8 flex items-center gap-2">
          <span className="flex h-8 w-8 items-center justify-center rounded-md border border-helios-accent/60 text-sm font-bold tracking-tight text-helios-accent">
            AN
          </span>
          <div className="leading-tight">
            <div className="text-base font-semibold">HELIOS</div>
            <div className="text-[10px] uppercase tracking-widest text-helios-muted">
              Angelo Navarro
            </div>
          </div>
        </div>
        <nav className="flex flex-col gap-1">
          {NAV.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              className={({ isActive }) =>
                `rounded-md px-3 py-2 text-sm ${
                  isActive
                    ? "bg-helios-accent/15 text-helios-accent"
                    : "text-helios-muted hover:bg-helios-border/40"
                }`
              }
            >
              {item.label}
            </NavLink>
          ))}
        </nav>
      </aside>

      <div className="flex flex-1 flex-col">
        <header className="flex items-center justify-between border-b border-helios-border px-6 py-3">
          <span className="text-sm text-helios-muted">Personal Intelligence Command Center</span>
          <div className="flex items-center gap-3 text-sm">
            <span className="text-helios-muted">{user?.username}</span>
            <button
              onClick={() => void logout()}
              className="rounded-md border border-helios-border px-3 py-1 text-helios-muted hover:text-helios-text"
            >
              Salir
            </button>
          </div>
        </header>
        <main className="flex-1 p-6">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
