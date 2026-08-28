"""
setup_check.py — diagnóstico del entorno local del pipeline de Loyalty.

Idempotente y sin secretos: NO imprime contraseñas ni tokens, solo si están
presentes y si funcionan. Lo usa el skill /configurar-entorno.

Uso:
    python setup_check.py            # chequeos rápidos (no toca el datalake)
    python setup_check.py --full     # además prueba conexión al datalake y a Drive
"""
import os
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

BASE      = Path(__file__).resolve().parent
ENVS_DIR  = BASE.parent / "envs"
WIN_USER  = os.environ.get("USERNAME", "").lower()
ENV_USER  = ENVS_DIR / f".env.{WIN_USER}"
ENV_GEN   = ENVS_DIR / ".env"
DSN_NAME  = "DataLake Treasure ODBC"
LOY_FOLDER = "1yCPp6hTusYmhhb17WiB6EuhFmsx7tlxb"

OK, NO, WARN = "OK  ", "FALTA", "OJO "
rows = []
def add(status, item, hint=""):
    rows.append((status, item, hint))


def _drive_service():
    from googleapiclient.discovery import build
    SCOPES = ["https://www.googleapis.com/auth/drive"]
    _sa = BASE / "service_account.json"
    if _sa.exists():
        from google.oauth2.service_account import Credentials as SAC
        return build("drive", "v3", credentials=SAC.from_service_account_file(str(_sa), scopes=SCOPES))
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    c = Credentials.from_authorized_user_file(str(BASE / "token_drive.json"), SCOPES)
    if not c.valid:
        c.refresh(Request())
    return build("drive", "v3", credentials=c)

# ── 1) Credenciales del datalake ────────────────────────────────────────────
env_path = ENV_USER if ENV_USER.exists() else (ENV_GEN if ENV_GEN.exists() else None)
if env_path is None:
    add(NO, f"envs\\.env.{WIN_USER}", "crear con USER= y PASSWORD= del datalake (paso datalake del skill)")
    env_vals = {}
else:
    env_vals = {}
    for line in env_path.read_text(encoding="utf-8", errors="replace").splitlines():
        if "=" in line and not line.strip().startswith("#"):
            k, _, v = line.partition("=")
            env_vals[k.strip().upper()] = v.strip()
    which = env_path.name
    if env_vals.get("USER") and env_vals.get("PASSWORD"):
        add(OK, f"credenciales datalake ({which})", f"USER={env_vals['USER']}")
    else:
        missing = [k for k in ("USER", "PASSWORD") if not env_vals.get(k)]
        add(NO, f"credenciales datalake ({which})", f"falta {', '.join(missing)}")

# ── 2) DSN ODBC ─────────────────────────────────────────────────────────────
try:
    import pyodbc
    dsns = {d.lower() for d in pyodbc.dataSources()}
    if DSN_NAME.lower() in dsns:
        add(OK, f"DSN ODBC '{DSN_NAME}'")
    else:
        add(NO, f"DSN ODBC '{DSN_NAME}'", "agregarlo en 'ODBC Data Sources (64-bit)' (copiar del equipo de datos)")
except ImportError:
    add(NO, "pyodbc", "pip install -r requirements.txt")

# ── 3) Librerías Python ─────────────────────────────────────────────────────
missing_pkgs = []
for mod in ("pandas", "dotenv", "requests", "google.auth", "googleapiclient", "openpyxl"):
    try:
        __import__(mod)
    except ImportError:
        missing_pkgs.append(mod)
if missing_pkgs:
    add(NO, "librerías Python", f"pip install -r requirements.txt  (faltan: {', '.join(missing_pkgs)})")
else:
    add(OK, "librerías Python")

# ── 4) Acceso a Google Drive ───────────────────────────────────────────────
sa   = BASE / "service_account.json"
tok  = BASE / "token_drive.json"
cred = BASE / "credentials_drive.json"
if sa.exists():
    add(OK, "Drive: service_account.json", "método recomendado (no expira)")
elif tok.exists():
    add(OK, "Drive: token_drive.json (OAuth personal)")
elif cred.exists():
    add(NO, "Drive: token_drive.json", "correr:  python auth_drive.py  (login con tu cuenta @despegar.com)")
else:
    add(NO, "Drive: sin credenciales",
        "conseguir service_account.json (recomendado) o credentials_drive.json de Diego / "
        "folder Drive 'Ops' (no está en el repo), y despues correr auth_drive.py")

# ── 5) Pruebas de conexión (--full) ────────────────────────────────────────
if "--full" in sys.argv:
    # datalake
    if env_vals.get("USER") and env_vals.get("PASSWORD"):
        try:
            import pyodbc
            cn = pyodbc.connect(f"DSN={DSN_NAME};UID={env_vals['USER']};PWD={env_vals['PASSWORD']};", timeout=10)
            cn.cursor().execute("SELECT 1").fetchone()
            cn.close()
            add(OK, "conexión al datalake (SELECT 1)")
        except Exception as e:
            add(NO, "conexión al datalake", str(e).splitlines()[0][:160])
    else:
        add(WARN, "conexión al datalake", "sin credenciales, no se probó")
    # drive
    try:
        svc = _drive_service()
        n = len(svc.files().list(q=f"'{LOY_FOLDER}' in parents and trashed=false",
                                 fields="files(id)", pageSize=5).execute().get("files", []))
        add(OK, "acceso al folder Drive de loyalty", f"{n}+ archivos visibles")
    except Exception as e:
        add(NO, "acceso al folder Drive de loyalty", str(e).splitlines()[0][:160])


# ── Reporte ────────────────────────────────────────────────────────────────
print()
print(f"  Entorno Loyalty - usuario Windows: {WIN_USER or '(desconocido)'}")
print("  " + "-" * 74)
for status, item, hint in rows:
    line = f"  [{status}] {item}"
    if hint:
        line += f"\n         -> {hint}"
    print(line)
print("  " + "-" * 74)
faltan = [r for r in rows if r[0] == NO]
if faltan:
    print(f"  {len(faltan)} cosa(s) por resolver. Ver arriba.")
    sys.exit(1)
print("  Entorno listo. Podés correr:  python loyalty_sync.py")
sys.exit(0)
