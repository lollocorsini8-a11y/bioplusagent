# Operazioni database (prototipo locale)

Wearable e invio di notifiche a professionisti restano simulati/non collegati.
Queste istruzioni riguardano il PostgreSQL locale e non costituiscono una
procedura di disaster recovery per produzione.

## Migrazioni dello schema

Le migrazioni versionate sono in `backend/migrations/`; il database non viene
più creato implicitamente dall'app fuori dai test. La revisione
`0001_initial` è la baseline dello schema attuale. Le migrazioni devono essere
eseguite esplicitamente e verificate prima di avviare versioni nuove
dell'applicazione.

Per un volume PostgreSQL vuoto, dalla root del progetto:

```powershell
docker compose up -d db redis
docker compose run --rm backend alembic upgrade head
docker compose up --build -d
```

Per il volume di sviluppo già creato da `Base.metadata.create_all`, prima
eseguire e verificare un backup. Solo se lo schema esistente corrisponde alla
baseline `0001_initial`, applicare il timbro iniziale senza ricreare tabelle:

```powershell
docker compose build backend
docker compose run --rm backend alembic stamp 0001_initial
docker compose run --rm backend alembic current
```

`stamp` non confronta né aggiorna le tabelle: non va usato su uno schema
diverso o non verificato. Per le revisioni future, generare con
`alembic revision --autogenerate -m "descrizione"`, revisionare manualmente
ogni file generato e provare `alembic upgrade head` su un database isolato
prima del database di sviluppo.

## Backup verificabile

Salvare gli archivi fuori dal repository, in un percorso protetto. I dump
contengono account, consensi e dati applicativi; proteggerli e cancellarli
secondo la policy del titolare. Il comando usa il container PostgreSQL come
trasporto dei byte, evitando la redirezione testuale PowerShell:

```powershell
$container = (docker compose ps -q db).Trim()
$dbUser = (docker compose exec -T db printenv POSTGRES_USER).Trim()
$dbName = (docker compose exec -T db printenv POSTGRES_DB).Trim()
$file = "biopulse-$((Get-Date).ToUniversalTime().ToString('yyyyMMddTHHmmssZ')).dump"
$backup = Join-Path $env:TEMP $file
docker compose exec -T db pg_dump -U $dbUser -d $dbName -Fc -f "/tmp/$file"
if ($LASTEXITCODE -ne 0) { throw "pg_dump non riuscito" }
docker cp "${container}:/tmp/$file" $backup
if ($LASTEXITCODE -ne 0) { throw "Copia del backup non riuscita" }
docker compose exec -T db pg_restore --list "/tmp/$file" | Out-Null
if ($LASTEXITCODE -ne 0) { throw "L'archivio non supera il controllo pg_restore --list" }
docker compose exec -T db rm -f "/tmp/$file"
Write-Output "Backup creato e verificato: $backup"
```

## Prova di ripristino isolata

Ripristinare in un database nuovo e temporaneo, mai sopra `biopulse`. Usare un
nome univoco con prefisso `biopulse_restore_test_`; verificare che
`pg_restore` termini con codice 0 e che le tabelle attese esistano. Eliminare
solo il database temporaneo creato per la prova:

```powershell
$container = (docker compose ps -q db).Trim()
$dbUser = (docker compose exec -T db printenv POSTGRES_USER).Trim()
$file = Split-Path $backup -Leaf
$restoreDb = "biopulse_restore_test_$((Get-Date).ToUniversalTime().ToString('yyyyMMddHHmmss'))"
docker cp $backup "${container}:/tmp/$file"
if ($LASTEXITCODE -ne 0) { throw "Copia del backup nel container non riuscita" }
docker compose exec -T db createdb -U $dbUser $restoreDb
if ($LASTEXITCODE -ne 0) { throw "Creazione del database temporaneo non riuscita" }
docker compose exec -T db pg_restore --exit-on-error --no-owner --no-acl -U $dbUser -d $restoreDb "/tmp/$file"
if ($LASTEXITCODE -ne 0) { throw "Ripristino fallito: conservare il database temporaneo per diagnosi" }
$schemaOk = (docker compose exec -T db psql -U $dbUser -d $restoreDb -tAc "SELECT to_regclass('public.athletes') IS NOT NULL AND to_regclass('public.daily_metrics') IS NOT NULL AND to_regclass('public.users') IS NOT NULL").Trim()
if ($LASTEXITCODE -ne 0 -or $schemaOk -ne "t") { throw "Verifica schema ripristinato fallita" }
docker compose exec -T db dropdb -U $dbUser $restoreDb
docker compose exec -T db rm -f "/tmp/$file"
```

Il 12 novembre 2026 sono stati eseguiti un dump custom-format e un ripristino
in un database temporaneo PostgreSQL; la verifica delle tabelle è riuscita e
il database attivo non è stato modificato. Ripetere e registrare data, esito e
durata per ogni backup operativo; questa prova locale non verifica la policy
né il ripristino di un deployment di produzione. Non ripristinare mai un dump
di prova sul database attivo.
