import { NavLink, Outlet } from "react-router-dom";

const NAV_LINKS = [
  { to: "/", label: "Live Map" },
  { to: "/orders", label: "Shipments" },
  { to: "/analytics", label: "Analytics" },
  { to: "/alerts", label: "Alerts" },
];

export function Layout() {
  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%" }}>
      <header style={headerStyle}>
        <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
          <div style={logoStyle}>PORT INTEL</div>
          <span style={{ color: "#1e293b", fontSize: 18 }}>|</span>
          <nav style={{ display: "flex", gap: 4 }}>
            {NAV_LINKS.map((l) => (
              <NavLink
                key={l.to}
                to={l.to}
                end={l.to === "/"}
                style={({ isActive }) => ({
                  ...navLink,
                  ...(isActive ? navLinkActive : {}),
                })}
              >
                {l.label}
              </NavLink>
            ))}
          </nav>
        </div>
        <div style={{ fontSize: 11, color: "#475569" }}>
          Real-Time Port & Logistics Intelligence
        </div>
      </header>
      <main style={{ flex: 1, overflow: "hidden", display: "flex", flexDirection: "column" }}>
        <Outlet />
      </main>
    </div>
  );
}

const headerStyle: React.CSSProperties = {
  background: "#0a0e1a",
  borderBottom: "1px solid #1e293b",
  padding: "10px 24px",
  display: "flex",
  alignItems: "center",
  justifyContent: "space-between",
  flexShrink: 0,
};

const logoStyle: React.CSSProperties = {
  fontSize: 14,
  fontWeight: 800,
  letterSpacing: 2,
  color: "#38bdf8",
};

const navLink: React.CSSProperties = {
  padding: "4px 12px",
  borderRadius: 6,
  fontSize: 13,
  color: "#64748b",
  textDecoration: "none",
  transition: "color 0.2s",
};

const navLinkActive: React.CSSProperties = {
  color: "#e2e8f0",
  background: "#1e293b",
};
