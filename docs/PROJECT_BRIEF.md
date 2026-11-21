# Project Brief: BioPulse-Agent

**1. Il problema.** Atleti di resistenza, paralimpici e master rischiano sovrallenamento, infortuni e stop prolungati perché l'analisi biometrica è frammentata e differita: nessuno confronta in tempo reale carico e recupero autonomico con la baseline individuale. Senza storico longitudinale i segnali precoci passano inosservati.

**2. L'agente.** *Percezione*: telemetria wearable (HRV, FC a riposo, sonno, SpO₂) e diario testuale (RPE, DOMS). *Pianificazione*: il motore White-Box calcola ACWR e Z-score HRV; sopra soglia scatta il protocollo di riduzione del carico, altrimenti il modello linguistico propone la progressione. *Strumenti*: lettura serie biometrica, calcolo metriche, ricerca RAG su letteratura, alert al professionista. *Memoria*: Redis per la sessione, PostgreSQL + pgvector per lo storico su mesi. *Feedback*: autoverifica dell'output contro i vincoli deterministici e approvazione umana (HITL) per i casi ad alto rischio.

**3. Il dominio.** Salute, prevenzione sportiva e longevità (panel 1, 4 e 5 dell'evento di Taranto).

**4. Dati e strumenti.** Dati wearable simulati (schema ispirato a Open Wearables) e ingestione pronta per API reali; Python 3.12, Agno, Groq (Llama 3.3 70B), FastAPI, PostgreSQL + pgvector, Redis, Next.js 15.

**5. Metrica di successo.** *Quantitativa (misurata su dati simulati)*: rilevamento del 100% dei sovraccarichi e cali HRV simulati con falsi allarmi rossi ≤ 1%; motore deterministico < 50 ms (misurato p95 ≈ 0.75 ms); 100% degli output LLM pericolosi del corpus corretti. *Qualitativa (obiettivo da misurare in pilota)*: SUS > 80; completamento delle sessioni di recupero suggerite > 85%.

**6. Considerazioni etiche.** *Preoccupazione*: raccomandazioni errate del modello in presenza di parametri critici, e bias verso atleti atipici. *Decisione di progettazione*: calcolo del rischio affidato solo al motore White-Box su baseline individuali, autoverifica dell'output e nodo decisionale vincolante Human-in-the-Loop per i casi ad alto rischio; consenso granulare e cancellazione dei dati.
