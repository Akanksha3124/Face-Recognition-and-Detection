import { NavLink, Outlet } from "react-router-dom";
import { useAuth } from "@/hooks/useAuth";

// Every one of these except Dashboard/Profile points at a page that
// doesn't exist yet — later phases fill them in (persons/cases have a
// backend already, Phase 4; face-search etc. come with Phase 6+). Listed
// here now so the nav shape matches the architecture doc's page list
// and doesn't need restructuring later.
const NAV_ITEMS = [
  { to: "/dashboard", label: "Dashboard" },
  { to: "/persons", label: "Persons" },
  { to: "/cases", label: "Cases" },
  { to: "/face-search", label: "Face Search" },
  { to: "/matches", label: "Matches" },
  { to: "/verification", label: "Verification" },
  { to: "/map", label: "Map" },
  { to: "/admin", label: "Admin" },
];

/** Sidebar + topbar shell for every authenticated page. */
export function AppLayout() {
  const { user, logout } = useAuth();

  return (
    <div className="min-h-screen flex bg-slate-50">
      <aside className="w-56 shrink-0 bg-white border-r border-slate-200 flex flex-col">
        <div className="px-4 py-4 border-b border-slate-200">
          <span className="font-semibold text-slate-800 text-sm">Person ID Platform</span>
        </div>
        <nav className="flex-1 py-2">
          {NAV_ITEMS.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              className={({ isActive }) =>
                `block px-4 py-2 text-sm rounded-none ${
                  isActive
                    ? "bg-slate-100 text-slate-900 font-medium"
                    : "text-slate-600 hover:bg-slate-50"
                }`
              }
            >
              {item.label}
            </NavLink>
          ))}
        </nav>
      </aside>

      <div className="flex-1 flex flex-col min-w-0">
        <header className="h-14 bg-white border-b border-slate-200 flex items-center justify-between px-6">
          <div />
          <div className="flex items-center gap-4">
            <NavLink to="/profile" className="text-sm text-slate-600 hover:text-slate-900">
              {user?.email} <span className="text-slate-400">({user?.role})</span>
            </NavLink>
            <button
              onClick={() => logout()}
              className="text-sm text-slate-500 hover:text-slate-900 border border-slate-200 rounded px-3 py-1"
            >
              Log out
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
