"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import { getDashboard, getSession } from "@/lib/api";
import type { Dashboard, SessionInfo } from "@/lib/types";

interface PortalState {
  session: SessionInfo;
  athleteId: string;
  setAthleteId: (id: string) => void;
  data: Dashboard | null;
  setData: (data: Dashboard | null) => void;
  refresh: () => Promise<void>;
  loading: boolean;
  error: string | null;
  setError: (message: string | null) => void;
}

const PortalContext = createContext<PortalState | null>(null);

export function PortalProvider({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const [session, setSession] = useState<SessionInfo | null>(null);
  const [athleteId, setAthleteId] = useState("");
  const [data, setData] = useState<Dashboard | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    getSession().then(value => {
      if (!active) return;
      setSession(value);
      setAthleteId(value.athletes[0]?.id ?? "");
      const completed = localStorage.getItem(`biopulse-onboarding:${value.user.id}`);
      if (completed !== "complete") router.replace("/onboarding");
    }).catch(() => {
      if (active) router.replace("/");
    }).finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [router]);

  useEffect(() => {
    if (!session) return;
    if (!session.athletes.some(a => a.id === athleteId)) {
      setAthleteId(session.athletes[0]?.id ?? "");
    }
  }, [session, athleteId]);

  const refresh = useCallback(async () => {
    if (!athleteId) { setData(null); return; }
    try {
      setData(await getDashboard(athleteId));
      setError(null);
    } catch (reason) {
      const failure = reason as { status?: number; message?: string };
      if (failure.status === 401) {
        router.replace("/");
        return;
      }
      setError(failure.message ?? "Non riesco a caricare i dati.");
    }
  }, [athleteId, router]);

  useEffect(() => {
    setData(null);
    if (athleteId && !loading) void refresh();
  }, [athleteId, loading, refresh]);

  const value = useMemo(() => session ? ({
    session, athleteId, setAthleteId, data, setData, refresh, loading, error, setError,
  }) : null, [session, athleteId, data, refresh, loading, error]);

  if (loading || !session || pathname === "/onboarding") {
    return <div className="portal-loading"><span className="brand-mark brand-mark-small" />Prepariamo il tuo spazio BioPulse…</div>;
  }

  return <PortalContext.Provider value={value}>{children}</PortalContext.Provider>;
}

export function usePortal() {
  const value = useContext(PortalContext);
  if (!value) throw new Error("usePortal deve essere usato all'interno di PortalProvider.");
  return value;
}
