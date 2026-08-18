# Autorización única de Google Drive (scope completo).
# Correr UNA vez de forma interactiva:  python auth_drive.py
# Abre el navegador, autorizás con tu cuenta @despegar.com y guarda token_drive.json.
from pathlib import Path
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ["https://www.googleapis.com/auth/drive"]
base   = Path(__file__).resolve().parent

flow  = InstalledAppFlow.from_client_secrets_file(
    str(base / "credentials_drive.json"), SCOPES)
creds = flow.run_local_server(
    port=0,
    prompt="select_account consent",
    login_hint="diego.bracco@despegar.com",
)
(base / "token_drive.json").write_text(creds.to_json())
print("OK -> token_drive.json guardado. Ya podes correr loyalty_sync.py")
