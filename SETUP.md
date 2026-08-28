# Setup — Loyalty Ecosystem

Pipeline: `loyalty_sync.py` (datalake → JSON en Drive) + landing GAS (`dashboard.html` / `Código.js`) que consume esos JSON.

```
Datalake (ODBC)  ─┐
Config Sheet     ─┼─►  loyalty_sync.py  ──►  JSON en Drive  ──►  landing GAS  ──►  navegador
breakage/dict    ─┘        (agendado)         (folder 1yCPp6…)      (webapp @5)
```

---

## A. Correr el pipeline de datos (`loyalty_sync.py`)

### A.1 — Credenciales del Datalake (1 vez por persona)

Cada analista usa su propio usuario/password del Datalake (los mismos de Mariano Bujía / Metabase). El script busca el archivo según el usuario de Windows:

```
C:\Users\<tu.usuario>\Proyectos IA\envs\.env.<tu.usuario.windows>
```

Contenido:
```
USER=nombre.apellido@ar.infra.d
PASSWORD=tu_password_datalake
```

Si no existe `.env.<usuario>`, cae a `envs\.env` (el genérico). **Nunca se sube al repo** (gitignoreado).

### A.2 — DSN ODBC (1 vez por máquina)

En "ODBC Data Sources (64-bit)" de Windows tiene que existir un DSN llamado **`DataLake Treasure ODBC`** apuntando al Treasure Data / Presto del datalake. Copiarlo de la config que ya tiene el equipo de datos.

### A.3 — Librerías Python (1 vez)

```powershell
pip install -r "C:\Users\<tu.usuario>\Proyectos IA\Loyalty_Ecosystem\requirements.txt"
```

### A.4 — Acceso a Google Drive (1 vez por persona)

**Opción recomendada — cuenta de servicio (no expira, no depende de nadie):**
1. Alguien crea la service account en GCP y baja `service_account.json` a la carpeta del proyecto.
2. Comparte los folders de Drive con el email de la SA (`…@…iam.gserviceaccount.com`), permiso *Editor*:
   - `1yCPp6hTusYmhhb17WiB6EuhFmsx7tlxb` (JSON de loyalty)
   - `1XqQPL_rlS0NRIPUnPfj5nALBTn7kAOQV` (baseline/budget/forecast — solo lectura)
3. `loyalty_sync.py` usa `service_account.json` si existe; si no, cae al flujo OAuth de abajo.

**Opción OAuth personal (fallback):**
```powershell
cd "C:\Users\<tu.usuario>\Proyectos IA\Loyalty_Ecosystem"
python auth_drive.py
```
Abre el navegador → autorizás con tu cuenta @despegar.com → queda en `token_drive.json` (gitignoreado, personal).

### A.5 — Ejecutar

```powershell
cd "C:\Users\<tu.usuario>\Proyectos IA\Loyalty_Ecosystem"
python loyalty_sync.py
```

Al final tiene que decir `OK Drive: actualizado (...)` para los 7 archivos:
`loyalty_acumulaciones_{2026,2025}.json`, `loyalty_redenciones_{2026,2025}.json`,
`loyalty_breakage.json`, `loyalty_dict.json`, `loyalty_ssp.json`.

### A.6 — Agendado (Task Scheduler, en la máquina "de turno")

1. "Programador de tareas" → "Crear tarea básica"
2. Nombre: `Loyalty Sync`
3. Trigger: diario 08:30 (después del Daily de B2B)
4. Acción → Iniciar programa:
   - Programa: `python`
   - Argumentos: `"C:\Users\<usuario>\Proyectos IA\Loyalty_Ecosystem\loyalty_sync.py"`
   - Iniciar en: `C:\Users\<usuario>\Proyectos IA\Loyalty_Ecosystem`
5. "Ejecutar tanto si el usuario inició sesión como si no" + "Ejecutar con los privilegios más altos"

Con esto los analistas **no corren nada** — los datos se refrescan solos.

---

