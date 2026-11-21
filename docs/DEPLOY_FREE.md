# Beta online gratuita per la commissione

## Architettura

- **Vercel Hobby** serve il frontend Next.js.
- **Render Free** ospita un solo servizio FastAPI, PostgreSQL con pgvector e Key Value compatibile con Redis.
- Le richieste `/api/*` passano da un rewrite Next.js al backend. Nel browser restano sul dominio Vercel, necessario per mantenere nello stesso sito i cookie HttpOnly/CSRF e lo streaming SSE.
- La beta crea un profilo ospite casuale, con dati sintetici e sessione di due ore. La chat è limitata a 10 richieste per ospite all'ora; la creazione è limitata a 10 sessioni per indirizzo sorgente all'ora. Gli avvisi a professionisti sono disabilitati. La chiave Groq è un segreto del solo backend.

Questa configurazione è una **preview per il concorso**, non un servizio affidabile per utenti reali. I piani gratuiti possono cambiare e non offrono una disponibilità garantita.

## 1. Preparare GitHub senza segreti

1. Crea un repository GitHub e carica il codice senza il file `.env`, cartelle `.venv`, `node_modules` o dati di database.
2. Controlla `.gitignore` e `.env.example`; quest'ultimo deve contenere solo valori vuoti o segnaposto.
3. Non aggiungere la chiave Groq né in GitHub né nelle variabili `NEXT_PUBLIC_*`. Se una chiave è mai stata pubblicata, revocala prima di proseguire.

Il workspace attuale non ha ancora un repository Git configurato. La verifica di ciò che è stato tracciato o pubblicato andrà quindi eseguita durante la creazione del repository, prima del primo push.

## 2. Creare le risorse Render

Usa una sola regione per API, database e Key Value.

1. Crea un database PostgreSQL Free e abilita `pgvector` (la migrazione iniziale lo abilita). Il piano gratuito di Render indica limiti temporali e di storage: crea il database vicino alla data della presentazione e predisponi un nuovo seed se dovesse scadere.
2. Crea un Key Value Free compatibile Redis e usa il suo URL interno `redis://` o `rediss://`; non esporre un URL pubblico se non serve.
3. Crea un Web Service dal repository GitHub: directory radice `backend`, runtime Docker e Dockerfile `./Dockerfile`.
4. Configura il servizio con queste variabili:

   | Variabile | Valore |
   | --- | --- |
   | `APP_ENV` | `production` |
   | `DEMO_MODE` | `false` |
   | `ALLOW_SELF_REGISTRATION` | `false` |
   | `PUBLIC_DEMO_ENABLED` | `true` |
   | `COOKIE_SECURE` | `true` |
   | `RUN_MIGRATIONS` | `true` |
   | `DATABASE_URL` | URL interno PostgreSQL con schema `postgresql+psycopg://` |
   | `REDIS_URL` | URL interno Key Value |
   | `CORS_ORIGINS` | origine esatta Vercel, per esempio `https://nome-progetto.vercel.app` |
   | `GROQ_API_KEY` | segreto aggiunto nel pannello Render, non nel repository |
   | `GROQ_MODEL` | modello atteso dalla chiave Groq |

   Lascia non configurate le variabili Twilio e `CLINICIAN_PHONE`. Non usare i valori locali di `.env.example` in produzione. Il comando del container applica le migrazioni quando `RUN_MIGRATIONS=true` e ascolta sulla porta indicata da Render.

5. Imposta il controllo di salute del servizio su `/api/health`. Prima di esporre la demo, verifica che la risposta segnali database e base di conoscenza disponibili.

## 3. Collegare Vercel

1. Importa lo stesso repository in Vercel; imposta `frontend` come **Root Directory** e lascia il build command predefinito (`npm run build`).
2. Aggiungi le variabili di build:

   | Variabile | Valore |
   | --- | --- |
   | `NEXT_PUBLIC_API_SAME_ORIGIN` | `true` |
   | `BIOPULSE_API_ORIGIN` | URL HTTPS del Web Service Render, senza slash finale |

3. Aggiungi l'origine Vercel effettiva a `CORS_ORIGINS` su Render e ridistribuisci l'API.
4. Usa l'indirizzo Vercel di produzione per la prova: i domini temporanei delle Preview non sono autorizzati finché non vengono aggiunti esplicitamente a `CORS_ORIGINS`.

Il rewrite in `frontend/next.config.mjs` mantiene la barra degli indirizzi sul dominio Vercel e inoltra `/api/*` all'API. Il flusso è stato verificato localmente attraverso il rewrite, inclusi cookie di sessione, CSRF, caricamento dei dati e risposta SSE. Va ripetuto sul deployment reale: la prova locale non verifica le intestazioni o le policy specifiche di Vercel e Render.

## 4. Collaudo prima di condividere

1. Apri l'URL Vercel in una finestra privata e verifica che la pagina offra **“Prova la beta con dati sintetici”**.
2. Avvia la sessione, consulta le informative e seleziona separatamente la casella che autorizza l'elaborazione dei soli dati sintetici.
3. Controlla che il dashboard iniziale mostri lo scenario sintetico di carico elevato; in chat prova una domanda concreta e osserva la traccia dell'agente.
4. Prova la modalità di riserva, revoca il consenso e cancella il profilo. Controlla che le sessioni ospiti siano separate e che non sia possibile autorizzare avvisi esterni.
5. Fai il collaudo con Groq configurato. Se il modello è indisponibile o la quota è esaurita, la demo deve mostrare il fallback deterministico senza esporre la chiave.

## Limiti gratuiti da pianificare

- Render Free sospende i servizi web inattivi dopo 15 minuti; il risveglio può richiedere circa un minuto. Render dichiara inoltre un limite mensile di ore gratuite per workspace e la scadenza del database PostgreSQL Free dopo 30 giorni.
- Il filesystem del Web Service è effimero; non usare SQLite sul servizio ospitato. Key Value gratuito è volatile, quindi i limiti di frequenza possono azzerarsi ai riavvii.
- Il limite di avvio ospite è applicato per indirizzo sorgente: se il proxy del provider presenta più visitatori con lo stesso indirizzo al backend, essi condividono la quota oraria. Verifica questo comportamento sul deployment e adegua la quota prima di una sessione con molti valutatori.
- Vercel Hobby e Render Free hanno quote e condizioni d'uso: controlla i pannelli di utilizzo e non aggiungere metodi di pagamento o ricariche automatiche senza approvazione. Anche Groq ha limiti e condizioni proprie; hosting gratuito non equivale a uso LLM illimitato o garantito senza costi.
- Prima della presentazione risveglia l'API, prova il percorso da un browser pulito e tieni pronto l'avvio locale Docker e il video di tre minuti come riserva.

Riferimenti ufficiali: [Vercel Hobby](https://vercel.com/pricing), [rewrite Vercel](https://vercel.com/docs/routing/rewrites), [servizi gratuiti Render](https://render.com/docs/free), [Render Postgres](https://render.com/docs/postgresql), [Render Key Value](https://render.com/docs/key-value).
