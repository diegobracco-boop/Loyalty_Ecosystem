# Pendiente — pasos manuales (Diego)

Lo que sigue **no lo puede hacer Claude** (necesita consola de GCP, settings de
GitHub, o compartir en Drive). Todo lo demás del onboarding ya está en el repo.

## 1. Auth de Drive — OAuth de usuario (mismo patrón que B2B)  ·  ~2 min por persona

**Decisión (07-sep):** NO se usa cuenta de servicio. `B2B_Ecosystem` corre su daily en
Task Scheduler con OAuth de usuario (`credentials_drive.json` compartido + `token_drive.json`
personal, lo genera `auth_drive.py`) y funciona bien; Loyalty queda igual. El código ya
no tiene la rama de service account.

Por cada operador nuevo:
1. Pasarle `credentials_drive.json` (es el **mismo archivo para todos** — client OAuth de
   escritorio, no versionado por push protection de GitHub). Dejarlo en el folder Drive
   restringido **"Loyalty Ecosystem - Ops"** o mandarlo 1:1.
2. La persona lo copia a la carpeta del repo y corre `python auth_drive.py` → login con su
   cuenta @despegar.com → se genera `token_drive.json` (personal, gitignoreado).
3. Darle acceso **Editor** al folder `1yCPp6hTusYmhhb17WiB6EuhFmsx7tlxb`.

Único chequeo pendiente en GCP: confirmar que la pantalla de consentimiento del proyecto
del `credentials_drive.json` está en modo **"Internal"** (solo @despegar.com). En ese modo
el refresh token no expira y el sync agendado no se corta. Es el mismo client OAuth que
usa B2B, así que casi seguro ya está así — solo verificarlo una vez.

## 2. (Opcional) Secret `CLASP_CREDENTIALS` en GitHub  ·  ~3 min  ·  habilita el deploy automático

**No es bloqueante.** Hoy el deploy de la landing se hace a mano con `clasp` local
(`/publicar`), igual que en B2B_Ecosystem. La Action `deploy-gas.yml` quedó solo
`workflow_dispatch`. Solo hacé esto si querés que el deploy vuelva a ser automático
al mergear a `main`:

1. En una máquina con clasp: `clasp login` con una cuenta **de equipo** @despegar.com
   con acceso de editor al Apps Script `1SXEXXwM9CromNRqhwiFFg34-rnO9Q3a85d3oMHsM9mgMS_NmpP2OrNLk`.
2. Copiar todo el contenido de `~/.clasprc.json`.
3. GitHub → repo → **Settings → Secrets and variables → Actions → New repository secret**
   - Name: `CLASP_CREDENTIALS`
   - Value: el JSON completo
4. En `.github/workflows/deploy-gas.yml`, descomentar el bloque `push:` del `on:`.

## 3. Accesos del equipo  ·  por persona

| Recurso | Permiso | Para |
|---|---|---|
| Repo GitHub `Loyalty_Ecosystem` (collaborator) | Write | todos |
| Planilla *Loyalty Ecosystem - Config* | Editor | analistas |
| Folder Drive `1yCPp6…` | Editor | operadores |
| `credentials_drive.json` (folder restringido "Ops") | — | operadores |
| Apps Script project | Editor | solo si deployan a mano |
| Datalake | usuario propio (equipo de datos) | quien corra `--dry-run` o la sync real |

Nota: el repo es personal (`diegobracco-boop`). Si el equipo crece, evaluá moverlo
a una org de Despegar.

## 4. Task Scheduler  ·  1 vez  ·  en la máquina "de turno"

`loyalty_sync.py` diario 08:30. Pasos en `SETUP.md` A.6. Con esto el 99% del equipo
nunca necesita correr la sync.

## 5. Serie mensual real de breakage esperado

La planilla *Config* → pestaña `breakage_esperado` tiene hoy el placeholder del cierre 07
replicado a todos los meses. Cargá los valores reales mes a mes.

## 6. Avisar a Control de Gestión: KPI de Acumulación de Pasaporte D! / IFOOD cambió (07-sep)

`loyalty_sync.py` tenía un bug desde el commit inicial del proyecto: `aggregate_acum()`
sumaba `abs(points)` en vez de netear, así que cualquier accrual con cancelaciones
quedaba sumado (`accrual + |cancelación|`) en vez de restado (`accrual − cancelación`).
Confirmado contra el bajada real de cierre de 06-2026 y su tabla dinámica (suma simple
con signo, sin abs()): **el cierre neteaba bien, el pipeline no.**

Ya está arreglado y deployado (commit `9f2ec2a`, sync corrida 07-sep 17:48). Efecto
visible en el dashboard, retroactivo a todo 2025/2026:
- **Pasaporte D! (`DP`/`general`) bajó a menos de la mitad** (2026: de 5.289M a 2.057M
  puntos acumulados, −157% relativo al número viejo).
- **IFOOD 2025 bajó ~34%** (de 4.645M a 3.472M), por una cancelación grande de
  `IFOOD_WEL` en oct-dic 2025 que antes se sumaba en vez de restarse.
- 2026 de IFOOD casi no cambia (<0,01%).

Si alguien ya usó los números viejos en algún reporte/conversación con el negocio,
conviene que lo sepan antes de que alguien note la diferencia solo. Detalle completo
en la memoria de Claude `bug-abs-cancelaciones-acumulacion` / commit `9f2ec2a`.

## 7. Avisar a Control de Gestión: "Valor Acumulado" (USD) cambió de fórmula (08-sep) — impacto grande y visible

`getAcumUsd` (`dashboard.html`) tenía una fórmula dimensionalmente inválida
(`|acum_usd_base × factor SSP|`, mezclaba USD × USD/punto) que daba un "Valor
Acumulado" ~6x menor al real para Pasaporte D! (ago-2026: $177k vs $1,13M de
Valor Redimido real — no cerraba contablemente). Se reemplazó por el método
contable estándar "relative fair value" (DRO): `R=acum_usd_base`,
`PV=-(puntos×factor SSP)`, `DRO=(PV/(|PV|+R))×R`. Commit `80fd681`, deploy `@31`.

Además, **IFOOD, Acciones Marketing y Club Despegar** (welcome bonuses / campañas /
subscripción, sin comisión de reserva de viaje detrás) tienen `acum_usd_base=0` en
el 100% de sus filas — con la fórmula DRO esto siempre daba `$0`, sin importar los
puntos (IFOOD: 34,2 mil millones de puntos en 2026 mostraban Valor Acumulado $0).
Se les aplicó un tercer método: valuar directo `puntos × factor SSP` (sin repartir
vía DRO, porque no hay revenue de viaje que diferir). Commits `81fc911` (IFOOD/
Acciones Marketing) y `77720d2` (Club Despegar), deploys `@33`/`@34`.

**Efecto visible, retroactivo a todo 2025/2026:** el KPI "Valor Acumulado" y el
gráfico "Acumulaciones — Valor USD por mes" cambiaron de forma sustancial para
CASI TODOS los programas (antes solo Pasaporte D! mostraba un valor USD ≠ $0 y
Cobrand/Partners vía `Input_Precios.xlsx`; ahora también IFOOD, Acciones
Marketing y Club Despegar muestran valores reales). Si alguien ya usó los
números viejos (o el hecho de que esos 3 programas daban $0) en algún reporte,
conviene que lo sepan. Detalle completo en la memoria de Claude
`dro-valor-acumulado-formula`.
