# Pendiente — pasos manuales (Diego)

Lo que sigue **no lo puede hacer Claude** (necesita consola de GCP, settings de
GitHub, o compartir en Drive). Todo lo demás del onboarding ya está en el repo.

## 1. Service account de Drive  ·  ~10 min  ·  destraba a TODOS los operadores

Es lo que resuelve de raíz el problema de credenciales (sin esto, cada operador
necesita `credentials_drive.json` + OAuth por browser).

1. [console.cloud.google.com](https://console.cloud.google.com) → proyecto `despegar-anaconda-juniper` (o el que uses).
2. **APIs y servicios → Biblioteca** → "Google Drive API" → **Habilitar**.
3. **IAM → Cuentas de servicio → Crear** → nombre `loyalty-sync` → Crear → (sin roles) → Listo.
4. Click en la cuenta → **Claves → Agregar clave → JSON** → se baja un `.json`.
5. Renombrar a `service_account.json`.
6. Copiar el email `loyalty-sync@…iam.gserviceaccount.com` y **compartir** (como a una persona):
   - Folder `1yCPp6hTusYmhhb17WiB6EuhFmsx7tlxb` → **Editor**
   - Folder `1XqQPL_rlS0NRIPUnPfj5nALBTn7kAOQV` → **Lector**
   - Planilla *Loyalty Ecosystem - Config* → **Lector**
7. Guardar `service_account.json` en un lugar restringido (folder Drive solo-operadores,
   o vault). Cada operador lo copia a su carpeta del repo. `loyalty_sync.py` lo usa solo.

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
| `service_account.json` (folder restringido) | — | operadores |
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