## B. Inputs de negocio → Google Sheet (sin código, sin git)

Los valores que cambian seguido viven en una planilla, no en el repo:

**Planilla:** *Loyalty Ecosystem — Config* (en el folder de Drive de Loyalty)
`SHEET_ID` en `loyalty_sync.py` → constante `CONFIG_SHEET_ID`.

| Pestaña | Qué es | Quién la edita |
|---|---|---|
| `breakage_esperado` | `country_code, month (YYYY-MM), breakage_esperado (0..1)` | Control de Gestión, mensual |
| `diccionario` | `partner, point_type, concatenado, seccion` — mapeo programa | Loyalty, cuando cambia un programa |

`loyalty_sync.py` la lee en cada corrida (export xlsx vía Drive API). Si la planilla no está accesible, cae a los archivos locales (`breakage_esperado.csv`, `Diccionario.xlsx`) para no romper.

Editar la planilla → efecto en el próximo sync (o inmediato para lo que el dashboard lee en vivo).

---

## C. Cambios de código → GitHub + deploy automático

Repo: `github.com/diegobracco-boop/Loyalty_Ecosystem`

### Flujo para un analista

```powershell
git checkout -b cambio-que-sea
# … editar dashboard.html / Código.js / loyalty_sync.py …
git add -A && git commit -m "..."
git push -u origin cambio-que-sea
# abrir PR en GitHub
```

Al mergear a `main`, la **GitHub Action** (`.github/workflows/deploy-gas.yml`) corre
`clasp push` + `clasp deploy` sola. No hace falta que nadie tenga `clasp` local.

### Requisito (1 vez) — secret `CLASP_CREDENTIALS`

1. En una máquina con clasp: `clasp login` con una cuenta @despegar.com que tenga
   acceso de editor al Apps Script (`1SXEXXwM9CromNRqhwiFFg34-rnO9Q3a85d3oMHsM9mgMS_NmpP2OrNLk`).
   Idealmente una cuenta de equipo, no personal.
2. Copiar el contenido de `~/.clasprc.json`.
3. GitHub → repo → Settings → Secrets and variables → Actions → New repository secret
   - Nombre: `CLASP_CREDENTIALS`
   - Valor: el JSON completo de `.clasprc.json`

### Deploy manual (si hace falta)

```powershell
cd Loyalty_Ecosystem
clasp push -f
clasp deploy -i AKfycbzyHV8nz_AppIX81qn8QJ9dyPT77i75lBz9nerKfsjhLEk8SfSdGPXeGk52oLpXvI2Fig -d "descripción"
```

---

## D. Accesos a dar (1 vez, por analista)

| Recurso | Permiso |
|---|---|
| Repo GitHub `Loyalty_Ecosystem` | Write (para PRs) |
| Folder Drive `1yCPp6hTusYmhhb17WiB6EuhFmsx7tlxb` | Editor |
| Planilla *Loyalty Ecosystem — Config* | Editor |
| Apps Script (project `1SXEXXw…`) | Editor (solo si van a deployar manual) |
| Datalake | usuario propio (equipo de datos) |

---

## Referencia rápida

| Cosa | Valor |
|---|---|
| Apps Script ID | `1SXEXXwM9CromNRqhwiFFg34-rnO9Q3a85d3oMHsM9mgMS_NmpP2OrNLk` |
| Deployment estable | `AKfycbzyHV8nz_AppIX81qn8QJ9dyPT77i75lBz9nerKfsjhLEk8SfSdGPXeGk52oLpXvI2Fig` (@5) |
| Deployment @HEAD | `AKfycby4_-hgcNdAaZfft_h9bsCXw41ZnAJjy093U6wPkbmM` |
| Folder JSON loyalty | `1yCPp6hTusYmhhb17WiB6EuhFmsx7tlxb` |
| Folder baseline/budget/forecast | `1XqQPL_rlS0NRIPUnPfj5nALBTn7kAOQV` |
| DSN ODBC | `DataLake Treasure ODBC` |
