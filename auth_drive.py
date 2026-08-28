# Autorización única de Google Drive (scope completo).
# Correr UNA vez de forma interactiva:  python auth_drive.py
# Abre el navegador, autorizás con TU cuenta @despegar.com y guarda token_drive.json.
# Requisito: credentials_drive.json en esta carpeta (te lo pasa Diego o está en el
# folder Drive restringido de operadores — no está versionado).
from pathlib import Path
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ["https://www.googleapis.com/auth/drive"]
base   = Path(__file__).resolve().parent

if not (base / "credentials_drive.json").exists():
    raise SystemExit("Falta credentials_drive.json en esta carpeta. Ver SETUP.md / docs/PENDIENTE-DIEGO.md.")

flow  = InstalledAppFlow.from_client_secrets_file(
    str(base / "credentials_drive.json"), SCOPES)
creds = flow.run_local_server(port=0, prompt="select_account consent")
(base / "token_drive.json").write_text(creds.to_json())
print("OK -> token_drive.json guardado. Ya podes correr loyalty_sync.py")
