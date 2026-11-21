"use client";

import { FormEvent, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import AthleteRail from "@/components/AthleteRail";
import { usePortal } from "@/components/PortalProvider";
import { updateAthleteProfile } from "@/lib/api";

export default function ProfilePage() {
  const router = useRouter();
  const { session, athleteId, data, setData } = usePortal();
  const [contact, setContact] = useState("");
  const [saved, setSaved] = useState(false);
  const [displayName, setDisplayName] = useState("");
  const [profile, setProfile] = useState("standard");
  const [profileBusy, setProfileBusy] = useState(false);
  const [profileError, setProfileError] = useState("");
  const [profileSaved, setProfileSaved] = useState(false);
  useEffect(() => {
    setContact(localStorage.getItem(`biopulse-coach-contact:${session.user.id}`) ?? "");
  }, [session.user.id]);
  useEffect(() => {
    if (!data) return;
    setDisplayName(data.athlete.name);
    setProfile(data.athlete.profile);
  }, [data]);
  function saveContact() {
    localStorage.setItem(`biopulse-coach-contact:${session.user.id}`, contact.trim());
    setSaved(true);
    window.setTimeout(() => setSaved(false), 2500);
  }
  async function saveProfile(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!data) return;
    setProfileBusy(true);
    setProfileError("");
    setProfileSaved(false);
    try {
      const updated = await updateAthleteProfile(athleteId, { name: displayName, profile });
      setData({ ...data, athlete: { ...data.athlete, name: updated.name, profile: updated.profile } });
      setProfileSaved(true);
    } catch (reason) {
      setProfileError((reason as Error).message);
    } finally { setProfileBusy(false); }
  }
  return <main className="portal-content profile-page">
    <div className="page-heading"><div><p className="eyebrow">IMPOSTAZIONI E CONTROLLO</p><h1>{session.user.role === "athlete" ? "Il mio profilo" : "Profilo atleta"}<span className="heading-period">.</span></h1>
      <p>{session.user.role === "athlete" ? "Gestisci le preferenze e controlla i dati demo associati all'account." : "Consulta il profilo atleta e lo stato dei dati demo assegnati."}</p></div></div>
    <div className="profile-layout">
      <section className="profile-primary">
        <div className="profile-card">
          <div className="profile-avatar">{(data?.athlete.name ?? session.user.email).slice(0, 1).toUpperCase()}</div>
          <div><p className="eyebrow">ACCOUNT ATLETA</p><h2>{data?.athlete.name ?? session.athletes[0]?.name ?? "Atleta"}</h2>
            <p>{session.user.demo_guest ? "Accesso ospite · sessione temporanea" : session.user.email}</p></div>
          <span className="profile-tag">{data?.athlete.profile ?? "standard"}</span>
        </div>
        {session.user.role === "athlete" && !session.user.demo_guest && <section className="profile-setting">
          <p className="eyebrow">PERSONALIZZAZIONE</p><h2>Come vuoi apparire?</h2>
          <p>La categoria è descrittiva e non modifica i calcoli o le raccomandazioni.</p>
          <form className="profile-edit-form" onSubmit={saveProfile}>
            <label className="contact-label">Nome visualizzato
              <input required minLength={1} maxLength={120} value={displayName} onChange={event => { setDisplayName(event.target.value); setProfileSaved(false); }} />
            </label>
            <label className="contact-label">Profilo descrittivo
              <select value={profile} onChange={event => { setProfile(event.target.value); setProfileSaved(false); }}>
                <option value="standard">Standard</option><option value="paralympic">Paralimpico</option><option value="master">Master</option>
              </select>
            </label>
            {profileError && <p role="alert" className="form-error">{profileError}</p>}
            {profileSaved && <p role="status" className="saved-note">Profilo aggiornato.</p>}
            <button type="submit" className="button-secondary" disabled={profileBusy || !data}>{profileBusy ? "Salvo…" : "Salva profilo"}</button>
          </form>
        </section>}
        {session.user.role === "athlete" && !session.user.demo_guest && <section className="profile-setting">
          <p className="eyebrow">CONNESSIONI</p><h2>Il tuo team</h2>
          <p>Questo contatto è un promemoria conservato in questo browser. Non viene inviato né usato per notifiche.</p>
          <label className="contact-label">Contatto allenatore o professionista
            <input value={contact} onChange={event => { setContact(event.target.value); setSaved(false); }} maxLength={160} placeholder="Facoltativo · non collegato" />
          </label>
          <button className="button-secondary" onClick={saveContact}>Salva nel browser</button>{saved && <span role="status" className="saved-note">Salvato su questo dispositivo</span>}
          <div className="connection-card profile-connection"><div className="connection-icon">⌁</div><div><h2>Wearable</h2><p>Provider reale non configurato. La sincronizzazione resta sintetica e serve solo a provare la demo.</p></div><span className="connection-status">SIMULATO</span></div>
        </section>}
        <section className="profile-setting">
          <p className="eyebrow">DATI E CONSENSI</p><h2>Scelte reversibili</h2><p>Il consenso biometrico è separato dall'accesso. Puoi revocarlo quando vuoi o eliminare i dati demo.</p>
          {data && <AthleteRail data={data} athleteId={athleteId} canManage={session.user.role === "athlete"} demoMode={session.demo_mode}
            isPublicDemo={session.user.demo_guest}
            onChange={setData} onReset={() => router.replace("/")} />}
        </section>
        <section className="profile-setting">
          <p className="eyebrow">INFORMAZIONI</p><h2>Testi e limiti del prototipo</h2>
          <div className="profile-links"><Link href="/privacy">Privacy e dati ↗</Link><Link href="/cookies">Cookie e memoria locale ↗</Link><Link href="/ethics">Etica, bias e validazione ↗</Link></div>
          <button className="button-secondary" onClick={() => {
            localStorage.removeItem(`biopulse-onboarding:${session.user.id}`);
            localStorage.removeItem(`biopulse-onboarding-step:${session.user.id}`);
            localStorage.removeItem(`biopulse-privacy-read:${session.user.id}`);
            router.replace("/onboarding");
          }}>Rivedi l'orientamento iniziale</button>
        </section>
      </section>
      <aside className="profile-aside"><span className="aside-disclaimer-icon">!</span><p className="eyebrow">STATO DEL PROTOTIPO</p><h2>Trasparenza prima di tutto.</h2><ul><li>Wearable: simulato</li><li>Coach: non collegato</li><li>Profili adattivi: descrittivi</li><li>Metriche: non validate clinicamente</li><li>Analytics: non presenti</li></ul></aside>
    </div>
  </main>;
}
