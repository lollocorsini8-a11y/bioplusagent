import Link from "next/link";

export default function InfoPage({ eyebrow, title, lead, children }: {
  eyebrow: string; title: string; lead: string; children: React.ReactNode;
}) {
  return <main className="info-page">
    <header className="info-header"><Link href="/" className="brand-lockup"><span className="brand-mark"><span /></span><span className="brand-word">bio<span>pulse</span><small>ATHLETE INTELLIGENCE</small></span></Link><Link href="/onboarding" className="info-back">← Torna al portale</Link></header>
    <article className="info-document"><p className="eyebrow">{eyebrow}</p><h1>{title}</h1><p className="info-lead">{lead}</p>
      <div className="draft-warning"><b>DOCUMENTO PROTOTIPALE · BOZZA NON APPROVATA</b><p>Descrive le funzionalità attuali del prototipo. Non costituisce consulenza legale né informativa definitiva; prima di un pilota o rilascio deve essere verificato dal titolare e da professionisti privacy/legali.</p></div>
      <div className="info-body">{children}</div>
      <div className="info-footer"><Link href="/privacy">Privacy</Link><Link href="/cookies">Cookie</Link><Link href="/ethics">Etica e limiti</Link><Link href="/">Accedi ↗</Link></div>
    </article>
  </main>;
}
