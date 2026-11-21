"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { logout } from "@/lib/api";
import { usePortal } from "./PortalProvider";

const NAV = [
  { href: "/dashboard", label: "Panoramica", icon: "◉" },
  { href: "/assistant", label: "BioPulse AI", icon: "✳" },
  { href: "/profile", label: "Il mio profilo", icon: "◎" },
];

export default function PortalShell({ children }: { children: React.ReactNode }) {
  const path = usePathname();
  const router = useRouter();
  const { session, data, athleteId, setAthleteId, setError } = usePortal();
  const athlete = session.athletes.find(item => item.id === athleteId);
  const nav = session.user.role === "athlete" ? NAV : [
    NAV[0], { href: "/assistant", label: "Area clinica", icon: "⬡" }, NAV[2],
  ];

  async function signOut() {
    try {
      await logout();
    } catch (reason) {
      setError((reason as Error).message);
    } finally {
      localStorage.removeItem(`biopulse-onboarding:${session.user.id}`);
      router.replace("/");
    }
  }

  return (
    <div className="portal-frame">
      <aside className="portal-sidebar">
        <Link href="/dashboard" className="brand-lockup" aria-label="BioPulse, panoramica">
          <span className="brand-mark"><span /></span>
          <span className="brand-word">bio<span>pulse</span><small>ATHLETE INTELLIGENCE</small></span>
        </Link>
        <div className="sidebar-caption">IL TUO SPAZIO</div>
        <nav className="portal-nav" aria-label="Navigazione principale">
          {nav.map(item => (
            <Link key={item.href} href={item.href} className={path === item.href ? "portal-nav-link active" : "portal-nav-link"}>
              <span className="nav-symbol" aria-hidden>{item.icon}</span>{item.label}
              {path === item.href && <span className="nav-current" />}
            </Link>
          ))}
        </nav>
        <div className="sidebar-status">
          <span className="status-orb" />
          <div><strong>Demo controllata</strong><small>Fonti sintetiche · no device</small></div>
        </div>
        <div className="sidebar-bottom">
          <Link href="/ethics" className="sidebar-quiet-link">Etica e limiti</Link>
          <Link href="/privacy" className="sidebar-quiet-link">Privacy</Link>
          <Link href="/cookies" className="sidebar-quiet-link">Cookie</Link>
          <button onClick={signOut} className="signout-button">Esci dall'account</button>
        </div>
      </aside>
      <div className="portal-main">
        <header className="portal-topbar">
          <div className="topbar-context">
            <span className="live-dot" /> SPAZIO PERSONALE
            {session.athletes.length > 1 && (
              <select aria-label="Seleziona atleta" value={athleteId} onChange={event => setAthleteId(event.target.value)}>
                {session.athletes.map(item => <option key={item.id} value={item.id}>{item.name}</option>)}
              </select>
            )}
          </div>
          <Link href="/profile" className="topbar-user">
            <span className="avatar">{(athlete?.name ?? session.user.email).slice(0, 1).toUpperCase()}</span>
            <span><strong>{athlete?.name ?? session.user.email}</strong><small>Profilo atleta · {data?.athlete.profile ?? "standard"}</small></span>
            <span className="chevron">↗</span>
          </Link>
        </header>
        {children}
        <footer className="portal-footer">
          <span>BioPulse-Agent · prototipo dimostrativo</span>
          <span>Non è un dispositivo medico · dati demo</span>
          <Link href="/ethics">Etica, limiti e accessibilità ↗</Link>
        </footer>
      </div>
      <nav className="mobile-nav" aria-label="Navigazione mobile">
        {nav.map(item => <Link key={item.href} href={item.href} className={path === item.href ? "mobile-nav-link active" : "mobile-nav-link"}>
          <span aria-hidden>{item.icon}</span>{item.label}
        </Link>)}
      </nav>
    </div>
  );
}
