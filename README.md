# BioPulse-Agent

Agente IA per il monitoraggio biometrico e la prevenzione dello stress atletico, progettato per la competizione **bioERGOtech** ("Vivere più a lungo: sport e intelligenza artificiale", Taranto, 10-11 dicembre 2026).

> Un motore **White-Box** (formule trasparenti) calcola indicatori; un modello linguistico **Black-Box** (configurabile via Groq, orchestrato con Agno) li spiega in italiano semplice. La telemetria di Agno è disattivata. I casi ad alto rischio sono registrati per revisione umana, ma l'account professionista e l'invio delle notifiche non sono collegati: la revisione non è garantita.

## 1. Il problema

Atleti di resistenza, paralimpici e master rischiano sovrallenamento e infortuni perché l'analisi dei dati biometrici è frammentata e arriva dopo l'allenamento. Senza uno storico longitudinale è difficile accorgersi che carico e recupero stanno perdendo equilibrio. BioPulse-Agent legge i dati del wearable, li confronta con la **baseline individuale** dell'atleta e agisce prima che il problema si accumuli.

## 2. L'agente

| Componente        | Come è realizzato                                                                                                                      | File                                   |
| ----------------- | -------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------- |
| Percezione        | telemetria wearable (JSON), testo libero dell'atleta (RPE, DOMS, sonno), sanificazione dei dati                                        | `whitebox/sanitizer.py`, `pipeline.py` |
| Pianificazione    | albero deterministico: prima il White-Box (ACWR > 1.5 o Z-score HRV < -1.5 → protocollo di allerta), poi il linguaggio                 | `pipeline.py`                          |
| Uso di strumenti  | `fetch_biometric_series`, `compute_strain_metrics`, `search_longevity_knowledge` (all'LLM) · `trigger_emergency_alert` (solo pipeline) | `tools.py`                             |
| Memoria           | breve termine su Redis · lungo termine su PostgreSQL + pgvector                                                                        | `memory.py`, `db.py`                   |
| Ciclo di feedback | autoverifica algoritmica + creazione di un caso da sottoporre a revisione umana (HITL)                                                     | `guardrails.py`, `HitlPanel.tsx`       |

Scelta di sicurezza: all'LLM sono esposti **solo tool di lettura**. L'invio di alert è fatto dalla pipeline, mai dal modello.

## 3. Il dominio

Salute, prevenzione sportiva e longevità (panel 1, 4 e 5 dell'evento). Dati telemetrici abbondanti e impatto diretto sulla speranza di vita in salute.

## 4. Dati e strumenti

- **Dati**: esclusivamente sintetici nei test e nella demo (`simulator.py`, 4 scenari). Il connettore backend `wearable.py` simula un payload esterno, normalizza i record e supporta sincronizzazione incrementale con sovrapposizione dell'ultimo giorno e upsert idempotente (`POST /api/athletes/{id}/wearable/sync`). La companion app Expo in `mobile/` include adapter in sola lettura per HealthKit e Health Connect: con consenso esplicito legge localmente gli ultimi 28 giorni di alcuni segnali, senza salvarli o inviarli al backend. Gli adapter non sono ancora validati su build native o dispositivi reali. Garmin richiede l'approvazione come partner. L'ingestione backend normalizzata resta disponibile (`POST /api/athletes/{id}/telemetry`), ma non è ancora collegata alla companion app.
- **Stack**: Python 3.12, FastAPI, Agno + Groq (modello definito da `GROQ_MODEL`), PostgreSQL + pgvector, Redis, Twilio (opzionale), Next.js 15 + React 19 + Tailwind + Framer Motion, Expo + React Native + TypeScript.
- **Dipendenze riproducibili**: `backend/requirements-lock.txt` blocca le versioni Python; `frontend/package-lock.json` blocca quelle npm. Le immagini Docker installano dai rispettivi lockfile.
- **RAG**: 8 schede in `backend/app/knowledge/`, sintesi del progetto con riferimenti **da verificare** prima dell'uso reale. L'embedding è locale (feature hashing); per produzione sostituirlo con un modello multilingue.

## 5. Metrica di successo

Misurate qui (dati simulati, vedi `docs/EVAL_RESULTS.md`, riproducibili con il comando eval sotto):

- Overload e calo HRV rilevati come ROSSI nel 100% dei 200 casi simulati; falsi rossi su atleta stabile 1.0% nella valutazione più recente.
- Motore White-Box: i risultati misurati più recenti sono registrati in `docs/EVAL_RESULTS.md` (sanificazione + calcolo).
- Autoverifica: 100% degli output LLM pericolosi del corpus corretti, 0% di falsi blocchi su output sicuri.

Obiettivi da misurare con utenti reali (non ancora misurati): usabilità SUS > 80, completamento delle sessioni di recupero suggerite > 85%.

**Gate di validazione:** i risultati simulati non validano soglie o utilità clinica. I profili standard/paralympic/master sono al momento descrittivi e non modificano gli algoritmi. La revisione specialistica e l'eventuale protocollo per misurare SUS/adesione sono tracciati in [`docs/VALIDATION_GATE.txt`](docs/VALIDATION_GATE.txt); non è stato avviato un pilota con persone.

La latenza end-to-end con l'LLM è tipicamente 1-4 s (rete + Groq): l'obiettivo "<800 ms" del documento iniziale riguarda solo il motore deterministico.

## Revisione etica

Il motore White-Box separa il calcolo del rischio dalla spiegazione LLM; consenso, guardrail e trattenimento delle bozze rosse riducono alcuni rischi, ma non sostituiscono una revisione clinica. La demo usa dati sintetici e non ha wearable sincronizzati né professionisti o notifiche collegati. [Leggi la revisione etica completa](./ethics-review.md) e il [registro dei test T1–T5](./backend/tests/test_edge_cases.py).

## Beta pubblica per la commissione

Il codice della beta è predisposto, ma **non è ancora distribuito online**; qui verrà aggiunto il link pubblico dopo il collaudo end-to-end. La commissione potrà avviare una sessione ospite senza account: ogni sessione ha un profilo separato, dati sintetici nello scenario iniziale di carico elevato, durata di due ore e limiti alle richieste. L'interfaccia richiede una scelta esplicita per elaborare i dati sintetici; gli avvisi esterni sono disabilitati. Non inserire dati personali o sanitari reali.

L'architettura prevista è frontend Next.js su Vercel e API FastAPI con PostgreSQL/pgvector e Redis su Render; la chiave Groq resta un segreto del backend. I piani gratuiti possono sospendere o rimuovere risorse, quindi la demo online è una preview temporanea, non un servizio sempre disponibile. Per istruzioni, variabili e collaudo vedere [la guida di deploy gratuito](./docs/DEPLOY_FREE.md). Tenere come riserva la [procedura di avvio locale](#avvio-rapido) e il video dimostrativo.

## 7. Portale e primo accesso

L'interfaccia separa accesso (`/`), orientamento e configurazione iniziale (`/onboarding`), panoramica biometrica (`/dashboard`), chat esplicabile (`/assistant`) e profilo (`/profile`). Le informative prototipali sono consultabili anche senza accesso su `/privacy`, `/cookies` e `/ethics`. Il primo accesso presenta il flusso di orientamento; la conferma richiesta documenta la presa visione nella demo, ma non è un consenso legale né abilita il trattamento biometrico.

Il profilo permette di modificare nome visualizzato e categoria descrittiva. L'eventuale contatto dell'allenatore è conservato solo nel browser e non è collegato a invii o notifiche. Il wearable continua a usare dati sintetici; le informative descrivono conservazione tecnica, cancellazione, LLM, supervisione, possibili bias e validazione mancante, ma sono bozze da rivedere con professionisti privacy/legali. L'interfaccia adatta la navigazione a schermi mobili e rispetta `prefers-reduced-motion`.

La chat integra **Pulsi**, la mascotte SVG animata dalla cartella `biomascotte`: cambia espressione durante l'elaborazione e riflette lo stato dei dati, con testi specifici che non implicano approvazione clinica o connessioni non attive. Il componente condiviso e i suoi stati sono in `frontend/components/mascot/`; le animazioni rispettano le preferenze di movimento ridotto.

---

## Avvio rapido

Requisiti: Docker Desktop (per Postgres/Redis), Python 3.12, Node.js (verificato con 26.13.0), VS Code. Una chiave Groq gratuita da <https://console.groq.com> è consigliata ma **non obbligatoria** (senza, l'agente risponde con regole deterministiche).

```powershell
Copy-Item .env.example .env     # file richiesto da Docker Compose; GROQ_API_KEY resta facoltativa
docker compose up -d db redis
docker compose run --rm backend alembic upgrade head  # solo su database appena creato
docker compose up --build -d    # backend (8000), frontend (3000)
docker compose exec backend python -m app.admin --email atleta@example.test --role athlete --athlete-id atleta-001 --name "Nome atleta"
```

Per un volume PostgreSQL preesistente non eseguire il comando `upgrade` iniziale: seguire prima la procedura `stamp` e backup in [`docs/OPERATIONS.md`](docs/OPERATIONS.md).

Il comando di provisioning chiede una password iniziale senza mostrarla a schermo. Crea anche il profilo senza consenso: accedi a <http://localhost:3000>, completa l'orientamento e abilita separatamente il consenso biometrico dal profilo prima di provare i dati demo. Per associare un professionista a un atleta gia' esistente:

```powershell
docker compose exec backend python -m app.admin --email professionista@example.test --role clinician --athlete-id atleta-001
```

Le API richiedono una sessione autenticata; i cookie sono HttpOnly e le scritture richiedono CSRF. Solo il ruolo atleta puo' modificare consensi, cancellare i dati o usare la chat; i professionisti vedono solo i profili assegnati. Le porte dei servizi Docker sono pubblicate su `127.0.0.1` per lo sviluppo locale.

**Configurazione beta ospitata:** non riutilizzare i valori di `.env.example`. Seguire [la guida di deploy gratuito](./docs/DEPLOY_FREE.md): il backend usa `APP_ENV=production`, `DEMO_MODE=false`, `ALLOW_SELF_REGISTRATION=false`, `PUBLIC_DEMO_ENABLED=true`, `COOKIE_SECURE=true`, database e Redis dedicati, e `CORS_ORIGINS` con la sola origine HTTPS del frontend. Il frontend usa `NEXT_PUBLIC_API_SAME_ORIGIN=true` e un rewrite verso l'API per mantenere i cookie sullo stesso sito. La chiave Groq va configurata solo come segreto server-side; non impostare Twilio per questa beta. La validazione backend rifiuta alcune configurazioni palesemente insicure, ma non sostituisce il collaudo del proxy, una gestione sicura dei segreti, backup o revisione privacy/legale.

In ambiente demo locale è disponibile la registrazione **solo atleta**; il consenso biometrico resta disattivato fino alla scelta esplicita nell'interfaccia. Non sono disponibili registrazione professionisti, inviti email o reset self-service. Per un account locale dimenticato, l'amministratore può reimpostare la password e revocare le sessioni con `docker compose exec backend python -m app.admin --email atleta@example.test --reset-password`.

**Sviluppo in VS Code su Windows** (PowerShell; Postgres e Redis in Docker):

```powershell
docker compose up -d db redis
Set-Location backend
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-lock.txt
Copy-Item ..\.env.example ..\.env
.\.venv\Scripts\alembic.exe upgrade head  # solo su database appena creato; per database esistenti vedi docs/OPERATIONS.md
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000
# In un altro terminale:
Set-Location frontend
$env:PATH = "$HOME\Desktop\node;" + $env:PATH
npm ci
npm run dev
```

## Test

```powershell
Set-Location backend
.\.venv\Scripts\python.exe -m pytest -v
.\.venv\Scripts\python.exe eval\run_eval.py --write
```

| Test                                | Cosa verifica                                                                         | Dove                                        |
| ----------------------------------- | ------------------------------------------------------------------------------------- | ------------------------------------------- |
| T1 Input vuoto/incompleto           | nessun errore, messaggio informativo                                                  | `test_edge_cases.py::test_t1_*`             |
| T2 Formato inatteso                 | HR = 0 o > 250, date testuali, RR anomali isolati con richiesta di ricalibrazione     | `test_t2_*`, `test_sanitizer_guardrails.py` |
| T3 Prompt injection e sintomi       | richiesta respinta; il messaggio distingue avviso inviato, simulato o non autorizzato | `test_t3_*`, `test_sintomi_*`               |
| T4 Strumento non disponibile        | wearable/RAG/LLM giù → modalità di riserva, nessun crash                              | `test_t4_*`                                 |
| T5 Input corretto, risultato errato | autovalutazione ottimistica vs metriche in rosso → prevalgono le metriche             | `test_t5_*`                                 |
| Consenso                            | cambio scenario non riattiva consensi revocati e non rigenera dati senza consenso     | `test_seed_demo_preserva_consensi_revocati` |
| Beta ospite                         | profili separati, consenso esplicito, limite chat e scadenza/cancellazione account    | `test_public_demo_*` in `test_auth.py`       |

### Stato di verifica

Verifiche e limiti dell'ultimo ambiente sono registrati in `docs/TEST_RESULTS.txt`. `docker compose up -d --build` e' stato verificato con i quattro servizi attivi, PostgreSQL/pgvector e Redis raggiungibili dal backend e homepage frontend HTTP 200. La suite pytest usa SQLite isolato; e' stata verificata separatamente una smoke test API su PostgreSQL. I risultati quantitativi del motore sono in `docs/EVAL_RESULTS.md`.

Per la companion app, dalla cartella `mobile/` eseguire `npm run typecheck` e `npm test`. I test attuali coprono la normalizzazione giornaliera sintetica; non sostituiscono le prove su development build e dispositivi iOS/Android.

## Struttura

```
backend/app/whitebox/   metriche deterministiche + sanificazione (solo libreria standard)
backend/app/            pipeline, guardrail, memoria, tool, API FastAPI, base di conoscenza
backend/tests, eval/    test e valutazione misurabile
frontend/               Next.js: login/onboarding, dashboard, agente, profilo e informative
docs/                   architettura, brief ufficiale, copione video, risultati
```

## Limiti noti

Dati simulati; nessun dispositivo o account wearable reale è ancora collegato. La companion app ha adapter locali per HealthKit e Health Connect, ma non una sincronizzazione backend: prima di abilitarla servono autenticazione mobile, contratto di ingestion con provenienza/idempotenza e prove su development build e dispositivi. Per fornitori diretti serviranno credenziali autorizzate e test esclusivamente con sandbox/dati sintetici; il simulatore attuale verifica il flusso ma non prova OAuth, disponibilità del provider o sincronizzazione live. L'ACWR è un indicatore di supporto la cui validità predittiva è discussa in letteratura; i guardrail sono regole testuali con corpora piccoli e fonti non revisionate. Il recupero password self-service e gli inviti email restano assenti; in demo locale il reset è amministrativo. Le migrazioni versionate sono in `backend/migrations/` e i passaggi di backup/ripristino sono in `docs/OPERATIONS.md`; restano necessarie una policy per la conservazione dei backup e dei log e una verifica operativa prima di un rilascio. Il login limita a 10 tentativi per IP ogni 15 minuti (Redis in produzione, memoria locale in sviluppo); il reverse proxy di produzione deve essere configurato in modo che l'indirizzo IP affidabile del client sia disponibile. I periodi di 12/24 mesi sono valori tecnici configurabili, da validare con il titolare del trattamento e un consulente privacy/legale. Il sistema non è un dispositivo medico e non ha validazione clinica.
